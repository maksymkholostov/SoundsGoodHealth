# backend/app/routes/recording_routes.py
"""
Routes for managing Recordings (upload, verification, streaming, etc.).
"""
from flask import (Blueprint, render_template, request, jsonify, current_app,
                   redirect, url_for, session, flash, send_file, Response)
from flask_login import login_required, current_user
from flask_jwt_extended import jwt_required, get_jwt_identity
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from backend.app.core.models.recording import RecordingType, Recording
# Assuming audio utils are in a relative path like ../ml/utils/
try:
    from ..ml.utils.audio_utils import load_audio_from_file, ensure_audio_format
except ImportError:
    # Fallback if structure is different - adjust as needed
    from backend.app.ml.utils.audio_utils import load_audio_from_file, ensure_audio_format
import urllib.parse


# Create blueprint
# Create blueprint
recording_web_bp = Blueprint('recording_web', __name__) # Renamed

# --- Recording/Verification Pages ---

@recording_web_bp.route('/recordings') # Renamed
@login_required
def recordings_page():
    """Serve the sound recording page."""
    user_id = current_user.id
    all_classes_data = [] # List of dicts {'id': ..., 'name': ...} for dropdown
    dictionaries_data = [] # List of dicts {'id': ..., 'name': ...} for dropdown
    selected_dictionary = None # Store full selected dictionary if ID provided
    selected_dict_id = request.args.get('dictionary_id')

    try:
        # --- Ensure Services Exist ---
        if not hasattr(current_app, 'dictionary_service'):
             raise RuntimeError("DictionaryService not available.")
        
        # --- Get Dictionaries for Dropdown ---
        user_dictionaries = current_app.dictionary_service.get_all_dictionaries()
        dictionaries_data = [
            {'id': dict_obj['id'], 'name': dict_obj['name']}
            for dict_obj in user_dictionaries
        ]
        dictionaries_data.sort(key=lambda x: x['name'].lower())

        # --- Get Selected Dictionary Details (if ID provided) ---
        if selected_dict_id:
             selected_dictionary = current_app.dictionary_service.get_dictionary_by_id(selected_dict_id)
             if not selected_dictionary or (selected_dictionary.creator_user_id != user_id):
                  flash("Selected dictionary not found or access denied.", "warning")
                  selected_dictionary = None
                  selected_dict_id = None
        
        # --- Get ALL Global Classes for Dropdown ---
        all_classes = current_app.dictionary_service.get_all_classes()
        all_classes_data = []
        if hasattr(current_app, 'recording_service'):
            for cls in all_classes:
                try:
                    counts = current_app.recording_service.get_class_sample_counts(cls.name)
                    sample_count = counts.get('total', 0) 
                except Exception as count_e:
                    current_app.logger.warning(f"Could not get sample counts for class '{cls.name}': {count_e}")
                    sample_count = 0
                all_classes_data.append({
                    'id': cls.id, 
                    'name': cls.name,
                    'sample_count': sample_count
                })
        else:
             current_app.logger.warning("Recording service unavailable for class counts on recordings page.")
             all_classes_data = [
                 {'id': cls.id, 'name': cls.name, 'sample_count': 0}
                 for cls in all_classes
             ]
        
        all_classes_data.sort(key=lambda x: x['name'].lower())

        # --- DEBUG LOGGING: Check the data being passed --- 
        current_app.logger.debug(f"[RecordingsPage] Data for sound_classes dropdown: {json.dumps(all_classes_data, indent=2)}")
        # --- END DEBUG LOGGING ---

        # --- Select Default Dictionary/Classes if None selected ---
        if not selected_dictionary and dictionaries_data:
            # Optionally select the first dictionary by default
            # selected_dict_id = dictionaries_data[0]['id']
            # selected_dictionary = current_app.dictionary_service.get_dictionary_by_id(selected_dict_id)
            pass # Or leave it unselected

        # Pass data to the template
        return render_template('sounds_record.html', 
                               sound_classes=all_classes_data, 
                               dictionaries=dictionaries_data,
                               selected_dictionary=selected_dictionary.to_dict() if selected_dictionary else None)

    except Exception as e:
        current_app.logger.error(f"Error loading recordings page: {str(e)}", exc_info=True)
        flash("An error occurred while loading the recording page.", "danger")
        return render_template('sounds_record.html', 
                               sound_classes=[], 
                               dictionaries=[], 
                               selected_dictionary=None, 
                               error=str(e))

@recording_web_bp.route('/verify') # Renamed
@recording_web_bp.route('/verify/<string:dictionary_identifier>') # Renamed
@login_required
def verify_sounds_page(dictionary_identifier=None):
    """Render the unified verification page (data loaded via API)."""
    # Get flags needed for frontend toggle logic
    is_admin = session.get('is_admin', False)
    allow_non_admin_global = current_app.config.get('ALLOW_ALL_USERS_VIEW_FOR_NON_ADMINS', False)
    can_toggle_view = is_admin or allow_non_admin_global
    
    # Pass identifier and flags to the template
    return render_template(
        'unified_verify.html', 
        dictionary_identifier=dictionary_identifier,
        is_admin=is_admin, # Pass admin status
        allow_global_view=allow_non_admin_global, # Pass global setting
        can_toggle_view=can_toggle_view # Pass pre-calculated toggle permission
    )

# Compatibility route for old sound_approval URLs
@recording_web_bp.route('/sound_approval') # Renamed
@recording_web_bp.route('/sound_approval/<string:dictionary_identifier>') # Renamed
@login_required
def sound_approval_page_compat(dictionary_identifier=None):
    """Compatibility route redirecting to verify_sounds_page."""
    current_app.logger.warning(f"Accessed deprecated /sound_approval route. Redirecting to /verify.")
    # Redirect to the new verify_sounds_page route within this blueprint
    return redirect(url_for('recording_web.verify_sounds_page', dictionary_identifier=dictionary_identifier)) # Renamed

