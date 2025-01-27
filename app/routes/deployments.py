from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import Deployment, User, Cluster, DeploymentQueue, db
from datetime import datetime, timezone, timedelta
import re

deployment_bp = Blueprint('deployments', __name__)

def check_deployment_access(user, deployment=None, cluster=None):
    """Check if user has access to deployment or cluster"""
    if user.role == 'admin':
        return True
        
    if deployment and deployment.cluster.organization_id != user.organization_id:
        return False
        
    if cluster and cluster.organization_id != user.organization_id:
        return False
        
    return True

def validate_deployment_data(data, cluster):
    """Validate deployment request data"""
    errors = []
    
    # Required fields
    required_fields = ['name', 'image', 'ram_gb', 'cpu_cores']
    for field in required_fields:
        if field not in data:
            errors.append(f"{field} is required")
    
    if errors:
        return errors
        
    # Name validation
    if not re.match(r'^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$', data['name']):
        errors.append("name must be 1-63 characters long and contain only lowercase letters, numbers, and hyphens")
    
    # Resource validation
    try:
        ram_gb = float(data['ram_gb'])
        if ram_gb <= 0 or ram_gb > cluster.total_ram_gb:
            errors.append(f"ram_gb must be between 0 and {cluster.total_ram_gb}")
    except ValueError:
        errors.append("ram_gb must be a number")
        
    try:
        cpu_cores = float(data['cpu_cores'])
        if cpu_cores <= 0 or cpu_cores > cluster.total_cpu_cores:
            errors.append(f"cpu_cores must be between 0 and {cluster.total_cpu_cores}")
    except ValueError:
        errors.append("cpu_cores must be a number")
        
    if 'gpu_count' in data:
        try:
            gpu_count = int(data['gpu_count'])
            if gpu_count < 0 or gpu_count > cluster.total_gpu_count:
                errors.append(f"gpu_count must be between 0 and {cluster.total_gpu_count}")
        except ValueError:
            errors.append("gpu_count must be an integer")
            
    if 'priority' in data:
        try:
            priority = int(data['priority'])
            if priority < 1 or priority > 5:
                errors.append("priority must be between 1 and 5")
        except ValueError:
            errors.append("priority must be an integer")
            
    if 'environment' in data and not isinstance(data['environment'], dict):
        errors.append("environment must be a dictionary")
    
    return errors

@deployment_bp.route('/', methods=['POST'])
@jwt_required()
def create_deployment():
    """Create a new deployment and queue it for scheduling"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Get target cluster
    cluster_id = data.get('cluster_id')
    if not cluster_id:
        return jsonify({"error": "cluster_id is required"}), 400
        
    cluster = Cluster.query.get(cluster_id)
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404
    
    # Check access and cluster status
    if not check_deployment_access(user, cluster=cluster):
        return jsonify({"error": "Access denied"}), 403
        
    if cluster.status != 'active':
        return jsonify({"error": "Cluster is not active"}), 400
    
    # Validate deployment data
    validation_errors = validate_deployment_data(data, cluster)
    if validation_errors:
        return jsonify({"errors": validation_errors}), 400
    
    # Create deployment in pending state
    deployment = Deployment(
        name=data['name'],
        image=data['image'],
        user_id=current_user_id,
        cluster_id=cluster.id,
        ram_gb=float(data['ram_gb']),
        cpu_cores=float(data['cpu_cores']),
        gpu_count=int(data.get('gpu_count', 0)),
        environment=data.get('environment', {}),
        status='pending',
        priority=int(data.get('priority', 1)),  # Default priority 1 (lowest)
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    # Create queue entry
    queue_entry = DeploymentQueue(
        deployment=deployment,
        priority=deployment.priority,
        queued_at=datetime.now(timezone.utc)
    )
    
    db.session.add(deployment)
    db.session.add(queue_entry)
    
    try:
        db.session.commit()
        # Notify scheduler about new deployment
        current_app.scheduler.notify_new_deployment(deployment.id)
        return jsonify(deployment.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@deployment_bp.route('/', methods=['GET'])
@jwt_required()
def list_deployments():
    """List deployments based on user's role and organization"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Admin can see all deployments
    if user.role == 'admin':
        deployments = Deployment.query.all()
    else:
        # Regular users can only see deployments in their organization's clusters
        deployments = Deployment.query.join(Cluster).filter(
            Cluster.organization_id == user.organization_id
        ).all()
    
    return jsonify([d.to_dict() for d in deployments]), 200

