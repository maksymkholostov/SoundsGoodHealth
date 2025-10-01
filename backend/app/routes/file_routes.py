"""
Routes specifically for serving files (e.g., audio).
"""
from flask import Blueprint, current_app, send_from_directory, abort, session, request
from flask_login import login_required, current_user
from pathlib import Path
import os
import urllib.parse

file_bp = Blueprint('file_routes', __name__)

@file_bp.route('/sounds/<path:filepath>', methods=['GET'])
@login_required
def serve_sound_file(filepath):
    """Serve a sound file (.wav) after performing security and authorization checks."""
    current_app.logger.debug(f"Request to serve sound file: {filepath}")
    user_id = current_user.id
    is_admin = session.get('is_admin', False)
    # Respect the view_all_mode toggle from session for authorization
    view_all = session.get('view_all_mode', False)

    try:
        file_manager = current_app.file_manager
        # Resolve the base sounds directory securely
        sounds_base_dir = (file_manager.get_data_root() / 'sounds').resolve()

        # --- Security Check 1: Normalize and Prevent Traversal ---
        # Decode URL encoding and normalize path separators
        normalized_path_str = os.path.normpath(urllib.parse.unquote(filepath)).replace("\\", "/")

        # Disallow '..' in the path components to prevent directory traversal
        if '..' in normalized_path_str.split('/'):
            current_app.logger.error(f"Serve sound DENIED: Path traversal attempt: {filepath}")
            abort(404) # Not Found is safer than Forbidden for traversal attempts

        # Construct the full, absolute path relative to the sounds base
        absolute_path = (sounds_base_dir / normalized_path_str).resolve()

        # --- Security Check 2: Ensure path stays within the allowed base directory ---
        if not str(absolute_path).startswith(str(sounds_base_dir)):
            current_app.logger.error(f"Serve sound DENIED: Path resolved outside allowed base directory: {absolute_path} (from: {filepath})")
            abort(404)

        # --- Authorization Check ---
        # Extract owner user_id from path structure (e.g., ClassName/UserID/type/filename.wav)
        try:
            path_parts = Path(normalized_path_str).parts
            # Expected structure depth: sounds / ClassName / UserID / RecordingType / filename.wav (relative to data_root)
            # So relative to sounds_base_dir, it's ClassName / UserID / ... (index 1 is UserID)
            if len(path_parts) >= 2:
                owner_user_id = path_parts[1] # Second part relative to 'sounds/' should be UserID
                current_app.logger.debug(f"Extracted owner_user_id '{owner_user_id}' from path '{normalized_path_str}'")
                # Allow access if current user is owner OR if viewing all is allowed by session toggle OR if user is admin
                if not view_all and not is_admin and str(owner_user_id) != str(user_id):
                    current_app.logger.warning(f"Serve sound FORBIDDEN: User {user_id} cannot access file owned by {owner_user_id} (view_all={view_all}, is_admin={is_admin}) - Path: {filepath}")
                    abort(403) # Forbidden
            else:
                # Path structure doesn't match expected format
                current_app.logger.error(f"Serve sound DENIED: Unexpected path structure for authorization check: {normalized_path_str}")
                abort(404) # Treat as Not Found if path is weird

        except IndexError:
            # Error parsing path components
            current_app.logger.error(f"Serve sound DENIED: Could not parse path for authorization: {normalized_path_str}")
            abort(404)

        # --- Serve File ---
        # Use send_from_directory for safety. It requires directory and filename separately.
        directory = str(absolute_path.parent)
        filename = absolute_path.name

        current_app.logger.info(f"Serving sound file: Directory='{directory}', Filename='{filename}'")
        # Let send_from_directory handle range requests if browser sends them
        return send_from_directory(directory, filename, mimetype='audio/wav', conditional=True) # Specify mimetype

    except FileNotFoundError:
        current_app.logger.error(f"Serve sound NOT FOUND: File not found at derived absolute path for {filepath}")
        abort(404)
    except PermissionError:
        current_app.logger.error(f"Serve sound PERMISSION ERROR: Cannot access file derived from {filepath}")
        abort(403)
    except Exception as e:
        current_app.logger.error(f"Error serving sound file {filepath}: {e}", exc_info=True)
        abort(500)
