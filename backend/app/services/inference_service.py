import os
import logging
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime
import json
import soundfile as sf

from ..core.models.model import ModelVersion, ModelType, ModelStatus
from ..core.repositories.model_repo import ModelRepository
from ..core.repositories.feature_repo import FeatureRepository
from ..core.repositories.dictionary_repo import DictionaryRepository
from ..services.file_service import FileService
from ..services.feature_service import FeatureService
from ..ml.inference.predictor import ModelPredictor, SVMPredictor, RandomForestPredictor, CNNPredictor
from ..ml.inference.cnn1d_predictor import CNN1DPredictor
from backend.app.ml.features.extractor import FeatureExtractor, FullFeatureExtractor
from backend.app.ml.utils.audio_utils import ensure_audio_format, pad_audio, load_audio_from_file
import tempfile
from backend.app.ml.preprocessing.segmentation import AudioSegmenter
from backend.app.ml.preprocessing.normalization import AudioNormalizer
from backend.app.ml.preprocessing.filtering import AudioFilter
import pyloudnorm as pyln
try:
    import noisereduce as nr
    NOISEREDUCE_AVAILABLE = True
except ImportError:
    NOISEREDUCE_AVAILABLE = False

# Custom exception for service-level processing errors
class ProcessingServiceError(Exception):
    pass

logger = logging.getLogger(__name__)

