import logging
from flask import Blueprint, jsonify, current_app, abort, make_response
from flask_login import login_required # Ensure user is logged in for dev actions

# Create blueprint
# Using '/api/_dev' makes it clear these are non-production endpoints
developer_bp = Blueprint('developer', __name__, url_prefix='/api/_dev')
logger = logging.getLogger(__name__)

@developer_bp.route('/regenerate-id-map', methods=['POST'])
@login_required # Optional but recommended: ensure user is logged in
def regenerate_id_map():
    """
    API endpoint to trigger the regeneration of the developer ID map.
    Only available in debug mode. Does NOT delete anything.
    """
    # --- Security Check: Only allow in Debug mode ---
    if not current_app.debug:
        logger.warning("Attempt to access developer route '/regenerate-id-map' outside of debug mode.")
        abort(403) # Forbidden

    logger.info("Received request to regenerate developer ID map...")
    try:
        # Get the service from the app context
        dev_service = getattr(current_app, 'developer_tools_service', None)
        if not dev_service:
            logger.error("DeveloperToolsService not found on app context.")
            return jsonify({"success": False, "error": "Developer service not configured."}), 500

        # Call the regeneration method
        success = dev_service.generate_developer_id_map()

        if success:
            logger.info("Developer ID map regeneration successful.")
            return jsonify({"success": True, "message": "Developer ID map regenerated."})
        else:
            logger.error("Developer ID map regeneration failed (see service logs).")
            return jsonify({"success": False, "error": "Failed to regenerate ID map."}), 500

    except Exception as e:
        logger.error(f"Error in /regenerate-id-map route: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An unexpected server error occurred."}), 500

@developer_bp.route('/get-id-map', methods=['GET'])
@login_required # Optional but recommended
def get_id_map():
    """
    API endpoint to retrieve the current developer ID map.
    Only available in debug mode.
    """
    # --- Security Check: Only allow in Debug mode ---
    if not current_app.debug:
        logger.warning("Attempt to access developer route '/get-id-map' outside of debug mode.")
        abort(403) # Forbidden

    try:
        dev_service = getattr(current_app, 'developer_tools_service', None)
        if not dev_service:
            logger.error("DeveloperToolsService not found on app context.")
            return jsonify({"success": False, "error": "Developer service not configured."}), 500

        map_data = dev_service.get_map()
        # Check if the service returned an error embedded in the data
        if isinstance(map_data, dict) and "error" in map_data:
             return jsonify({"success": False, "error": map_data["error"]}), 404 # Or 500

        # Return as JSON
        response = make_response(jsonify(map_data))
        response.headers['Content-Type'] = 'application/json'
        return response

    except Exception as e:
        logger.error(f"Error in /get-id-map route: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An unexpected server error occurred."}), 500
