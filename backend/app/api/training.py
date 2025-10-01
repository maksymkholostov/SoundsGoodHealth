import logging
from typing import Dict, Any
from flask import Blueprint, request, jsonify

from ..services.training_service import TrainingService

logger = logging.getLogger(__name__)

training_bp = Blueprint('training', __name__)

def init_training_routes(training_service: TrainingService) -> Blueprint:
    """
    Initialize training routes with the training service.
    
    Args:
        training_service: Instance of TrainingService
        
    Returns:
        Configured Blueprint
    """
    # Check if the blueprint is already initialized to prevent registration errors
    if hasattr(training_bp, "_initialized") and training_bp._initialized:
        return training_bp
        
    # Mark as initialized to prevent double registration
    training_bp._initialized = True
    
    @training_bp.route('/api/models/types', methods=['GET'])
    # DB-OPERATION: read model
    def get_available_model_types() -> Dict[str, Any]:
        """Get the list of available model types."""
        try:
            models = training_service.get_available_models()
            return jsonify({
                'success': True,
                'model_types': models
            })
        except Exception as e:
            logger.error(f"Error getting available model types: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @training_bp.route('/api/models/train', methods=['POST'])
    def train_model() -> Dict[str, Any]:
        """Train a model with the specified parameters."""
        try:
            data = request.json
            
            # Validate required fields
            required_fields = ['user_id', 'dictionary_id', 'model_type', 'model_name']
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        'success': False,
                        'error': f"Missing required field: {field}"
                    }), 400
            
            # Get optional parameters
            feature_version = data.get('feature_version', 'v0.1')
            use_augmented = data.get('use_augmented', True)
            params = data.get('params', None)
            
            # Train the model
            result = training_service.train_model(
                user_id=data['user_id'],
                dictionary_id=data['dictionary_id'],
                model_type=data['model_type'],
                model_name=data['model_name'],
                feature_version=feature_version,
                use_augmented=use_augmented,
                params=params
            )
            
            return jsonify({
                'success': True,
                'model': result
            })
        except ValueError as e:
            logger.error(f"Validation error in train_model: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400
        except Exception as e:
            logger.error(f"Error training model: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @training_bp.route('/api/models/<user_id>/<dictionary_id>', methods=['GET'])
    # DB-OPERATION: read user
    def get_models(user_id: str, dictionary_id: str) -> Dict[str, Any]:
        """Get all trained models for a dictionary."""
        try:
            models = training_service.get_trained_models(user_id, dictionary_id)
            
            return jsonify({
                'success': True,
                'models': models
            })
        except Exception as e:
            logger.error(f"Error getting models: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @training_bp.route('/api/models/<user_id>/<dictionary_id>/<model_id>', methods=['GET'])
    # DB-OPERATION: read user
    def get_model(user_id: str, dictionary_id: str, model_id: str) -> Dict[str, Any]:
        """Get a specific model by ID."""
        try:
            model = training_service.get_model(user_id, dictionary_id, model_id)
            
            if not model:
                return jsonify({
                    'success': False,
                    'error': f"Model {model_id} not found"
                }), 404
            
            return jsonify({
                'success': True,
                'model': model
            })
        except Exception as e:
            logger.error(f"Error getting model: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @training_bp.route('/api/models/<user_id>/<dictionary_id>/<model_id>', methods=['DELETE'])
    # DB-OPERATION: delete user
    def delete_model(user_id: str, dictionary_id: str, model_id: str) -> Dict[str, Any]:
        """Delete a specific model."""
        try:
            success = training_service.delete_model(user_id, dictionary_id, model_id)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f"Model {model_id} deleted successfully"
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f"Failed to delete model {model_id}"
                }), 404
        except Exception as e:
            logger.error(f"Error deleting model: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    return training_bp