@recording_web_bp.route('/record_test') # Renamed
@login_required
def record_test_page():
    """Serve the simplified recording test page."""
    # Ensure template exists
    template_path = os.path.join(current_app.template_folder, 'record_test.html')
    if not os.path.exists(template_path):
         return "Error: record_test.html template not found.", 404
    return render_template('record_test.html')

# --- ADDED: Upload Sounds Page Route ---
@recording_web_bp.route('/upload_sounds') 
@login_required
def upload_sounds_page():
    """Serve the sound upload page."""
    user_id = current_user.id
    all_classes_data = [] # List of dicts {'id': ..., 'name': ...} for dropdown

    try:
        # --- Ensure Services Exist ---
        if not hasattr(current_app, 'dictionary_service'):
             raise RuntimeError("DictionaryService not available.")
        
        # --- Get ALL Global Classes for Dropdown ---
        all_classes = current_app.dictionary_service.get_all_classes()
        all_classes_data = []
        if hasattr(current_app, 'recording_service'):
            for cls in all_classes:
                try:
                    counts = current_app.recording_service.get_class_sample_counts(cls.name)
                    sample_count = counts.get('total', 0) 
                except Exception as count_e:
                    current_app.logger.warning(f"Could not get sample counts for class '{cls.name}': {count_e}")
                    sample_count = 0
                all_classes_data.append({
                    'id': cls.id, 
                    'name': cls.name,
                    'sample_count': sample_count
                })
        else:
             current_app.logger.warning("Recording service unavailable for class counts on upload page.")
             all_classes_data = [
                 {'id': cls.id, 'name': cls.name, 'sample_count': 0}
                 for cls in all_classes
             ]
        
        all_classes_data.sort(key=lambda x: x['name'].lower())

        # Pass only necessary data to the template
        return render_template('upload_sounds.html', 
                               sound_classes=all_classes_data)

    except Exception as e:
        current_app.logger.error(f"Error loading upload sounds page: {str(e)}", exc_info=True)
        flash("An error occurred while loading the upload page.", "danger")
        return render_template('upload_sounds.html', 
                               sound_classes=[], 
                               error=str(e))
# --- END ADDED ---

# --- Recording/Verification API Endpoints ---

@recording_web_bp.route('/api/ml/record', methods=['POST']) # Renamed
@login_required # Session auth based on original
def api_record_audio_sample():
    """API: Process and save a recorded audio sample (session auth)."""
    user_id = current_user.id
    username = current_user.username 
    # user_email no longer needed here for path logic
    try:
        audio_file = request.files.get('audio')
        # Original form field name was 'sound', ensure frontend sends this or adjust here
        sound_class_id = request.form.get('sound_class_id', '').strip() # Expecting class ID now

        if not audio_file:
            return jsonify({"success": False, "error": "No audio file provided ('audio' field)"}), 400
        if not sound_class_id:
            # TODO: Fetch class name using class_id via DictionaryService if needed downstream
            return jsonify({"success": False, "error": "Sound class ID ('sound_class_id' field) is required"}), 400

        # --- Service Layer Interaction ---
        # 1. Save Raw Recording using RecordingService
        if not hasattr(current_app, 'recording_service'):
             raise RuntimeError("RecordingService not available.")
        
        # Assuming service method handles standardization and saving .wav + .json (RAW)
        # using FileManager and V10 paths.
        raw_sound_instance = current_app.recording_service.save_raw_recording(
            user_id=user_id,
            username=username, # Pass username for metadata
            class_id=sound_class_id, 
            audio_file_storage=audio_file,
            source="system" # Indicate it came from UI recording
        )
        
        if not raw_sound_instance: # Check if service indicated failure
             # Assume service logged the error
             return jsonify({"success": False, "error": "Failed to save the raw recording."}), 500
             
        current_app.logger.info(f"Raw recording saved: {raw_sound_instance.get('path', 'N/A')} by user {raw_sound_instance.get('username')}")

        # 2. Trigger Processing using ProcessingService
        if not hasattr(current_app, 'processing_service'):
             # Log the error and potentially return a specific server config error
             current_app.logger.error("ProcessingService not available during recording save.")
             return jsonify({"success": False, "error": "Server configuration error: Processing service unavailable."}), 500
             
        processing_service = getattr(current_app, 'processing_service', None)
        if not processing_service:
            raise RuntimeError("ProcessingService not available.")
        pending_segments = processing_service.process_sound(raw_sound_instance)

        if pending_segments is None: # Service might return None on internal error
            # Assume service logged the error
            current_app.logger.error(f"Audio processing failed critically after saving raw file {raw_sound_instance.get('id')}. Check ProcessingService logs.")
            # Optionally delete the raw file if processing fails critically? Needs discussion.
            # For now, just return error
            return jsonify({"success": False, "error": "Audio processing failed after saving."}), 500
            
        if not pending_segments: # Service returns empty list if no segments found/saved
            current_app.logger.warning(f"No valid segments found or saved for raw file: {raw_sound_instance.get('path')}")
            # Return success=True, but indicate no segments found
            return jsonify({
                "success": True,
                "message": "Recording saved, but no valid speech or sound segments were detected.",
                "raw_file_info": raw_sound_instance, # Return info about the saved raw file
                "segments": [],
                "segment_count": 0
            })

        # 3. Prepare Response with Pending Segment Details
        segment_details = []
        for segment_instance in pending_segments:
            segment_path = segment_instance.get('path')
            if not segment_path: continue
            
            try:
                # Generate stream URL using the instance path (should be V10 pending path)
                stream_url = url_for('recording_web.api_stream_audio_file', path=segment_path, _external=False)
            except Exception as url_e:
                 current_app.logger.warning(f"Could not generate stream URL for {segment_path}: {url_e}")
                 stream_url = f"/api/sounds/stream?path={segment_path}" # Fallback

            segment_details.append({
                "id": segment_instance.get('id'), # Use the ID from the metadata
                "filename": Path(segment_path).name,
                "path": segment_path,
                "url": stream_url,
                "duration": segment_instance.get('duration', 0),
                "status": segment_instance.get('status'),
                "type": segment_instance.get('type')
            })

        return jsonify({
            "success": True,
            "message": f"{len(pending_segments)} segment(s) extracted and saved for verification.",
            "raw_file_info": raw_sound_instance,
            "segments": segment_details,
            "segment_count": len(pending_segments)
        })

    except Exception as e:
        # Catch unexpected errors during request handling or service calls
        current_app.logger.error(f"API ML Record Error: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected server error occurred: {str(e)}"}), 500

