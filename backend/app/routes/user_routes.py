"""
Routes related to user profile, settings, and preferences.
"""
from flask import Blueprint, request, jsonify, session, current_app
from flask_login import login_required, current_user

# Create blueprint
user_bp = Blueprint('user', __name__, url_prefix='/user') # Add '/user' prefix

# --- User Preferences API ---

# Renamed endpoint URL to be more user-centric
@user_bp.route('/api/preferences/view_mode', methods=['POST']) 
@login_required
def set_view_mode():
    """API endpoint to set the user's preferred data view mode (own vs all)."""
    data = request.get_json()
    view_all = data.get('view_all', False) # Expecting {"view_all": true/false}

    # Validate input
    if not isinstance(view_all, bool):
        return jsonify({"success": False, "error": "Invalid value for view_all, must be boolean."}), 400

    try:
        session['view_all_mode'] = view_all
        session.modified = True # Ensure session is saved
        current_app.logger.info(f"User {session.get('_user_id', getattr(current_user, 'id', 'N/A'))} set view_all_mode to: {view_all}")
        return jsonify({"success": True, "view_all_mode": view_all})
    except Exception as e:
        current_app.logger.error(f"Error setting view mode in session: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to update setting."}), 500

# --- Add other user-related routes here (e.g., profile page, settings page) ---

# Example placeholder for a user profile page:
# @user_bp.route('/profile')
# @login_required
# def profile_page():
#     # Fetch user data and render template
#     return render_template('user_profile.html', user=current_user) 