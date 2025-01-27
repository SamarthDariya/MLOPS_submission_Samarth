from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import Organization, User, db
from datetime import datetime, timezone, timedelta
import random
import string
from flask import current_app

org_bp = Blueprint('organizations', __name__)

def validate_organization_data(data):
    """Validate organization data"""
    errors = []
    
    # Check required fields
    required_fields = ['name']
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
            
    # Validate name length
    if 'name' in data:
        if len(data['name'].strip()) < 3:
            errors.append("Organization name must be at least 3 characters long")
        if len(data['name'].strip()) > 100:
            errors.append("Organization name must not exceed 100 characters")
            
    return errors

@org_bp.route('/', methods=['POST'])
@jwt_required()
def create_organization():
    """Create a new organization"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    if user.role != 'admin':
        return jsonify({"error": "Only admins can create organizations"}), 403
        
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    # Validate organization data
    validation_errors = validate_organization_data(data)
    if validation_errors:
        return jsonify({"errors": validation_errors}), 400
        
    # Check if organization with same name exists
    if Organization.query.filter_by(name=data['name'].strip()).first():
        return jsonify({"error": "Organization with this name already exists"}), 400
        
    # Create new organization
    org = Organization(
        name=data['name'].strip(),
        description=data.get('description', '').strip(),
        status='active',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    db.session.add(org)
    try:
        db.session.commit()
        return jsonify(org.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@org_bp.route('/', methods=['GET'])
@jwt_required()
def list_organizations():
    """List organizations based on user's role"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    # Admin can see all organizations
    if user.role == 'admin':
        orgs = Organization.query.all()
    else:
        # Regular users can only see their organization
        if user.organization_id:
            orgs = [Organization.query.get(user.organization_id)]
        else:
            orgs = []
            
    return jsonify([org.to_dict() for org in orgs if org]), 200

