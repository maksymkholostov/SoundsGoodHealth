# backend/app/routes/class_routes.py
"""
Routes for managing Sound Classes (pages and API).
"""
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, session, flash
from flask_login import login_required, current_user
from backend.app.core.models.dictionary import Dictionary
from backend.app.core.models.recording import RecordingType
from backend.app.services.dictionary_service import DictionaryService
from backend.app.services.recording_service import RecordingService
# Removed unused imports: Path, json, os, datetime

# Create blueprint
class_bp = Blueprint('sound_class', __name__, url_prefix='/sound_classes') # Standardized prefix

# --- Class Pages ---

@class_bp.route('/')
@login_required
def sound_classes_page():
    """Serve the sound classes management page, showing all unique classes."""
    user_id = current_user.id
    all_classes_formatted = [] # List of dicts for template

    try:
        # --- Use DictionaryService to get all global classes ---
        if not hasattr(current_app, 'dictionary_service'):
             raise RuntimeError("DictionaryService not available.")
        if not hasattr(current_app, 'recording_service'):
             raise RuntimeError("RecordingService not available.")
             
        # 1. Get Class Definition Objects (using correct method)
        all_class_definitions = current_app.dictionary_service.get_all_classes() # Returns List[SoundClass]

        # --- Get Sample Counts using RecordingService ---
        for sound_class in all_class_definitions: # Now sound_class is an object
             # 2. Get counts for this class
             try:
                  # Access name via attribute
                  counts = current_app.recording_service.get_class_sample_counts(sound_class.name)

                  # Fetch Pending/Raw counts (Potentially Slow)
                  # Calls find_recordings for PENDING
                  pending_recs = current_app.recording_service.find_recordings(
                       class_id=sound_class.id, # Access id via attribute
                       recording_type=RecordingType.PENDING)
                  
                  # Correctly fetch both types of RAW recordings
                  raw_recorded_recs = current_app.recording_service.find_recordings(
                       class_id=sound_class.id, 
                       recording_type=RecordingType.RAW_RECORDED)
                  raw_uploaded_recs = current_app.recording_service.find_recordings(
                       class_id=sound_class.id, 
                       recording_type=RecordingType.RAW_UPLOADED)

                  pending_count = len(pending_recs)
                  # Sum the counts for the two raw types
                  raw_count = len(raw_recorded_recs) + len(raw_uploaded_recs)

             except Exception as count_e:
                  # Access name via attribute here too for logging
                  current_app.logger.error(f"Error getting counts for class {getattr(sound_class, 'name', 'UNKNOWN')}: {count_e}")
                  # Default counts on error
                  counts = {'gold': 0, 'augmented': 0, 'total': 0}
                  pending_count = 0
                  raw_count = 0

             # 3. Format data for template (accessing attributes)
             all_classes_formatted.append({
                  "id": sound_class.id,
                  "name": sound_class.name,
                  "description": sound_class.description,
                  "owner": getattr(sound_class, 'creator_user_id', 'N/A'), # Keep getattr for safety
                  "training_count": counts.get('total', 0), # Renamed from sample_count (Gold + Augmented)
                  "gold_count": counts.get('gold', 0),      # Added Gold count separately
                  "pending_count": pending_count,
                  "augmented_count": counts.get('augmented', 0),
                  "raw_count": raw_count
             })

        # Sort classes by name for display
        all_classes_formatted.sort(key=lambda x: x["name"].lower())

        current_app.logger.info(f"Prepared {len(all_classes_formatted)} unique sound classes for management page.")
        return render_template('sounds_management.html', sound_classes=all_classes_formatted)

    except Exception as e:
        # Log the actual error encountered in the try block
        current_app.logger.error(f"Error loading sound classes page: {str(e)}", exc_info=True) 
        flash("An error occurred while loading sound classes.", "error")
        # Render with empty data on error - Render the same template, don't redirect
        return render_template('sounds_management.html', sound_classes=[], error=str(e))