@recording_web_bp.route('/api/sounds/verify', methods=['POST']) # Renamed
@login_required
def api_verify_recording():
    """API: Verify (approve) or discard/delete a sound instance using its ID."""
    user_id = current_user.id
    data = request.get_json() if request.is_json else request.form

    try:
        # Expecting sound_instance_id (usually the JSON filename stem)
        sound_instance_id = data.get('sound_instance_id', '').strip()
        # Ensure 'keep' is treated as boolean
        keep_input = data.get('keep', 'false')
        keep = str(keep_input).lower() in ['true', '1', 'yes', 'on']

        if not sound_instance_id:
            return jsonify({"success": False, "error": "'sound_instance_id' is required"}), 400

        current_app.logger.info(f"API Verify Request: User={user_id}, InstanceID={sound_instance_id}, Keep={keep}")

        # --- Ensure Service Exists ---
        if not hasattr(current_app, 'recording_service'):
            raise RuntimeError("RecordingService not available.")

        # --- Delegate to Service ---
        # Service handles finding, permission checks, file operations (move/delete), metadata updates
        success = current_app.recording_service.verify_sound_instance(
            sound_instance_id=sound_instance_id,
            keep=keep,
            requesting_user_id=user_id
        )

        if success:
            action = "Approved" if keep else "Discarded/Deleted"
            return jsonify({
                "success": True, 
                "message": f"Sound instance {action.lower()} successfully.", 
                "sound_instance_id": sound_instance_id,
                "keep": keep
            })
        else:
            # Service should have logged the specific error (not found, permission denied, file error)
            return jsonify({
                "success": False, 
                "error": f"Failed to verify/discard instance '{sound_instance_id}'. Check server logs for details."
            }), 500

    except Exception as e:
        # Catch-all for unexpected errors during request processing
        current_app.logger.error(f"API Error verifying recording: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected server error occurred: {str(e)}"}), 500

@recording_web_bp.route('/api/sounds/pending/<string:class_id>', methods=['GET'])
@login_required
def api_get_pending_recordings(class_id):
    """API: Get pending instances for a specific class OR all classes.
       Use class_id='__all__' to fetch for all classes.
       Allows toggling between own/all data based on user role and config."""
    # Redirect to the direct loader now
    return direct_pending_loader(class_id)

