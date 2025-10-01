from flask import Blueprint, request, jsonify
import logging
from typing import Dict, Any
import tempfile
import os
import base64
import io
import wave
import numpy as np

from ..services.inference_service import InferenceService
from .prediction_events import publish_prediction_event

logger = logging.getLogger(__name__)

# Create blueprint for API routes
inference_api_bp = Blueprint('inference_api', __name__) # Correct name for API blueprint

def init_inference_routes(inference_service: InferenceService) -> Blueprint:
    """
    Initialize inference API routes with the inference service.
    
    Args:
        inference_service: Instance of InferenceService
        
    Returns:
        Configured Blueprint (inference_api_bp)
    """
    
    # Check if the blueprint is already initialized to prevent registration errors
    if getattr(inference_api_bp, "_initialized", False):
        return inference_api_bp
        
    # Mark as initialized to prevent double registration
    setattr(inference_api_bp, "_initialized", True)
    
    @inference_api_bp.route('/api/models/inference/<user_id>/<dictionary_id>', methods=['GET'])
    # DB-OPERATION: read user
    def get_available_models(user_id: str, dictionary_id: str) -> Dict[str, Any]:
        """API: Get available models for inference for a specific dictionary."""
        try:
            models = inference_service.get_available_models(user_id, dictionary_id)
            
            return jsonify({
                'success': True,
                'models': models
            })
        except Exception as e:
            logger.exception("API Error getting available models for user %s, dict %s: %s", user_id, dictionary_id, e)
            return jsonify({
                'success': False,
                'error': "Failed to retrieve available models."
            }), 500
    
    @inference_api_bp.route('/api/inference', methods=['POST'])
    def predict() -> Dict[str, Any]:
        """API: Make a prediction for an audio sample file."""
        try:
            # Check if file was uploaded
            if 'audio' not in request.files:
                return jsonify({
                    'success': False,
                    'error': "No audio file provided in 'audio' field"
                }), 400
            
            audio_file = request.files['audio']
            
            # Check other required parameters from form data
            user_id = request.form.get('user_id')
            dictionary_id = request.form.get('dictionary_id')
            model_id = request.form.get('model_id')
            
            if not all([user_id, dictionary_id, model_id]):
                return jsonify({
                    'success': False,
                    'error': "Missing required form parameters: user_id, dictionary_id, model_id"
                }), 400
            
            # Save the uploaded file to a temporary location
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    audio_file.save(temp_file.name)
                    temp_path = temp_file.name
                
                # Delegate prediction to the service
                result = inference_service.predict_file(
                    user_id, dictionary_id, model_id, temp_path
                )
                
                # Check if saving is requested and actual_class is provided
                save_result = request.form.get('save_result', 'false').lower() == 'true'
                actual_class = request.form.get('actual_class') if save_result else None
                
                if save_result:
                    # Load audio data again for saving (service might need it)
                    try:
                        # Use the service's method for saving inference results
                        inference_service.save_inference_result_from_file(
                            user_id, dictionary_id, model_id, temp_path, result, actual_class
                        )
                        logger.info("Saved inference result for user %s, dict %s, model %s", user_id, dictionary_id, model_id)
                    except Exception as save_e:
                        # Log error but don't fail the prediction response
                        logger.error("API Error saving inference result: %s", save_e)
                
                # Return successful prediction
                # Also publish SSE event
                try:
                    publish_prediction_event({
                        'event': 'prediction',
                        'timestamp': time.time(),
                        'dictionary_id': dictionary_id,
                        'model_id': model_id,
                        'result': result
                    })
                except Exception:
                    pass

                return jsonify({'success': True, 'prediction': result})
            finally:
                # Clean up temporary file if it was created
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                        # STORAGE-OPERATION: Will be replaced by DatabaseManager (Placeholder)
                    except OSError as e:
                        logger.error("API Error removing temporary audio file %s: %s", temp_path, e)
        except ValueError as e:
            logger.warning("API Validation error during prediction: %s", e)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400
        except FileNotFoundError as e:
             logger.warning("API File not found during prediction: %s", e)
             return jsonify({
                 'success': False,
                 'error': str(e)
             }), 404
        except Exception as e:
            logger.exception("API Unexpected error during prediction: %s", e)
            return jsonify({
                'success': False,
                'error': "An unexpected error occurred during prediction."
            }), 500
    
    @inference_api_bp.route('/api/inference/stream', methods=['POST'])
    def predict_stream() -> Dict[str, Any]:
        """API: Make a prediction for streaming audio data (sent as base64 in JSON)."""
        try:
            # Get the JSON data
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'Request body must be JSON'}), 400
            
            # Validate required fields in JSON payload
            required_fields = ['user_id', 'dictionary_id', 'model_id', 'audio_data']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return jsonify({
                    'success': False,
                    'error': f"Missing required JSON fields: {', '.join(missing_fields)}"
                }), 400
            
            user_id = data['user_id']
            dictionary_id = data['dictionary_id']
            model_id = data['model_id']
            audio_data_b64 = data['audio_data']
            
            # Decode base64 audio
            try:
                audio_data_bytes = base64.b64decode(audio_data_b64)
            except (TypeError, base64.binascii.Error) as b64_e:
                 logger.warning("API Invalid base64 audio data received: %s", b64_e)
                 return jsonify({'success': False, 'error': 'Invalid base64 audio data'}), 400
            
            # Parse WAV data from bytes
            try:
                with io.BytesIO(audio_data_bytes) as wav_io:
                    with wave.open(wav_io, 'rb') as wav_file:
                    # STORAGE-OPERATION: Placeholder for potential DB interaction
                        sample_rate = wav_file.getframerate()
                        n_frames = wav_file.getnframes()
                        if wav_file.getsampwidth() != 2: # Assuming 16-bit PCM
                            raise ValueError("Unsupported sample width")
                        audio_bytes = wav_file.readframes(n_frames)
            except (wave.Error, ValueError) as wav_e:
                logger.warning("API Error parsing WAV data from stream: %s", wav_e)
                return jsonify({'success': False, 'error': f'Error parsing WAV audio data: {wav_e}'}), 400
            
            # Convert to numpy array (float32, normalized)
            try:
                audio_data_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            except Exception as np_e:
                logger.error("API Error converting audio bytes to numpy array: %s", np_e)
                return jsonify({'success': False, 'error': 'Internal error processing audio data'}), 500
            
            # Make the prediction using the service
            result = inference_service.predict(
                user_id, dictionary_id, model_id,
                audio_data_np, sample_rate
            )
            
            # Check if saving is requested and actual_class is provided
            save_result = data.get('save_result', False)
            actual_class = data.get('actual_class') if save_result else None
            
            if save_result:
                 try:
                    # Use the service's method for saving inference results (requires audio_data_np)
                    inference_service.save_inference_result(
                        user_id, dictionary_id, model_id,
                        audio_data_np, result, actual_class
                    )
                    logger.info("Saved streamed inference result for user %s, dict %s, model %s", user_id, dictionary_id, model_id)
                 except Exception as save_e:
                    # Log error but don't fail the prediction response
                    logger.error("API Error saving streamed inference result: %s", save_e)
            
            try:
                publish_prediction_event({
                    'event': 'prediction',
                    'timestamp': time.time(),
                    'dictionary_id': dictionary_id,
                    'model_id': model_id,
                    'result': result
                })
            except Exception:
                pass

            return jsonify({'success': True, 'prediction': result})
        except ValueError as e:
            logger.warning("API Validation error during stream prediction: %s", e)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400
        except FileNotFoundError as e:
             logger.warning("API File not found during stream prediction: %s", e)
             return jsonify({
                 'success': False,
                 'error': str(e)
             }), 404
        except Exception as e:
            logger.exception("API Unexpected error during stream prediction: %s", e)
            return jsonify({
                'success': False,
                'error': "An unexpected error occurred during stream prediction."
            }), 500
    
    return inference_api_bp