@class_bp.route('/view/<path:class_name>')
@login_required
def sound_class_view(class_name):
    """View a specific sound class and its recordings across all users."""
    user_id = current_user.id
    sound_class_info = None
    # Dictionary to hold lists of Recording objects
    all_recordings = {'pending': [], 'gold': [], 'raw': [], 'augmented': []}
    
    try:
        # --- Load Class Definition using DictionaryService ---
        if not hasattr(current_app, 'dictionary_service'):
             raise RuntimeError("DictionaryService not available.")
        if not hasattr(current_app, 'recording_service'):
             raise RuntimeError("RecordingService not available.")

        # Call the correct service method
        sound_class_info = current_app.dictionary_service.get_class_by_name(class_name)
        
        if not sound_class_info:
             flash(f"Sound class '{class_name}' definition not found.", "danger")
             return redirect(url_for('sound_class.sound_classes_page')) # Redirect within blueprint

        class_id = sound_class_info.id

        # --- Get All Recordings for this Class using RecordingService ---
        all_recordings['pending'] = current_app.recording_service.find_recordings(
            class_id=class_id, recording_type=RecordingType.PENDING
        )
        all_recordings['gold'] = current_app.recording_service.find_recordings(
            class_id=class_id, recording_type=RecordingType.GOLD
        )
        # Get both types of raw recordings
        raw_recorded_recs = current_app.recording_service.find_recordings(
            class_id=class_id, recording_type=RecordingType.RAW_RECORDED
        )
        raw_uploaded_recs = current_app.recording_service.find_recordings(
            class_id=class_id, recording_type=RecordingType.RAW_UPLOADED
        )
        all_recordings['raw'] = raw_recorded_recs + raw_uploaded_recs
        all_recordings['augmented'] = current_app.recording_service.find_recordings(
            class_id=class_id, recording_type=RecordingType.AUGMENTED
        )

        # Prepare data for template (convert Recording objects to dicts if needed by template)
        # NOTE: The template might need adjustments if it expects specific fields like 'url'
        # which were generated by the old _collect_recordings helper.
        pending_for_template = [rec.to_dict() for rec in all_recordings['pending']]
        gold_for_template = [rec.to_dict() for rec in all_recordings['gold']]
        raw_for_template = [rec.to_dict() for rec in all_recordings['raw']]
        augmented_for_template = [rec.to_dict() for rec in all_recordings['augmented']]
        
        # Add streaming URL if possible - This requires careful handling
        server_origin = request.host_url.rstrip('/')
        for rec_list in [pending_for_template, gold_for_template, raw_for_template, augmented_for_template]:
            for rec_dict in rec_list:
                 try:
                      # FIXED: Use the correct field name and endpoint
                      if rec_dict.get('relative_wav_path'):
                          # Use the by_path endpoint with relative path
                          stream_url = url_for('recording_web.api_stream_audio_file_by_path', path=rec_dict['relative_wav_path'], _external=False)
                          rec_dict['url'] = stream_url
                      else:
                          # Fallback to using the ID-based endpoint if available
                          stream_url = url_for('recording_web.api_stream_audio_file', id=rec_dict.get('id'), _external=False)
                          rec_dict['url'] = stream_url
                 except Exception as url_e:
                      # Log the specific error during URL generation
                      current_app.logger.error(f"Error generating stream URL for rec_id {rec_dict.get('id')} with relative_path {rec_dict.get('relative_wav_path')}: {url_e}", exc_info=True)
                      # Fallback or leave URL empty? Using relative path as fallback query param
                      if rec_dict.get('relative_wav_path'):
                           rec_dict['url'] = f"/api/sounds/stream?path={rec_dict['relative_wav_path']}" # Fallback
                      else:
                           rec_dict['url'] = None


        # Sort recordings within each type (e.g., by timestamp descending)
        # Assuming Recording objects/dicts have a 'timestamp' attribute/key
        for rec_list in [pending_for_template, gold_for_template, raw_for_template, augmented_for_template]:
             rec_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        current_app.logger.info(f"Found recordings for class '{class_name}': "
                                f"Pending={len(pending_for_template)}, "
                                f"Gold={len(gold_for_template)}, "
                                f"Augmented={len(augmented_for_template)}, "
                                f"Raw={len(raw_for_template)}")

        # Render the template, passing collected data
        return render_template('sound_class_view.html',
                               sound_class=sound_class_info.to_dict(), # Pass class definition as dict
                               class_name=class_name,
                               # Pass recordings lists
                               pending_recordings=pending_for_template,
                               approved_recordings=gold_for_template, # Template uses 'approved'
                               augmented_recordings=augmented_for_template,
                               raw_recordings=raw_for_template,
                               current_user_id=user_id) # For ownership checks in template

    except Exception as e:
        # Log the actual error encountered in the try block before redirecting
        current_app.logger.error(f"Error displaying sound class view for '{class_name}': {str(e)}", exc_info=True)
        # Flash a user-friendly message, potentially referencing the error type if helpful
        flash(f"Error loading class details or recordings: {type(e).__name__}. Check logs for details.", "danger")
        # Ensure redirect uses the correct endpoint name for the classes list page
        return redirect(url_for('sound_class.sound_classes_page'))


