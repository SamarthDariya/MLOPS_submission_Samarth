from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from ..models import Cluster, User, db
from datetime import datetime, timezone

cluster_bp = Blueprint('clusters', __name__)

def validate_cluster_resources(data):
    """Validate cluster resource specifications"""
    errors = []
    
    # Check required fields
    required_fields = ['name', 'total_ram_gb', 'total_cpu_cores']
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    # Validate resource values
    if 'total_ram_gb' in data:
        try:
            ram = float(data['total_ram_gb'])
            if ram <= 0:
                errors.append("total_ram_gb must be greater than 0")
        except ValueError:
            errors.append("total_ram_gb must be a number")
            
    if 'total_cpu_cores' in data:
        try:
            cpu = float(data['total_cpu_cores'])
            if cpu <= 0:
                errors.append("total_cpu_cores must be greater than 0")
        except ValueError:
            errors.append("total_cpu_cores must be a number")
            
    if 'total_gpu_count' in data:
        try:
            gpu = int(data['total_gpu_count'])
            if gpu < 0:
                errors.append("total_gpu_count must be non-negative")
        except ValueError:
            errors.append("total_gpu_count must be an integer")
    
    return errors

def check_admin_or_org_member(user, cluster=None):
    """Check if user is admin or member of cluster's organization"""
    if user.role == 'admin':
        return True
    if cluster and cluster.organization_id == user.organization_id:
        return True
    return False

@cluster_bp.route('/', methods=['POST'])
@jwt_required()
def create_cluster():
    """Create a new cluster"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    if user.role not in ['admin', 'developer']:
        return jsonify({"error": "Insufficient permissions"}), 403
        
    if not user.organization_id:
        return jsonify({"error": "User must belong to an organization"}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    # Validate cluster resources
    validation_errors = validate_cluster_resources(data)
    if validation_errors:
        return jsonify({"errors": validation_errors}), 400
    
    # Create new cluster
    cluster = Cluster(
        name=data['name'],
        organization_id=user.organization_id,
        total_ram_gb=float(data['total_ram_gb']),
        total_cpu_cores=float(data['total_cpu_cores']),
        total_gpu_count=int(data.get('total_gpu_count', 0)),
        status='active'
    )
    
    db.session.add(cluster)
    try:
        db.session.commit()
        return jsonify(cluster.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@cluster_bp.route('/', methods=['GET'])
@jwt_required()
def list_clusters():
    """List clusters based on user's role and organization"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Admin can see all clusters
    if user.role == 'admin':
        clusters = Cluster.query.all()
    else:
        # Regular users can only see clusters in their organization
        clusters = Cluster.query.filter_by(organization_id=user.organization_id).all()
    
    return jsonify([cluster.to_dict() for cluster in clusters]), 200

@cluster_bp.route('/<int:cluster_id>', methods=['GET'])
@jwt_required()
def get_cluster(cluster_id):
    """Get cluster details"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    cluster = Cluster.query.get(cluster_id)
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404
        
    if not check_admin_or_org_member(user, cluster):
        return jsonify({"error": "Access denied"}), 403
    
    return jsonify(cluster.to_dict()), 200

@cluster_bp.route('/<int:cluster_id>', methods=['PUT'])
@jwt_required()
def update_cluster(cluster_id):
    """Update cluster details"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    cluster = Cluster.query.get(cluster_id)
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404
        
    if not check_admin_or_org_member(user, cluster):
        return jsonify({"error": "Access denied"}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Validate updates
    if 'status' in data:
        if data['status'] not in ['active', 'maintenance', 'offline']:
            return jsonify({"error": "Invalid status"}), 400
        cluster.status = data['status']
    
    if any(key in data for key in ['total_ram_gb', 'total_cpu_cores', 'total_gpu_count']):
        validation_errors = validate_cluster_resources(data)
        if validation_errors:
            return jsonify({"errors": validation_errors}), 400
            
        # Update resources if provided
        if 'total_ram_gb' in data:
            cluster.total_ram_gb = float(data['total_ram_gb'])
            cluster.available_ram_gb = float(data['total_ram_gb'])
        if 'total_cpu_cores' in data:
            cluster.total_cpu_cores = float(data['total_cpu_cores'])
            cluster.available_cpu_cores = float(data['total_cpu_cores'])
        if 'total_gpu_count' in data:
            cluster.total_gpu_count = int(data['total_gpu_count'])
            cluster.available_gpu_count = int(data['total_gpu_count'])
    
    if 'name' in data:
        cluster.name = data['name']
    
    cluster.updated_at = datetime.now(timezone.utc)
    
    try:
        db.session.commit()
        return jsonify(cluster.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@cluster_bp.route('/<int:cluster_id>', methods=['DELETE'])
@jwt_required()
def delete_cluster(cluster_id):
    """Delete a cluster"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    if user.role != 'admin':
        return jsonify({"error": "Only admins can delete clusters"}), 403
    
    cluster = Cluster.query.get(cluster_id)
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404
    
    # Check if cluster has active deployments
    if cluster.deployments and any(d.status == 'running' for d in cluster.deployments):
        return jsonify({
            "error": "Cannot delete cluster with active deployments",
            "active_deployments": [d.to_dict() for d in cluster.deployments if d.status == 'running']
        }), 400
    
    try:
        db.session.delete(cluster)
        db.session.commit()
        return jsonify({"message": "Cluster deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@cluster_bp.route('/<int:cluster_id>/status', methods=['GET'])
@jwt_required()
def get_cluster_status(cluster_id):
    """Get detailed cluster status including resource usage"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    cluster = Cluster.query.get(cluster_id)
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404
        
    if not check_admin_or_org_member(user, cluster):
        return jsonify({"error": "Access denied"}), 403
    
    # Calculate resource usage
    total_ram = cluster.total_ram_gb
    total_cpu = cluster.total_cpu_cores
    total_gpu = cluster.total_gpu_count
    
    available_ram = cluster.available_ram_gb
    available_cpu = cluster.available_cpu_cores
    available_gpu = cluster.available_gpu_count
    
    used_ram = total_ram - available_ram
    used_cpu = total_cpu - available_cpu
    used_gpu = total_gpu - available_gpu
    
    # Get active deployments
    active_deployments = [d.to_dict() for d in cluster.deployments if d.status == 'running']
    
    status = {
        "cluster": cluster.to_dict(),
        "resources": {
            "ram_gb": {
                "total": total_ram,
                "used": used_ram,
                "available": available_ram,
                "utilization": (used_ram / total_ram * 100) if total_ram > 0 else 0
            },
            "cpu_cores": {
                "total": total_cpu,
                "used": used_cpu,
                "available": available_cpu,
                "utilization": (used_cpu / total_cpu * 100) if total_cpu > 0 else 0
            },
            "gpu_count": {
                "total": total_gpu,
                "used": used_gpu,
                "available": available_gpu,
                "utilization": (used_gpu / total_gpu * 100) if total_gpu > 0 else 0
            }
        },
        "active_deployments": active_deployments,
        "deployment_count": len(active_deployments)
    }
    
    return jsonify(status), 200 