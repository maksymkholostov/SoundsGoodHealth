# backend/app/routes/inference_routes.py
"""
Routes related to model inference (prediction/classification).
"""
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
# from flask_jwt_extended import jwt_required, get_jwt_identity # Keep if JWT needed, remove if only session
import os # For checking template existence
import tempfile # Add tempfile import
from pathlib import Path # Add Path import
from datetime import datetime # Add datetime import
import time

# Publish prediction events to SSE stream
from backend.app.api.prediction_events import publish_prediction_event
# Removed import of utils.id_mapper as it's no longer needed

# Create blueprint for WEB routes
inference_web_bp = Blueprint('inference_web', __name__) # Correct name for web blueprint

# --- Inference Pages ---

@inference_web_bp.route('/predict') # Primary route
@login_required
def inference_page():
    """Serve the inference/prediction page (data loaded/actions via API)."""
    # Ensure template exists
    template_path = os.path.join(current_app.template_folder, 'predict.html')
    if not os.path.exists(template_path):
        current_app.logger.error("Template file not found: %s", template_path)
        return "Error: Inference page template not found.", 404
    
    # Pass current_user to the template context. 
    # We don't know the dictionary yet, so pass None for current_dictionary_id.
    return render_template(
        'predict.html',
        current_user=current_user,
        current_dictionary_id=None # Dictionary will be selected by user on the page
    )

@inference_web_bp.route('/predict_hub') # New route for predict hub
@login_required
def predict_hub():
    """Serve the predict hub page."""
    # Ensure template exists
    template_path = os.path.join(current_app.template_folder, 'predict_hub.html')
    if not os.path.exists(template_path):
        current_app.logger.error("Template file not found: %s", template_path)
        return "Error: Predict hub page template not found.", 404
    
    return render_template('predict_hub.html')


# --- Inference API Endpoints (Hosted under Web Blueprint) ---
# Note: The original file had the API endpoint here too.
# It might be cleaner to move this API endpoint entirely to backend/app/api/inference.py
# and register it under inference_api_bp. However, keeping it here for now
# to match the file structure implied by the error. If moved later, remove this section.

