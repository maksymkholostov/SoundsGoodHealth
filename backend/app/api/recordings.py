from flask import Blueprint, request, jsonify, current_app
import logging
import numpy as np
import base64
import io
import tempfile
import os
from typing import Dict, List, Any
from backend.app.ml.utils.audio_utils import load_audio_from_bytes

from ..services.recording_service import RecordingService
from ..services.processing_service import ProcessingService
from ..core.repositories.dictionary_repo import DictionaryRepository

logger = logging.getLogger(__name__)

recording_bp = Blueprint('recording', __name__)

def init_recording_routes(recording_service: RecordingService, processing_service: ProcessingService) -> Blueprint:
    """
    Initialize recording routes with the recording service.
    
    Args:
        recording_service: Instance of RecordingService
        processing_service: Instance of ProcessingService
        
    Returns:
        Configured Blueprint
    """
    # Check if the blueprint is already initialized to prevent registration errors
    if hasattr(recording_bp, "_initialized") and recording_bp._initialized:
        return recording_bp
        
    # Mark as initialized to prevent double registration
    recording_bp._initialized = True
    
    # Helper function to get class_id from class_name
    def get_class_id(class_name: str) -> str:
        """Get the global class ID for a class name."""
        dictionary_repo = current_app.dictionary_service.dictionary_repo
        sound_class = dictionary_repo.get_class_by_name(class_name)
        if not sound_class:
            raise ValueError(f"Class not found: {class_name}")
        return sound_class.id
    
    @recording_bp.route('/api/recordings/by-class/<user_id>/<class_name>', methods=['GET'])
    def get_recordings_by_class(user_id: str, class_name: str) -> Dict[str, Any]:
        """Get all recordings for a class."""
        try:
            # Get the class_id from class_name
            class_id = get_class_id(class_name)
            
            # Get recordings for this class and user
            recordings = recording_service.find_recordings(
                class_id=class_id,
                user_id=user_id
            )
            
            # Convert recordings to dictionaries for JSON response
            recording_dicts = [recording.to_dict() for recording in recordings]
            
            return jsonify({
                'success': True,
                'recordings': recording_dicts
            })
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400
        except Exception as e:
            logger.error("Error getting recordings: %s", e)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @recording_bp.route('/api/recordings/<recording_id>', methods=['GET'])
    def get_recording(recording_id: str) -> Dict[str, Any]:
        """Get a specific recording by ID."""
        try:
            recording = recording_service.get_recording_by_id(recording_id)
            
            if not recording:
                return jsonify({
                    'success': False,
                    'error': f"Recording {recording_id} not found"
                }), 404
            
            return jsonify({
                'success': True,
                'recording': recording.to_dict()
            })
        except Exception as e:
            logger.error("Error getting recording: %s", e)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @recording_bp.route('/api/recordings/<user_id>/<class_name>', methods=['POST'])
    def create_recording(user_id: str, class_name: str) -> Dict[str, Any]:
        """Create a new recording from uploaded audio file."""
        try:
            # Get the class_id from class_name
            class_id = get_class_id(class_name)
            
            # Check if file was uploaded
            if 'audio' not in request.files:
                return jsonify({
                    'success': False,
                    'error': "No audio file provided"
                }), 400
            
            audio_file = request.files['audio']
            
            # Read the file content
            audio_data = audio_file.read()
            
            # Save the recording
            success, recording = recording_service.create_raw_recording(
                user_id=user_id,
                class_id=class_id,
                audio_data=audio_data
            )
            
            if not success or not recording:
                return jsonify({
                    'success': False,
                    'error': "Failed to save recording"
                }), 500
            
            return jsonify({
                'success': True,
                'recording': recording.to_dict()
            })
                
        except ValueError as e:
            logger.error("Validation error in create_recording: %s", e)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400
        except Exception as e:
            logger.error("Error creating recording: %s", e)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @recording_bp.route('/api/recordings/stream/<user_id>/<class_name>', methods=['POST'])
    def create_recording_stream(user_id: str, class_name: str) -> Dict[str, Any]:
        """Create a new recording from streaming audio data."""
        try:
            # Get the class_id from class_name
            class_id = get_class_id(class_name)
            
            # Get the JSON data
            data = request.json
            
            # Validate required fields
            if 'audio_data' not in data:
                return jsonify({
                    'success': False,
                    'error': "Missing required field: audio_data"
                }), 400
            
            # Decode base64 audio
            audio_data_b64 = data['audio_data']
            audio_data_bytes = base64.b64decode(audio_data_b64)
            
            # Save the recording
            success, recording = recording_service.create_raw_recording(
                user_id=user_id,
                class_id=class_id,
                audio_data=audio_data_bytes
            )
            
            if not success or not recording:
                return jsonify({
                    'success': False,
                    'error': "Failed to save recording"
                }), 500
            
            return jsonify({
                'success': True,
                'recording': recording.to_dict()
            })
        except ValueError as e:
            logger.error("Validation error in create_recording_stream: %s", e)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400
        except Exception as e:
            logger.error("Error creating recording from stream: %s", e)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @recording_bp.route('/api/recordings/<recording_id>', methods=['DELETE'])
    def delete_recording(recording_id: str) -> Dict[str, Any]:
        """Delete a recording by ID."""
        try:
            success = recording_service.delete_recording(recording_id)
            
            if not success:
                return jsonify({
                    'success': False,
                    'error': f"Failed to delete recording {recording_id}"
                }), 404
            
            return jsonify({
                'success': True,
                'message': f"Recording {recording_id} deleted successfully"
            })
        except Exception as e:
            logger.error("Error deleting recording: %s", e)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @recording_bp.route('/api/recordings/process/<recording_id>', methods=['POST'])
    def process_recording(recording_id: str) -> Dict[str, Any]:
        """Process a raw recording to extract segments."""
        try:
            # Get processing parameters from request
            data = request.json or {}
            min_segment_length = data.get('min_segment_length', 0.2)
            max_segment_length = data.get('max_segment_length', 2.0)
            silence_threshold = data.get('silence_threshold', 0.02)
            
            # Process the recording using the updated ProcessingService method
            segments = processing_service.process_recording(
                recording_id=recording_id,
                min_segment_length=min_segment_length,
                max_segment_length=max_segment_length,
                silence_threshold=silence_threshold
            )
            
            return jsonify({
                'success': True,
                'segments': segments
            })
        except ValueError as e:
            logger.error("Validation error in process_recording: %s", e)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400
        except Exception as e:
            logger.error("Error processing recording: %s", e)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @recording_bp.route('/api/segments/pending/<user_id>/<class_name>', methods=['GET'])
    def get_pending_segments(user_id: str, class_name: str) -> Dict[str, Any]:
        """Get pending segments for a class."""
        try:
            # Get the class_id from class_name
            class_id = get_class_id(class_name)
            
            # Get pending segments for this class and user
            segments = processing_service.get_pending_segments(
                class_id=class_id,
                user_id=user_id
            )
            
            # Convert segments to dictionaries for JSON response
            segment_dicts = [segment.to_dict() for segment in segments]
            
            return jsonify({
                'success': True,
                'segments': segment_dicts
            })
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400
        except Exception as e:
            logger.error("Error getting pending segments: %s", e)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @recording_bp.route('/api/segments/verify/<segment_id>', methods=['POST'])
    def verify_segment(segment_id: str) -> Dict[str, Any]:
        """Verify or reject a segment."""
        try:
            data = request.json
            
            # Validate data
            if 'approved' not in data:
                return jsonify({
                    'success': False,
                    'error': "Approval status is required"
                }), 400
            
            approved = data['approved']
            
            # Verify the segment using the ProcessingService
            success = processing_service.verify_segment(segment_id, approved)
            
            if not success:
                return jsonify({
                    'success': False,
                    'error': f"Failed to {'approve' if approved else 'reject'} segment {segment_id}"
                }), 404
            
            return jsonify({
                'success': True,
                'message': f"Segment {segment_id} {'approved' if approved else 'rejected'} successfully"
            })
        except ValueError as e:
            logger.error("Validation error in verify_segment: %s", e)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400
        except Exception as e:
            logger.error("Error verifying segment: %s", e)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @recording_bp.route('/api/segments/verified/<user_id>/<class_name>', methods=['GET'])
    def get_verified_segments(user_id: str, class_name: str) -> Dict[str, Any]:
        """Get verified segments (gold recordings) for a class."""
        try:
            # Get the class_id from class_name
            class_id = get_class_id(class_name)
            
            # Get gold recordings for this class and user
            recordings = processing_service.get_gold_recordings(
                class_id=class_id,
                user_id=user_id
            )
            
            # Convert recordings to dictionaries for JSON response
            recording_dicts = [recording.to_dict() for recording in recordings]
            
            return jsonify({
                'success': True,
                'recordings': recording_dicts
            })
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400
        except Exception as e:
            logger.error("Error getting verified segments: %s", e)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # Legacy augmentation routes - need to be updated separately
    @recording_bp.route('/augmentation/options', methods=['GET'])
    def get_augmentation_options():
        """Get available augmentation options and their configuration ranges."""
        try:
            # Get augmentation service from current app
            augmentation_service = current_app.augmentation_service
            
            # Get available augmentation options
            options = augmentation_service.get_augmentation_options()
            
            return jsonify(options), 200
        except Exception as e:
            current_app.logger.error("Error getting augmentation options: %s", str(e))
            return jsonify({"error": str(e)}), 500
    
    @recording_bp.route('/augmentation/status/<user_id>/<class_name>', methods=['GET'])
    def get_augmentation_status(user_id, class_name):
        """Get augmentation status for a specific class."""
        try:
            # Get the class_id from class_name
            try:
                class_id = get_class_id(class_name)
            except ValueError:
                return jsonify({"error": f"Class not found: {class_name}"}), 404
                
            # Get augmentation service from current app
            augmentation_service = current_app.augmentation_service
            
            # Get augmentation status (needs updated to work with new model)
            status = {"status": "unavailable", "message": "Augmentation endpoint needs to be updated to new model structure"}
            
            return jsonify(status), 200
        except Exception as e:
            current_app.logger.error("Error getting augmentation status: %s", str(e))
            return jsonify({"error": str(e)}), 500
    
    @recording_bp.route('/augmentation/perform', methods=['POST'])
    def perform_augmentation():
        """Perform augmentation for selected recordings."""
        # This endpoint needs to be updated to work with the new model structure
        return jsonify({
            "error": "This endpoint needs to be updated to work with the new model structure"
        }), 501
    
    return recording_bp
