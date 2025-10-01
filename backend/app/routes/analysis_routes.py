# backend/app/routes/analysis_routes.py
"""
Routes related to analysis results (e.g., feature visualization, model performance).
"""
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for
from flask_login import login_required, current_user
# from flask_jwt_extended import jwt_required, get_jwt_identity # Keep if JWT is used for API
import os # For checking template existence

# Create blueprint for WEB routes
analysis_web_bp = Blueprint('analysis_web', __name__) # Renamed

# --- Analysis Pages ---

@analysis_web_bp.route('/analysis') # Renamed
@login_required
def analysis_page():
    """Serve the main analysis page (data loaded via API)."""
    # Ensure template exists
    template_path = os.path.join(current_app.template_folder, 'view_analysis.html')
    if not os.path.exists(template_path):
        current_app.logger.error("Template file not found: %s", template_path)
        return "Error: view_analysis.html template not found.", 404
    return render_template('view_analysis.html') # Original template name

@analysis_web_bp.route('/analytics') # Renamed
@login_required
def analytics_page_alias():
    """Alias redirecting to the main /analysis page."""
    return redirect(url_for('analysis_web.analysis_page')) # Renamed


# --- Analysis API Endpoints (Hosted under Web Blueprint) ---
# Note: If you create a separate AnalysisService, ensure it's initialized
# and attached to current_app in backend/app/__init__.py

@analysis_web_bp.route('/api/analysis/recording/<dictionary_id>/<recording_id>', methods=['GET']) # Renamed
@login_required
def api_analyze_recording(dictionary_id, recording_id):
    """API: Get analysis results for a specific recording (session auth)."""
    user_id = current_user.id
    # Get query parameters (e.g., include visualizations)
    include_viz = request.args.get('visualizations', 'true').lower() == 'true' # Match original call

    # Check if analysis service is available
    # Assuming AnalysisService exists and is attached to app
    if not hasattr(current_app, 'analysis_service') or not hasattr(current_app.analysis_service, 'analyze_recording'):
        current_app.logger.error("API Analyze Error: analysis_service.analyze_recording not available.")
        return jsonify({"success": False, "error": "Analysis service is currently unavailable"}), 503

    try:
        # Delegate analysis to the AnalysisService
        result = current_app.analysis_service.analyze_recording(
            user_id, dictionary_id, recording_id, include_visualizations=include_viz
        )
        # Assuming service returns dict: {"success": True, "analysis": {...}, "visualizations": {...}}
        if not result.get('success'): # Check if service indicated failure
            status_code = result.get('status_code', 500)
            return jsonify(result), status_code

        return jsonify(result) # Return successful analysis results

    except FileNotFoundError as rec_e: # Example specific exception
        current_app.logger.warning("API Analyze Error: Recording '%s' (dict: %s) not found: %s", recording_id, dictionary_id, rec_e) # Use % formatting
        return jsonify({"success": False, "error": "Recording not found or inaccessible."}), 404
    except PermissionError as perm_e: # Example specific exception
        current_app.logger.warning("API Analyze Error: Permission denied for user %s on recording '%s': %s", user_id, recording_id, perm_e) # Use % formatting
        return jsonify({"success": False, "error": "Permission denied to analyze this recording."}), 403
    except Exception as e:
        # Catch unexpected errors during analysis
        current_app.logger.exception("API Error analyzing recording %s for dict %s: %s", recording_id, dictionary_id, e) # Use % formatting and logger.exception
        return jsonify({"success": False, "error": "An unexpected error occurred during analysis."}), 500 # Generic error

# Add other analysis API endpoints as needed (e.g., model performance analysis)