@inference_web_bp.route('/api/inference/classify', methods=['POST']) # Use web blueprint
@login_required
def api_classify_audio():
    """API: Classify an audio recording using a specified model (session auth)."""
    user_id = current_user.id
    dictionary_id = request.form.get('dictionary_id')
    model_id = request.form.get('model_id')
    audio_file = request.files.get('audio')

    # Validation
    if not audio_file:
        return jsonify({"success": False, "error": "Missing audio file ('audio' field)"}), 400
    if not dictionary_id:
        # Dictionary context might be needed to know which classes are relevant
        return jsonify({"success": False, "error": "Missing dictionary context ('dictionary_id' field)"}), 400
    if not model_id:
        return jsonify({"success": False, "error": "Missing model identifier ('model_id' field)"}), 400

    # --- DEBUGGING: Log current_app contents ---
    current_app.logger.debug(f"[api_classify_audio] Checking for inference_service. current_app type: {type(current_app)}")
    current_app.logger.debug(f"[api_classify_audio] hasattr(current_app, 'inference_service'): {hasattr(current_app, 'inference_service')}")
    if hasattr(current_app, 'inference_service'):
        current_app.logger.debug(f"[api_classify_audio] current_app.inference_service type: {type(current_app.inference_service)}")
        current_app.logger.debug(f"[api_classify_audio] hasattr(inference_service, 'predict_file'): {hasattr(current_app.inference_service, 'predict_file')}")
    # --- END DEBUGGING ---

    # Check if inference service is available
    if not hasattr(current_app, 'inference_service') or not hasattr(current_app.inference_service, 'predict_file'):
        current_app.logger.error("API Classify Error: inference_service or predict_file method not available.")
        return jsonify({"success": False, "error": "Inference service is currently unavailable"}), 503

    temp_audio_path = None
    try:
        # --- Save uploaded audio to a temporary file --- 
        if not audio_file.filename:
             # Give it a default name if none provided
             audio_file.filename = f"upload_{datetime.now().strftime('%Y%m%d%H%M%S')}.wav"
             
        # Create a temporary file, ensuring it gets deleted
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(audio_file.filename).suffix or '.wav') as temp_file:
            audio_file.save(temp_file.name)
            temp_audio_path = temp_file.name
            current_app.logger.debug(f"Saved uploaded audio chunk to temp file: {temp_audio_path}")
        # --- End Save Temp File ---

        # Delegate classification to the InferenceService using the temp file path
        result = current_app.inference_service.predict_file(
            user_id=user_id, 
            dictionary_id=dictionary_id, 
            model_id=model_id, 
            audio_file_path=temp_audio_path # Pass the path to the temporary file
        )
        
        # --- Standardize Response Format --- 
        # predict_file returns {'prediction': {...}, 'model_id': ..., 'classes': [list_of_class_ids], ...}
        # The frontend expects {"success": True, "predictions": [ {"class": ..., "confidence": ...}, ... ], "class_names": [list_of_names] }
        if isinstance(result, dict) and 'prediction' in result:
            # --- Corrected Prediction Formatting ---
            formatted_predictions = []
            # prediction_dict is NAME -> probability (e.g., {'Eh': 0.3, 'Oh': 0.7})
            prediction_dict = result.get('prediction', {})
            
            current_app.logger.debug(f"[api_classify_audio] Formatting predictions from service: {prediction_dict}")

            for class_name, probability in prediction_dict.items():
                # Generate class ID from name (follows cls_<lowercase_name> convention)
                class_id = f"cls_{class_name.lower()}"
                
                formatted_predictions.append({
                    "class":      class_name,
                    "class_id":   class_id,
                    "confidence": float(probability)
                })

            # Sort predictions by confidence (descending) 
            prediction_list_sorted = sorted(formatted_predictions, key=lambda x: x['confidence'], reverse=True)
            # --- End Corrected Prediction Formatting ---
            
            # Map class IDs in 'classes' to names for feedback options
            class_ids = result.get('classes', [])
            class_names_for_feedback = []
            if class_ids and hasattr(current_app, 'dictionary_service'):
                dictionary_service = current_app.dictionary_service
                for class_id in class_ids:
                    try:
                        class_obj = dictionary_service.get_global_class_by_id(class_id)
                        if class_obj and class_obj.name:
                            class_names_for_feedback.append(class_obj.name)
                        else:
                            current_app.logger.warning(f"Could not find name for class ID {class_id} when preparing feedback options. Skipping.")
                    except Exception as lookup_e:
                        current_app.logger.error(f"Error looking up class name for ID {class_id} for feedback: {lookup_e}")
            else:
                current_app.logger.warning(f"Could not map class IDs to names for feedback: Missing 'classes' in result or DictionaryService unavailable.")
                class_names_for_feedback = list(result.get('prediction', {}).keys())
            
            # --- ADDED: Log the final payload --- 
            response_payload = {
                "success": True, 
                "predictions": prediction_list_sorted, # Use the correctly formatted list
                "model_used": result.get('model_id'),
                "dictionary_id": result.get('dictionary_id'),
                "class_names": class_names_for_feedback # Keep this for general info if needed
            }
            current_app.logger.debug(f"[api_classify_audio] Sending response payload: {response_payload}")
            # --- END Log --- 

            # Publish SSE prediction event (normalized fields: label/prob)
            try:
                mapped_preds = [
                    {"label": p.get("class"), "prob": float(p.get("confidence", 0.0))}
                    for p in prediction_list_sorted
                ]
                publish_prediction_event({
                    'event': 'prediction',
                    'timestamp': time.time(),
                    'dictionary_id': response_payload.get('dictionary_id') or dictionary_id,
                    'model_id': response_payload.get('model_used') or model_id,
                    'result': { 'predictions': mapped_preds }
                })
            except Exception as _e:
                # Do not fail the API if publish fails
                current_app.logger.debug(f"[api_classify_audio] SSE publish skipped/failed: {_e}")
            
            return jsonify(response_payload)
        else:
            # Handle unexpected result format from service
            current_app.logger.error(f"Unexpected result format from predict_file: {result}")
            return jsonify({"success": False, "error": "Internal error during prediction processing."}), 500
        # --- End Standardize Response --- 

    except FileNotFoundError as model_e: 
        current_app.logger.warning(f"API Classify Error: Model '{model_id}' or audio file '{temp_audio_path}' not found: {model_e}") 
        return jsonify({"success": False, "error": f"Model '{model_id}' not found or inaccessible."}), 404
    except ValueError as audio_e: 
        current_app.logger.warning(f"API Classify Error: Invalid audio file or parameters: {audio_e}") 
        return jsonify({"success": False, "error": f"Invalid audio file or parameters: {audio_e}"}), 400
    except Exception as e:
        current_app.logger.exception(f"API Error classifying audio for dict {dictionary_id}, model {model_id}: {e}") 
        return jsonify({"success": False, "error": "An unexpected error occurred during classification."}), 500
    finally:
        # --- Ensure temporary file is deleted --- 
        if temp_audio_path and os.path.exists(temp_audio_path):
             try:
                 os.unlink(temp_audio_path)
                 current_app.logger.debug(f"Deleted temporary audio file: {temp_audio_path}")
             except OSError as unlink_e:
                 current_app.logger.error(f"Error deleting temporary audio file {temp_audio_path}: {unlink_e}")
        # --- End Cleanup ---


def init_inference_web_routes(inference_service):
    """
    Initialize inference web routes with the needed services.
    
    Args:
        inference_service: InferenceService instance
        
    Returns:
        Configured Blueprint
    """
    return inference_web_bp

