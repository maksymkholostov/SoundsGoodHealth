"""
Improved feature extraction routes with progress tracking and better performance.
"""
from flask import Blueprint, request, jsonify, current_app, Response
from flask_login import login_required, current_user
import json
import time
from typing import Generator
from pathlib import Path
import threading
from queue import Queue
from datetime import datetime
import uuid

# Blueprint definition
feature_improved_bp = Blueprint('feature_improved', __name__)

# Need RecordingType enum for subset logic
from backend.app.core.models.recording import RecordingType

# Global storage for extraction progress (in production, use Redis or database)
extraction_progress = {}

@feature_improved_bp.route('/api/features/status/<dictionary_id>', methods=['GET'])
@login_required
def api_check_feature_status(dictionary_id):
    """
    Quick API endpoint to check feature extraction status for a dictionary.
    Optimized to avoid long queries.
    """
    try:
        user_id = current_user.id
        feature_service = current_app.feature_service
        
        # Get cached status if available (cache for 5 seconds)
        cache_key = f"feature_status_{user_id}_{dictionary_id}"
        cached = getattr(current_app, '_feature_status_cache', {}).get(cache_key)
        
        if cached and (time.time() - cached['timestamp']) < 5:
            return jsonify({
                "success": True,
                "status": cached['status'],
                "cached": True
            })
        
        # Get feature status with timeout
        status = feature_service.get_dictionary_feature_status(
            user_id=user_id,
            dictionary_id=dictionary_id,
            feature_set_id="v0.1"
        )
        
        # Add percentage for UI
        if status['total_files'] > 0:
            status['percentage'] = round(
                (status['files_with_features'] / status['total_files']) * 100, 1
            )
        else:
            status['percentage'] = 0
        
        # Cache the result
        if not hasattr(current_app, '_feature_status_cache'):
            current_app._feature_status_cache = {}
        current_app._feature_status_cache[cache_key] = {
            'status': status,
            'timestamp': time.time()
        }
            
        return jsonify({
            "success": True,
            "status": status,
            "cached": False
        })
    except Exception as e:
        current_app.logger.error(f"Error checking feature status: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@feature_improved_bp.route('/api/features/extract/stream', methods=['POST'])
@login_required
def api_extract_features_stream():
    """
    Server-Sent Events endpoint for feature extraction with real-time progress.
    """
    user_id = current_user.id
    data = request.get_json()
    
    if not data or 'recording_ids' not in data:
        return jsonify({"success": False, "error": "Missing recording_ids"}), 400
    
    recording_ids = data['recording_ids']
    if not recording_ids:
        return jsonify({"success": True, "message": "No recordings to process"}), 200
    
    def generate_progress() -> Generator[str, None, None]:
        """Generator function for SSE stream"""
        try:
            feature_service = current_app.feature_service
            recording_repo = current_app.recording_repository
            
            total = len(recording_ids)
            processed = 0
            failed = 0
            BATCH_SIZE = 5  # Smaller batches for more frequent updates
            
            # Send initial event
            yield f"data: {json.dumps({'type': 'start', 'total': total, 'message': f'Starting extraction for {total} recordings'})}\n\n"
            
            # Process in small batches
            for batch_start in range(0, total, BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, total)
                batch = recording_ids[batch_start:batch_end]
                batch_num = (batch_start // BATCH_SIZE) + 1
                total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
                
                # Send batch start event
                yield f"data: {json.dumps({'type': 'batch_start', 'batch': batch_num, 'total_batches': total_batches, 'progress': round((processed/total)*100, 1)})}\n\n"
                
                for rec_id in batch:
                    try:
                        # Get recording info
                        recording = recording_repo.find_by_id(rec_id)
                        if not recording:
                            failed += 1
                            yield f"data: {json.dumps({'type': 'error', 'recording_id': rec_id, 'message': 'Recording not found'})}\n\n"
                            continue
                        
                        class_name = recording.metadata.get('class_name', 'Unknown')
                        
                        # Send processing event
                        yield f"data: {json.dumps({'type': 'processing', 'recording_id': rec_id, 'class': class_name, 'progress': round((processed/total)*100, 1)})}\n\n"
                        
                        # Extract features
                        success, _ = feature_service.extract_features_for_recording(
                            user_id=recording.user_id,
                            dictionary_id=None,
                            recording_id=rec_id,
                            feature_set_id="v0.1"
                        )
                        
                        if success:
                            processed += 1
                            yield f"data: {json.dumps({'type': 'success', 'recording_id': rec_id, 'processed': processed, 'total': total, 'progress': round((processed/total)*100, 1)})}\n\n"
                        else:
                            failed += 1
                            yield f"data: {json.dumps({'type': 'error', 'recording_id': rec_id, 'message': 'Extraction failed'})}\n\n"
                    
                    except Exception as e:
                        failed += 1
                        current_app.logger.error(f"Error processing {rec_id}: {e}")
                        yield f"data: {json.dumps({'type': 'error', 'recording_id': rec_id, 'message': str(e)})}\n\n"
                
                # Small delay between batches to prevent overwhelming
                time.sleep(0.1)
            
            # Send completion event
            yield f"data: {json.dumps({'type': 'complete', 'processed': processed, 'failed': failed, 'total': total, 'progress': 100})}\n\n"
            
        except Exception as e:
            current_app.logger.error(f"Stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'fatal_error', 'message': str(e)})}\n\n"
    
    return Response(
        generate_progress(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
            'Connection': 'keep-alive'
        }
    )

@feature_improved_bp.route('/api/features/extract/batch', methods=['POST'])
@login_required
def api_extract_features_batch():
    """
    Improved batch extraction with better error handling and progress tracking.
    """
    user_id = current_user.id
    data = request.get_json()
    
    if not data or 'recording_ids' not in data:
        return jsonify({"success": False, "error": "Missing recording_ids"}), 400
    
    recording_ids = data['recording_ids']
    dictionary_id = data.get('dictionary_id')  # Optional dictionary context
    
    if not recording_ids:
        return jsonify({"success": True, "processed": 0, "failed": 0}), 200
    
    try:
        feature_service = current_app.feature_service
        recording_repo = current_app.recording_repository
        
        # Create a progress tracking ID
        progress_id = f"{user_id}_{int(time.time())}"
        extraction_progress[progress_id] = {
            'total': len(recording_ids),
            'processed': 0,
            'failed': 0,
            'status': 'running',
            'started': datetime.now().isoformat()
        }
        
        # Process recordings in optimized batches
        results = {
            'processed': [],
            'failed': [],
            'errors': {}
        }
        
        BATCH_SIZE = 10
        for i in range(0, len(recording_ids), BATCH_SIZE):
            batch = recording_ids[i:i+BATCH_SIZE]
            
            for rec_id in batch:
                try:
                    recording = recording_repo.find_by_id(rec_id)
                    if not recording:
                        results['failed'].append(rec_id)
                        results['errors'][rec_id] = "Recording not found"
                        extraction_progress[progress_id]['failed'] += 1
                        continue
                    
                    # Extract features
                    success, extraction = feature_service.extract_features_for_recording(
                        user_id=recording.user_id,
                        dictionary_id=dictionary_id,
                        recording_id=rec_id,
                        feature_set_id="v0.1"
                    )
                    
                    if success:
                        results['processed'].append(rec_id)
                        extraction_progress[progress_id]['processed'] += 1
                    else:
                        results['failed'].append(rec_id)
                        results['errors'][rec_id] = "Extraction failed"
                        extraction_progress[progress_id]['failed'] += 1
                        
                except Exception as e:
                    current_app.logger.error(f"Error extracting {rec_id}: {e}")
                    results['failed'].append(rec_id)
                    results['errors'][rec_id] = str(e)
                    extraction_progress[progress_id]['failed'] += 1
            
            # Update progress
            extraction_progress[progress_id]['status'] = 'running'
        
        # Mark as complete
        extraction_progress[progress_id]['status'] = 'complete'
        extraction_progress[progress_id]['completed'] = datetime.now().isoformat()
        
        # Clear feature status cache for this dictionary
        if dictionary_id and hasattr(current_app, '_feature_status_cache'):
            cache_key = f"feature_status_{user_id}_{dictionary_id}"
            current_app._feature_status_cache.pop(cache_key, None)
        
        return jsonify({
            "success": len(results['failed']) == 0,
            "progress_id": progress_id,
            "processed": len(results['processed']),
            "failed": len(results['failed']),
            "errors": results['errors'] if results['failed'] else None
        })
        
    except Exception as e:
        current_app.logger.error(f"Batch extraction error: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@feature_improved_bp.route('/api/features/progress/<progress_id>', methods=['GET'])
@login_required
def api_get_extraction_progress(progress_id):
    """
    Stream the progress of a feature extraction job using Server-Sent Events.
    """
    def generate():
        """Generate SSE updates"""
        last_update = None
        retry_count = 0
        max_retries = 600  # 10 minutes at 1 second intervals
        
        while retry_count < max_retries:
            progress = extraction_progress.get(progress_id)
            
            if not progress and retry_count == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Progress ID not found'})}\n\n"
                break
            
            if progress and progress != last_update:
                # Calculate percentage
                if progress['total'] > 0:
                    percentage = round(
                        ((progress['processed'] + progress['failed']) / progress['total']) * 100, 1
                    )
                else:
                    percentage = 100
                
                # Send update
                update = {
                    'type': 'progress',
                    'processed': progress['processed'],
                    'failed': progress['failed'],
                    'total': progress['total'],
                    'current_file': progress.get('current_file'),
                    'percentage': percentage,
                    'status': progress.get('status')
                }
                yield f"data: {json.dumps(update)}\n\n"
                
                last_update = progress.copy()
                
                # Check if complete
                if progress.get('status') == 'complete':
                    yield f"data: {json.dumps({'type': 'complete', 'message': 'Extraction complete'})}\n\n"
                    break
                elif progress.get('status') == 'failed':
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Extraction failed'})}\n\n"
                    break
            
            time.sleep(1)
            retry_count += 1
            
            # Send heartbeat every 30 seconds
            if retry_count % 30 == 0:
                yield f": heartbeat\n\n"
        
        if retry_count >= max_retries:
            yield f"data: {json.dumps({'type': 'timeout', 'message': 'Progress monitoring timeout'})}\n\n"
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

@feature_improved_bp.route('/api/features/trigger/<dictionary_id>', methods=['POST'])
@login_required
def api_trigger_missing_features(dictionary_id):
    """
    Automatically extract features for all recordings missing features in a dictionary.
    """
    # Import at the top to avoid UnboundLocalError
    from backend.app.core.models.recording import RecordingType
    
    try:
        user_id = current_user.id
        feature_service = current_app.feature_service
        recording_repo = current_app.recording_repository
        dictionary_repo = current_app.dictionary_repository
        
        # Get dictionary
        dictionary = dictionary_repo.get_dictionary_by_id(dictionary_id)
        if not dictionary:
            return jsonify({"success": False, "error": "Dictionary not found"}), 404
        
        # Get all recordings for this dictionary that need features
        class_ids = dictionary.class_ids
        if not class_ids:
            return jsonify({"success": True, "message": "No classes in dictionary"}), 200
        
        # Find recordings without features (get all gold and augmented)
        
        # Check if we should include all users' recordings
        include_all_users = current_app.config.get('INCLUDE_ALL_USER_RECORDINGS', False)
        user_filter = None if include_all_users else user_id
        
        current_app.logger.info(f"[EXTRACT] Getting recordings for dictionary {dictionary_id}, user filter: {user_filter} (include_all={include_all_users})")
        
        # Get GOLD recordings
        gold_recordings = recording_repo.get_all_for_dictionary(
            dictionary_id=dictionary_id,
            user_id=user_filter,
            rec_type=RecordingType.GOLD
        )
        current_app.logger.info(f"[EXTRACT] Found {len(gold_recordings)} GOLD recordings")
        
        # Get AUGMENTED recordings
        augmented_recordings = recording_repo.get_all_for_dictionary(
            dictionary_id=dictionary_id,
            user_id=user_filter,
            rec_type=RecordingType.AUGMENTED
        )
        current_app.logger.info(f"[EXTRACT] Found {len(augmented_recordings)} AUGMENTED recordings")
        
        # Combine both types
        recordings = gold_recordings + augmented_recordings
        current_app.logger.info(f"[EXTRACT] Total recordings to check: {len(recordings)}")
        
        # Check which ones need features
        missing_features = []
        for recording in recordings:
            # Quick check if features exist (could be optimized with batch check)
            class_name = recording.metadata.get('class_name')
            if not class_name:
                class_name = recording_repo._get_class_name(recording.class_id)
            
            if class_name:
                # Determine subset based on recording ID pattern
                subset = 'augmented' if recording.id.startswith('aug_') else 'gold'
                recording_id_base = recording.id.split('_seg')[0]
                npz_filename = f"{recording_id_base}_features.npz"
                
                feature_path = current_app.file_manager.get_feature_data_path(
                    feature_version="v0.1",
                    user_id=recording.user_id,
                    subset=subset,
                    class_name=class_name,
                    filename=npz_filename
                )
                
                if not feature_path.exists():
                    current_app.logger.info(f"[EXTRACT] Missing features: {recording.id} (class: {class_name}, subset: {subset})")
                    missing_features.append(recording.id)
                else:
                    current_app.logger.debug(f"[EXTRACT] Has features: {recording.id}")
            else:
                current_app.logger.warning(f"[EXTRACT] Cannot determine class name for {recording.id}")
        
        current_app.logger.info(f"[EXTRACT] Total missing features: {len(missing_features)}")
        if not missing_features:
            return jsonify({
                "success": True,
                "message": "All recordings already have features",
                "count": 0
            })
        
        # Create a progress ID for this extraction job
        progress_id = str(uuid.uuid4())
        
        current_app.logger.info(f"[EXTRACT] Starting extraction job {progress_id} for {len(missing_features)} recordings")
        current_app.logger.info(f"[EXTRACT] Recording IDs: {missing_features[:5]}..." if len(missing_features) > 5 else f"[EXTRACT] Recording IDs: {missing_features}")
        
        # Initialize progress tracking
        extraction_progress[progress_id] = {
            'id': progress_id,
            'dictionary_id': dictionary_id,
            'user_id': user_id,
            'total': len(missing_features),
            'processed': 0,
            'failed': 0,
            'status': 'starting',
            'started': datetime.now().isoformat(),
            'current_file': None
        }
        
        # Start extraction in background with proper app context
        from threading import Thread
        
        def extract_in_background(app, feature_svc, user, dict_id, prog_id, recordings):
            with app.app_context():
                BATCH_SIZE = 5  # Process 5 at a time to prevent overload
                
                for i in range(0, len(recordings), BATCH_SIZE):
                    batch = recordings[i:i+BATCH_SIZE]
                    
                    for rec_id in batch:
                        try:
                            extraction_progress[prog_id]['current_file'] = rec_id
                            
                            # Extract features
                            success, _ = feature_svc.extract_features_for_recording(
                                user_id=user,
                                dictionary_id=dict_id,
                                recording_id=rec_id,
                                feature_set_id="v0.1"
                            )
                            
                            if success:
                                extraction_progress[prog_id]['processed'] += 1
                            else:
                                extraction_progress[prog_id]['failed'] += 1
                                
                        except Exception as e:
                            app.logger.error(f"Error extracting {rec_id}: {e}")
                            extraction_progress[prog_id]['failed'] += 1
                    
                    # Small delay between batches to prevent overload
                    import time
                    time.sleep(0.5)
                
                # Mark as complete
                extraction_progress[prog_id]['status'] = 'complete'
                extraction_progress[prog_id]['completed'] = datetime.now().isoformat()
                
                # Clear cache
                if hasattr(app, '_feature_status_cache'):
                    cache_key = f"feature_status_{user}_{dict_id}"
                    app._feature_status_cache.pop(cache_key, None)
        
        # Start background extraction with app context
        thread = Thread(
            target=extract_in_background,
            args=(current_app._get_current_object(), feature_service, user_id, 
                  dictionary_id, progress_id, missing_features)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "success": True,
            "message": f"Started extraction for {len(missing_features)} recordings",
            "progress_id": progress_id,
            "count": len(missing_features)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error triggering features: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500