@recording_web_bp.route('/api/sounds/direct_pending/<string:class_id>', methods=['GET'])
@login_required
def direct_pending_loader(class_id):
    """A direct loader for pending files that bypasses the repository layer.
    This is a workaround to ensure pending files are found."""
    user_id = current_user.id
    
    # Check for special 'all' case
    target_class_id = None if class_id == '__all__' else class_id
    fetch_globally = (class_id == '__all__') # Flag if we are fetching all classes
    
    # Determine if user wants all user data (query param)
    fetch_all_users_requested = request.args.get('all_users', 'false').lower() == 'true'
    
    # Determine permission to view all users' data
    is_admin = session.get('is_admin', False)
    allow_non_admin_global = current_app.config.get('ALLOW_ALL_USERS_VIEW_FOR_NON_ADMINS', False)
    can_view_all_users_data = is_admin or allow_non_admin_global
    
    # Determine final scope for the query
    # If config allows all users to see all data, default to showing all
    # Otherwise, default to current user only
    if can_view_all_users_data:
        user_scope = '*'  # Show all users' recordings by default
    else:
        user_scope = user_id  # Show only current user's recordings
        
    # If user explicitly requested only their own data, override
    if fetch_all_users_requested and not can_view_all_users_data:
        # User requested all but doesn't have permission - show only theirs
        user_scope = user_id

    try:
        # Get direct access to file_manager
        file_manager = current_app.file_manager
        data_root = file_manager.get_data_root()
        
        # Determine directory patterns to search
        # Per COMPLETE_NAMING_SYSTEM.md, pending segments are named seg_<class>_<user>_<timestamp>_<index>.json
        if target_class_id is None:
            # All classes - use a wildcard
            if user_scope == '*':
                # All users, all classes
                search_pattern = f"{data_root}/sounds/*/*/pending/seg_*.json"
            else:
                # Specific user, all classes
                search_pattern = f"{data_root}/sounds/*/{user_scope}/pending/seg_*.json"
            current_app.logger.info(f"DIRECT LOADER: Searching for pending files with pattern: {search_pattern}")
        else:
            # Get specific class name
            dictionary_service = current_app.dictionary_service
            class_info = dictionary_service.get_class_by_id(target_class_id)
            if not class_info:
                current_app.logger.error(f"Class ID {target_class_id} not found")
                return jsonify({"success": False, "error": f"Class ID {target_class_id} not found"}), 404
                
            class_name = class_info.name
            
            if user_scope == '*':
                # All users, specific class
                search_pattern = f"{data_root}/sounds/{class_name}/*/pending/seg_*.json"
            else:
                # Specific user, specific class
                search_pattern = f"{data_root}/sounds/{class_name}/{user_scope}/pending/seg_*.json"
            current_app.logger.info(f"DIRECT LOADER: Searching for pending files for class {class_name} with pattern: {search_pattern}")

        # Directly find JSON files matching pattern
        import glob
        json_files = glob.glob(search_pattern)
        current_app.logger.info(f"DIRECT LOADER: Found {len(json_files)} JSON files")
        
        # Load each JSON file and build recording objects
        pending_instances = []
        for json_path in json_files:
            try:
                # Load the JSON data
                with open(json_path, 'r') as f:
                    recording_data = json.load(f)
                
                # Check that it's a pending type
                if recording_data.get('recording_type') != 'pending':
                    current_app.logger.debug(f"Skipping non-pending file: {json_path}, type={recording_data.get('recording_type')}")
                    continue
                
                # Ensure necessary fields exist
                if not all(key in recording_data for key in ['id', 'user_id', 'class_id', 'relative_wav_path']):
                    current_app.logger.warning(f"Missing required fields in JSON file: {json_path}")
                    continue
                
                # Check wav file exists
                wav_path = data_root / recording_data['relative_wav_path']
                if not wav_path.exists():
                    current_app.logger.warning(f"WAV file not found: {wav_path}")
                    continue
                
                # Add additional fields needed by the frontend
                recording_data['path'] = str(wav_path)
                if 'class_name' not in recording_data:
                    # Try to get from metadata
                    recording_data['class_name'] = recording_data.get('metadata', {}).get('class_name', 'Unknown')
                
                # Add URL for streaming
                try:
                    recording_data['url'] = url_for('recording_web.api_stream_audio_file_by_path', 
                                                 path=recording_data['relative_wav_path'], 
                                                 _external=False)
                except Exception as url_e:
                    current_app.logger.warning(f"Could not generate stream URL: {url_e}")
                    recording_data['url'] = None
                
                # Add to our results
                pending_instances.append(recording_data)
                current_app.logger.debug(f"Added pending file: {recording_data['id']}")
                
            except Exception as e:
                current_app.logger.error(f"Error processing JSON file {json_path}: {e}")
                continue
                
        # Sort results
        pending_instances.sort(key=lambda x: (x.get('class_name', 'zzzz'), x.get('timestamp', '')))

        # Determine class name for response (if specific class)
        class_name_for_response = "All"
        if target_class_id:
            try:
                class_obj = current_app.dictionary_service.get_class_by_id(target_class_id)
                if class_obj:
                    class_name_for_response = class_obj.name
            except Exception as e:
                current_app.logger.warning(f"Could not look up class name: {e}")
        
        # Return the results
        return jsonify({
            "success": True,
            "recordings": pending_instances, 
            "class_id": target_class_id if not fetch_globally else '__all__',
            "class_name": class_name_for_response,
            "count": len(pending_instances),
            "source": "direct_loader"  # Indicate this came from direct loader
        })

    except Exception as e:
        current_app.logger.error(f"Error in direct pending loader: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected error occurred: {str(e)}"}), 500