# --- Class API Endpoints ---

@class_bp.route('/api', methods=['GET'])
@login_required
def api_list_sound_classes():
    """API: List all unique sound classes available in the system."""
    # user_id = current_user.id # Not needed if listing global classes
    try:
        # --- Use DictionaryService ---
        if not hasattr(current_app, 'dictionary_service'):
             raise RuntimeError("DictionaryService not available.")
             
        all_classes = current_app.dictionary_service.get_all_classes() # List of SoundClass objects
        classes_list = [cls.to_dict() for cls in all_classes] # Convert to dicts for JSON

        # Optionally add sample counts if needed by API consumer
        # This might be slow if done here for every class. Consider a separate stats endpoint.
        # if hasattr(current_app, 'recording_service'):
        #     for cls_data in classes_list:
        #         try:
        #             counts = current_app.recording_service.get_class_sample_counts(cls_data['name'])
        #             cls_data['sample_count'] = counts.get('total', 0) # Example: total count
        #         except Exception: 
        #             cls_data['sample_count'] = 0 # Default on error

        classes_list.sort(key=lambda x: x['name'].lower())

        current_app.logger.debug(f"API returning {len(classes_list)} unique classes.")
        return jsonify({"success": True, "classes": classes_list})

    except Exception as e:
        current_app.logger.error(f"API Error listing sound classes: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e), "classes": []}), 500


@class_bp.route('/api', methods=['POST'])
@login_required
def api_create_sound_class():
    """API: Create a new sound class globally (associated with the current user)."""
    user_id = current_user.id
    data = request.get_json() if request.is_json else request.form

    try:
        class_name = data.get('class_name', '').strip()
        description = data.get('description', '')

        if not class_name:
            return jsonify({"success": False, "error": "Class name is required"}), 400

        current_app.logger.info(f"API request to create sound class '{class_name}' by user {user_id}")

        # --- Use Service Method ---
        if not hasattr(current_app, 'dictionary_service'):
             raise RuntimeError("Dictionary service not found.")
        
        # First check if the class already exists
        existing_class = current_app.dictionary_service.get_class_by_name(class_name)
        if existing_class:
            current_app.logger.warning(f"API attempted to create class '{class_name}' that already exists")
            return jsonify({"success": False, "error": f"Class '{class_name}' already exists."}), 409
        
        # Create the new class using the private method
        sound_class_obj = current_app.dictionary_service._create_global_class(
            user_id=user_id, 
            class_name=class_name, 
            description=description
        )
        error_msg = None if sound_class_obj else "Failed to create class." 

        if not sound_class_obj:
            # Service should return specific error message if possible (e.g., already exists)
            status_code = 409 if "already exists" in (error_msg or "").lower() else 500
            current_app.logger.error(f"API failed to create sound class '{class_name}': {error_msg or 'Internal service error.'}")
            return jsonify({"success": False, "error": error_msg or "Failed to create class."}), status_code

        current_app.logger.info(f"API Successfully created sound class: {sound_class_obj.to_dict()}")
        return jsonify({
            "success": True,
            "message": f"Created sound class '{class_name}'",
            "class": sound_class_obj.to_dict() # Return created object details
        }), 201 # HTTP 201 Created

    except Exception as e:
        # Catch specific service exceptions if possible (e.g., DuplicateNameError)
        current_app.logger.error(f"API Error creating sound class '{class_name}': {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"Failed to create class: {str(e)}"}), 500


@class_bp.route('/api/<path:class_name>', methods=['DELETE'])
@login_required
def api_delete_sound_class(class_name):
    """API: Delete a sound class globally."""
    user_id = current_user.id # For permission checks if needed by service

    try:
        current_app.logger.warning(f"API request to delete global class '{class_name}' by user {user_id}")

        # --- Use Service Method ---
        if not hasattr(current_app, 'dictionary_service'):
             raise RuntimeError("Dictionary service not found.")
        
        # Assuming dictionary_service has a method like delete_global_class
        if not hasattr(current_app.dictionary_service, 'delete_global_class'):
             # Fallback or check for _delete_global_class if needed temporarily
             if hasattr(current_app.dictionary_service, '_delete_global_class'):
                 delete_method = current_app.dictionary_service._delete_global_class
             else:
                  raise RuntimeError("Method delete_global_class not found in DictionaryService.")
        else:
             delete_method = current_app.dictionary_service.delete_global_class

        # Service should handle checking permissions (e.g., only owner or admin) internally if required
        # Pass user_id for context
        success, message = delete_method(class_name=class_name, requesting_user_id=user_id)

        if not success:
             # Service should provide appropriate message and status code (404 Not Found, 403 Forbidden)
             status_code = 404 if "not found" in message.lower() else 403 if "permission" in message.lower() else 500
             current_app.logger.error(f"API failed to delete class '{class_name}': {message}")
             return jsonify({"success": False, "error": message}), status_code

        current_app.logger.info(f"API Deleted global class '{class_name}' (initiated by user {user_id})")
        return jsonify({"success": True, "message": message or f"Class '{class_name}' deleted successfully."}) # Return message from service

    except Exception as e:
        current_app.logger.error(f"API Error deleting sound class '{class_name}': {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@class_bp.route('/api/<path:class_name>/samples/count', methods=['GET'])
@login_required
def api_get_sample_count_for_class(class_name):
    """API: Get the count of gold/augmented/etc samples for a class across all users."""
    try:
        # --- Use RecordingService ---
        if not hasattr(current_app, 'recording_service'):
             raise RuntimeError("RecordingService not available.")
             
        # Use the service method that gets counts from the repository
        counts = current_app.recording_service.get_class_sample_counts(class_name)
        # counts is {'gold': G, 'augmented': A, 'total': T}
        
        # Get pending/raw counts separately if needed (potentially slow)
        sound_class = current_app.dictionary_service.get_class_by_name(class_name)
        pending_count = 0
        raw_count = 0
        if sound_class:
            pending_recs = current_app.recording_service.find_recordings(
                class_id=sound_class.id, 
                recording_type=RecordingType.PENDING)
            # Get both types of raw recordings
            raw_recorded_recs = current_app.recording_service.find_recordings(
                class_id=sound_class.id, 
                recording_type=RecordingType.RAW_RECORDED)
            raw_uploaded_recs = current_app.recording_service.find_recordings(
                class_id=sound_class.id, 
                recording_type=RecordingType.RAW_UPLOADED)
            raw_recs = raw_recorded_recs + raw_uploaded_recs 
            pending_count = len(pending_recs)
            raw_count = len(raw_recs)
        else:
             current_app.logger.warning(f"Cannot get pending/raw counts for unknown class: {class_name}")


        return jsonify({
            "success": True,
            # Return detailed breakdown
            "details": {
                'gold': counts.get('gold', 0),
                'augmented': counts.get('augmented', 0),
                'pending': pending_count,
                'raw': raw_count,
                'total_training': counts.get('total', 0) # Gold + Augmented
            },
            "class_name": class_name
        })

    except Exception as e:
        current_app.logger.error(f"API Error counting samples for class '{class_name}': {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


def init_class_web_routes(dictionary_service):
    """
    Initialize class web routes with the dictionary service.
    
    Args:
        dictionary_service: Instance of DictionaryService
        
    Returns:
        Configured Blueprint
    """
    return class_bp