@org_bp.route('/<int:org_id>', methods=['GET'])
@jwt_required()
def get_organization(org_id):
    """Get organization details"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    org = Organization.query.get(org_id)
    if not org:
        return jsonify({"error": "Organization not found"}), 404
        
    # Check if user has access to this organization
    if user.role != 'admin' and user.organization_id != org_id:
        return jsonify({"error": "Access denied"}), 403
        
    return jsonify(org.to_dict()), 200

@org_bp.route('/<int:org_id>', methods=['PUT'])
@jwt_required()
def update_organization(org_id):
    """Update organization details"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    if user.role != 'admin':
        return jsonify({"error": "Only admins can update organizations"}), 403
        
    org = Organization.query.get(org_id)
    if not org:
        return jsonify({"error": "Organization not found"}), 404
        
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    # Validate updates if name is being changed
    if 'name' in data:
        validation_errors = validate_organization_data(data)
        if validation_errors:
            return jsonify({"errors": validation_errors}), 400
            
        # Check if new name conflicts with existing organization
        existing_org = Organization.query.filter_by(name=data['name'].strip()).first()
        if existing_org and existing_org.id != org_id:
            return jsonify({"error": "Organization with this name already exists"}), 400
            
        org.name = data['name'].strip()
        
    if 'description' in data:
        org.description = data['description'].strip()
        
    if 'status' in data:
        if data['status'] not in ['active', 'inactive']:
            return jsonify({"error": "Invalid status"}), 400
        org.status = data['status']
        
    org.updated_at = datetime.now(timezone.utc)
    
    try:
        db.session.commit()
        return jsonify(org.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@org_bp.route('/<int:org_id>', methods=['DELETE'])
@jwt_required()
def delete_organization(org_id):
    """Delete an organization"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    if user.role != 'admin':
        return jsonify({"error": "Only admins can delete organizations"}), 403
        
    org = Organization.query.get(org_id)
    if not org:
        return jsonify({"error": "Organization not found"}), 404
        
    # Check if organization has any users
    if org.users:
        return jsonify({
            "error": "Cannot delete organization with active users",
            "user_count": len(org.users)
        }), 400
        
    # Check if organization has any clusters
    if org.clusters:
        return jsonify({
            "error": "Cannot delete organization with active clusters",
            "cluster_count": len(org.clusters)
        }), 400
        
    try:
        db.session.delete(org)
        db.session.commit()
        return jsonify({"message": "Organization deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@org_bp.route('/<int:org_id>/users', methods=['GET'])
@jwt_required()
def list_organization_users(org_id):
    """List all users in an organization"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    org = Organization.query.get(org_id)
    if not org:
        return jsonify({"error": "Organization not found"}), 404
        
    # Check if user has access to this organization
    if user.role != 'admin' and user.organization_id != org_id:
        return jsonify({"error": "Access denied"}), 403
        
    return jsonify([user.to_dict() for user in org.users]), 200

@org_bp.route('/<int:org_id>/clusters', methods=['GET'])
@jwt_required()
def list_organization_clusters(org_id):
    """List all clusters in an organization"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    org = Organization.query.get(org_id)
    if not org:
        return jsonify({"error": "Organization not found"}), 404
        
    # Check if user has access to this organization
    if user.role != 'admin' and user.organization_id != org_id:
        return jsonify({"error": "Access denied"}), 403
        
    return jsonify([cluster.to_dict() for cluster in org.clusters]), 200

@org_bp.route('/<int:org_id>/stats', methods=['GET'])
@jwt_required()
def get_organization_stats(org_id):
    """Get organization statistics"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    org = Organization.query.get(org_id)
    if not org:
        return jsonify({"error": "Organization not found"}), 404
        
    # Check if user has access to this organization
    if user.role != 'admin' and user.organization_id != org_id:
        return jsonify({"error": "Access denied"}), 403
        
    # Calculate resource usage across all clusters
    total_ram = sum(cluster.total_ram_gb for cluster in org.clusters)
    total_cpu = sum(cluster.total_cpu_cores for cluster in org.clusters)
    total_gpu = sum(cluster.total_gpu_count for cluster in org.clusters)
    
    available_ram = sum(cluster.available_ram_gb for cluster in org.clusters)
    available_cpu = sum(cluster.available_cpu_cores for cluster in org.clusters)
    available_gpu = sum(cluster.available_gpu_count for cluster in org.clusters)
    
    active_deployments = sum(
        len([d for d in cluster.deployments if d.status == 'running'])
        for cluster in org.clusters
    )
    
    stats = {
        "organization": org.to_dict(),
        "user_count": len(org.users),
        "cluster_count": len(org.clusters),
        "active_deployment_count": active_deployments,
        "resources": {
            "ram_gb": {
                "total": total_ram,
                "used": total_ram - available_ram,
                "available": available_ram,
                "utilization": (total_ram - available_ram) / total_ram * 100 if total_ram > 0 else 0
            },
            "cpu_cores": {
                "total": total_cpu,
                "used": total_cpu - available_cpu,
                "available": available_cpu,
                "utilization": (total_cpu - available_cpu) / total_cpu * 100 if total_cpu > 0 else 0
            },
            "gpu_count": {
                "total": total_gpu,
                "used": total_gpu - available_gpu,
                "available": available_gpu,
                "utilization": (total_gpu - available_gpu) / total_gpu * 100 if total_gpu > 0 else 0
            }
        }
    }
    
    return jsonify(stats), 200

@org_bp.route('/<int:org_id>/invite', methods=['POST'])
@jwt_required()
def generate_invite_code(org_id):
    """Generate an invite code for an organization"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    org = Organization.query.get(org_id)
    if not org:
        return jsonify({"error": "Organization not found"}), 404
        
    # Check if user has permission to generate invite code
    if user.role != 'admin' and user.organization_id != org_id:
        return jsonify({"error": "Access denied"}), 403
    
    # Generate a random invite code
    invite_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    # Store invite code in Redis with expiration
    expiry_hours = current_app.config.get('INVITE_CODE_EXPIRY_HOURS', 24)
    current_app.redis.setex(
        f"invite_code:{invite_code}",
        timedelta(hours=expiry_hours),
        str(org_id)
    )
    
    return jsonify({
        "invite_code": invite_code,
        "expires_in": f"{expiry_hours} hours"
    }), 201

@org_bp.route('/join', methods=['POST'])
@jwt_required()
def join_organization():
    """Join an organization using invite code"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    if user.organization_id:
        return jsonify({"error": "User already belongs to an organization"}), 400
    
    data = request.get_json()
    if not data or 'invite_code' not in data:
        return jsonify({"error": "Invite code is required"}), 400
    
    invite_code = data['invite_code']
    
    # Check if invite code exists and get organization ID
    org_id = current_app.redis.get(f"invite_code:{invite_code}")
    if not org_id:
        return jsonify({"error": "Invalid or expired invite code"}), 400
    
    org_id = int(org_id)
    organization = Organization.query.get(org_id)
    if not organization:
        return jsonify({"error": "Organization not found"}), 404
    
    # Update user's organization
    user.organization_id = org_id
    user.updated_at = datetime.now(timezone.utc)
    
    try:
        db.session.commit()
        # Delete the used invite code
        current_app.redis.delete(f"invite_code:{invite_code}")
        return jsonify(user.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500 