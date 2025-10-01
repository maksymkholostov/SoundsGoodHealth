"""
Custom speech API for SoundClassifiers, providing integration with C# clients.
This API allows clients to classify phonemes/sounds using trained models.
"""

from flask import Blueprint, request, jsonify, current_app, g
import logging
import os
import io
import base64
import tempfile
import traceback
from typing import Dict, Any, List
import wave
import numpy as np

from ..services.inference_service import InferenceService

logger = logging.getLogger(__name__)

# Create a blueprint for the custom speech API
custom_speech_api_bp = Blueprint('custom_speech_api', __name__)

def init_custom_speech_routes(inference_service=None, model_repo=None):
    """
    Initialize routes for the custom speech API.
    
    Args:
        inference_service: The inference service for sound classification
        model_repo: The model repository for model data
        
    Returns:
        Configured Blueprint
    """
    # Store the services on the blueprint for access in routes
    if not hasattr(custom_speech_api_bp, "_services_set"):
        if inference_service:
            custom_speech_api_bp.inference_service = inference_service
        if model_repo:
            custom_speech_api_bp.model_repo = model_repo
        custom_speech_api_bp._services_set = True
    
    @custom_speech_api_bp.route('/api/speech/recognize', methods=['POST'])
    def recognize_speech():
        """
        Recognize a sound/phoneme from audio data.
        
        Supports two formats:
        1. Multipart form upload with 'audio' file and 'model_id'
        2. JSON with 'audio_data' (base64) and 'model_id'
        
        Returns:
            JSON response with recognition results
        """
        try:
            # Get inference service
            inference_service = getattr(custom_speech_api_bp, 'inference_service', 
                                      getattr(current_app, 'inference_service', None))
            if not inference_service:
                logger.error("No inference service available for speech recognition")
                return jsonify({
                    'success': False,
                    'error': "Service unavailable"
                }), 503
            
            # Get model ID from form or JSON
            model_id = None
            audio_data = None
            
            # 1. Check for form data with file upload
            if 'audio' in request.files:
                audio_file = request.files['audio']
                model_id = request.form.get('model_id')
                
                if not model_id:
                    return jsonify({
                        'success': False,
                        'error': "Missing required parameter 'model_id'"
                    }), 400
                
                # Process the audio file
                temp_path = None # Initialize path variable
                try:
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                        audio_file.save(tmp.name)
                        temp_path = tmp.name
                    
                    # Call inference service to classify the audio
                    result = process_audio_file(temp_path, model_id, inference_service)
                    
                    # Return result
                    return jsonify({
                        'success': True,
                        'phoneme': result.get('top_class', 'Unknown'),
                        'alternatives': [
                            {'phoneme': alt.get('class', 'Unknown')} 
                            for alt in result.get('alternatives', [])
                        ],
                        'model_id': model_id
                    })
                finally:
                    # Clean up the temporary file
                    if temp_path and os.path.exists(temp_path):
                        try:
                            os.unlink(temp_path)
                            logger.debug(f"Cleaned up temp file: {temp_path}")
                        except OSError as e:
                            logger.error(f"Error cleaning up temp file {temp_path}: {e}")
            
            # 2. Check for JSON data with base64 audio
            elif request.is_json:
                data = request.json
                if not data:
                    return jsonify({
                        'success': False,
                        'error': "Empty JSON request"
                    }), 400
                
                model_id = data.get('model_id')
                audio_data_b64 = data.get('audio_data')
                
                if not model_id or not audio_data_b64:
                    return jsonify({
                        'success': False,
                        'error': "Missing required parameters: 'model_id' and 'audio_data'"
                    }), 400
                
                # Decode base64 audio
                try:
                    audio_data_bytes = base64.b64decode(audio_data_b64)
                except Exception as e:
                    logger.error(f"Error decoding base64 audio: {e}")
                    return jsonify({
                        'success': False,
                        'error': "Invalid base64 audio data"
                    }), 400
            
                # Save to temporary file for processing
                temp_path = None # Initialize path variable
                try:
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                        tmp.write(audio_data_bytes)
                        temp_path = tmp.name
                    
                    # Call inference service to classify the audio
                    result = process_audio_file(temp_path, model_id, inference_service)
                
                    # Return result
                    return jsonify({
                        'success': True,
                        'phoneme': result.get('top_class', 'Unknown'),
                        'alternatives': [
                            {'phoneme': alt.get('class', 'Unknown')} 
                            for alt in result.get('alternatives', [])
                        ],
                        'model_id': model_id
                    })
                finally:
                    # Clean up the temporary file
                    if temp_path and os.path.exists(temp_path):
                        try:
                            os.unlink(temp_path)
                            logger.debug(f"Cleaned up temp file: {temp_path}")
                        except OSError as e:
                            logger.error(f"Error cleaning up temp file {temp_path}: {e}")
            
            else:
                return jsonify({
                    'success': False,
                    'error': "No audio data provided. Send a file upload with 'audio' or JSON with 'audio_data' (base64)"
                }), 400
                
        except Exception as e:
            logger.error(f"Error in speech recognition: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'success': False,
                'error': f"Internal server error: {str(e)}"
            }), 500
    
    @custom_speech_api_bp.route('/api/speech/models', methods=['GET'])
    def get_speech_models():
        """
        Get available speech recognition models.
        
        Optional query parameters:
        - user_id: Filter by user ID
        
        Returns:
            JSON list of available models
        """
        try:
            # Get model repo
            model_repo = getattr(custom_speech_api_bp, 'model_repo', 
                              getattr(current_app, 'model_repo', None))
            
            if not model_repo:
                logger.error("No model repository available for speech models")
                return jsonify({
                    'success': False,
                    'error': "Service unavailable"
                }), 503
            
            # Get user_id from query params (optional)
            user_id = request.args.get('user_id')
            
            # Get models
            if user_id:
                models = model_repo.get_models_by_user(user_id)
            else:
                models = model_repo.get_all_models()
            
            # Format for response
            model_list = []
            for model in models:
                model_info = {
                    'id': model.id,
                    'name': model.name,
                    'description': getattr(model, 'description', ''),
                    'created_at': str(getattr(model, 'created_at', '')),
                    'user_id': getattr(model, 'user_id', '')
                }
                
                # Add dictionary name if available
                if hasattr(model, 'dictionary_id') and hasattr(current_app, 'dictionary_service'):
                    try:
                        dictionary = current_app.dictionary_service.get_dictionary(model.dictionary_id)
                        if dictionary:
                            model_info['dictionary_name'] = dictionary.name
                    except:
                        pass
                
                model_list.append(model_info)
            
            return jsonify({
                'success': True,
                'models': model_list
            })
                
        except Exception as e:
            logger.error(f"Error getting speech models: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'success': False,
                'error': f"Internal server error: {str(e)}"
            }), 500
    
    return custom_speech_api_bp 

