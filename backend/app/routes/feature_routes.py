"""
Routes related to feature extraction management and triggering.
"""
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
import numpy as np  # Import numpy for calculations
import os           # Import os for path operations
from pathlib import Path

# Blueprint definition
feature_bp = Blueprint('feature_web', __name__) # Use 'feature_web' to match url_for

# Need RecordingType enum for subset logic
from backend.app.core.models.recording import RecordingType

@feature_bp.route('/api/features/extract', methods=['POST'])
@login_required
def api_extract_features_for_list():
    """
    API Endpoint to extract features for a list of recording IDs.
    """
    user_id = current_user.id
    data = request.get_json()

    if not data or 'recording_ids' not in data or not isinstance(data['recording_ids'], list):
        return jsonify({"success": False, "error": "Missing or invalid 'recording_ids' list in request body"}), 400

    recording_ids_to_process = data['recording_ids']
    if not recording_ids_to_process:
        return jsonify({"success": True, "message": "No recording IDs provided to process.", "processed_count": 0, "failed_count": 0, "log": []})

    # BATCH SIZE LIMIT - prevent timeouts
    MAX_BATCH_SIZE = 20  # Process max 20 recordings at once
    if len(recording_ids_to_process) > MAX_BATCH_SIZE:
        return jsonify({
            "success": False,
            "error": f"Too many recordings ({len(recording_ids_to_process)}). Maximum batch size is {MAX_BATCH_SIZE}. Please process in smaller batches.",
            "max_batch_size": MAX_BATCH_SIZE
        }), 400

    # Access services/repositories
    try:
        feature_service = current_app.feature_service
        recording_repo = current_app.recording_repository
    except AttributeError as e:
        current_app.logger.error(f"API Feature Extract Error: Service/Repository not available: {e}")
        return jsonify({"success": False, "error": "Server configuration error: required service unavailable."}), 503

    processed_count = 0
    failed_count = 0
    log_messages = []
    default_feature_set_id = "v0.1" # Or get from request if needed later

    # Process in batches to prevent timeouts
    BATCH_SIZE = 10  # Process 10 at a time internally
    total_recordings = len(recording_ids_to_process)
    
    current_app.logger.info(f"User {user_id} initiated feature extraction for {total_recordings} recordings.")
    log_messages.append(f"Starting feature extraction for {total_recordings} sounds in batches of {BATCH_SIZE}...")

    # Process in chunks
    for batch_start in range(0, total_recordings, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_recordings)
        batch = recording_ids_to_process[batch_start:batch_end]
        batch_num = (batch_start // BATCH_SIZE) + 1
        total_batches = (total_recordings + BATCH_SIZE - 1) // BATCH_SIZE
        
        log_messages.append(f"Processing batch {batch_num}/{total_batches} ({len(batch)} recordings)...")
        current_app.logger.info(f"Processing batch {batch_num}/{total_batches}")

        for rec_id in batch:
            try:
                # Find the recording to get owner user_id and dictionary_id context
                recording = recording_repo.find_by_id(rec_id)
                if not recording:
                    log_messages.append(f"ERROR: Recording {rec_id} not found. Skipping.")
                    failed_count += 1
                    continue

                # Extract owner_id and potentially dictionary_id (for metadata, not path)
                owner_user_id = recording.user_id
                # dictionary_id_context = recording.metadata.get('dictionary_id') # Get dict_id if present for metadata saving

                log_messages.append(f"Processing {rec_id} (Class: {recording.metadata.get('class_name','N/A')}, Type: {recording.recording_type.value})...")

                # Call the service using owner's user_id for path context, but dictionary_id is optional here
                # Pass dictionary_id_context if FeatureExtraction metadata needs it
                success, _ = feature_service.extract_features_for_recording(
                    user_id=owner_user_id,  # Use owner for path consistency
                    dictionary_id=None, # Pass None, path logic handles it
                    recording_id=rec_id,
                    feature_set_id=default_feature_set_id
                    # Pass dictionary_id_context here if needed for metadata record later
                )

                if success:
                    log_messages.append(f"-> SUCCESS: Features extracted for {rec_id}.")
                    processed_count += 1
                else:
                    # Service should log specific errors
                    log_messages.append(f"-> FAILED: Feature extraction failed for {rec_id}. See server logs.")
                    failed_count += 1

            except Exception as e:
                log_messages.append(f"-> ERROR: Unexpected error processing {rec_id}: {str(e)}")
                current_app.logger.error(f"Unexpected error during feature extraction loop for {rec_id}: {e}", exc_info=True)
                failed_count += 1
                continue
        
        # Log batch completion
        log_messages.append(f"Batch {batch_num}/{total_batches} complete. Progress: {processed_count}/{total_recordings} processed.")
        current_app.logger.info(f"Batch {batch_num} complete: {processed_count} processed, {failed_count} failed so far")

    log_messages.append(f"All batches finished. Total Processed: {processed_count}, Failed: {failed_count}.")
    final_status = failed_count == 0 # True only if all succeeded

    return jsonify({
        "success": final_status,
        "message": f"Extraction finished. Processed: {processed_count}, Failed: {failed_count}.",
        "processed_count": processed_count,
        "failed_count": failed_count,
        "log": log_messages
    })

# --- NEW ROUTE ---
@feature_bp.route('/api/features/data/<string:recording_id>', methods=['GET'])
@login_required
def api_get_feature_data_stats(recording_id: str):
    """
    API Endpoint to get statistics (shape, count, zeros, dtype) about
    the extracted feature data for a specific recording.
    """
    user_id = current_user.id
    current_app.logger.info(f"User {user_id} requesting feature data stats for recording {recording_id}.")

    try:
        # Access services/repositories
        recording_repo = current_app.recording_repository
        file_manager = current_app.file_manager
        feature_repo = current_app.feature_repository # Needed for extraction metadata

    except AttributeError as e:
        current_app.logger.error(f"API Feature Stats Error: Service/Repository not available: {e}")
        return jsonify({"success": False, "error": "Server configuration error: required service unavailable."}), 503

    try:
        # 1. Find the recording metadata
        recording = recording_repo.find_by_id(recording_id)
        if not recording:
            return jsonify({"success": False, "error": f"Recording {recording_id} not found."}), 404

        # Optional: Add ownership check if needed
        # if recording.user_id != user_id:
        #     return jsonify({"success": False, "error": "Permission denied."}), 403

        # 2. Determine the feature file path (using default 'v0.1' for now)
        #    This logic might need refinement if multiple feature sets can exist per recording.
        feature_set_id = "v0.1" # TODO: Determine this dynamically if needed
        class_name = recording.metadata.get('class_name')
        if not class_name:
            class_name = recording_repo._get_class_name(recording.class_id) # Fetch if missing
        
        if not class_name:
             current_app.logger.error(f"Cannot determine class name for recording {recording_id} to find feature path.")
             return jsonify({"success": False, "error": "Cannot determine class name for recording."}), 500

        subset = 'gold' if recording.recording_type == RecordingType.GOLD else \
                 'augmented' if recording.recording_type == RecordingType.AUGMENTED else \
                 'unknown'
        
        if subset == 'unknown':
            current_app.logger.error(f"Unknown recording type for {recording_id}.")
            return jsonify({"success": False, "error": "Unknown recording type."}), 500

        # Use the *original* recording ID base for the filename
        recording_id_base = recording.id.split('_seg')[0] 
        npz_filename = f"{recording_id_base}_features.npz"
        
        feature_npz_path = file_manager.get_feature_data_path(
            feature_version=feature_set_id,
            user_id=recording.user_id, # Use owner's ID for path
            subset=subset,
            class_name=class_name,
            filename=npz_filename
        )

        current_app.logger.debug(f"Attempting to load feature stats from: {feature_npz_path}")

        if not feature_npz_path.exists():
            current_app.logger.warning(f"Feature file not found for {recording_id} at {feature_npz_path}")
            return jsonify({"success": False, "error": "Feature data file (.npz) not found for this recording."}), 404

        # 3. Load the NPZ file and calculate stats
        feature_data_stats = {}
        try:
            with np.load(feature_npz_path, allow_pickle=True) as data:
                # Extract the feature names order from the FeatureSet definition
                feature_set = feature_repo.get_feature_set(feature_set_id)
                if not feature_set or not feature_set.features:
                    current_app.logger.error(f"Could not load feature set definition {feature_set_id} to determine feature order.")
                    # Fallback: use keys from the npz file directly, but order might be wrong
                    feature_names_in_order = list(data.keys()) 
                else:
                    # Use the order defined in the feature set
                    feature_names_in_order = feature_set.features

                # Process features based on the defined order
                for feature_name in feature_names_in_order:
                    if feature_name in data:
                        array = data[feature_name]
                        shape = array.shape
                        total_elements = array.size
                        # Handle potential non-numeric or complex types gracefully
                        try:
                           zero_count = np.count_nonzero(array == 0) if np.issubdtype(array.dtype, np.number) else 'N/A'
                           zero_percentage = (zero_count / total_elements * 100) if total_elements > 0 and isinstance(zero_count, (int, float)) else 'N/A'
                           zero_count_str = f"{zero_count} ({zero_percentage:.2f}%)" if isinstance(zero_count, (int, float)) else zero_count
                        except TypeError: # Handle complex types where comparison might fail
                            zero_count_str = 'N/A (non-numeric data)'

                        # Determine time frames (assuming 2D: features x time)
                        time_frames = shape[1] if len(shape) == 2 else 'N/A (not 2D)'
                        
                        feature_data_stats[feature_name] = {
                            "shape": str(shape),
                            "total_elements": total_elements,
                            "time_frames": time_frames,
                            "dtype": str(array.dtype),
                            "zeros": zero_count_str,
                        }
                    else:
                        current_app.logger.warning(f"Feature '{feature_name}' defined in set '{feature_set_id}' not found in NPZ file {feature_npz_path}.")
                        feature_data_stats[feature_name] = {"error": "Feature not found in data file"}

        except Exception as load_err:
            current_app.logger.error(f"Error loading or processing NPZ file {feature_npz_path}: {load_err}", exc_info=True)
            return jsonify({"success": False, "error": f"Failed to load or process feature data: {str(load_err)}"}), 500

        # 4. Return the stats
        return jsonify({"success": True, "recording_id": recording_id, "feature_stats": feature_data_stats})

    except Exception as e:
        current_app.logger.error(f"Unexpected error getting feature stats for {recording_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected error occurred: {str(e)}"}), 500

# --- END NEW ROUTE ---
