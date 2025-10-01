# backend/app/routes/training_routes.py
"""
Routes related to model training and feature extraction.
"""
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, session, flash
from flask_login import login_required, current_user
# from flask_jwt_extended import jwt_required, get_jwt_identity # Comment out if not used/installed
import os
from pathlib import Path
from ..core.models.recording import RecordingType

# Create blueprint
training_web_bp = Blueprint('training_web', __name__) # Renamed
# --- Training/Feature Pages ---

@training_web_bp.route('/training')
@login_required
def training_page():
    """Serve the training page and load available dictionaries."""
    try:
        user_id = current_user.id
        dictionary_service = getattr(current_app, 'dictionary_service', None)
        feature_service = getattr(current_app, 'feature_service', None)
        recording_repo = getattr(current_app, 'recording_repository', None)
        training_service = getattr(current_app, 'training_service', None) # Get training service

        if not dictionary_service or not feature_service or not recording_repo or not training_service:
             current_app.logger.error("Required services (dictionary, feature, recording_repo, training) not available in app context.")
             flash("Server configuration error: Services not available.", "danger")
             return render_template('training.html', dictionaries=[], available_models=[], error="Server configuration error.")


        # --- Fetch Dictionaries for Dropdown (CORRECTED LOGIC) ---
        current_app.logger.info(f"[TrainingPage] Fetching all dictionaries...")
        # ***** FIX: Call service WITHOUT user_id *****
        all_dictionaries = dictionary_service.get_all_dictionaries()
        current_app.logger.info(f"[TrainingPage] Found {len(all_dictionaries)} total dictionaries.")
        # Use all dictionaries without filtering by user
        user_dictionaries_data = all_dictionaries
        current_app.logger.info(f"[TrainingPage] Making all {len(user_dictionaries_data)} dictionaries available for training.")
        # --- END CORRECTION ---

        # Prepare data for the template (including counts)
        dictionaries_for_template = []
        for d_data in user_dictionaries_data:
            # Handle both dict and Dictionary object
            if hasattr(d_data, 'to_dict'):
                d_dict = d_data.to_dict()
            else:
                d_dict = d_data
                
            dict_id = d_dict.get('id')
            if not dict_id: continue

            class_ids = d_dict.get('class_ids', [])
            class_count = len(class_ids)
            sample_count = 0
            if class_ids:
                try:
                    # Count samples across all users for this dictionary
                    recordings = recording_repo.find(
                        class_id__in=class_ids,
                        recording_type__in=[RecordingType.GOLD, RecordingType.AUGMENTED]
                    )
                    sample_count = len(recordings)
                except Exception as rc_err:
                    current_app.logger.error(f"Error counting samples for dict {dict_id}: {rc_err}")

            dictionaries_for_template.append({
                'id': dict_id,
                'name': d_dict.get('name', 'Unknown'),
                'classes': [{'id': cid} for cid in class_ids],
                'sample_count': sample_count
            })

        # Corrected indentation
        dictionaries_for_template.sort(key=lambda x: x['name'])
        
        # Debug logging
        current_app.logger.info(f"[TrainingPage] Final dictionaries_for_template: {dictionaries_for_template}")

        # --- Handle Selected Dictionary and Feature Status ---
        selected_dict_name = request.args.get('dictionary', None)
        selected_dict_id = None
        feature_status = None
        extract_done = request.args.get('check_features') == 'true'

        if selected_dict_name:
            for d in dictionaries_for_template:
                if d['name'] == selected_dict_name:
                    selected_dict_id = d['id']
                    break

            if selected_dict_id:
                try:
                    feature_status = feature_service.get_dictionary_feature_status(
                        user_id=user_id,
                        dictionary_id=selected_dict_id
                    )
                except Exception as fs_err:
                    current_app.logger.error(f"Error getting feature status for dict_id {selected_dict_id}: {fs_err}")
                    feature_status = {"error": str(fs_err)}
            else:
                 # Corrected indentation
                 current_app.logger.warning(f"Dictionary name '{selected_dict_name}' provided in URL not found for user {user_id}.")

        # --- Get Available Model Types ---
        available_models = []
        if hasattr(training_service, 'get_available_models'):
             available_models = training_service.get_available_models()
        else:
            current_app.logger.warning("Training service or get_available_models not found. Model list will be empty.")

        return render_template(
            'training.html',
            dictionaries=dictionaries_for_template,
            selected_dict=selected_dict_name,
            feature_status=feature_status,
            extract_done=extract_done,
            available_models=available_models # Pass models to template
        )
    except Exception as e:
        current_app.logger.error(f"Error loading training page: {e}", exc_info=True)
        flash("Error loading training page data. Please try again.", "danger")
        return render_template('training.html', dictionaries=[], available_models=[], error=str(e))