@recording_web_bp.route('/api/sounds/stream', methods=['GET']) # Renamed
@login_required
def api_stream_audio_file():
    """API: Stream an audio file by its instance ID, handling range requests and optional format conversion."""
    user_id = current_user.id
    # Change parameter from 'path' to 'id' (sound_instance_id)
    sound_instance_id = request.args.get('id')
    convert_format = request.args.get('format', '').lower() # mp3, ogg

    if not sound_instance_id:
        # return jsonify({"success": False, "error": "Query parameter 'path' is required"}), 400
        return jsonify({"success": False, "error": "Query parameter 'id' (sound_instance_id) is required"}), 400

    try:
        # --- Get Instance Metadata via Service --- 
        if not hasattr(current_app, 'recording_service'):
            raise RuntimeError("RecordingService not available.")
            
        # Use the correct service method name
        instance_info = current_app.recording_service.get_sound_instance_by_id(sound_instance_id) # Changed back from get_sound_instance_metadata_by_id
        
        if not instance_info:
             current_app.logger.error(f"STREAM NOT FOUND: Sound instance '{sound_instance_id}' not found.")
             return jsonify({"success": False, "error": "Requested sound instance not found"}), 404

        # --- Security Check (using metadata) ---
        is_admin = session.get('is_admin', False)
        instance_owner_id = instance_info.get('user_id')
        
        if not is_admin and str(instance_owner_id) != str(user_id):
             current_app.logger.error(f"STREAM FORBIDDEN: User {user_id} attempted to stream instance {sound_instance_id} owned by {instance_owner_id}")
             return jsonify({"success": False, "error": "Permission denied to access this sound instance"}), 403

        # --- Get Actual File Path and Check Existence ---
        file_path_str = instance_info.get('path')
        if not file_path_str:
             current_app.logger.error(f"STREAM ERROR: Metadata found for {sound_instance_id}, but file path is missing.")
             return jsonify({"success": False, "error": "File path information missing for this sound instance"}), 500
             
        file_path = Path(file_path_str).resolve()
        if not file_path.is_file():
            current_app.logger.error(f"STREAM NOT FOUND: Audio file not found at expected path {file_path} for instance {sound_instance_id}")
            return jsonify({"success": False, "error": "Requested audio file not found"}), 404

        # --- Format Conversion (Optional, using ffmpeg) ---
        # This logic remains largely the same, but operates on the validated 'file_path'
        source_path_for_stream = file_path 
        content_type = 'audio/wav' # Default
        # Determine original content type based on suffix
        suffix = source_path_for_stream.suffix.lower()
        if suffix == '.mp3': content_type = 'audio/mpeg'
        elif suffix == '.ogg': content_type = 'audio/ogg'
        elif suffix == '.flac': content_type = 'audio/flac'
        # Add more types if needed

        # Check if conversion is requested and necessary
        if convert_format in ['mp3', 'ogg'] and suffix != f".{convert_format}":
             try:
                  # Generate path for potentially cached converted file in temp dir
                  temp_dir = Path(tempfile.gettempdir()) / 'audio_conversions' # Subdir for organization
                  temp_dir.mkdir(exist_ok=True)
                  # Unique name based on original path hash and target format
                  output_filename = f"{source_path_for_stream.stem}_{hash(str(source_path_for_stream))}.{convert_format}"
                  output_path = temp_dir / output_filename

                  # Convert only if cached file doesn't exist
                  if not output_path.is_file():
                       current_app.logger.info(f"STREAM CONVERT: Converting '{source_path_for_stream}' to {convert_format} at '{output_path}'")
                       ffmpeg_cmd = ['ffmpeg', '-y', '-i', str(source_path_for_stream), '-vn'] # Input, overwrite, no video
                       # Add format specific options (adjust quality/bitrate as needed)
                       if convert_format == 'mp3':
                            ffmpeg_cmd.extend(['-codec:a', 'libmp3lame', '-qscale:a', '2']) # VBR quality 2
                            new_content_type = 'audio/mpeg'
                       else: # ogg
                            ffmpeg_cmd.extend(['-codec:a', 'libvorbis', '-qscale:a', '5']) # VBR quality 5
                            new_content_type = 'audio/ogg'
                       ffmpeg_cmd.append(str(output_path)) # Output file

                       # Execute ffmpeg command
                       result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=False)

                       if result.returncode != 0:
                            current_app.logger.error(f"STREAM FFMPEG Error (Return Code {result.returncode}): {result.stderr}")
                            # Don't raise error, just log and serve original below
                       else:
                            current_app.logger.info(f"STREAM CONVERT Success: Created '{output_path}'")
                            source_path_for_stream = output_path # Update path to converted file
                            content_type = new_content_type

                  else: # Use cached converted file
                       current_app.logger.debug(f"STREAM CONVERT: Using cached converted file '{output_path}'")
                       source_path_for_stream = output_path
                       content_type = 'audio/mpeg' if convert_format == 'mp3' else 'audio/ogg'

             except Exception as conv_e:
                  current_app.logger.error(f"STREAM Conversion failed: {conv_e}. Serving original file '{file_path}'.")
                  # Fallback: source_path_for_stream remains original file_path

        # --- Streaming Logic (Handle Range Requests) ---
        try:
             file_size = source_path_for_stream.stat().st_size
        except FileNotFoundError: # Handle case where even original file disappeared
             current_app.logger.error(f"STREAM FINAL CHECK FAILED: File not found at {source_path_for_stream}")
             return jsonify({"success": False, "error": "Audio file could not be accessed"}), 404

        range_header = request.headers.get('Range', None)

        if not range_header:
             # --- Send Full File ---
             response = send_file(str(source_path_for_stream), mimetype=content_type, conditional=True)
             response.headers['Accept-Ranges'] = 'bytes'
             response.headers['Content-Length'] = str(file_size)
             response.headers['Access-Control-Allow-Origin'] = '*' # CORS for JS audio players
             current_app.logger.debug(f"STREAM Full File: {source_path_for_stream} ({content_type}, {file_size} bytes)")
             return response
        else:
             # --- Handle Partial Content (Range Request) ---
             try:
                  # Parse range header (e.g., "bytes=0-499", "bytes=500-", "bytes=-100")
                  byte_unit, range_spec = range_header.split('=', 1)
                  if byte_unit.strip().lower() != 'bytes': raise ValueError("Invalid range unit")

                  start_str, end_str = range_spec.split('-', 1)
                  start = int(start_str.strip()) if start_str.strip() else 0
                  end = int(end_str.strip()) if end_str.strip() else file_size - 1

                  # Handle suffix range (e.g., "bytes=-100")
                  if not start_str.strip() and end_str.strip():
                       start = file_size - int(end_str.strip())
                       end = file_size - 1

                  # Clamp range to valid file bounds
                  start = max(0, start)
                  end = min(end, file_size - 1)

                  if start > end or start >= file_size:
                       raise ValueError("Invalid range start/end")

                  chunk_size = end - start + 1
                  current_app.logger.debug(f"STREAM Range Request: {source_path_for_stream} bytes {start}-{end}/{file_size}")

                  # Read the specified byte range
                  with open(source_path_for_stream, 'rb') as f:
                       f.seek(start)
                       data = f.read(chunk_size)

                  # Create 206 Partial Content response
                  response = Response(data, 206, mimetype=content_type, direct_passthrough=True)
                  response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
                  response.headers['Accept-Ranges'] = 'bytes'
                  response.headers['Content-Length'] = str(chunk_size)
                  response.headers['Access-Control-Allow-Origin'] = '*' # CORS
                  return response

             except ValueError as range_e:
                  current_app.logger.warning(f"STREAM Invalid Range Header: '{range_header}' - {range_e}")
                  # Return 416 Range Not Satisfiable if range is invalid
                  return Response("Requested Range Not Satisfiable", 416, {'Content-Range': f'bytes */{file_size}'})


    except FileNotFoundError:
         # Catch if initial path resolution fails
         current_app.logger.error(f"STREAM Initial File Not Found Error: {file_path_str}")
         return jsonify({"success": False, "error": "Audio file not found"}), 404
    except PermissionError:
         # Catch permission errors during file access
         current_app.logger.error(f"STREAM Permission Error accessing: {file_path_str}")
         return jsonify({"success": False, "error": "Permission denied to access audio file"}), 403
    except Exception as e:
        # Catch-all for unexpected errors
        current_app.logger.error(f"API Error streaming audio '{file_path_str}': {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected server error occurred: {str(e)}"}), 500

