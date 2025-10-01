import logging
from flask import Blueprint, request, jsonify, current_app, session
from flask_login import current_user
from typing import Dict, Any
from datetime import datetime, timedelta

from backend.app.services.system_service import SystemService
from backend.app.api.auth import admin_required

# Set up logging
logger = logging.getLogger(__name__)

admin_api_bp = Blueprint('admin_api', __name__)

def init_admin_routes(system_service: SystemService) -> Blueprint:
    """Initialize admin routes with required services."""
    
    @admin_api_bp.route('/api/admin/active-users', methods=['GET'])
    @admin_required
    def get_active_users() -> Dict[str, Any]:
        """
        Get a list of users who are currently active (logged in recently).
        For admin dashboard display.
        """
        try:
            # Get auth service from app context
            auth_service = current_app.auth_service
            if not auth_service:
                return jsonify({
                    'success': False,
                    'error': 'Auth service not available'
                }), 500
                
            # Get all users from auth service
            all_users = auth_service.list_users()
            
            # Get current time and threshold (active within last 30 minutes)
            now = datetime.now()
            threshold = now - timedelta(minutes=30)
            
            # Filter active users
            active_users = []
            for user in all_users:
                # Check if user has a last_active timestamp
                last_active = user.get('last_active')
                if last_active:
                    # Convert string to datetime if needed
                    if isinstance(last_active, str):
                        try:
                            last_active = datetime.fromisoformat(last_active)
                        except (ValueError, TypeError):
                            last_active = None
                            
                    # Check if user is active within threshold
                    if last_active and last_active > threshold:
                        active_users.append({
                            'id': user['id'],
                            'username': user['username'],
                            'last_active': last_active.isoformat() if isinstance(last_active, datetime) else last_active
                        })
            
            return jsonify({
                'success': True,
                'active_users': active_users
            })
                
        except Exception as e:
            logger.error(f"Error getting active users: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @admin_api_bp.route('/api/admin/system/reset', methods=['POST'])
    @admin_required
    def reset_system() -> Dict[str, Any]:
        """
        Reset system data to initial state. 
        Requires admin permissions and a security passcode.
        """
        try:
            data = request.json or {}
            
            # Validate required passcode
            if 'passcode' not in data:
                return jsonify({
                    'success': False,
                    'error': 'Security passcode is required'
                }), 400
                
            # Default options
            options = {
                'reset_dictionaries': data.get('reset_dictionaries', True),
                'reset_classes': data.get('reset_classes', True),
                'reset_stats': data.get('reset_stats', True),
                'reset_recordings': data.get('reset_recordings', True),
                'preserve_user_accounts': data.get('preserve_user_accounts', True),
                'dry_run': data.get('dry_run', False)
            }
            
            # Perform reset using the service
            result = system_service.reset_system(
                passcode=data.get('passcode'),
                **options
            )
            
            if result.get('success', False):
                return jsonify(result), 200
            else:
                return jsonify(result), 400
                
        except Exception as e:
            logger.error(f"Error in reset_system API: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    return admin_api_bp 