@training_web_bp.route('/features') # Renamed
@login_required
def feature_extraction_page():
    """Serve the feature extraction page, loading initial stats and sound lists."""
    try:
        user_id = current_user.id
        view_all = session.get('view_all_mode', False)
        user_id_filter = None if view_all else user_id

        # Access services/repositories via current_app using correct names
        recording_repo = current_app.recording_repository
        feature_service = current_app.feature_service 
        file_manager = current_app.file_manager 
        feature_repo = current_app.feature_repository

        # Fetch relevant recordings (GOLD and AUGMENTED)
        recordings = recording_repo.find(
            user_id=user_id_filter, 
            recording_type__in=[RecordingType.GOLD, RecordingType.AUGMENTED]
        )
        
        sounds_missing_features_list = []
        sounds_with_features_list = []
        total_sounds = 0
        sounds_with_features_count = 0
        default_feature_set_id = "v0.1" # Assuming default set

        for recording in recordings:
            total_sounds += 1
            has_features = False
            extracted_sets = []
            feature_npz_path = None

            try:
                # Determine class name for path construction
                class_name = recording_repo._get_class_name(recording.class_id)
                if not class_name:
                    current_app.logger.warning(f"Cannot determine class name for recording {recording.id}, assuming features missing.")
                    sounds_missing_features_list.append(recording.to_dict())
                    continue

                # Determine subset for path construction
                subset = 'gold' if recording.recording_type == RecordingType.GOLD else \
                         'augmented' if recording.recording_type == RecordingType.AUGMENTED else \
                         'unknown'
                if subset == 'unknown': 
                    current_app.logger.warning(f"Unknown recording type {recording.recording_type} for {recording.id}, assuming features missing.")
                    sounds_missing_features_list.append(recording.to_dict())
                    continue 

                # Construct the expected feature file path
                recording_id_base = recording.id.split('_seg')[0]
                npz_filename = f"{recording_id_base}_features.npz"
                feature_npz_path = file_manager.get_feature_data_path(
                    feature_version=default_feature_set_id, 
                    user_id=recording.user_id,
                    subset=subset,
                    class_name=class_name,
                    filename=npz_filename
                )

                # --- Start Debug Logging ---
                current_app.logger.debug(
                    f"Checking features for recording {recording.id}: "
                    f"Class='{class_name}', User='{recording.user_id}', Subset='{subset}', "
                    f"File='{npz_filename}'. Path checked: {feature_npz_path}"
                )
                # --- End Debug Logging ---

                # Primary Check: Does the NPZ file exist?
                if feature_npz_path.exists():
                    has_features = True
                    # If NPZ exists, *then* try to get metadata for feature set IDs
                    try:
                        # Get all extraction metadata records for this recording
                        extractions = feature_repo.get_extractions_for_recording(recording.user_id, recording.id)
                        # Now fetch the full details for each unique feature set ID found
                        feature_set_details = []
                        processed_set_ids = set()
                        if extractions:
                            for extraction in extractions:
                                set_id = getattr(extraction, 'feature_set_id', None)
                                if set_id and set_id not in processed_set_ids:
                                    feature_set = feature_repo.get_feature_set(set_id)
                                    if feature_set:
                                        feature_set_details.append({
                                            'id': feature_set.id,
                                            'name': feature_set.name,
                                            'description': feature_set.description,
                                            'features': feature_set.features
                                        })
                                        processed_set_ids.add(set_id)
                                    else:
                                        # Handle case where set metadata is missing for a found extraction
                                        feature_set_details.append({'id': set_id, 'name': f'Set {set_id} (Details Missing)', 'description':'N/A', 'features':[]})
                                        processed_set_ids.add(set_id)
                        extracted_sets = feature_set_details # Store the detailed list

                    except Exception as repo_err:
                        current_app.logger.error(f"Error querying feature extractions for {recording.id} (NPZ exists): {repo_err}", exc_info=True)
                        # Proceed without feature set info if repo query fails

            except AttributeError as attr_err:
                current_app.logger.error(f"FileManager missing 'get_feature_data_path'? Error: {attr_err}. Assuming features missing.")
                has_features = False # Can't check path
            except Exception as path_err:
                current_app.logger.error(f"Error constructing feature path for {recording.id}: {path_err}. Assuming features missing.")
                has_features = False # Can't check path
                
            # Convert recording to dict for template consistency
            recording_dict = recording.to_dict() if hasattr(recording, 'to_dict') else recording
            if not isinstance(recording_dict, dict):
                current_app.logger.warning(f"Could not convert recording {recording.id} to dict.")
                recording_dict = {"id": recording.id, "metadata": {}} # Fixed indentation
            
            # Add to appropriate list
            if has_features:
                recording_dict['extracted_feature_sets'] = extracted_sets # Add potentially empty list
                sounds_with_features_list.append(recording_dict)
                sounds_with_features_count += 1
            else:
                sounds_missing_features_list.append(recording_dict)

        sounds_missing_features_count = total_sounds - sounds_with_features_count
        
        # Get feature set count
        try:
            all_feature_sets = feature_repo.get_all_feature_sets()
            feature_sets_count = len(all_feature_sets) if all_feature_sets else 0
        except Exception as e:
            current_app.logger.error(f"Error getting feature sets count: {e}")
            feature_sets_count = 0 # Default to 0 on error

        # Pass calculated stats AND the lists to the template
        current_app.logger.debug(f"sounds_with_features_list: {sounds_with_features_list}")
        return render_template(
            'feature_extraction.html',
            total_sounds=total_sounds,
            sounds_with_features=sounds_with_features_count,
            sounds_missing_features=sounds_missing_features_count,
            feature_sets=feature_sets_count,
            sounds_missing_features_list=sounds_missing_features_list, # Pass list
            sounds_with_features_list=sounds_with_features_list, # Pass list
            RecordingType=RecordingType # Pass the Enum class itself
        )
        
    except Exception as e:
        current_app.logger.error(f"Error loading feature extraction page: {e}", exc_info=True)
        # Handle error gracefully, maybe redirect or show error page
        return "Error loading page, check logs.", 500


