from flask import Blueprint, jsonify, request, redirect, url_for, make_response
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_current_user,
    JWTManager,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
    get_jwt
)
from ..models import User, db, Organization
from datetime import timedelta, datetime, timezone
from functools import wraps

auth_bp = Blueprint('auth', __name__)

def handle_invalid_token(error_message="Invalid token or user not found"):
    """Helper function to handle invalid token scenarios"""
    response = jsonify({
        "error": error_message,
        "redirect_to": url_for('auth.login')
    })
    response.status_code = 401
    return response

def token_and_user_required():
    """Custom decorator to verify both token and user existence"""
    def wrapper(fn):
        @wraps(fn)
        @jwt_required()
        def decorator(*args, **kwargs):
            current_user_id = get_jwt_identity()
            user = User.query.get(current_user_id)
            
            if not user:
                return handle_invalid_token()
                
            return fn(*args, **kwargs)
        return decorator
    return wrapper

@auth_bp.route('/auto-login', methods=['GET'])
def auto_login():
    """Attempt to automatically log in user using cookies"""
    try:
        # This will raise an exception if no valid token exists
        @jwt_required(optional=True)
        def check_token():
            return get_jwt_identity()
        
        current_user_id = check_token()
        if current_user_id:
            user = User.query.get(current_user_id)
            if user:
                return jsonify({
                    "message": "Auto-login successful",
                    "user": user.to_dict()
                }), 200
    except Exception:
        pass
    
    return jsonify({
        "error": "No valid session found",
        "redirect_to": url_for('auth.login')
    }), 401

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Validate required fields
    if not all(k in data for k in ['username', 'email', 'password']):
        return jsonify({"error": "Missing required fields"}), 400
        
    # Check if user already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({"error": "Username already exists"}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"error": "Email already exists"}), 400
        
    # Create new user
    user = User(
        username=data['username'],
        email=data['email'],
        role=data.get('role', 'user')  # Default to 'user' if role not specified
    )
    user.set_password(data['password'])
    
    # If this is the first user, make them an admin
    if User.query.count() == 0:
        user.role = 'admin'
    
    db.session.add(user)
    try:
        db.session.commit()
        # Generate tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        return jsonify({
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Missing username or password"}), 400
        
    user = User.query.filter_by(username=data['username']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({"error": "Invalid username or password"}), 401
        
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict()
    }), 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token using refresh token"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return handle_invalid_token("User not found during token refresh")
        
    # Create new access token
    access_token = create_access_token(
        identity=current_user_id,
        fresh=False
    )
    
    response = jsonify({
        "message": "Token refreshed successfully",
        "user": user.to_dict()
    })
    
    # Set new access token cookie
    set_access_cookies(response, access_token)
    
    return response, 200

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_user_info():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    return jsonify(user.to_dict()), 200

@auth_bp.route('/logout', methods=['POST'])
@token_and_user_required()
def logout():
    """Logout user by removing JWT cookies"""
    response = jsonify({"message": "Successfully logged out"})
    unset_jwt_cookies(response)
    return response, 200

@auth_bp.route('/users/<int:user_id>/organization', methods=['PUT'])
@token_and_user_required()
def update_user_organization(user_id):
    """Update a user's organization"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    if not current_user:
        return jsonify({"error": "User not found"}), 404
    
    if current_user.role != 'admin':
        return jsonify({"error": "Only admins can update user organizations"}), 403
    
    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({"error": "Target user not found"}), 404
    
    data = request.get_json()
    if not data or 'organization_id' not in data:
        return jsonify({"error": "organization_id is required"}), 400
    
    org_id = data['organization_id']
    organization = Organization.query.get(org_id)
    if not organization:
        return jsonify({"error": "Organization not found"}), 404
    
    target_user.organization_id = org_id
    target_user.updated_at = datetime.now(timezone.utc)
    
    try:
        db.session.commit()
        return jsonify(target_user.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/users/<int:user_id>/role', methods=['PUT'])
@token_and_user_required()
def update_user_role(user_id):
    """Update a user's role"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    if not current_user:
        return jsonify({"error": "User not found"}), 404
    
    if current_user.role != 'admin':
        return jsonify({"error": "Only admins can update user roles"}), 403
    
    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({"error": "Target user not found"}), 404
    
    data = request.get_json()
    if not data or 'role' not in data:
        return jsonify({"error": "role is required"}), 400
    
    new_role = data['role']
    if new_role not in ['admin', 'developer', 'user']:
        return jsonify({"error": "Invalid role. Must be one of: admin, developer, user"}), 400
    
    target_user.role = new_role
    target_user.updated_at = datetime.now(timezone.utc)
    
    try:
        db.session.commit()
        return jsonify(target_user.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# Error handlers for JWT exceptions
@auth_bp.errorhandler(401)
def handle_unauthorized(error):
    return jsonify({
        "error": "Unauthorized",
        "message": str(error)
    }), 401 