class InferenceService:
    """Service for using trained models to perform inference on new audio."""
    
    # --- ADDED: Toggle flags for preprocessing steps --- 
    ENABLE_FILTERING = True
    ENABLE_LUFS_NORMALIZATION = True  # Enable to match training preprocessing
    ENABLE_NOISE_REDUCTION = False # Keep disabled until profile loading is implemented
    # --- 
    # --- Access control toggle (minimal change) ---
    # When True, models are discoverable/usable across users ("all for one")
    ALLOW_SHARED_MODELS = True
    # ---
    
    def __init__(
        self,
        model_repo: ModelRepository,
        feature_repo: FeatureRepository,
        dictionary_repo: DictionaryRepository,
        file_service: FileService,
        feature_service: FeatureService
    ):
        logger.info("--- Initializing InferenceService START ---") # DEBUG LOG
        self.model_repo = model_repo
        self.feature_repo = feature_repo
        self.dictionary_repo = dictionary_repo
        self.file_service = file_service
        self.feature_service = feature_service
        self.file_manager = file_service.file_manager # Get FileManager from FileService
        self.feature_extractor = FullFeatureExtractor() # Default feature extractor
        self._loaded_models: Dict[str, Tuple[Any, Dict[str, Any]]] = {} # Cache: {model_id: (model_object, metadata)}
        self.logger = logging.getLogger(__name__)
        
        # Initialize processing components needed for inference pipeline
        # Use same defaults as ProcessingService if possible
        self.filter = AudioFilter({
            "use_bandpass": True, 
            "bandpass_low": 80.0, 
            "bandpass_high": 7800.0, 
            "use_pre_emphasis": True
        }) 
        self.normalizer = AudioNormalizer() # Assuming default normalizer is okay
        self.target_lufs = -23.0 # Target for LUFS normalization
        self.target_sample_rate = 16000

        # Initialize model predictors
        self.predictors = {
            ModelType.SVM.value: SVMPredictor(),
            ModelType.RF.value: RandomForestPredictor(),
            ModelType.CNN.value: CNNPredictor(),
            ModelType.CNN1D.value: CNN1DPredictor()
        }
        logger.info("--- Initializing InferenceService END ---") # DEBUG LOG
    
    def predict(
        self,
        user_id: str,
        dictionary_id: str,
        model_id: str,
        audio_data: np.ndarray,
        sample_rate: int = 16000
    ) -> Dict[str, Any]:
        """
        Make a prediction for new audio data using a trained model.
        
        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            model_id: Model ID
            audio_data: Audio data to classify
            sample_rate: Sample rate of the audio
            
        Returns:
            Dictionary with prediction results
        """
        # Get the model metadata
        model = self.model_repo.get_by_id(user_id, dictionary_id, model_id)
        if not model and self.ALLOW_SHARED_MODELS:
            # Fallback: allow using models owned by other users
            self.logger.info(f"Shared models enabled. Searching globally for model {model_id}")
            model = self.model_repo.find_model_by_id(model_id)
            if model and model.dictionary_id != dictionary_id:
                # Safety check: ensure requested dictionary matches model's dictionary
                self.logger.warning(
                    f"Requested dictionary {dictionary_id} does not match model's dictionary {model.dictionary_id}."
                )
                raise ValueError(f"Model {model_id} does not belong to dictionary {dictionary_id}")
        if not model:
            # Ensure this check is robust - does get_by_id return None or raise?
            self.logger.warning(f"Model {model_id} not found for user {user_id}, dict {dictionary_id}")
            raise ValueError(f"Model {model_id} not found") # Or return specific error dict
        
        # Only trained models can be used for inference
        if model.status != ModelStatus.TRAINED:
            self.logger.warning(f"Model {model_id} status is {model.status}, not TRAINED.")
            raise ValueError(f"Model {model_id} is not trained")
        
        # Get the dictionary to get class information
        dictionary = self.dictionary_repo.get_dictionary_by_id(dictionary_id)
        if not dictionary:
            self.logger.warning(f"Dictionary {dictionary_id} not found in repository.")
            raise ValueError(f"Dictionary {dictionary_id} not found")
            
        # Permission check (skip if shared models are enabled)
        if not self.ALLOW_SHARED_MODELS:
            if dictionary.creator_user_id != user_id:
                # TODO: Add admin check if required for inference on others' dicts?
                self.logger.warning(
                    f"User {user_id} attempting inference using dictionary {dictionary_id} owned by {dictionary.creator_user_id}"
                )
                raise PermissionError(
                    f"User does not have permission for dictionary {dictionary_id}"
                )
        
        # Get feature set ID
        feature_set_id = model.feature_set_id
        if not feature_set_id:
            self.logger.error(f"Feature set ID attribute is missing for model {model_id}")
            raise ValueError(f"Configuration error: Feature set ID not found for model {model_id}")

        self.logger.info(f"Using feature set ID: {feature_set_id} for model {model_id}")
        
        target_sr = self.target_sample_rate

        # --- Input Audio Logging --- 
        self.logger.debug(f"[Predict START] Input audio_data - Shape: {getattr(audio_data, 'shape', 'N/A')}, SR: {sample_rate}")
        if isinstance(audio_data, np.ndarray):
            self.logger.debug(f"[Predict Input Stats] dtype: {audio_data.dtype}, Min: {np.min(audio_data):.4f}, Max: {np.max(audio_data):.4f}, Mean: {np.mean(audio_data):.4f}")

        # --- Preprocessing Pipeline --- 
        try:
            # 1. Format Standardization
            standardized_audio, current_sr = ensure_audio_format(audio_data, sample_rate, target_sr=target_sr, normalize=False)
            if current_sr != target_sr:
                self.logger.warning(f"Inference audio SR mismatch. Resampled to {target_sr}")
            self.logger.debug(f"[Predict Post-Format] Shape: {standardized_audio.shape}, Min: {np.min(standardized_audio):.4f}, Max: {np.max(standardized_audio):.4f}")
            
            # 2. Filtering (Conditional)
            filtered_audio = standardized_audio # Default if skipping
            if self.ENABLE_FILTERING:
                try:
                    filtered_audio = self.filter.apply_filters(standardized_audio, target_sr)
                    self.logger.debug(f"[Predict Post-Filter] Applied. Shape: {filtered_audio.shape}, Min: {np.min(filtered_audio):.4f}, Max: {np.max(filtered_audio):.4f}")
                except Exception as filter_err:
                    self.logger.error(f"[Predict Filter] Error applying filters: {filter_err}", exc_info=True)
                    # Fallback to standardized audio if filtering fails
                    filtered_audio = standardized_audio 
            else:
                self.logger.info("[Predict Filter] Filtering DISABLED by flag.")

            # 3. Noise Reduction (Conditional)
            noise_reduced_audio = filtered_audio # Start with filtered (or standardized)
            if self.ENABLE_NOISE_REDUCTION:
                user_noise_profile_clip = None # TODO: Load profile
                if NOISEREDUCE_AVAILABLE and user_noise_profile_clip is not None:
                    try:
                        noise_reduced_audio = nr.reduce_noise(y=filtered_audio, sr=target_sr, y_noise=user_noise_profile_clip, prop_decrease=1.0, stationary=True)
                        self.logger.debug(f"[Predict Post-NR] Applied. Shape: {noise_reduced_audio.shape}, Min {np.min(noise_reduced_audio):.4f}, Max: {np.max(noise_reduced_audio):.4f}")
                    except Exception as nr_err:
                        self.logger.error(f"[Predict NR] Noise reduction failed: {nr_err}", exc_info=True)
                        noise_reduced_audio = filtered_audio # Fallback
                else:
                    self.logger.debug("[Predict NR] Skipping noise reduction (library/profile unavailable).")
            else:
                 self.logger.info("[Predict NR] Noise Reduction DISABLED by flag.")
                 # Ensure noise_reduced_audio uses the output of the previous step
                 noise_reduced_audio = filtered_audio 

            # 4. Padding/Trimming to 1.25s (Always applied for now)
            padded_audio = pad_audio(noise_reduced_audio, target_sr, target_length=1.25)
            if padded_audio is None:
                self.logger.error(f"[Predict Padding] Segment discarded during padding/trimming.")
                raise ValueError("Input audio segment too long after processing")
            self.logger.debug(f"[Predict Post-Pad] Shape: {padded_audio.shape}, Min: {np.min(padded_audio):.4f}, Max: {np.max(padded_audio):.4f}") # Should be 20000 samples

            # 5. LUFS Normalization (Conditional)
            final_audio = padded_audio # Default if skipping
            if self.ENABLE_LUFS_NORMALIZATION:
                try:
                    meter = pyln.Meter(target_sr)
                    loudness = meter.integrated_loudness(padded_audio)
                    if np.isfinite(loudness):
                        gain_db = self.target_lufs - loudness
                        gain_linear = 10.0**(gain_db / 20.0)
                        norm_audio = (padded_audio * gain_linear).astype(np.float32)
                        final_audio = np.clip(norm_audio, -1.0, 1.0)
                        self.logger.debug(f"[Predict Post-LUFS] Applied. Target: {self.target_lufs} LUFS. Original: {loudness:.2f} LUFS, Gain: {gain_db:.2f} dB. Shape: {final_audio.shape}, Min: {np.min(final_audio):.4f}, Max: {np.max(final_audio):.4f}")
                    else:
                        self.logger.warning(f"[Predict LUFS] Could not measure loudness (LUFS: {loudness}). Skipping normalization.")
                        final_audio = padded_audio
                except ImportError:
                    self.logger.error("[Predict LUFS] pyloudnorm not installed. Skipping normalization.")
                    final_audio = padded_audio
                except Exception as norm_err:
                    self.logger.error(f"[Predict LUFS] Error during LUFS normalization: {norm_err}", exc_info=True)
                    final_audio = padded_audio # Fallback
            else:
                 self.logger.info("[Predict LUFS] LUFS Normalization DISABLED by flag.")

        except Exception as e:
            # Catch errors from any preprocessing step not caught individually
            self.logger.error(f"[Predict Preprocessing] Unexpected error: {e}", exc_info=True)
            raise ProcessingServiceError(f"Preprocessing failed: {e}") from e
        # --- END PREPROCESSING --- 

        # --- Feature Extraction --- 
        try:
            features_dict = self.feature_service.extract_features(
                final_audio, target_sr, feature_set_id 
            )
            if not features_dict or not isinstance(features_dict, dict):
                raise ValueError("Feature extraction returned invalid data")
            
            # Log feature details
            self.logger.debug(f"[Predict Features] Extracted keys: {list(features_dict.keys())}")
            for key, value in features_dict.items():
                if isinstance(value, np.ndarray):
                    self.logger.debug(f"[Predict Feature Stats] '{key}' - Shape: {value.shape}, Min: {np.min(value):.4f}, Max: {np.max(value):.4f}, Mean: {np.mean(value):.4f}")
                else:
                    self.logger.debug(f"[Predict Feature Type] '{key}' - Type: {type(value)}")

        except Exception as feat_err:
            self.logger.error(f"[Predict Feature Extraction] Error: {feat_err}", exc_info=True)
            raise ProcessingServiceError(f"Feature extraction failed: {feat_err}") from feat_err
        # --- END Feature Extraction --- 
        
        # --- Feature Reshaping --- 
        try:
            # Determine which feature to use based on model type? Assume Mel for now.
            feature_key_for_model = 'mel_spectrogram'
            features_array = features_dict.get(feature_key_for_model)
            
            if features_array is None:
                self.logger.error(f"Expected feature key '{feature_key_for_model}' not found in extracted features dict for model {model_id}")
                raise ValueError(f"Missing expected feature '{feature_key_for_model}' in extraction results")
            
            if not isinstance(features_array, np.ndarray):
                try: 
                    features_array = np.array(features_array) 
                except Exception as np_err:
                    self.logger.error(f"Could not convert feature data for '{feature_key_for_model}' to numpy array: {np_err}")
                    raise ValueError(f"Invalid feature data format for '{feature_key_for_model}'")
            
            # --- Reshape based on Model Type --- 
            self.logger.debug(f"Original extracted feature '{feature_key_for_model}' shape: {features_array.shape}")
            self.logger.debug(f"Feature statistics - Min: {np.min(features_array):.4f}, Max: {np.max(features_array):.4f}, Mean: {np.mean(features_array):.4f}")
            if model.type == ModelType.CNN:
                # Reshape for CNN (add batch and channel dimensions)
                if features_array.ndim == 2: # (height, width)
                    features_for_prediction = np.expand_dims(np.expand_dims(features_array, axis=0), axis=-1)
                elif features_array.ndim == 3: # Maybe (height, width, channels)?
                     # Should not happen if extractor provides consistent 2D mel spec
                     self.logger.warning(f"CNN inference received 3D feature array {features_array.shape}, attempting to add batch dim -> (1, H, W, C)")
                     features_for_prediction = np.expand_dims(features_array, axis=0) 
                elif features_array.ndim == 4: # Assume (batch, height, width, channels)
                     features_for_prediction = features_array # Assume correct shape
                else:
                    raise ValueError(f"Unsupported feature array dimensions for CNN: {features_array.ndim}")
                self.logger.debug(f"Reshaped features for CNN prediction. Shape: {features_for_prediction.shape}")

            elif model.type == ModelType.CNN1D:
                # Reshape for 1D CNN - it expects flattened mel_spectrogram which it converts to MFCCs
                # The predictor handles MFCC extraction, just pass flattened mel_spectrogram
                if features_array.ndim == 2: # (height, width)
                    features_flat = features_array.flatten()
                    features_for_prediction = np.expand_dims(features_flat, axis=0) 
                else:
                    raise ValueError(f"Unsupported feature array dimensions for CNN1D: {features_array.ndim}")
                self.logger.debug(f"Flattened features for CNN1D prediction. Shape: {features_for_prediction.shape}")

            elif model.type in [ModelType.SVM, ModelType.RF]:
                # Reshape for SVM/RF (flatten features, add batch dimension)
                if features_array.ndim >= 2: # e.g., (height, width) or potentially more dims
                    # Flatten all dimensions except the first (batch, if present, though unlikely here)
                    # Then add batch dim -> (1, num_flattened_features)
                    features_flat = features_array.flatten()
                    features_for_prediction = np.expand_dims(features_flat, axis=0) 
                else:
                     raise ValueError(f"Unsupported feature array dimensions for SVM/RF: {features_array.ndim}")
                self.logger.debug(f"Flattened and reshaped features for {model.type.name} prediction. Shape: {features_for_prediction.shape}")
            
            else:
                 raise ValueError(f"Unsupported model type for feature reshaping: {model.type}")
            # --- End Reshape --- 

        except Exception as reshape_err:
            self.logger.error(f"[Predict Reshape] Error: {reshape_err}", exc_info=True)
            raise ProcessingServiceError(f"Feature reshaping failed: {reshape_err}") from reshape_err
        # --- END Reshape --- 

        # --- Model Loading --- 
        try:
            # Load the trained model artifact path using FileManager
            # Get the specific directory for this model ID
            model_dir_path = self.file_manager.get_specific_model_dir(
                dictionary_id=dictionary_id, 
                model_type_version=model.id # Use the unique model ID as the dir name
            )
            
            # --- CHECKING MODEL PATH & TYPE --- 
            if not model_dir_path.exists() or not model_dir_path.is_dir():
                self.logger.warning(f"Model artifact directory not found at expected path: {model_dir_path}")
                # Optional: Check legacy path if needed
                # legacy_path = ...
                # if legacy_path.exists(): model_dir_path = legacy_path
                # else:
                raise FileNotFoundError(f"Model artifact directory not found at {model_dir_path}")
            
            # Handle CNN/CNN1D (SavedModel directory or weights-only) vs other types (.pkl file)
            if model.type in [ModelType.CNN, ModelType.CNN1D]:
                # Check for different CNN model formats
                saved_model_file = model_dir_path / 'saved_model.pb'
                weights_file = model_dir_path / 'model.weights.h5'
                architecture_file = model_dir_path / 'architecture.json'
                
                if saved_model_file.exists():
                    # Standard SavedModel format
                    self.logger.debug(f"Using {model.type.value} SavedModel directory: {model_dir_path}")
                    path_for_predictor = str(model_dir_path)
                elif weights_file.exists() and architecture_file.exists():
                    # Weights-only format with separate architecture
                    self.logger.debug(f"Using {model.type.value} weights+architecture format: {model_dir_path}")
                    path_for_predictor = str(model_dir_path)
                else:
                    raise FileNotFoundError(f"{model.type.value} model files not found in directory {model_dir_path}. Expected either 'saved_model.pb' or both 'model.weights.h5' and 'architecture.json'") 
            else:
                # For PKL models, construct the full path using filename from metadata
                if not model.filename: # Check if filename exists in metadata
                    raise ValueError(f"Missing filename in metadata for non-CNN model {model.id}")
                # Ensure filename has .pkl extension (handle potential inconsistencies)
                pkl_filename = model.filename if model.filename.endswith('.pkl') else f"{model.filename}.pkl"
                
                full_pkl_path = model_dir_path / pkl_filename
                if not full_pkl_path.is_file():
                    raise FileNotFoundError(f"Model file {pkl_filename} not found inside directory {model_dir_path}")
                self.logger.debug(f"Using PKL model file: {full_pkl_path}")
                path_for_predictor = str(full_pkl_path)
            # --- END PATH CHECKING --- 

            predictor = self.predictors.get(model.type.value)
            if not predictor:
                raise ValueError(f"No predictor available for model type {model.type.value}")
            
            # Load the model
            # self.logger.debug(f"Loading model using predictor: {type(predictor).__name__} from path: {path_for_predictor}")
            trained_model = predictor.load_model(path_for_predictor)
            self.logger.debug(f"[Predict Model Load] Loaded model for {model.type.name}")
        except Exception as load_err:
            self.logger.error(f"[Predict Model Load] Error: {load_err}", exc_info=True)
            raise ProcessingServiceError(f"Model loading failed: {load_err}") from load_err
        # --- END Model Loading --- 
        
        # --- Prediction --- 
        try:
            self.logger.debug(f"[Predict Run] Running predictor with features shape: {features_for_prediction.shape}")
            self.logger.debug(f"[Predict Run] Model classes order: {model.classes}")
            prediction_result = predictor.predict(trained_model, features_for_prediction)
            self.logger.debug(f"[Predict Run] Raw result from predictor: {prediction_result}") # Log raw output
            if prediction_result is None: raise ValueError("Predictor returned None")
        except Exception as pred_err:
             self.logger.error(f"[Predict Run] Error during prediction: {pred_err}", exc_info=True)
             raise ProcessingServiceError(f"Prediction failed: {pred_err}") from pred_err
        # --- END Prediction --- 

        # --- Name Mapping --- 
        try:
            # --- Map prediction indices/IDs to Class Names ---
            named_prediction_result = {}
            # model.classes should contain the list of class IDs in the order the model expects
            class_ids_ordered = model.classes 
            
            # Debug logging
            self.logger.debug(f"[Predict Mapping] Model classes order: {class_ids_ordered}")
            self.logger.debug(f"[Predict Mapping] Prediction result keys: {list(prediction_result.keys())}")
            self.logger.debug(f"[Predict Mapping] Prediction result values: {prediction_result}")
            
            # Assuming predictor.predict returns a dict mapping index (as str) to probability
            # Example: {"0": 0.9, "1": 0.1}
            # Or it might return mapping class_id to probability directly? Let's handle index first.
            
            successful_mapping = True
            for index_str, probability in prediction_result.items():
                try:
                    index = int(index_str)
                    if 0 <= index < len(class_ids_ordered):
                        class_id = class_ids_ordered[index]
                        # Look up the class name using the dictionary repository
                        class_obj = self.dictionary_repo.get_class_by_id(class_id)
                        self.logger.debug(f"[Predict Mapping] Looking up class_id '{class_id}' -> got class_obj: {class_obj}")
                        if class_obj and class_obj.name:
                            named_prediction_result[class_obj.name] = probability
                            self.logger.debug(f"[Predict Mapping] SUCCESS: Mapped index {index} -> class_id {class_id} -> name {class_obj.name} with probability {probability}")
                        else:
                            self.logger.error(f"Could not find class name for ID: {class_id} (at index {index}) in dictionary {dictionary_id}. Using ID as fallback.")
                            named_prediction_result[class_id] = probability # Fallback to ID
                            successful_mapping = False
                    else:
                        self.logger.error(f"Prediction result index {index} is out of bounds for model classes (length {len(class_ids_ordered)}).")
                        # Fallback? Or raise error? Using original key as fallback.
                        named_prediction_result[index_str] = probability 
                        successful_mapping = False

                except (ValueError, TypeError) as e:
                    # Handle cases where the key isn't an integer index string
                    # Maybe it's already a class ID?
                    self.logger.warning(f"Prediction key '{index_str}' is not an integer index. Attempting lookup as class ID. Error: {e}")
                    class_id_key = index_str # Assume the key *is* the class ID
                    class_obj = self.dictionary_repo.get_class_by_id(class_id_key)
                    if class_obj and class_obj.name:
                        named_prediction_result[class_obj.name] = probability
                    else:
                        self.logger.error(f"Could not find class name for prediction key/ID: {class_id_key}. Using key as fallback.")
                        named_prediction_result[class_id_key] = probability # Fallback to original key
                        successful_mapping = False
            
            if not successful_mapping:
                self.logger.warning(f"Prediction result mapping to class names encountered issues for model {model_id}. Result may contain class IDs.")
             
            # If named_prediction_result is empty after loop (e.g., predictor returned empty dict), use original
            final_prediction_dict = named_prediction_result if named_prediction_result else prediction_result
            self.logger.debug(f"[Predict Name Map] Final mapped prediction: {final_prediction_dict}")
        except Exception as map_err:
             self.logger.error(f"[Predict Name Map] Error: {map_err}", exc_info=True)
             # Fallback or raise? Using raw result as fallback.
             final_prediction_dict = prediction_result
        # --- END Name Mapping --- 

        # Return final structure
        return {
            'prediction': final_prediction_dict,
            'model_id': model_id,
            'dictionary_id': dictionary_id,
            'classes': model.classes,
            'top_class': self._get_top_class(final_prediction_dict)
        }
    
    def predict_file(
        self,
        user_id: str,
        dictionary_id: str,
        model_id: str,
        audio_file_path: str
    ) -> Dict[str, Any]:
        """
        Make a prediction for an audio file using a trained model.
        
        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            model_id: Model ID
            audio_file_path: Path to the audio file
            
        Returns:
            Dictionary with prediction results
        """
        self.logger.debug(f"Predicting file: {audio_file_path}")
        try:
            # Load audio using utility function
            audio_data, sample_rate = load_audio_from_file(audio_file_path)
            
            # Make the prediction using the core predict method (which now handles preprocessing)
            return self.predict(user_id, dictionary_id, model_id, audio_data, sample_rate)
            
        except FileNotFoundError as fnf_err:
            self.logger.error(f"Audio file not found at path {audio_file_path}: {fnf_err}")
            raise # Re-raise FileNotFoundError to be caught by route
        except ValueError as val_err:
            self.logger.error(f"ValueError during audio loading or prediction for {audio_file_path}: {val_err}")
            raise # Re-raise ValueError to be caught by route
        except Exception as e:
            self.logger.error(f"Unexpected error in predict_file for {audio_file_path}: {e}", exc_info=True)
            raise ProcessingServiceError(f"Failed to process or predict file: {e}") from e # Wrap in a custom error
    
    # DB-OPERATION: read user
    def get_available_models(self, user_id: str, dictionary_id: str) -> List[Dict[str, Any]]:
        """
        Get all available trained models for a dictionary.
        
        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            
        Returns:
            List of available model dictionaries
        """
        # If shared access is enabled, scan all users' metadata for this dictionary
        if self.ALLOW_SHARED_MODELS:
            try:
                models: List[ModelVersion] = []
                metadata_root = getattr(self.model_repo, 'models_meta_dir', None)
                if metadata_root and metadata_root.exists():
                    for user_dir in metadata_root.iterdir():
                        if not user_dir.is_dir():
                            continue
                        dict_dir = user_dir / dictionary_id
                        if not dict_dir.is_dir():
                            continue
                        for meta_file in dict_dir.glob('*.json'):
                            data = self.file_manager.load_json(meta_file)
                            if not data:
                                continue
                            try:
                                mv = ModelVersion.from_dict(data)
                                if mv.status == ModelStatus.TRAINED:
                                    models.append(mv)
                            except Exception:
                                # Skip malformed entries
                                continue
                return [m.to_dict() for m in models]
            except Exception as e:
                self.logger.error(f"Shared model listing failed: {e}")
                # Fallback to per-user listing
        
        # Per-user listing (default)
        models = self.model_repo.get_for_dictionary(
            user_id, dictionary_id, status=ModelStatus.TRAINED
        )
        return [model.to_dict() for model in models]
    
    def _get_top_class(self, prediction: Dict[str, float]) -> str:
        """Get the class with the highest probability."""
        if not prediction: # Handle empty prediction dict
            return "Unknown"
        return max(prediction.items(), key=lambda x: x[1])[0]
    
    # DB-OPERATION: create unknown
    def save_inference_result(
        self,
        user_id: str,
        dictionary_id: str,
        model_id: str,
        audio_data: np.ndarray,
        prediction: Dict[str, Any],
        actual_class: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Save an inference result for later evaluation.
        
        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            model_id: Model ID
            audio_data: The audio data that was classified
            prediction: The prediction result
            actual_class: The actual class if known
            
        Returns:
            Dictionary with the saved result info
        """
        import uuid
        from datetime import datetime
        
        # Generate a unique ID for this inference
        inference_id = str(uuid.uuid4())
        
        # Save the audio file
        inference_dir = self.file_service.get_inference_dir(user_id, dictionary_id, model_id)
        os.makedirs(inference_dir, exist_ok=True)
        
        audio_path = os.path.join(inference_dir, f"{inference_id}.wav")
        self.file_service.save_audio(audio_data, audio_path)
        
        # Create the result object
        result = {
            'id': inference_id,
            'user_id': user_id,
            'dictionary_id': dictionary_id,
            'model_id': model_id,
            'prediction': prediction,
            'actual_class': actual_class,
            'audio_path': audio_path,
            'timestamp': datetime.now().isoformat(),
            'correct': actual_class and prediction['top_class'] == actual_class
        }
        
        # Save the result
        result_path = os.path.join(inference_dir, f"{inference_id}.json")
        self.file_service.save_json(result, result_path)
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
        
        return result

    def classify_audio(self, user_id: str, dictionary_name: str, audio_data: bytes,
                     model_type: Optional[str] = None, model_version: Optional[str] = None) -> Dict[str, Any]:
        """
        Classify an audio sample using a trained model.
        
        Args:
            user_id: The user ID
            dictionary_name: The dictionary name
            audio_data: The audio data to classify
            model_type: Optional model type to use (defaults to the default)
            model_version: Optional model version to use (defaults to the latest)
            
        Returns:
            Dictionary with classification results
        """
        try:
            # First, find the dictionary by name
            dictionaries = self.dictionary_repo.get_all_for_user(user_id)
            dictionary = next((d for d in dictionaries if d.name.lower() == dictionary_name.lower()), None)
            
            # If not found for current user, check other users (if sharing is enabled)
            if dictionary is None and True:  # Always check other users
                self.logger.info(f"Dictionary '{dictionary_name}' not found for user {user_id}, checking other users")
                # Check other users' dictionaries dir
                dict_dir = Path(self.file_service.file_manager.data_root) / 'dictionaries'
                if dict_dir.exists():
                # STORAGE-OPERATION: Will be replaced by DatabaseManager
                    for user_dir in dict_dir.iterdir():
                        if user_dir.is_dir() and user_dir.name != user_id:
                            other_user_id = user_dir.name
                            try:
                                other_dictionaries = self.dictionary_repo.get_all_for_user(other_user_id)
                                other_dictionary = next((d for d in other_dictionaries 
                                                      if d.name.lower() == dictionary_name.lower()), None)
                                if other_dictionary:
                                    self.logger.info(f"Found dictionary '{dictionary_name}' for user {other_user_id}")
                                    dictionary = other_dictionary
                                    user_id = other_user_id  # Use the owner's user ID for model lookup
                                    break
                            except Exception as e:
                                self.logger.error(f"Error checking dictionaries for user {other_user_id}: {str(e)}")
            
            if not dictionary:
                self.logger.error(f"Dictionary '{dictionary_name}' not found")
                return {
                    "success": False,
                    "error": f"Dictionary '{dictionary_name}' not found"
                }
            
            dictionary_id = dictionary.id
            
            # Find the latest model for this dictionary
            model = self.model_repo.get_latest_model(
                user_id, dictionary_id, model_type or "cnn", model_version
            )
            
            # If not found for owner, check if there are models from other users
            if model is None and True:  # Always check other users
                self.logger.info(f"Model not found for dictionary {dictionary_id} for user {user_id}, checking other users")
                # Search in the models directory for any model for this dictionary
                models_dir = Path(self.file_service.file_manager.data_root) / 'models'
                if models_dir.exists():
                # STORAGE-OPERATION: Will be replaced by DatabaseManager
                    for model_user_dir in models_dir.iterdir():
                        if model_user_dir.is_dir() and model_user_dir.name != user_id:
                            other_model_user_id = model_user_dir.name
                            try:
                                other_model = self.model_repo.get_latest_model(
                                    other_model_user_id, dictionary_id, model_type or "cnn", model_version
                                )
                                if other_model:
                                    self.logger.info(f"Found model for dictionary {dictionary_id} from user {other_model_user_id}")
                                    model = other_model
                                    user_id = other_model_user_id  # Use this user's ID for feature extraction
                                    break
                            except Exception as e:
                                self.logger.error(f"Error checking models for user {other_model_user_id}: {str(e)}")
            
            if not model:
                self.logger.error(f"No trained model found for dictionary '{dictionary_name}'")
                return {
                    "success": False,
                    "error": f"No trained model found for dictionary '{dictionary_name}'"
                }
            
            # Use the model to extract features from the audio
            feature_version = model.feature_version
            feature_data = self.feature_service.extract_features_from_audio(
                audio_data, feature_version
            )
            
            if not feature_data or "features" not in feature_data:
                self.logger.error("Failed to extract features from audio")
                return {
                    "success": False,
                    "error": "Failed to extract features from audio"
                }
            
            # Load the model from disk
            model_path = self.model_repo.get_model_path(model)
            model_obj = self._load_model(model_path)
            
            if not model_obj:
                self.logger.error(f"Failed to load model from {model_path}")
                return {
                    "success": False,
                    "error": "Failed to load model"
                }
            
            # Make the prediction
            features = feature_data["features"]
            prediction = self._predict(model_obj, features)
            
            if prediction is None:
                self.logger.error("Failed to make prediction")
                return {
                    "success": False,
                    "error": "Failed to make prediction"
                }
            
            # Get the class names
            class_names = [cls.name for cls in dictionary.classes]
            
            # Format the results
            results = []
            for i, class_name in enumerate(class_names):
                results.append({
                    "class": class_name,
                    "probability": float(prediction[i]),
                    "is_top": i == prediction.argmax()
                })
            
            # Sort by probability (descending)
            results.sort(key=lambda x: x["probability"], reverse=True)
            
            return {
                "success": True,
                "dictionary": dictionary.name,
                "results": results,
                "top_class": results[0]["class"],
                "top_probability": results[0]["probability"],
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error classifying audio: {str(e)}")
            return {
                "success": False,
                "error": f"Classification error: {str(e)}"
            }

    def _load_model(self, model_path: str) -> Optional[Any]:
        """Helper to load a model object from a file path."""
        # This is a placeholder - actual implementation depends on model format
        # For .pkl:
        import pickle
        try:
            with open(model_path, 'rb') as f:
                model_obj = pickle.load(f)
            return model_obj
        except Exception as e:
            self.logger.error(f"Error loading model from {model_path}: {e}")
            return None
        # For other formats (e.g., TF SavedModel), adjust loading logic

    def _predict(self, model_obj: Any, features: np.ndarray) -> Optional[np.ndarray]:
        """Helper to make a prediction using a loaded model object."""
        # This is a placeholder - actual implementation depends on model type
        try:
            # Assuming model object has a predict_proba method
            if hasattr(model_obj, 'predict_proba'):
                # Reshape features if necessary (e.g., for sklearn models)
                if features.ndim == 4: # (batch, height, width, channel)
                    # Flatten for non-CNN models? This needs careful handling based on training!
                    # Assuming features are already appropriate for the model type here.
                    # For CNN, this might need to stay 4D.
                    # For SVM/RF trained on flattened features, flatten here:
                    # n_samples = features.shape[0]
                    # features_flat = features.reshape(n_samples, -1)
                    # prediction = model_obj.predict_proba(features_flat)[0] # Get first sample's probs
                    
                    # Let's assume the predictor handled reshaping appropriately before _predict is called
                    # IF NOT, this logic needs to be specific to the model type.
                    # For now, pass features as is.
                    prediction = model_obj.predict_proba(features)
                    # Check if prediction is nested (e.g., [[probs]])
                    if isinstance(prediction, list) and len(prediction) == 1 and isinstance(prediction[0], np.ndarray):
                        prediction = prediction[0]
                    elif prediction.ndim > 1 and prediction.shape[0] == 1:
                        prediction = prediction[0] # Extract first batch item
                        
                else:
                    # Assume features are already in correct shape (e.g., 2D for sklearn)
                    prediction = model_obj.predict_proba(features)
                    if prediction.ndim > 1 and prediction.shape[0] == 1:
                        prediction = prediction[0] # Handle [[probs]] output

            elif hasattr(model_obj, 'predict'): # Fallback to predict if predict_proba not available
                # This will give class indices, not probabilities - needs mapping
                prediction_indices = model_obj.predict(features)
                # Convert indices to one-hot probabilities (crude)
                num_classes = len(model_obj.classes_) # Assuming sklearn model
                prediction = np.eye(num_classes)[prediction_indices]
                if prediction.ndim > 1 and prediction.shape[0] == 1:
                    prediction = prediction[0]
            else:
                self.logger.error("Model object lacks predict_proba or predict method.")
                return None
            return prediction
        except Exception as e:
            self.logger.error(f"Error during prediction: {e}", exc_info=True)
            return None