# --- Training/Feature API Endpoints ---

# Note: Original code had JWT and Session versions for some endpoints.
# Consolidating here - choose one auth method (e.g., session via @login_required)
# or keep both if frontend uses both JWT and session cookies.
# Using @login_required (session) for consistency with page routes unless specified otherwise.

@training_web_bp.route('/api/ml/train/model', methods=['POST']) # Renamed
@login_required
def api_train_model():
    """API: Start training a model for a dictionary (session auth)."""
    user_id = current_user.id
    data = request.get_json() if request.is_json else request.form

    # Extract required and optional parameters from the request data
    dictionary_id = data.get('dictionary_id')
    model_type = data.get('model_type', 'cnn').lower() # Default to 'cnn', normalize case
    model_name = data.get('model_name', f"{model_type.upper()} - {dictionary_id}") # Provide a default name
    feature_version = data.get('feature_version', 'v0.1') # Default feature version
    use_augmented = data.get('use_augmented', True) # Default to using augmented data
    force_preparation = data.get('force_preparation', False) # Default to not forcing prep
    params = data.get('params', None) # Optional model parameters
    # If params not provided as an object, build from top-level fields (epochs, batch_size, etc.)
    if not isinstance(params, dict):
        candidate_keys = [
            'epochs', 'batch_size', 'learning_rate', 'use_class_weights',
            'n_mfcc', 'dropout_rate', 'l2_reg'
        ]
        params = {}
        for k in candidate_keys:
            if k in data and data[k] is not None and data[k] != "":
                params[k] = data[k]

    if not dictionary_id:
        return jsonify({"success": False, "error": "Dictionary ID ('dictionary_id') is required"}), 400

    # Validate boolean flags (handle potential string inputs like 'true'/'false')
    if isinstance(use_augmented, str):
        use_augmented = use_augmented.lower() == 'true'
    if isinstance(force_preparation, str):
        force_preparation = force_preparation.lower() == 'true'

    # Check if training service is available
    if not hasattr(current_app, 'training_service') or not hasattr(current_app.training_service, 'train_model'):
        current_app.logger.error("API Train Error: training_service.train_model not available.")
        return jsonify({"success": False, "error": "Training service is currently unavailable"}), 503 # Service Unavailable

    try:
        # Call the training service with all parameters
        result = current_app.training_service.train_model(
            user_id=user_id,
            dictionary_id=dictionary_id,
            model_type=model_type,
            model_name=model_name,
            feature_version=feature_version,
            use_augmented=use_augmented,
            params=params
        )

        # Determine status code based on result (assuming service returns dict with 'status')
        if result.get('status') == 'error':
            if result.get('is_training'):
                status_code = 409 # Conflict - already training
            else:
                status_code = 400 # Bad Request (e.g., validation error in service)
        elif result.get('status') == 'success' or 'id' in result:
            status_code = 202 # Accepted (assuming async job started)
        else:
            status_code = 500 # Internal Server Error if result format is unexpected

        return jsonify(result), status_code

    except ValueError as ve:
         current_app.logger.error(f"API Validation Error starting training for dict {dictionary_id}: {ve}")
         return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        current_app.logger.error(f"API Error starting training for dict {dictionary_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Failed to start training: {str(e)}"}), 500

