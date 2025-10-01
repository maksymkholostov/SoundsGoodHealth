from flask import Blueprint, request, jsonify, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from functools import wraps

from ..auth.service import AuthService
from ..auth.models import User

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth_api', __name__)

def login_required(f):
    """Decorator to require login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                'success': False,
                'error': "You must be logged in to access this resource"
            }), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f: Callable) -> Callable:
    """
    Decorator to protect routes that require admin privileges.
    Must be applied after @login_required.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # First check if user is logged in
        if not current_user.is_authenticated:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 401
        
        # Then check if user is an admin
        if not session.get('is_admin', False) and not getattr(current_user, 'is_admin', False):
            current_app.logger.warning(f"Non-admin user {current_user.username} attempted to access admin route")
            return jsonify({
                'success': False,
                'error': 'Administrator privileges required'
            }), 403
            
        return f(*args, **kwargs)
    return decorated

def api_token_required(f):
    """Decorator to require API token for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('X-API-Token')
        if not token:
            return jsonify({
                'success': False,
                'error': "API token is required"
            }), 401
        
        auth_service = current_app.auth_service
        user = auth_service.get_user_by_token(token)
        
        if not user:
            return jsonify({
                'success': False,
                'error': "Invalid API token"
            }), 401
        
        # Add user to request context
        request.user = user
            
        return f(*args, **kwargs)
    return decorated_function

def init_auth_routes(auth_service: AuthService) -> Blueprint:
    """
    Initialize auth routes with the auth service.
    
    Args:
        auth_service: Instance of AuthService
        
    Returns:
        Configured Blueprint
    """
    
    @auth_bp.route('/api/auth/register', methods=['POST'])
    def register() -> Dict[str, Any]:
        """Register a new user."""
        try:
            data = request.json
            
            # Validate required fields
            required_fields = ['username', 'email', 'password']
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        'success': False,
                        'error': f"Missing required field: {field}"
                    }), 400
            
            # Register the user
            user, error = auth_service.register_user(
                username=data['username'],
                email=data['email'],
                password=data['password'],
                first_name=data.get('first_name'),
                last_name=data.get('last_name')
            )
            
            if error:
                return jsonify({
                    'success': False,
                    'error': error
                }), 400
            
            # Log in the user automatically
            session['user_id'] = user.id
            
            return jsonify({
                'success': True,
                'user': user.to_dict()
            })
        except Exception as e:
            logger.error(f"Error in register: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @auth_bp.route('/api/auth/login', methods=['POST'])
    def login() -> Dict[str, Any]:
        """Log in a user."""
        try:
            data = request.json
            
            # Validate required fields
            if 'username_or_email' not in data or 'password' not in data:
                return jsonify({
                    'success': False,
                    'error': "Username/email and password are required"
                }), 400
            
            # Authenticate the user
            user, error = auth_service.authenticate(
                username_or_email=data['username_or_email'],
                password=data['password']
            )
            
            if error:
                return jsonify({
                    'success': False,
                    'error': error
                }), 401
            
            # Set session
            session['user_id'] = user.id
            
            return jsonify({
                'success': True,
                'user': user.to_dict(),
                'api_token': user.api_token
            })
        except Exception as e:
            logger.error(f"Error in login: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @auth_bp.route('/api/auth/logout', methods=['POST'])
    def logout() -> Dict[str, Any]:
        """Log out a user."""
        try:
            session.pop('user_id', None)
            
            return jsonify({
                'success': True,
                'message': "Logged out successfully"
            })
        except Exception as e:
            logger.error(f"Error in logout: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @auth_bp.route('/api/auth/profile', methods=['GET'])
    @login_required
    # DB-OPERATION: read file
    def get_profile() -> Dict[str, Any]:
        """Get the current user's profile."""
        try:
            user_id = session['user_id']
            user = auth_service.get_user_by_id(user_id)
            
            if not user:
                session.pop('user_id', None)
                return jsonify({
                    'success': False,
                    'error': "User not found"
                }), 404
            
            return jsonify({
                'success': True,
                'user': user.to_dict()
            })
        except Exception as e:
            logger.error(f"Error in get_profile: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @auth_bp.route('/api/auth/profile', methods=['PUT'])
    @login_required
    # DB-OPERATION: update file
    def update_profile() -> Dict[str, Any]:
        """Update the current user's profile."""
        try:
            user_id = session['user_id']
            data = request.json or {}
            
            # Check if the current user exists
            current_user = auth_service.get_user_by_id(user_id)
            if not current_user:
                session.pop('user_id', None)
                return jsonify({
                    'success': False,
                    'error': "User not found"
                }), 404
            
            # Update the user
            updatable_fields = ['username', 'email', 'first_name', 'last_name', 'preferences']
            update_data = {k: v for k, v in data.items() if k in updatable_fields}
            
            user, error = auth_service.update_user(user_id, **update_data)
            
            if error:
                return jsonify({
                    'success': False,
                    'error': error
                }), 400
            
            return jsonify({
                'success': True,
                'user': user.to_dict()
            })
        except Exception as e:
            logger.error(f"Error in update_profile: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @auth_bp.route('/api/auth/password', methods=['PUT'])
    @login_required
    def change_password() -> Dict[str, Any]:
        """Change the current user's password."""
        try:
            user_id = session['user_id']
            data = request.json
            
            # Validate required fields
            if 'current_password' not in data or 'new_password' not in data:
                return jsonify({
                    'success': False,
                    'error': "Current password and new password are required"
                }), 400
            
            # Change the password
            success, error = auth_service.change_password(
                user_id=user_id,
                current_password=data['current_password'],
                new_password=data['new_password']
            )
            
            if not success:
                return jsonify({
                    'success': False,
                    'error': error
                }), 400
            
            return jsonify({
                'success': True,
                'message': "Password changed successfully"
            })
        except Exception as e:
            logger.error(f"Error in change_password: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @auth_bp.route('/api/auth/token', methods=['POST'])
    @login_required
    def generate_token() -> Dict[str, Any]:
        """Generate a new API token for the current user."""
        try:
            user_id = session['user_id']
            
            # Generate a new token
            token, error = auth_service.generate_new_token(user_id)
            
            if error:
                return jsonify({
                    'success': False,
                    'error': error
                }), 400
            
            return jsonify({
                'success': True,
                'token': token
            })
        except Exception as e:
            logger.error(f"Error in generate_token: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @auth_bp.route('/api/auth/users', methods=['GET'])
    @admin_required
    # DB-OPERATION: read user
    def list_users() -> Dict[str, Any]:
        """List all users (admin only)."""
        try:
            users = auth_service.list_users()
            
            return jsonify({
                'success': True,
                'users': users
            })
        except Exception as e:
            logger.error(f"Error in list_users: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @auth_bp.route('/api/auth/users/<user_id>', methods=['PUT'])
    @admin_required
    def admin_update_user(user_id: str) -> Dict[str, Any]:
        """Update a user (admin only)."""
        try:
            data = request.json or {}
            
            # Update the user
            updatable_fields = ['username', 'email', 'first_name', 'last_name', 
                              'is_active', 'is_admin', 'preferences']
            update_data = {k: v for k, v in data.items() if k in updatable_fields}
            
            user, error = auth_service.update_user(user_id, **update_data)
            
            if error:
                return jsonify({
                    'success': False,
                    'error': error
                }), 400
            
            return jsonify({
                'success': True,
                'user': user.to_dict()
            })
        except Exception as e:
            logger.error(f"Error in admin_update_user: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @auth_bp.route('/api/auth/users/<user_id>', methods=['DELETE'])
    @admin_required
    # DB-OPERATION: delete user
    def delete_user(user_id: str) -> Dict[str, Any]:
        """Delete a user (admin only)."""
        try:
            # Prevent deleting yourself
            current_user_id = session['user_id']
            if user_id == current_user_id:
                return jsonify({
                    'success': False,
                    'error': "You cannot delete your own account"
                }), 400
            
            # Delete the user
            success, error = auth_service.delete_user(user_id)
            
            if not success:
                return jsonify({
                    'success': False,
                    'error': error
                }), 400
            
            return jsonify({
                'success': True,
                'message': "User deleted successfully"
            })
        except Exception as e:
            logger.error(f"Error in delete_user: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @auth_bp.route('/api/auth/token/verify', methods=['GET'])
    @api_token_required
    def verify_token() -> Dict[str, Any]:
        """Verify an API token."""
        # If we get here, the token is valid (thanks to @api_token_required)
        return jsonify({
            'success': True,
            'user': request.user.to_dict()
        })
    
    return auth_bp