def process_audio_file(file_path, model_id, inference_service):
    """
    Process an audio file and return classification results.
    Finds model context first using ModelRepository.

    Args:
        file_path: Path to the audio file
        model_id: ID of the model to use
        inference_service: The inference service to use

    Returns:
        Classification results dictionary or raises an error.
    """
    model = None

    try:
        model_repo = getattr(inference_service, 'model_repo', None)
        if not model_repo:
            logger.error("Model repository not found within InferenceService context.")
            raise ValueError("Internal server error: Model repository configuration.")

        logger.debug(f"Attempting to find model context using model_repo.find_model_by_id for ID: {model_id}")
        # --- Ensure find_model_by_id EXISTS in ModelRepository and USE IT ---
        if not hasattr(model_repo, 'find_model_by_id'):
             logger.error("ModelRepository does not have the required 'find_model_by_id' method.")
             raise NotImplementedError("Model lookup by ID is not implemented in ModelRepository.")

        model = model_repo.find_model_by_id(model_id)

        if not model:
            logger.error(f"Model with ID {model_id} could not be found.")
            raise ValueError(f"Model not found: {model_id}")

        user_id = getattr(model, 'user_id', None)
        dictionary_id = getattr(model, 'dictionary_id', None)

        if not user_id or not dictionary_id:
            logger.error(f"Found model {model_id} but it's missing user_id or dictionary_id in its metadata.")
            raise ValueError(f"Incomplete metadata for model {model_id}")

        logger.info(f"Found context for model {model_id}: User={user_id}, Dict={dictionary_id}")

        # --- Now call the correct inference service method ---
        result = inference_service.predict_file(user_id, dictionary_id, model_id, file_path)
        # Ensure predict_file returns a dictionary or handle None if necessary
        if result is None:
            logger.error(f"inference_service.predict_file returned None for model {model_id}")
            raise RuntimeError("Prediction failed unexpectedly.") # Or a more specific error

        return result

    except ValueError as ve:
        logger.error(f"Value error processing audio for model {model_id}: {ve}")
        raise
    except FileNotFoundError as fnf:
        logger.error(f"Audio file not found by inference service: {fnf}")
        raise
    except NotImplementedError as nie: # Catch if find_model_by_id is missing
        logger.error(f"Model lookup failed: {nie}")
        raise # Re-raise to cause 500 error with specific message
    except Exception as e:
        logger.error(f"Unexpected error processing audio file for model {model_id}: {e}", exc_info=True)
        raise RuntimeError(f"Error during audio processing or prediction: {e}") from e 