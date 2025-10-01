"""
Improved training routes with progress tracking and optimization.
"""
from flask import Blueprint, request, jsonify, current_app, Response
from flask_login import login_required, current_user
import json
import time
from typing import Generator

# Create blueprint
training_improved_bp = Blueprint('training_improved', __name__)

@training_improved_bp.route('/api/ml/train/model/optimized', methods=['POST'])
@login_required
def api_train_model_optimized():
    """
    Optimized model training endpoint with progress support.
    """
    try:
        user_id = current_user.id
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['dictionary_id', 'model_type', 'model_name']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Get training service
        training_service = getattr(current_app, 'training_service', None)
        if not training_service:
            return jsonify({
                'success': False,
                'error': 'Training service not available'
            }), 503
        
        # Check if optimized service is available
        if not hasattr(current_app, 'optimized_training_service'):
            # Create optimized wrapper
            from backend.app.services.training_service_optimized import OptimizedTrainingService
            current_app.optimized_training_service = OptimizedTrainingService(training_service)
        
        optimized_service = current_app.optimized_training_service
        
        # Start training with progress tracking
        result = optimized_service.train_model_with_progress(
            user_id=user_id,
            dictionary_id=data['dictionary_id'],
            model_type=data['model_type'],
            model_name=data['model_name'],
            feature_version=data.get('feature_version', 'v0.1'),
            use_augmented=data.get('use_augmented', True),
            params=data.get('params', {})
        )
        
        return jsonify({
            'success': True,
            'status': 'started',
            'id': result['id'],  # Ensure model_id is at top level
            'model_id': result['id'],  # Also include as model_id
            'model': result
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        current_app.logger.error(f"Training error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@training_improved_bp.route('/api/ml/train/progress/<model_id>', methods=['GET'])
@login_required
def api_get_training_progress(model_id):
    """
    Get training progress for a specific model - returns JSON for polling.
    """
    try:
        # Get services
        optimized_service = getattr(current_app, 'optimized_training_service', None)
        training_service = getattr(current_app, 'training_service', None)
        
        progress = None
        
        # Try optimized service first
        if optimized_service and hasattr(optimized_service, 'get_training_progress'):
            progress = optimized_service.get_training_progress(model_id)
        
        # Fallback to regular training service
        if not progress and training_service:
            if hasattr(training_service, 'get_training_status'):
                status = training_service.get_training_status(model_id)
                if status:
                    progress = {
                        'status': status.get('status', 'unknown'),
                        'progress': status.get('progress', 0),
                        'message': status.get('message', 'Training...'),
                    }
        
        if progress:
            return jsonify({
                'success': True,
                'progress': progress
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No progress data available'
            }), 404
            
    except Exception as e:
        current_app.logger.error(f"Progress check error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@training_improved_bp.route('/api/ml/train/progress/stream/<model_id>', methods=['GET'])
@login_required
def api_get_training_progress_sse(model_id):
    """
    Get training progress for a specific model - SSE endpoint for real-time updates.
    """
    # Get services BEFORE the generator (while in app context)
    optimized_service = getattr(current_app, 'optimized_training_service', None)
    training_service = getattr(current_app, 'training_service', None)
    logger = current_app.logger
    
    def generate():
        """Generate SSE events for training progress"""
        
        last_progress = None
        retry_count = 0
        max_retries = 600  # 10 minutes at 1 second intervals
        
        while retry_count < max_retries:
            try:
                progress = None
                
                # Try optimized service first
                if optimized_service and hasattr(optimized_service, 'get_training_progress'):
                    progress = optimized_service.get_training_progress(model_id)
                
                # Fallback to regular training service
                if not progress and training_service:
                    if hasattr(training_service, 'get_training_status'):
                        status = training_service.get_training_status(model_id)
                        if status:
                            progress = {
                                'status': status.get('status', 'unknown'),
                                'progress': status.get('progress', 0),
                                'message': status.get('message', 'Training...'),
                            }
                
                # If we have progress and it changed, send update
                if progress and progress != last_progress:
                    # Add SSE type field
                    progress['type'] = 'progress'
                    
                    # Send the progress update
                    yield f"data: {json.dumps(progress)}\n\n"
                    
                    last_progress = progress.copy()
                    
                    # Check if complete
                    if progress.get('status') in ['complete', 'completed', 'failed', 'error']:
                        final_msg = {
                            'type': 'done',
                            'status': progress.get('status'),
                            'message': progress.get('message', 'Training finished')
                        }
                        yield f"data: {json.dumps(final_msg)}\n\n"
                        break
                
                # Send heartbeat every 30 seconds
                if retry_count % 30 == 0:
                    yield f": heartbeat\n\n"
                
                time.sleep(1)
                retry_count += 1
                
            except Exception as e:
                logger.error(f"Progress stream error: {e}")
                error_msg = {
                    'type': 'error',
                    'message': str(e)
                }
                yield f"data: {json.dumps(error_msg)}\n\n"
                break
        
        if retry_count >= max_retries:
            timeout_msg = {
                'type': 'timeout',
                'message': 'Progress monitoring timeout'
            }
            yield f"data: {json.dumps(timeout_msg)}\n\n"
    
    # Return SSE response
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

@training_improved_bp.route('/api/ml/train/stream/<model_id>', methods=['GET'])
@login_required  
def api_training_progress_stream(model_id):
    """
    Server-Sent Events stream for real-time training progress.
    """
    def generate_progress() -> Generator[str, None, None]:
        """Generator for SSE stream"""
        optimized_service = getattr(current_app, 'optimized_training_service', None)
        if not optimized_service:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Service not available'})}\n\n"
            return
        
        last_update = None
        retry_count = 0
        max_retries = 1800  # 30 minutes at 1 second intervals
        
        while retry_count < max_retries:
            try:
                progress = optimized_service.get_training_progress(model_id)
                
                if progress and progress != last_update:
                    # Send progress update
                    yield f"data: {json.dumps({'type': 'progress', **progress})}\n\n"
                    last_update = progress
                    
                    # Check if training is complete or failed
                    if progress.get('status') in ['complete', 'failed']:
                        yield f"data: {json.dumps({'type': 'done', 'status': progress['status']})}\n\n"
                        break
                
                # Sleep before next check
                time.sleep(1)
                retry_count += 1
                
                # Send heartbeat every 30 seconds
                if retry_count % 30 == 0:
                    yield f": heartbeat\n\n"
                    
            except Exception as e:
                current_app.logger.error(f"Stream error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                break
        
        if retry_count >= max_retries:
            yield f"data: {json.dumps({'type': 'timeout', 'message': 'Training timeout'})}\n\n"
    
    return Response(
        generate_progress(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

@training_improved_bp.route('/api/ml/train/stats/live/<model_id>', methods=['GET'])
@login_required
def api_get_live_training_stats(model_id):
    """
    Get live training statistics and epoch data.
    """
    try:
        # Try to read from training log file if it exists
        from pathlib import Path
        log_dir = Path('/tmp/training_logs')  # Or wherever logs are stored
        log_file = log_dir / f"{model_id}_progress.json"
        
        if log_file.exists():
            with open(log_file, 'r') as f:
                stats = json.load(f)
            return jsonify({
                'success': True,
                'stats': stats
            })
        
        # Fallback to progress data
        optimized_service = getattr(current_app, 'optimized_training_service', None)
        if optimized_service:
            progress = optimized_service.get_training_progress(model_id)
            if progress:
                return jsonify({
                    'success': True,
                    'stats': {
                        'progress': progress,
                        'epochs': []  # No epoch data available yet
                    }
                })
        
        return jsonify({
            'success': False,
            'error': 'No stats available'
        }), 404
        
    except Exception as e:
        current_app.logger.error(f"Stats error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@training_improved_bp.route('/api/ml/train/clear-stuck/<model_id>', methods=['POST'])
@login_required
def api_clear_stuck_training(model_id):
    """
    Clear a stuck training model by marking it as failed.
    """
    try:
        from backend.app.core.models.model import ModelStatus
        
        user_id = current_user.id
        training_service = getattr(current_app, 'training_service', None)
        if not training_service:
            return jsonify({
                'success': False,
                'error': 'Training service not available'
            }), 503
        
        # Find the model across all user's dictionaries
        all_dictionaries = training_service.dictionary_repo.get_all_dictionaries()
        user_dictionaries = [d for d in all_dictionaries if hasattr(d, 'creator_user_id') and d.creator_user_id == user_id]
        
        model_found = False
        for dictionary in user_dictionaries:
            try:
                model = training_service.model_repo.get_by_id(user_id, dictionary.id, model_id)
                if model and model.status == ModelStatus.TRAINING:
                    # Mark as failed
                    model.mark_failed("Training interrupted - cleared stuck status")
                    training_service.model_repo.save(model)
                    model_found = True
                    current_app.logger.info(f"Cleared stuck training for model {model_id}")
                    break
            except:
                continue
        
        if model_found:
            return jsonify({
                'success': True,
                'message': f'Cleared stuck training for model {model_id}'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Model {model_id} not found or not in training status'
            }), 404
            
    except Exception as e:
        current_app.logger.error(f"Clear stuck training error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500