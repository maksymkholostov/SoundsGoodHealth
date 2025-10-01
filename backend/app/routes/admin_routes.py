# backend/app/routes/admin_routes.py
"""
Routes restricted to admin users.
"""
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, session, flash
from flask_login import login_required, current_user
from functools import wraps
import os # For checking template existence

# Create blueprint with URL prefix
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# --- Admin Decorator ---
def admin_required(f):
    """Decorator to ensure user is logged in AND is an admin."""
    @wraps(f)
    @login_required # User must be logged in
    def decorated_function(*args, **kwargs):
        # Check admin status from session or current_user object
        is_admin = session.get('is_admin', False)
        if not is_admin and hasattr(current_user, 'is_admin'): # Fallback check on user object
             is_admin = getattr(current_user, 'is_admin', False)

        if not is_admin:
            user_identifier = current_user.username if hasattr(current_user, 'username') else session.get('user_id', 'Unknown')
            current_app.logger.warning(f"Non-admin user '{user_identifier}' attempted to access admin route: {request.path}")
            flash("You do not have permission to access this administrative page.", "danger")
            # Redirect to the main index page
            try: return redirect(url_for('core_web.index'))
            except: return redirect('/') # Absolute fallback
        # User is admin, proceed to the route function
        return f(*args, **kwargs)
    return decorated_function

# --- Admin Pages ---

@admin_bp.route('/error-analysis')
@admin_required # Apply the decorator
def admin_error_analysis_page():
    """Serve the admin error analysis page."""
    # Ensure template exists before rendering
    template_path = os.path.join(current_app.template_folder, 'admin_error_analysis.html')
    if not os.path.exists(template_path):
         return "Error: admin_error_analysis.html template not found.", 404
    # Page likely fetches data via specific admin APIs
    return render_template('admin_error_analysis.html')

@admin_bp.route('/sync-models')
@admin_required # Apply the decorator
def admin_sync_models_page():
    """Serve the admin model sync/summary page."""
    # Ensure template exists
    template_path = os.path.join(current_app.template_folder, 'model_summary_hub.html')
    if not os.path.exists(template_path):
         return "Error: model_summary_hub.html template not found.", 404
    # Page likely fetches data/triggers actions via specific admin APIs
    return render_template('model_summary_hub.html')

# --- Example Admin API Endpoint ---
# @admin_bp.route('/api/users', methods=['GET'])
# @admin_required
# def api_admin_get_users():
#     """API endpoint for admins to list users."""
#     try:
#         # Assumes auth_service has a method to get all users
#         users = current_app.auth_service.get_all_users()
#         # Convert user objects to dicts for JSON response, excluding sensitive info
#         user_list = [{'id': u.id, 'username': u.username, 'email': u.email, 'is_admin': u.is_admin} for u in users]
#         return jsonify({"success": True, "users": user_list})
#     except Exception as e:
#         current_app.logger.error(f"Admin API Error getting users: {e}", exc_info=True)
#         return jsonify({"success": False, "error": "Failed to retrieve user list"}), 500