@training_web_bp.route('/api/ml/train/status', methods=['GET']) # Renamed
@login_required
def api_get_training_status():
    """API: Get the status of active training jobs for the user (session auth)."""
    user_id = current_user.id

    if not hasattr(current_app, 'training_service') or not hasattr(current_app.training_service, 'get_user_training_status'):
        current_app.logger.error("API Train Status Error: training_service.get_user_training_status not available.")
        return jsonify({"success": False, "error": "Training status service not available"}), 503

    try:
        # Service should return the status of ongoing/recent jobs for this user
        status_data = current_app.training_service.get_user_training_status(user_id)
        # Assuming service returns dict: {"success": True, "jobs": [...]} or similar
        return jsonify(status_data)
    except Exception as e:
        current_app.logger.error(f"API Error getting training status for user {user_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Failed to get training status: {str(e)}"}), 500

@training_web_bp.route('/api/ml/train/results/<model_id>', methods=['GET']) # Renamed
@login_required
def api_get_training_results(model_id):
    """API: Get the final results/metadata for a specific completed model (session auth)."""
    user_id = current_user.id

    if not hasattr(current_app, 'training_service') or not hasattr(current_app.training_service, 'get_model_results'):
        current_app.logger.error("API Train Results Error: training_service.get_model_results not available.")
        return jsonify({"error": "Training results service not available"}), 503

    try:
        # Service method searches across user's dictionaries for the model ID
        model_data = current_app.training_service.get_model_results(user_id, model_id)
        
        if model_data:
            # Return the full ModelVersion dictionary
            return jsonify(model_data)
        else:
            # Model not found or not accessible/completed
            current_app.logger.warning(f"Model results requested but not found/ready for model {model_id}, user {user_id}.")
            return jsonify({"error": "Model results not found or not ready"}), 404

    except Exception as e:
        current_app.logger.error(f"API Error getting training results for model {model_id}, user {user_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to get training results: {str(e)}"}), 500

@training_web_bp.route('/api/ml/train/stats/<model_id>', methods=['GET']) # Renamed
@login_required
def api_get_training_stats_log(model_id):
    """API: Get the content of the training status log file for a given model ID."""
    user_id = current_user.id # Keep user ID for potential future permission checks
    
    # Define the expected log directory (should match CNN_Trainer)
    log_dir = Path(current_app.config.get("DATA_ROOT", "backend/data")) / "logs" / "training"
    status_log_path = log_dir / f"{model_id}.log"
    
    current_app.logger.debug(f"Attempting to read training log: {status_log_path}")

    if not status_log_path.is_file():
         current_app.logger.warning(f"Training status log file not found for model {model_id} at {status_log_path}")
         return jsonify({"success": True, "log_lines": [], "message": "Log file not found (training might not have started writing yet)."})
         
    try:
        log_lines = []
        with open(status_log_path, 'r') as f:
            header = f.readline().strip().split(',')
            for line in f:
                try:
                    values = line.strip().split(',')
                    if len(values) == len(header):
                        epoch_data = {header[i]: values[i] for i in range(len(header))}
                        for key in ['loss', 'accuracy', 'val_loss', 'val_accuracy']:
                            if key in epoch_data:
                                epoch_data[key] = float(epoch_data[key])
                        if 'improved' in epoch_data:
                            epoch_data['improved'] = epoch_data['improved'].lower() == 'true'
                        if 'epoch' in epoch_data:
                            epoch_data['epoch'] = int(epoch_data['epoch'])
                        log_lines.append(epoch_data)
                except Exception as parse_err:
                     current_app.logger.warning(f"Skipping malformed line in {status_log_path}: {line.strip()} - Error: {parse_err}")
                    
        return jsonify({"success": True, "log_lines": log_lines})

    except Exception as e:
        current_app.logger.error(f"API Error reading training status log {status_log_path}: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Failed to read training status log: {str(e)}"}), 500