@recording_web_bp.route('/api/sounds/delete', methods=['POST']) # Renamed
@login_required
def api_delete_sound_file():
    """API: Delete a specified sound instance (audio and metadata) by its ID."""
    user_id = current_user.id
    # Change parameter from 'file_path' to 'sound_instance_id'
    sound_instance_id = request.form.get('sound_instance_id', '').strip()

    if not sound_instance_id:
        # return jsonify({"success": False, "error": "File path ('file_path' parameter) is required"}), 400
        return jsonify({"success": False, "error": "'sound_instance_id' parameter is required"}), 400

    try:
        # --- Ensure Service Exists ---
        if not hasattr(current_app, 'recording_service'):
            raise RuntimeError("RecordingService not available.")
            
        current_app.logger.info(f"API Delete Request: User={user_id}, InstanceID={sound_instance_id}")

        # --- Delegate to Service (using verify with keep=False) ---
        # Service handles finding, permission check, deletion of audio + metadata
        success = current_app.recording_service.verify_sound_instance(
            sound_instance_id=sound_instance_id,
            keep=False, # Setting keep=False triggers deletion logic in the service
            requesting_user_id=user_id
        )

        if success:
            current_app.logger.info(f"API Deleted sound instance: {sound_instance_id} (initiated by user {user_id})")
            return jsonify({"success": True, "message": f"Deleted instance '{sound_instance_id}' successfully"})
        else:
            # Service should log specific reason (not found, permission denied, file error)
            current_app.logger.error(f"API Failed to delete instance: {sound_instance_id}")
            return jsonify({"success": False, "error": f"Failed to delete instance '{sound_instance_id}'. See server logs."}), 500

    except Exception as e:
        current_app.logger.error(f"API Error deleting sound instance '{sound_instance_id}': {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected server error occurred: {str(e)}"}), 500

# --- NEW Streaming Endpoint by Relative Path --- 
@recording_web_bp.route('/api/sounds/stream_by_path', methods=['GET'])
@login_required
def api_stream_audio_file_by_path():
    """API: Stream an audio file given its relative path within the data directory.
       Includes validation to prevent directory traversal.
    """
    relative_path_encoded = request.args.get('path')
    if not relative_path_encoded:
        return jsonify({"success": False, "error": "Query parameter 'path' is required"}), 400

    try:
        # Decode and normalize the path
        relative_path_str = urllib.parse.unquote(relative_path_encoded)
        # Basic normalization (replace backslashes, remove redundant separators)
        relative_path_str = os.path.normpath(relative_path_str).replace("\\", "/") 

        # --- SECURITY VALIDATION --- 
        # 1. Ensure it starts with 'sounds/' (or expected base)
        if not relative_path_str.startswith("sounds/"):
             current_app.logger.error(f"STREAM FORBIDDEN: Invalid path requested (does not start with sounds/): {relative_path_str}")
             return jsonify({"success": False, "error": "Invalid file path requested"}), 400

        # 2. Ensure it doesn't contain '..' for traversal
        if '..' in relative_path_str.split('/'):
            current_app.logger.error(f"STREAM FORBIDDEN: Path traversal attempt detected: {relative_path_str}")
            return jsonify({"success": False, "error": "Invalid file path requested"}), 400
            
        # 3. Ensure it ends with expected audio extension (e.g., .wav)
        if not relative_path_str.lower().endswith('.wav'): # Adjust if other types allowed
            current_app.logger.error(f"STREAM FORBIDDEN: Non-audio file requested: {relative_path_str}")
            return jsonify({"success": False, "error": "Invalid file type requested"}), 400

        # --- Construct Absolute Path --- 
        file_manager = current_app.file_manager # Get FileManager instance
        absolute_path = (file_manager.get_data_root() / relative_path_str).resolve()

        # --- Check File Existence --- 
        if not absolute_path.is_file():
            current_app.logger.error(f"STREAM NOT FOUND: Audio file not found at expected absolute path {absolute_path} (derived from {relative_path_str})")
            # Double check it didn't somehow resolve outside data_root (though resolve() should help)
            if not str(absolute_path).startswith(str(file_manager.get_data_root().resolve())):
                 current_app.logger.critical(f"SECURITY ALERT: Path resolved outside data root! Original: '{relative_path_str}', Resolved: '{absolute_path}'")
                 return jsonify({"success": False, "error": "Server configuration error"}), 500
            return jsonify({"success": False, "error": "Requested audio file not found"}), 404

        # --- Get File Info & Stream (using existing logic from api_stream_audio_file) --- 
        try:
             file_size = absolute_path.stat().st_size
        except FileNotFoundError:
             current_app.logger.error(f"STREAM FINAL CHECK FAILED: File not found at {absolute_path}")
             return jsonify({"success": False, "error": "Audio file could not be accessed"}), 404

        range_header = request.headers.get('Range', None)
        content_type = 'audio/wav' # Assuming WAV for now

        if not range_header:
             response = send_file(str(absolute_path), mimetype=content_type, conditional=True)
             response.headers['Accept-Ranges'] = 'bytes'
             response.headers['Content-Length'] = str(file_size)
             response.headers['Access-Control-Allow-Origin'] = '*'
             current_app.logger.debug(f"STREAM Full File by Path: {absolute_path} ({content_type}, {file_size} bytes)")
             return response
        else:
             # Handle Partial Content (simplified - copy logic from original stream route if full range support needed)
             try:
                 byte_unit, range_spec = range_header.split('=', 1)
                 if byte_unit.strip().lower() != 'bytes': raise ValueError("Invalid range unit")
                 start_str, end_str = range_spec.split('-', 1)
                 start = int(start_str.strip()) if start_str.strip() else 0
                 end = int(end_str.strip()) if end_str.strip() else file_size - 1
                 if not start_str.strip() and end_str.strip():
                      start = file_size - int(end_str.strip())
                      end = file_size - 1
                 start = max(0, start)
                 end = min(end, file_size - 1)
                 if start > end or start >= file_size: raise ValueError("Invalid range start/end")
                 chunk_size = end - start + 1
                 
                 current_app.logger.debug(f"STREAM Range Request by Path: {absolute_path} bytes {start}-{end}/{file_size}")
                 with open(absolute_path, 'rb') as f:
                      f.seek(start)
                      data = f.read(chunk_size)
                 response = Response(data, 206, mimetype=content_type, direct_passthrough=True)
                 response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
                 response.headers['Accept-Ranges'] = 'bytes'
                 response.headers['Content-Length'] = str(chunk_size)
                 response.headers['Access-Control-Allow-Origin'] = '*'
                 return response
             except ValueError as range_e:
                  current_app.logger.warning(f"STREAM Invalid Range Header: '{range_header}' - {range_e}")
                  return Response("Requested Range Not Satisfiable", 416, {'Content-Range': f'bytes */{file_size}'})

    except Exception as e:
        current_app.logger.error(f"API Error streaming audio by path '{relative_path_encoded}': {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected server error occurred: {str(e)}"}), 500