@deployment_bp.route('/<int:deployment_id>', methods=['GET'])
@jwt_required()
def get_deployment(deployment_id):
    """Get deployment details"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "Deployment not found"}), 404
    
    if not check_deployment_access(user, deployment=deployment):
        return jsonify({"error": "Access denied"}), 403
    
    return jsonify(deployment.to_dict()), 200

@deployment_bp.route('/<int:deployment_id>', methods=['PUT'])
@jwt_required()
def update_deployment(deployment_id):
    """Update deployment details"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "Deployment not found"}), 404
    
    if not check_deployment_access(user, deployment=deployment):
        return jsonify({"error": "Access denied"}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Prevent updates to running deployments
    if deployment.status == 'running' and any(key in data for key in ['ram_gb', 'cpu_cores', 'gpu_count']):
        return jsonify({"error": "Cannot update resources of running deployment"}), 400
    
    # Validate updates
    if any(key in data for key in ['ram_gb', 'cpu_cores', 'gpu_count']):
        validation_errors = validate_deployment_data(data, deployment.cluster)
        if validation_errors:
            return jsonify({"errors": validation_errors}), 400
        
        # Update cluster resource allocation
        if 'ram_gb' in data:
            deployment.cluster.available_ram_gb += deployment.ram_gb
            deployment.ram_gb = float(data['ram_gb'])
            deployment.cluster.available_ram_gb -= deployment.ram_gb
            
        if 'cpu_cores' in data:
            deployment.cluster.available_cpu_cores += deployment.cpu_cores
            deployment.cpu_cores = float(data['cpu_cores'])
            deployment.cluster.available_cpu_cores -= deployment.cpu_cores
            
        if 'gpu_count' in data:
            deployment.cluster.available_gpu_count += deployment.gpu_count
            deployment.gpu_count = int(data['gpu_count'])
            deployment.cluster.available_gpu_count -= deployment.gpu_count
    
    # Update other fields
    if 'name' in data:
        deployment.name = data['name']
    if 'image' in data:
        deployment.image = data['image']
    if 'environment' in data:
        deployment.environment = data['environment']
    if 'status' in data:
        if data['status'] not in ['pending', 'running', 'stopped', 'failed']:
            return jsonify({"error": "Invalid status"}), 400
        deployment.status = data['status']
    
    deployment.updated_at = datetime.now(timezone.utc)
    
    try:
        db.session.commit()
        return jsonify(deployment.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@deployment_bp.route('/<int:deployment_id>', methods=['DELETE'])
@jwt_required()
def delete_deployment(deployment_id):
    """Delete a deployment"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "Deployment not found"}), 404
    
    if not check_deployment_access(user, deployment=deployment):
        return jsonify({"error": "Access denied"}), 403
    
    # Return resources to cluster
    cluster = deployment.cluster
    cluster.available_ram_gb += deployment.ram_gb
    cluster.available_cpu_cores += deployment.cpu_cores
    cluster.available_gpu_count += deployment.gpu_count
    
    try:
        db.session.delete(deployment)
        db.session.commit()
        return jsonify({"message": "Deployment deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@deployment_bp.route('/<int:deployment_id>/logs', methods=['GET'])
@jwt_required()
def get_deployment_logs(deployment_id):
    """Get deployment logs"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "Deployment not found"}), 404
    
    if not check_deployment_access(user, deployment=deployment):
        return jsonify({"error": "Access denied"}), 403
    
    # Get log parameters
    tail = request.args.get('tail', type=int, default=100)
    since = request.args.get('since', type=str)  # ISO format datetime
    
    # TODO: Implement actual log retrieval from container runtime
    # For now, return dummy logs
    logs = {
        "deployment_id": deployment_id,
        "name": deployment.name,
        "status": deployment.status,
        "logs": [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "INFO",
                "message": "Deployment logs will be implemented with container runtime integration"
            }
        ]
    }
    
    return jsonify(logs), 200

@deployment_bp.route('/<int:deployment_id>/schedule', methods=['POST'])
@jwt_required()
def schedule_deployment(deployment_id):
    """Manually trigger scheduling of a deployment"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "Deployment not found"}), 404
    
    if not check_deployment_access(user, deployment=deployment):
        return jsonify({"error": "Access denied"}), 403
    
    if deployment.status != 'pending':
        return jsonify({"error": "Only pending deployments can be scheduled"}), 400
    
    try:
        # Attempt to schedule the deployment
        success = current_app.scheduler.schedule_deployment(deployment_id)
        if success:
            return jsonify({"message": "Deployment scheduled successfully"}), 200
        else:
            return jsonify({"error": "Unable to schedule deployment at this time"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@deployment_bp.route('/queue', methods=['GET'])
@jwt_required()
def get_deployment_queue():
    """Get the current deployment queue status"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Get queue entries based on user's role/organization
    if user.role == 'admin':
        queue = DeploymentQueue.query.order_by(
            DeploymentQueue.priority.desc(),
            DeploymentQueue.queued_at.asc()
        ).all()
    else:
        queue = DeploymentQueue.query.join(Deployment).join(Cluster).filter(
            Cluster.organization_id == user.organization_id
        ).order_by(
            DeploymentQueue.priority.desc(),
            DeploymentQueue.queued_at.asc()
        ).all()
    
    queue_status = {
        "queue_length": len(queue),
        "entries": [
            {
                "deployment": q.deployment.to_dict(),
                "priority": q.priority,
                "queued_at": q.queued_at.isoformat(),
                "position": idx + 1
            }
            for idx, q in enumerate(queue)
        ]
    }
    
    return jsonify(queue_status), 200

@deployment_bp.route('/<int:deployment_id>/priority', methods=['PUT'])
@jwt_required()
def update_deployment_priority(deployment_id):
    """Update the priority of a queued deployment"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "Deployment not found"}), 404
    
    if not check_deployment_access(user, deployment=deployment):
        return jsonify({"error": "Access denied"}), 403
    
    data = request.get_json()
    if not data or 'priority' not in data:
        return jsonify({"error": "Priority is required"}), 400
    
    try:
        priority = int(data['priority'])
        if priority < 1 or priority > 5:
            return jsonify({"error": "Priority must be between 1 and 5"}), 400
    except ValueError:
        return jsonify({"error": "Priority must be an integer"}), 400
    
    # Update priority in both deployment and queue
    deployment.priority = priority
    queue_entry = DeploymentQueue.query.filter_by(deployment_id=deployment_id).first()
    if queue_entry:
        queue_entry.priority = priority
    
    try:
        db.session.commit()
        # Notify scheduler about priority change
        current_app.scheduler.notify_priority_change(deployment_id)
        return jsonify({"message": "Priority updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@deployment_bp.route('/<int:deployment_id>/status', methods=['GET'])
@jwt_required()
def get_deployment_status(deployment_id):
    """Get detailed deployment status including queue position"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "Deployment not found"}), 404
    
    if not check_deployment_access(user, deployment=deployment):
        return jsonify({"error": "Access denied"}), 403
    
    # Get queue position if deployment is pending
    queue_position = None
    estimated_start_time = None
    if deployment.status == 'pending':
        queue_entry = DeploymentQueue.query.filter_by(deployment_id=deployment_id).first()
        if queue_entry:
            higher_priority = DeploymentQueue.query.filter(
                DeploymentQueue.priority > queue_entry.priority
            ).count()
            same_priority_earlier = DeploymentQueue.query.filter(
                DeploymentQueue.priority == queue_entry.priority,
                DeploymentQueue.queued_at < queue_entry.queued_at
            ).count()
            queue_position = higher_priority + same_priority_earlier + 1
            # Rough estimate: 5 minutes per deployment ahead in queue
            estimated_start_time = (
                datetime.now(timezone.utc) + 
                timedelta(minutes=5 * (queue_position - 1))
            ).isoformat()
    
    # Get runtime metrics if deployment is running
    metrics = {
        "ram_usage": {
            "allocated_gb": deployment.ram_gb,
            "used_gb": 0,  # To be implemented with container runtime
            "utilization": 0
        },
        "cpu_usage": {
            "allocated_cores": deployment.cpu_cores,
            "used_cores": 0,  # To be implemented with container runtime
            "utilization": 0
        },
        "gpu_usage": {
            "allocated_count": deployment.gpu_count,
            "used_count": 0,  # To be implemented with container runtime
            "utilization": 0
        }
    }
    
    if deployment.status == 'running':
        # TODO: Get actual metrics from container runtime
        pass
    
    status = {
        "deployment": deployment.to_dict(),
        "queue_info": {
            "position": queue_position,
            "estimated_start_time": estimated_start_time
        } if queue_position else None,
        "metrics": metrics,
        "health": {
            "status": deployment.status,
            "last_updated": deployment.updated_at.isoformat(),
            "uptime": None  # To be implemented
        }
    }
    
    return jsonify(status), 200 