@training_web_bp.route('/api/ml/feature/status/<dictionary_id>', methods=['GET']) # Renamed
@login_required
def api_get_feature_status(dictionary_id):
    """API: Get feature extraction status for a dictionary (session auth)."""
    user_id = current_user.id

    # Assuming a dedicated FeatureService or method on TrainingService/DataService
    if not hasattr(current_app, 'feature_service') or not hasattr(current_app.feature_service, 'get_feature_status'):
        current_app.logger.error("API Feature Status Error: feature_service.get_feature_status not available.")
        return jsonify({"success": False, "error": "Feature status service not available"}), 503

    try:
        # Service should check dictionary ownership (using user_id) and return status
        status_data = current_app.feature_service.get_feature_status(user_id, dictionary_id)
        # Assuming service returns dict: {"success": True, "status": "...", "progress": ..., "missing_features": bool}
        return jsonify(status_data)
    except FileNotFoundError: # Example specific exception
        current_app.logger.warning(f"Feature status check: Dictionary {dictionary_id} not found for user {user_id}.")
        return jsonify({"success": False, "error": "Dictionary not found"}), 404
    except PermissionError: # Example specific exception
        current_app.logger.warning(f"Feature status check: Permission denied for user {user_id} on dictionary {dictionary_id}.")
        return jsonify({"success": False, "error": "Permission denied"}), 403
    except Exception as e:
        current_app.logger.error(f"API Error getting feature status for dict {dictionary_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Failed to get feature status: {str(e)}"}), 500

@training_web_bp.route('/api/training/extract-features', methods=['POST']) # Renamed
@login_required
def api_training_extract_features():
    """API: Trigger feature extraction for a dictionary (session auth)."""
    user_id = current_user.id
    data = request.get_json() if request.is_json else request.form

    # Use 'dictionary_id' for consistency, allow 'dict_name' as fallback from original code
    dictionary_identifier = data.get('dictionary_id', data.get('dict_name', '')).strip()

    if not dictionary_identifier:
        return jsonify({"success": False, "error": "Dictionary identifier ('dictionary_id' or 'dict_name') is required"}), 400

    # Assuming FeatureService handles extraction
    if not hasattr(current_app, 'feature_service') or not hasattr(current_app.feature_service, 'extract_features_for_dictionary'):
        current_app.logger.error("API Feature Extract Error: feature_service.extract_features_for_dictionary not available.")
        return jsonify({"success": False, "error": "Feature extraction service not available"}), 503

    try:
        # Service should handle:
        # - Finding the dictionary by identifier (ID or name)
        # - Checking ownership (using user_id)
        # - Triggering the extraction process (likely async)
        # - Returning job status/ID or immediate result if synchronous
        result = current_app.feature_service.extract_features_for_dictionary(user_id, dictionary_identifier)
        # Assuming service returns dict: {"success": True, "job_id": ..., "message": ...}
        status_code = 202 if result.get('success') else 500 # 202 Accepted if async job started
        return jsonify(result), status_code
    except FileNotFoundError: # Example specific exception
        current_app.logger.warning(f"Feature extract trigger: Dictionary '{dictionary_identifier}' not found for user {user_id}.")
        return jsonify({"success": False, "error": "Dictionary not found"}), 404
    except PermissionError: # Example specific exception
        current_app.logger.warning(f"Feature extract trigger: Permission denied for user {user_id} on dictionary '{dictionary_identifier}'.")
        return jsonify({"success": False, "error": "Permission denied"}), 403
    except Exception as e:
        current_app.logger.error(f"API Error triggering feature extraction for dict '{dictionary_identifier}': {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Failed to start feature extraction: {str(e)}"}), 500

def init_training_web_routes(training_service):
    """
    Initialize training web routes with the training service.
    
    Args:
        training_service: Instance of TrainingService
        
    Returns:
        Configured Blueprint
    """
    return training_web_bp