@recording_web_bp.route('/api/sounds/noise_profile', methods=['POST'])
@login_required
def api_save_noise_profile():
    """API: Saves the uploaded noise profile audio for the current user."""
    user_id = current_user.id
    if not user_id:
        return jsonify({"success": False, "error": "User not logged in or ID missing"}), 401
        
    noise_file = request.files.get('noise_profile')
    if not noise_file:
        return jsonify({"success": False, "error": "No 'noise_profile' file provided in the request"}), 400

    try:
        file_manager = current_app.file_manager
        noise_profile_path = file_manager.get_user_noise_profile_path(user_id)
        
        # Read file content as bytes
        noise_data = noise_file.read()
        
        # Save the file using FileManager
        if file_manager.save_file(noise_data, noise_profile_path):
             current_app.logger.info(f"Saved noise profile for user {user_id} to {noise_profile_path}")
             return jsonify({"success": True, "message": "Noise profile saved."}) 
        else:
             current_app.logger.error(f"Failed to save noise profile file using FileManager for user {user_id}")
             return jsonify({"success": False, "error": "Server error saving noise profile."}), 500

    except Exception as e:
        current_app.logger.error(f"Error saving noise profile for user {user_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An unexpected error occurred."}), 500

@recording_web_bp.route('/api/recordings/<string:recording_id>', methods=['GET'])
@login_required
def api_get_recording_details(recording_id):
    """API: Get full metadata details for a specific recording instance."""
    user_id = current_user.id
    is_admin = session.get('is_admin', False)
    view_all = session.get('view_all_mode', False)
    
    try:
        recording_repo = current_app.recording_repository
        recording = recording_repo.find_by_id(recording_id)
        
        if not recording:
            current_app.logger.warning(f"API get details: Recording {recording_id} not found.")
            return jsonify({"success": False, "error": "Recording not found"}), 404
            
        # --- Authorization Check ---
        # Allow if user owns the recording OR if user is admin/viewing all
        if not is_admin and not view_all and str(recording.user_id) != str(user_id):
             current_app.logger.warning(f"API get details: User {user_id} forbidden from accessing recording {recording_id} owned by {recording.user_id}.")
             return jsonify({"success": False, "error": "Permission denied"}), 403
             
        # Return the full recording data as a dictionary
        return jsonify({"success": True, "recording": recording.to_dict()})
        
    except Exception as e:
        current_app.logger.error(f"API Error getting details for recording {recording_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An unexpected server error occurred"}), 500

# --- ADDED: API Endpoint to Discard/Delete a Sound Instance ---
@recording_web_bp.route('/api/sounds/<string:sound_id>', methods=['DELETE'])
@login_required
def discard_sound_instance_api(sound_id):
    """API endpoint to discard a sound instance (moves files to discarded folder)."""
    user_id = getattr(current_user, 'id', None)
    username = getattr(current_user, 'username', 'Unknown') # Get username for logging
    
    if not user_id:
        current_app.logger.error(f"Discard request failed: User not logged in for sound_id {sound_id}.")
        return jsonify({"success": False, "error": "Authentication required."}), 401

    current_app.logger.info(f"Received discard request for sound_id: {sound_id} from user: {username} ({user_id})")

    recording_service = current_app.recording_service
    if not recording_service:
        current_app.logger.error(f"Discard failed: RecordingService not available for sound_id {sound_id}.")
        return jsonify({"success": False, "error": "Internal server error: Service unavailable."}), 500

    try:
        # Call the existing verify_sound_instance method with keep=False to discard
        success = recording_service.verify_sound_instance(
            sound_instance_id=sound_id,
            keep=False, # keep=False triggers the move-to-discarded logic
            requesting_user_id=user_id
        )

        if success:
            current_app.logger.info(f"Successfully discarded sound instance {sound_id} by user {username}.")
            return jsonify({"success": True, "message": "Sound instance discarded successfully."}), 200
        else:
            # verify_sound_instance logs errors internally, return appropriate error
            recording = recording_service.get_recording_by_id(sound_id) # Check if it exists after failed discard
            error_msg = "Failed to discard sound instance. It might have already been deleted or an error occurred."
            status_code = 400 
            if not recording: # If it doesn't exist, it was likely already gone or never existed
                 error_msg = "Sound instance not found."
                 status_code = 404
            current_app.logger.warning(f"Discard operation failed for sound instance {sound_id} (initiated by user {username}). Status: {status_code}, Message: {error_msg}")
            return jsonify({"success": False, "error": error_msg}), status_code

    except Exception as e:
        current_app.logger.error(f"Exception during discard request for sound_id {sound_id} by user {username}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An unexpected server error occurred during discard."}), 500

