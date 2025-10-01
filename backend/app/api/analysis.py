"""
API endpoints for data analysis operations.

This module provides endpoints for analyzing recordings, training metrics,
and inference results, and retrieving analysis data.
"""
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging

analysis_bp = Blueprint('analysis', __name__)
logger = logging.getLogger(__name__)

@analysis_bp.route('/recording/<dictionary_id>/<recording_id>', methods=['GET'])
@jwt_required()
def analyze_recording(dictionary_id, recording_id):
    """
    Analyze a single recording.
    
    Query parameters:
    - include_visualizations: Whether to include visualizations (default: true)
    """
    user_id = get_jwt_identity()
    include_visualizations = request.args.get('include_visualizations', 'true').lower() == 'true'
    
    try:
        analysis_service = current_app.analysis_service
        result = analysis_service.analyze_recording(
            user_id, dictionary_id, recording_id, include_visualizations
        )
        
        if "error" in result:
            return jsonify({"error": result["error"]}), 404
            
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error analyzing recording: {str(e)}")
        return jsonify({"error": "Failed to analyze recording"}), 500

@analysis_bp.route('/recordings/<dictionary_id>', methods=['GET'])
@jwt_required()
def analyze_dictionary_recordings(dictionary_id):
    """
    Analyze all recordings in a dictionary.
    
    Query parameters:
    - recording_type: Type of recordings to analyze (default: 'gold')
    - include_visualizations: Whether to include visualizations (default: false)
    """
    user_id = get_jwt_identity()
    recording_type = request.args.get('recording_type', 'gold')
    include_visualizations = request.args.get('include_visualizations', 'false').lower() == 'true'
    
    if recording_type not in ['gold', 'raw', 'augmented']:
        return jsonify({"error": "Invalid recording_type. Must be 'gold', 'raw', or 'augmented'"}), 400
    
    try:
        analysis_service = current_app.analysis_service
        result = analysis_service.analyze_dictionary_recordings(
            user_id, dictionary_id, recording_type, include_visualizations
        )
        
        if "error" in result:
            return jsonify({"error": result["error"]}), 404
            
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error analyzing dictionary recordings: {str(e)}")
        return jsonify({"error": "Failed to analyze dictionary recordings"}), 500

@analysis_bp.route('/training/<dictionary_id>/<model_id>/history', methods=['POST'])
@jwt_required()
def analyze_training_history(dictionary_id, model_id):
    """
    Analyze training history data.
    
    Request body:
    {
        "history": {
            "loss": [0.5, 0.4, 0.3, ...],
            "accuracy": [0.6, 0.7, 0.8, ...],
            ...
        }
    }
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data or "history" not in data:
        return jsonify({"error": "history data is required"}), 400
    
    try:
        analysis_service = current_app.analysis_service
        result = analysis_service.analyze_training_history(
            user_id, dictionary_id, model_id, data["history"]
        )
        
        if "error" in result:
            return jsonify({"error": result["error"]}), 400
            
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error analyzing training history: {str(e)}")
        return jsonify({"error": "Failed to analyze training history"}), 500

@analysis_bp.route('/training/<dictionary_id>/<model_id>/performance', methods=['POST'])
@jwt_required()
def analyze_model_performance(dictionary_id, model_id):
    """
    Analyze model performance based on predictions.
    
    Request body:
    {
        "true_labels": ["class1", "class2", ...],
        "predicted_labels": ["class1", "class2", ...],
        "class_names": ["class1", "class2", ...]
    }
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "prediction data is required"}), 400
    
    if "true_labels" not in data or "predicted_labels" not in data:
        return jsonify({"error": "true_labels and predicted_labels are required"}), 400
    
    if len(data["true_labels"]) != len(data["predicted_labels"]):
        return jsonify({"error": "true_labels and predicted_labels must have the same length"}), 400
    
    try:
        analysis_service = current_app.analysis_service
        result = analysis_service.analyze_model_performance(
            user_id, 
            dictionary_id, 
            model_id,
            data["true_labels"],
            data["predicted_labels"],
            data.get("class_names")
        )
        
        if "error" in result:
            return jsonify({"error": result["error"]}), 400
            
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error analyzing model performance: {str(e)}")
        return jsonify({"error": "Failed to analyze model performance"}), 500

@analysis_bp.route('/training/<dictionary_id>/compare', methods=['POST'])
@jwt_required()
def compare_models(dictionary_id):
    """
    Compare multiple models based on their performance.
    
    Request body:
    {
        "model_ids": ["model1", "model2", ...],
        "metric": "accuracy"
    }
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data or "model_ids" not in data:
        return jsonify({"error": "model_ids are required"}), 400
    
    try:
        analysis_service = current_app.analysis_service
        result = analysis_service.compare_models(
            user_id,
            dictionary_id,
            data["model_ids"],
            data.get("metric", "accuracy")
        )
        
        if "error" in result:
            return jsonify({"error": result["error"]}), 400
            
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error comparing models: {str(e)}")
        return jsonify({"error": "Failed to compare models"}), 500

@analysis_bp.route('/inference/<dictionary_id>/<model_id>/<session_id>', methods=['POST'])
@jwt_required()
def analyze_inference_session(dictionary_id, model_id, session_id):
    """
    Analyze results from an inference session.
    
    Request body:
    {
        "results": [
            {
                "prediction": "class1",
                "confidence": 0.9,
                "ground_truth": "class1",  # Optional
                "timestamp": "2023-01-01T12:00:00"  # Optional
            },
            ...
        ]
    }
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data or "results" not in data:
        return jsonify({"error": "inference results are required"}), 400
    
    try:
        analysis_service = current_app.analysis_service
        result = analysis_service.analyze_inference_session(
            user_id,
            dictionary_id,
            model_id,
            session_id,
            data["results"]
        )
        
        if "error" in result:
            return jsonify({"error": result["error"]}), 400
            
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error analyzing inference session: {str(e)}")
        return jsonify({"error": "Failed to analyze inference session"}), 500

@analysis_bp.route('/inference/<dictionary_id>/progress', methods=['GET'])
@jwt_required()
def analyze_user_progress(dictionary_id):
    """
    Analyze user progress across multiple inference sessions.
    
    Query parameters:
    - metric: Metric to track progress for (default: 'overall_accuracy')
    """
    user_id = get_jwt_identity()
    metric = request.args.get('metric', 'overall_accuracy')
    
    try:
        analysis_service = current_app.analysis_service
        result = analysis_service.analyze_user_progress(
            user_id,
            dictionary_id,
            metric
        )
        
        if "error" in result:
            return jsonify({"error": result["error"]}), 404
            
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error analyzing user progress: {str(e)}")
        return jsonify({"error": "Failed to analyze user progress"}), 500

@analysis_bp.route('/inference/<dictionary_id>/errors', methods=['GET'])
@jwt_required()
def detect_error_patterns(dictionary_id):
    """
    Detect patterns in incorrect predictions.
    
    Query parameters:
    - model_id: Model ID (optional)
    - session_id: Session ID (optional)
    """
    user_id = get_jwt_identity()
    model_id = request.args.get('model_id', None)
    session_id = request.args.get('session_id', None)
    
    try:
        analysis_service = current_app.analysis_service
        result = analysis_service.detect_error_patterns(
            user_id,
            dictionary_id,
            model_id,
            session_id
        )
        
        if "error" in result:
            return jsonify({"error": result["error"]}), 404
            
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error detecting error patterns: {str(e)}")
        return jsonify({"error": "Failed to detect error patterns"}), 500