# --- ADDED: API Endpoint for Uploading Audio ---
@recording_web_bp.route('/api/sounds/upload', methods=['POST']) 
@login_required
def api_upload_audio_sample():
    """API: Process and save an uploaded audio sample."""
    user_id = current_user.id
    username = current_user.username 
    
    try:
        audio_file = request.files.get('audio_file') # Use the name from the form
        sound_class_id = request.form.get('sound_class_id', '').strip()

        if not audio_file:
            return jsonify({"success": False, "error": "No audio file provided ('audio_file' field)"}), 400
        # Basic validation for filename (e.g., check extension)
        if not audio_file.filename or not audio_file.filename.lower().endswith('.wav'):
             return jsonify({"success": False, "error": "Invalid file type. Please upload a .wav file."}), 400
        if not sound_class_id:
            return jsonify({"success": False, "error": "Sound class ID ('sound_class_id' field) is required"}), 400

        # --- Service Layer Interaction ---
        if not hasattr(current_app, 'recording_service'):
             raise RuntimeError("RecordingService not available.")
        
        # Call save_raw_recording with source='upload'
        # Ensure recording_service is attached to current_app
        recording_service = getattr(current_app, 'recording_service', None)
        if not recording_service:
            raise RuntimeError("RecordingService not available.")
        raw_sound_instance = recording_service.save_raw_recording(
            user_id=user_id,
            username=username,
            class_id=sound_class_id, 
            audio_file_storage=audio_file, # Pass the FileStorage object
            source="upload" # Crucial: Indicate source is upload
        )
        
        if not raw_sound_instance:
             return jsonify({"success": False, "error": "Failed to save the uploaded raw recording."}), 500
             
        current_app.logger.info(f"Uploaded raw recording saved: {raw_sound_instance.get('path', 'N/A')} by user {username}")

        # --- Trigger Processing (Same as recording) ---
        if not hasattr(current_app, 'processing_service'):
             current_app.logger.error("ProcessingService not available during upload processing.")
             return jsonify({"success": False, "error": "Server configuration error: Processing service unavailable."}), 500
             
        processing_service = getattr(current_app, 'processing_service', None)
        if not processing_service:
            current_app.logger.error("ProcessingService not available during upload processing.")
            return jsonify({"success": False, "error": "Server configuration error: Processing service unavailable."}), 500
        pending_segments = processing_service.process_sound(raw_sound_instance)

        if pending_segments is None:
            current_app.logger.error(f"Audio processing failed critically after saving uploaded raw file {raw_sound_instance.get('id')}.")
            return jsonify({"success": False, "error": "Audio processing failed after saving."}), 500
            
        if not pending_segments: 
            return jsonify({
                "success": True,
                "message": "File uploaded and saved, but no valid sound segments were detected for verification.",
                "raw_file_info": raw_sound_instance,
                "segments": [],
                "segment_count": 0
            })

        # --- Prepare Response (Same as recording) ---
        segment_details = []
        for segment_instance in pending_segments:
            # Generate stream URL using relative path
            relative_path = segment_instance.get('relative_path')
            stream_url = None
            if relative_path:
                try:
                    stream_url = url_for('recording_web.api_stream_audio_file_by_path', 
                                      path=relative_path, 
                                      _external=False)
                except Exception as url_e:
                     current_app.logger.warning(f"Could not generate stream URL for uploaded segment {segment_instance.get('id')}: {url_e}")
                     stream_url = None # Or fallback?

            segment_details.append({
                "id": segment_instance.get('id'),
                "filename": Path(segment_instance.get('relative_path', '')).name, # Use relative path for filename
                "path": segment_instance.get('relative_path'), # Return relative path
                "url": stream_url, 
                "duration": segment_instance.get('duration', 0),
                "status": RecordingType.PENDING.value, # Explicitly pending
                "type": RecordingType.PENDING.value
            })

        # Generate the verify page URL
        verify_url = url_for('recording_web.verify_sounds_page', _external=False)

        return jsonify({
            "success": True,
            "message": f"{len(pending_segments)} segment(s) extracted from upload and saved for verification.",
            "raw_file_info": raw_sound_instance,
            "segments": segment_details,
            "segment_count": len(pending_segments),
            "verify_url": verify_url,
            "instructions": "Please go to the Verify page to review and approve your sound segments.",
            "next_steps": "Click the link below to verify your uploaded sounds:",
            "verify_link_text": "Go to Verify Page"
        })

    except Exception as e:
        current_app.logger.error(f"API Upload Error: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected server error occurred: {str(e)}"}), 500
# --- END ADDED ---

# --- Initialization Function ---

def init_recording_web_routes(recording_service, processing_service):
    """
    Initialize recording web routes with the services.
    
    Args:
        recording_service: Instance of RecordingService
        processing_service: Instance of ProcessingService
        
    Returns:
        Configured Blueprint
    """
    return recording_web_bp

