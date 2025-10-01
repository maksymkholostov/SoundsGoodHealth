import os
import json
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Set
import uuid
from datetime import datetime
from pathlib import Path
import threading
from flask import current_app

from ..core.models.model import ModelVersion, ModelType, ModelStatus
from ..core.models.dictionary import Dictionary
from ..core.repositories.dictionary_repo import DictionaryRepository
from ..core.repositories.feature_repo import FeatureRepository
from ..core.repositories.model_repo import ModelRepository
from ..core.repositories.recording_repo import RecordingRepository
from ..core.models.recording import RecordingType
from ..ml.training.trainer import ModelTrainer, SVM_Trainer, RandomForest_Trainer, CNN_Trainer
from ..ml.training.cnn1d_trainer import CNN1D_Trainer
from ..services.file_service import FileService
from ..services.augmentation_service import AugmentationService
from ..analysis.training_analyzer import TrainingAnalyzer
from ..services.model_registry_service import ModelRegistryService

logger = logging.getLogger(__name__)

class TrainingService:
    """Service for training ML models on extracted features."""
    
    def __init__(
        self,
        dictionary_repo: DictionaryRepository,
        feature_repo: FeatureRepository,
        model_repo: ModelRepository,
        recording_repo: RecordingRepository,
        file_service: FileService,
        augmentation_service: AugmentationService,
        training_analyzer: TrainingAnalyzer,
        config: Optional[Dict[str, Any]] = None
    ):
        self.dictionary_repo = dictionary_repo
        self.feature_repo = feature_repo
        self.model_repo = model_repo
        self.recording_repo = recording_repo
        self.file_service = file_service
        self.augmentation_service = augmentation_service
        self.training_analyzer = training_analyzer
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize model registry service
        data_root = config.get('DATA_ROOT', 'backend/data') if config else 'backend/data'
        self.registry_service = ModelRegistryService(data_root)
        # Access control toggle to align with InferenceService (minimal change approach)
        # When True, training can use recordings/features across users (already largely supported)
        # and will save models in shared-access manner (artifacts per dictionary; metadata still per owner).
        self.ALLOW_SHARED_MODELS = True
        
        # Available model trainers
        self.trainers = {
            ModelType.SVM.value: SVM_Trainer(),
            ModelType.RF.value: RandomForest_Trainer(),
            ModelType.CNN.value: CNN_Trainer(),
            ModelType.CNN1D.value: CNN1D_Trainer()
        }
    
    # DB-OPERATION: read model
    def get_available_models(self) -> List[str]:
        """Returns a list of available ML model types.
        
        Note: CNN and Ensemble models are hidden from users for now.
        Only RF, CNN1D, and SVM are available for training.
        """
        # Filter out CNN (keeping CNN1D) and Ensemble from user-facing options
        available = []
        for model_type in self.trainers.keys():
            # Only include RF, SVM, and CNN1D
            if model_type in [ModelType.SVM.value, ModelType.RF.value, ModelType.CNN1D.value]:
                available.append(model_type)
        return available
    
    def train_model(
        self,
        user_id: str,
        dictionary_id: str,
        model_type: str,
        model_name: str,
        feature_version: str = "v0.1",
        use_augmented: bool = True,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Train a model for a specific dictionary using existing features.
        Assumes feature data (.npz) already exists.
        
        Args:
            user_id: The user ID
            dictionary_id: The dictionary ID
            model_type: Type of model to train (cnn, svm, rf)
            model_name: User-friendly name for the model
            feature_version: Version of feature extraction to use
            use_augmented: Whether to include augmented data features in training
            params: Optional model-specific parameters
            
        Returns:
            Dictionary with model details and training metrics, or error info.
        """
        self.logger.info(f"Received train_model request: user={user_id}, dict={dictionary_id}, type={model_type}")
        
        # --- Initial Synchronous Checks --- 
        # Check if model type is in the allowed list (not just in trainers)
        allowed_types = self.get_available_models()
        if model_type not in allowed_types:
            raise ValueError(f"Model type '{model_type}' is not available. Available types: {allowed_types}")
        
        dictionary = self.dictionary_repo.get_dictionary_by_id(dictionary_id)
        if not dictionary:
            raise ValueError(f"Dictionary {dictionary_id} not found.")
        
        # Optional: User permission check (disabled if shared models enabled)
        if not self.ALLOW_SHARED_MODELS:
            if dictionary.creator_user_id != user_id:
                raise PermissionError(f"User {user_id} does not have permission to train on dictionary {dictionary_id}")

        # Check if user is already training
        status_check = self.get_user_training_status(user_id)
        if status_check.get('is_training'):
             err_msg = f"User {user_id} already has a model training (ID: {status_check.get('model_id')}). Please wait."
             self.logger.warning(err_msg)
             # Return error but maybe indicate conflict? Return a specific status?
             # For now, raising ValueError which results in 400 Bad Request.
             raise ValueError(err_msg)

        # --- Create Model Record (Synchronous) --- 
        version = self._get_next_model_version(user_id, dictionary_id, model_type)
        # Correct filename base for model saving (TF needs dir, others might need .pkl)
        model_filename_base = f"{model_type}_v{version}" 
        
        model_version = ModelVersion.create(
            dictionary_id=dictionary_id,
            feature_set_id=feature_version,
            user_id=user_id,
            name=model_name,
            model_type=ModelType(model_type),
            version=version,
            parameters=params or {},
            classes=dictionary.class_ids,
            filename=model_filename_base # Use the base name
        )
        
        # Save initial CREATED status
        self.model_repo.save(model_version)
        self.logger.info(f"Created ModelVersion {model_version.id}, status: {model_version.status}")

        # --- Start Background Training Thread --- 
        self.logger.info(f"Starting background training thread for model {model_version.id}")
        # Pass necessary arguments to the thread target function
        # Important: Need app context for logging/services within the thread
        app_context = current_app.app_context()
        thread = threading.Thread(target=self._run_training_task, 
                                  args=(app_context, model_version.id, user_id, dictionary_id, model_type, 
                                        feature_version, use_augmented, params))
        thread.daemon = True # Allows app to exit even if thread is running (consider implications)
        thread.start()

        # --- Return Immediately --- 
        # Return the initial model data (status CREATED or maybe TRAINING if marked quickly)
        # Frontend will poll for completion using the ID
        return model_version.to_dict() 

    def _run_training_task(self, app_context, model_id: str, user_id: str, dictionary_id: str, 
                           model_type: str, feature_version: str, use_augmented: bool, 
                           params: Optional[Dict[str, Any]]):
        """
        The actual training logic run in a background thread.
        Requires app_context to use Flask services/logging.
        """
        with app_context:
            self.logger.info(f"[Thread:{model_id}] Background training task started.")
            model_version = None # Initialize in case initial fetch fails
            try:
                # --- Fetch model record and mark as TRAINING --- 
                # Need dictionary_id again to fetch the model within the thread
                model_version = self.model_repo.get_by_id(user_id, dictionary_id, model_id)
                if not model_version:
                    self.logger.error(f"[Thread:{model_id}] Failed to fetch model record from repo.")
                    return # Cannot proceed without model record
                
                model_version.mark_training()
                self.model_repo.save(model_version)
                self.logger.info(f"[Thread:{model_id}] Marked model as TRAINING.")

                # --- Load Features --- 
                self.logger.info(f"[Thread:{model_id}] Loading features... (version: {feature_version}, augmented: {use_augmented})")
                X_train, y_train, training_ids = self._load_training_features(
                    user_id, dictionary_id, model_version.classes, feature_version, use_augmented
                )
                
                if len(X_train) == 0:
                    raise ValueError(f"No training data features loaded for dictionary {dictionary_id}, version {feature_version}")
                
                self.logger.info(f"[Thread:{model_id}] Training {model_type} model with {len(X_train)} samples.")
                model_version.add_training_data(training_ids) # Add loaded IDs
                
                # --- Train the Model --- 
                trainer = self.trainers[model_type]
                # Add model_id to params for the callback to use
                train_params = params or {}
                train_params['_model_id_for_log'] = model_id
                # Pass the total number of classes to handle missing classes in training data
                train_params['num_classes'] = len(model_version.classes)
                
                self.logger.info(f"[Thread:{model_id}] 🚀 STARTING TRAINING with {len(model_version.classes)} classes...")
                import time
                training_start_time = time.time()
                training_result = trainer.train(X_train, y_train, train_params)
                training_duration = time.time() - training_start_time
                self.logger.info(f"[Thread:{model_id}] ✅ TRAINING RETURNED SUCCESSFULLY! Duration: {training_duration:.2f} seconds")
                
                if len(training_result) == 3:
                    model, metrics, history_data = training_result
                else:
                    model, metrics = training_result
                    history_data = None
                self.logger.info(f"[Thread:{model_id}] Training complete. Metrics: {metrics}")

                # --- Save Model Artifact --- 
                self.logger.info(f"[Thread:{model_id}] 🔄 PREPARING TO SAVE MODEL...")
                model_save_dir = self.file_service.file_manager.get_specific_model_dir(
                    dictionary_id=dictionary_id,
                    model_type_version=model_id # Use model_id as the unique directory 
                )
                
                # Determine the actual path/target for save_model based on type
                if model_type in [ModelType.CNN.value, ModelType.CNN1D.value]:
                    # CNN and CNN1D trainers save as a directory format
                    # Ensure the directory doesn't exist so TensorFlow can create it fresh
                    if model_save_dir.exists():
                        import shutil
                        shutil.rmtree(model_save_dir)
                    # TensorFlow/Keras will create the directory with model files
                    save_target = str(model_save_dir)
                    actual_filename_in_metadata = "" # No filename needed for directory format
                    self.logger.info(f"[Thread:{model_id}] 💾 CALLING SAVE_MODEL for {model_type} to: {save_target}")
                else:
                    # Other trainers (SVM, RF) expect a file path for pickling
                    # Ensure directory exists for file-based models
                    os.makedirs(model_save_dir, exist_ok=True)
                    actual_filename = f"{model_version.filename}.pkl" # Add .pkl extension
                    save_target = str(model_save_dir / actual_filename)
                    actual_filename_in_metadata = actual_filename # Store full filename
                    self.logger.info(f"[Thread:{model_id}] 💾 CALLING SAVE_MODEL for {model_type} to: {save_target}")

                trainer.save_model(model, save_target) 
                self.logger.info(f"[Thread:{model_id}] ✅ SAVE_MODEL RETURNED SUCCESSFULLY!")
                self.logger.info(f"[Thread:{model_id}] Saved trained model artifact to {save_target}")

                # --- Create Training Summary Report ---
                training_summary = {
                    'model_name': model_version.name,
                    'model_type': model_type,
                    'model_id': model_id,
                    'dictionary_id': dictionary_id,
                    'classes': list(model_version.classes),
                    'num_classes': len(model_version.classes),
                    'total_samples': len(X_train),
                    'class_distribution': {},
                    'metrics': metrics,
                    'training_params': params or {},
                    'feature_version': feature_version,
                    'use_augmented': use_augmented,
                    'training_duration': training_duration
                }
                
                # Calculate class distribution
                for class_id in model_version.classes:
                    class_idx = list(model_version.classes).index(class_id)
                    class_count = np.sum(y_train == class_idx)
                    training_summary['class_distribution'][class_id] = int(class_count)
                
                # --- Update and Save Final Model Metadata --- 
                model_version.mark_trained(metrics)
                model_version.filename = actual_filename_in_metadata # Update filename in metadata
                model_version.metadata['training_summary'] = training_summary
                if history_data:
                    model_version.metadata['training_history'] = history_data 
                    try:
                        # Convert epoch-based history to metric-based format for analyzer
                        if isinstance(history_data, list) and len(history_data) > 0:
                            # Convert from [{"epoch": 1, "loss": 0.6, "accuracy": 0.7}, ...] 
                            # to {"loss": [0.6, ...], "accuracy": [0.7, ...]}
                            metrics_format = {}
                            for epoch_data in history_data:
                                for key, value in epoch_data.items():
                                    if key != 'epoch' and isinstance(value, (int, float)):
                                        if key not in metrics_format:
                                            metrics_format[key] = []
                                        metrics_format[key].append(value)
                            
                            if metrics_format:
                                analysis_results = self.training_analyzer.analyze_training_history(metrics_format)
                                model_version.metadata['training_analysis'] = analysis_results
                                self.logger.info(f"[Thread:{model_id}] Stored training analysis for {len(metrics_format)} metrics.")
                            else:
                                self.logger.warning(f"[Thread:{model_id}] No numeric metrics found in history data for analysis.")
                        else:
                            self.logger.warning(f"[Thread:{model_id}] History data format not recognized for analysis: {type(history_data)}")
                    except Exception as analysis_err:
                        self.logger.error(f"[Thread:{model_id}] Failed to run training analysis: {analysis_err}", exc_info=True)
                
                save_success = self.model_repo.save(model_version)
                self.logger.info(f"[Thread:{model_id}] Marked model as TRAINED. Metadata save success: {save_success}")
                
                # Update model registry after successful training
                if save_success:
                    try:
                        metadata_path = self.model_repo._get_model_path(user_id, dictionary_id, model_id)
                        registry_updated = self.registry_service.add_model(
                            model_id=model_id,
                            user_id=user_id,
                            dict_id=dictionary_id,
                            metadata_path=str(metadata_path)
                        )
                        if registry_updated:
                            self.logger.info(f"[Thread:{model_id}] Successfully updated model registry")
                        else:
                            self.logger.warning(f"[Thread:{model_id}] Failed to update model registry")
                    except Exception as reg_e:
                        self.logger.error(f"[Thread:{model_id}] Error updating model registry: {reg_e}")

            except Exception as e:
                self.logger.error(f"[Thread:{model_id}] Error during training task: {e}", exc_info=True)
                # Ensure model_version is fetched before trying to mark failed
                if model_version is None:
                     # Attempt to fetch again if initial fetch failed but we have ID
                     model_version = self.model_repo.get_by_id(user_id, dictionary_id, model_id)
                
                if model_version: # Mark as FAILED if we have the record
                    try:
                        model_version.mark_failed(str(e))
                        self.model_repo.save(model_version)
                        self.logger.info(f"[Thread:{model_id}] Marked model as FAILED.")
                    except Exception as fail_save_e:
                        self.logger.error(f"[Thread:{model_id}] Additionally failed to save FAILED status: {fail_save_e}")
                else:
                    self.logger.error(f"[Thread:{model_id}] Cannot mark model as FAILED because model record could not be loaded.")
            finally:
                 self.logger.info(f"[Thread:{model_id}] Background training task finished.")

    def _load_training_features(
        self,
        user_id: str,
        dictionary_id: str,
        class_ids: List[str],
        feature_version: str,
        use_augmented: bool
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Load features data (.npz files) for training.

        Args:
            user_id: The user ID requesting the training.
            dictionary_id: The dictionary ID.
            class_ids: List of class IDs in the dictionary.
            feature_version: Version of features (feature_set_id) to use.
            use_augmented: Whether to include augmented data.

        Returns:
            Tuple of (features, labels, recording_ids)
        """
        all_features = []
        all_labels = []
        all_recording_ids = []
        processed_recording_ids = set()

        # Determine which recording types to load
        types_to_load = [RecordingType.GOLD]
        if use_augmented:
            types_to_load.append(RecordingType.AUGMENTED)

        self.logger.info(f"Loading features for dict {dictionary_id}, classes: {class_ids}, version: {feature_version}, types: {types_to_load}")
        
        # Track recordings per class for debugging
        recordings_per_class = {class_id: 0 for class_id in class_ids}
        skipped_per_class = {class_id: {'no_extraction': 0, 'load_failed': 0, 'missing_key': 0, 'wrong_dims': 0} for class_id in class_ids}

        # Get all recordings for the dictionary matching the required types
        # Note: Recording repo might need adjustment if it doesn't handle user_id filtering well here.
        # Assuming we want *all* recordings for the dictionary classes, regardless of original user.
        recordings = self.recording_repo.find(
            class_id__in=class_ids,
            recording_type__in=types_to_load
        )
        
        self.logger.error(f"[TRAIN-DEBUG] Found {len(recordings)} total recordings for classes {class_ids}")
        for rec in recordings[:5]:  # Log first 5
            self.logger.error(f"[TRAIN-DEBUG] Recording: {rec.id}, class: {rec.class_id}, user: {rec.user_id}, type: {rec.recording_type}")

        # Need class name mapping for path construction
        class_id_to_name = {cls.id: cls.name for cls in self.dictionary_repo.get_all_classes() if cls.id in class_ids}

        # --- Get FeatureSet definition to know which features to load/combine ---
        feature_set = self.feature_repo.get_feature_set(feature_version)
        if not feature_set:
            self.logger.error(f"Feature set '{feature_version}' definition not found. Cannot load features.")
            return np.array([]), np.array([]), []
        expected_feature_key = 'mel_spectrogram' # Define the specific key to load
        self.logger.info(f"Expecting specific feature: '{expected_feature_key}' based on set {feature_version}")
        # --- End FeatureSet fetch ---

        for recording in recordings:
            if recording.id in processed_recording_ids:
                continue # Skip if already processed (e.g., via cross-user search)
            
            # Track which class this recording belongs to
            recordings_per_class[recording.class_id] = recordings_per_class.get(recording.class_id, 0) + 1

            try:
                # Find the specific feature extraction metadata for this recording and version
                extractions = self.feature_repo.get_extractions_for_recording(recording.user_id, recording.id)
                target_extraction = None
                for ext in extractions:
                    if ext.feature_set_id == feature_version:
                        target_extraction = ext
                        break

                if not target_extraction:
                    self.logger.debug(f"No feature extraction found for recording {recording.id} (class: {recording.class_id}) and version {feature_version}. Skipping.")
                    if recording.class_id in skipped_per_class:
                        skipped_per_class[recording.class_id]['no_extraction'] += 1
                    continue

                # --- CORRECTED PATH CONSTRUCTION --- 
                # The filename stored in FeatureExtraction metadata is the relative path
                relative_npz_path = Path(target_extraction.filename)
                npz_path = self.file_service.file_manager.get_data_root() / relative_npz_path
                # --- END CORRECTED PATH CONSTRUCTION --- 

                # Load the feature data from the NPZ file
                feature_data = self.file_service.file_manager.load_npz(npz_path)
                if feature_data is None:
                    self.logger.warning(f"Failed to load feature data from {npz_path} for recording {recording.id} (class: {recording.class_id}). Skipping.")
                    if recording.class_id in skipped_per_class:
                        skipped_per_class[recording.class_id]['load_failed'] += 1
                    continue

                # --- Get the specific 2D feature array (Mel Spectrogram) --- 
                features = feature_data.get(expected_feature_key)
                if features is None:
                    self.logger.warning(f"Expected feature key '{expected_feature_key}' not found in {npz_path} for recording {recording.id} (class: {recording.class_id}). Keys available: {list(feature_data.keys())}. Skipping.")
                    if recording.class_id in skipped_per_class:
                        skipped_per_class[recording.class_id]['missing_key'] += 1
                    continue

                # Ensure it's a 2D array (or suitable for CNN input)
                if features.ndim < 2:
                    self.logger.warning(f"Feature '{expected_feature_key}' in {npz_path} has {features.ndim} dimensions, expected at least 2 for recording {recording.id} (class: {recording.class_id}). Skipping.")
                    if recording.class_id in skipped_per_class:
                        skipped_per_class[recording.class_id]['wrong_dims'] += 1
                    continue
                # --- End Feature Loading --- 

                # Add features, label (class_id), and recording ID
                all_features.append(features)
                all_labels.append(recording.class_id)
                all_recording_ids.append(recording.id)
                processed_recording_ids.add(recording.id)
                self.logger.debug(f"Loaded features for recording {recording.id}")

            except Exception as e:
                self.logger.error(f"Error processing features for recording {recording.id}: {e}", exc_info=True)
                continue # Skip this recording on error

        # Convert to numpy arrays
        if not all_features:
            self.logger.warning(f"No features successfully loaded for dictionary {dictionary_id}, version {feature_version}.")
            return np.array([]), np.array([]), []

        X = np.array(all_features)

        # Convert class_id labels to numerical indices for training
        label_to_idx = {label: i for i, label in enumerate(class_ids)}
        y = np.array([label_to_idx[label] for label in all_labels])

        # Print detailed loading report
        self.logger.error("=" * 60)
        self.logger.error("FEATURE LOADING REPORT:")
        for class_id in class_ids:
            total_recordings = recordings_per_class.get(class_id, 0)
            skip_reasons = skipped_per_class.get(class_id, {})
            total_skipped = sum(skip_reasons.values())
            loaded = total_recordings - total_skipped
            
            self.logger.error(f"Class '{class_id}':")
            self.logger.error(f"  Total recordings found: {total_recordings}")
            self.logger.error(f"  Successfully loaded: {loaded}")
            if total_skipped > 0:
                self.logger.error(f"  Skipped: {total_skipped}")
                if skip_reasons.get('no_extraction', 0) > 0:
                    self.logger.error(f"    - No feature extraction: {skip_reasons['no_extraction']}")
                if skip_reasons.get('load_failed', 0) > 0:
                    self.logger.error(f"    - Failed to load NPZ: {skip_reasons['load_failed']}")
                if skip_reasons.get('missing_key', 0) > 0:
                    self.logger.error(f"    - Missing mel_spectrogram key: {skip_reasons['missing_key']}")
                if skip_reasons.get('wrong_dims', 0) > 0:
                    self.logger.error(f"    - Wrong dimensions: {skip_reasons['wrong_dims']}")
        self.logger.error("=" * 60)
        
        # Check which classes actually have training data
        unique_labels = np.unique(y) if len(y) > 0 else np.array([])
        classes_with_data = [class_ids[i] for i in unique_labels] if len(unique_labels) > 0 else []
        classes_without_data = [class_ids[i] for i in range(len(class_ids)) if i not in unique_labels]
        
        self.logger.info(f"Loaded {len(X)} total features across {len(class_ids)} classes for dictionary {dictionary_id}.")
        self.logger.info(f"Classes with training data: {classes_with_data}")
        
        if classes_without_data:
            self.logger.error(f"ERROR: The following classes have NO training data: {classes_without_data}")
            self.logger.error(f"Cannot train model with missing classes. Please ensure all classes have training samples.")
            
            # Provide more helpful error message based on skip reasons
            for class_id in classes_without_data:
                skip_reasons = skipped_per_class.get(class_id, {})
                if skip_reasons.get('no_extraction', 0) > 0:
                    self.logger.error(f"  Class '{class_id}': Features not extracted. Run feature extraction first.")
                elif skip_reasons.get('missing_key', 0) > 0:
                    self.logger.error(f"  Class '{class_id}': Feature files missing 'mel_spectrogram' key.")
                elif skip_reasons.get('load_failed', 0) > 0:
                    self.logger.error(f"  Class '{class_id}': Could not load feature files (may be corrupted).")
                elif skip_reasons.get('wrong_dims', 0) > 0:
                    self.logger.error(f"  Class '{class_id}': Feature arrays have wrong dimensions.")
                else:
                    self.logger.error(f"  Class '{class_id}': No recordings found for this class.")
            
            raise ValueError(f"Cannot train model: Classes {classes_without_data} have no training data. "
                           f"Check the logs above for specific reasons.")
        
        return X, y, all_recording_ids
    
    def _get_next_model_version(self, user_id: str, dictionary_id: str, model_type: str) -> str:
        """Determine the next version number for a model."""
        models = self.model_repo.get_for_dictionary(
            user_id, dictionary_id, ModelType(model_type)
        )
        
        if not models:
            return "01"  # First version
        
        # Extract version numbers - strip leading zeros and convert to int
        versions = []
        for model in models:
            try:
                versions.append(int(model.version.lstrip('0')))
            except ValueError:
                # If version is not numeric, skip it
                continue
                
        next_version = max(versions) + 1 if versions else 1
        
        return f"{next_version:02d}"
    
    # DB-OPERATION: read user
    def get_user_training_status(self, user_id: str) -> Dict[str, Any]:
        """
        Checks if a user currently has any model in the 'training' state across all their dictionaries.

        Args:
            user_id: The user ID to check.

        Returns:
            A dictionary indicating training status, e.g.,
            {'is_training': True, 'model_id': 'some_model_id', 'dictionary_id': 'dict_id'} or
            {'is_training': False, 'model_id': None, 'dictionary_id': None}
        """
        self.logger.debug(f"Checking training status for user {user_id}")
        try:
            # Get all dictionaries from the system
            all_dictionaries = self.dictionary_repo.get_all_dictionaries()

            # Filter dictionaries belonging to the user
            user_dictionaries = [d for d in all_dictionaries if hasattr(d, 'creator_user_id') and d.creator_user_id == user_id]

            if not user_dictionaries:
                self.logger.debug(f"No dictionaries found for user {user_id}, assuming no training.")
                return {'is_training': False, 'model_id': None, 'dictionary_id': None}

            training_model_id = None
            training_dict_id = None
            for dictionary in user_dictionaries:
                # Check models for this specific dictionary with TRAINING status
                # Note: ModelRepository.get_for_dictionary handles user_id internally
                training_models = self.model_repo.get_for_dictionary(
                    user_id=user_id, # Pass user_id here as well
                    dict_id=dictionary.id,
                    status=ModelStatus.TRAINING
                )
                if training_models:
                    # Found at least one model training in this dictionary
                    found_model = training_models[0] # Get the first one found
                    training_model_id = found_model.id
                    training_dict_id = dictionary.id
                    self.logger.info(f"User {user_id} has model {training_model_id} (dictionary {training_dict_id}) currently training.")
                    break # Stop searching once one training model is found

            if training_model_id:
                return {'is_training': True, 'model_id': training_model_id, 'dictionary_id': training_dict_id}
            else:
                self.logger.debug(f"No models currently training for user {user_id} across their dictionaries.")
                return {'is_training': False, 'model_id': None, 'dictionary_id': None}

        except Exception as e:
            self.logger.error(f"Error checking training status for user {user_id}: {e}", exc_info=True)
            # Return False in case of error to avoid blocking UI potentially
            return {'is_training': False, 'model_id': None, 'dictionary_id': None, 'error': str(e)}

    # DB-OPERATION: read user
    def get_trained_models(self, user_id: str, dictionary_id: str) -> List[Dict[str, Any]]:
        """
        Get all trained models for a dictionary.
        
        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            
        Returns:
            List of model metadata dictionaries
        """
        # Get trained models
        trained_status = [ModelStatus.TRAINED]
        models = self.model_repo.get_for_dictionary(user_id, dictionary_id)
        
        # Filter models by status
        models = [model for model in models if model.status in trained_status]
        
        return [model.to_dict() for model in models]
    
    # DB-OPERATION: read user
    def get_model(self, user_id: str, dictionary_id: str, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific model by ID.
        
        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            model_id: Model ID
            
        Returns:
            Model metadata dictionary if found, None otherwise
        """
        model = self.model_repo.get_by_id(user_id, dictionary_id, model_id)
        
        return model.to_dict() if model else None
    
    # DB-OPERATION: read user
    def get_model_results(self, user_id: str, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the results/metadata for a specific trained model ID, searching across user's dictionaries.

        Args:
            user_id: User ID
            model_id: The specific Model ID to find.

        Returns:
            Model metadata dictionary if found and belongs to the user, None otherwise.
        """
        self.logger.debug(f"Attempting to find model results for model_id: {model_id}, user: {user_id}")
        try:
            # Get all dictionaries for the user
            all_dictionaries = self.dictionary_repo.get_all_dictionaries()
            user_dictionaries = [d for d in all_dictionaries if hasattr(d, 'creator_user_id') and d.creator_user_id == user_id]

            if not user_dictionaries:
                self.logger.warning(f"No dictionaries found for user {user_id} when searching for model {model_id}.")
                return None

            # Check each dictionary for the model
            for dictionary in user_dictionaries:
                 # Use the existing get_by_id method from ModelRepository
                 model = self.model_repo.get_by_id(user_id, dictionary.id, model_id)
                 if model:
                     self.logger.info(f"Found model {model_id} in dictionary {dictionary.id} for user {user_id}.")
                     # Ensure the model status indicates completion (optional but good practice)
                     if model.status in [ModelStatus.TRAINED, ModelStatus.FAILED]:
                         return model.to_dict()
                     else:
                         self.logger.warning(f"Found model {model_id} but its status is {model.status}. Not returning results yet.")
                         return None # Or maybe return partial data?
            
            # If model not found in any user dictionary
            self.logger.warning(f"Model {model_id} not found in any dictionary belonging to user {user_id}.")
            return None

        except Exception as e:
            self.logger.error(f"Error retrieving model results for model {model_id}, user {user_id}: {e}", exc_info=True)
            return None

    # DB-OPERATION: delete user
    def delete_model(self, user_id: str, dictionary_id: str, model_id: str) -> bool:
        """
        Delete a model completely (metadata and file).
        
        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            model_id: Model ID
            
        Returns:
            True if deleted successfully, False otherwise
        """
        model = self.model_repo.get_by_id(user_id, dictionary_id, model_id)
        
        if not model and self.ALLOW_SHARED_MODELS:
            # Allow deleting models owned by others (shared mode)
            self.logger.info(f"Shared models enabled. Searching globally for model {model_id} to delete.")
            model = self.model_repo.find_model_by_id(model_id)
            if model and model.dictionary_id != dictionary_id:
                self.logger.warning(
                    f"Requested dictionary {dictionary_id} does not match model's dictionary {model.dictionary_id}"
                )
                return False
        
        if not model:
            return False
        
        # Delete the model files and metadata
        deleted = self.model_repo.delete_with_file(model)
        
        # Update model registry after successful deletion
        if deleted:
            try:
                registry_updated = self.registry_service.remove_model(model_id)
                if registry_updated:
                    self.logger.info(f"Successfully removed model {model_id} from registry")
                else:
                    self.logger.warning(f"Failed to remove model {model_id} from registry")
            except Exception as reg_e:
                self.logger.error(f"Error updating model registry after deletion: {reg_e}")
        
        return deleted

    def prepare_training_data(self,
                            user_id: str,
                            dictionary_id: str,
                            feature_version: str = "v0.1",
                            include_augmented: bool = True,
                            force_augmentation: bool = False,
                            num_augmentations_per_file: int = 5) -> Dict[str, Any]:
        """
        Prepare data for training: Check/generate features and augmentations.

        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            feature_version: The specific feature set version ID to check/use.
            include_augmented: Whether to perform augmentation.
            force_augmentation: Whether to force regeneration of augmentations.
            num_augmentations_per_file: How many variations per gold file.

        Returns:
            Dictionary containing prepared data information and feature status.
        """
        result = {
            'user_id': user_id,
            'dictionary_id': dictionary_id,
            'steps': [],
            'feature_status': {
                'gold': {'total': 0, 'extracted': 0},
                'augmented': {'total': 0, 'extracted': 0}
            }
        }
        feature_check_errors_gold = []
        gold_recordings = [] # Keep list of gold recordings for augmentation loop

        # Step 1: Check features for gold standard recordings
        self.logger.info(f"Checking GOLD features for dict {dictionary_id}, version {feature_version}")
        try:
            gold_recordings = self.recording_repo.get_all_for_dictionary(
                dictionary_id=dictionary_id,
                user_id=user_id,
                rec_type=RecordingType.GOLD
            )
            result['feature_status']['gold']['total'] = len(gold_recordings)
            extracted_count_gold = 0

            class_id_to_name = {cls.id: cls.name for cls in self.dictionary_repo.get_all_classes()}

            for rec in gold_recordings:
                try:
                    extractions = self.feature_repo.get_extractions_for_recording(user_id, rec.id)
                    if any(ext.feature_set_id == feature_version for ext in extractions):
                        extracted_count_gold += 1
                except Exception as check_exc:
                    msg = f"Error checking features for gold recording {rec.id}: {check_exc}"
                    self.logger.warning(msg)
                    feature_check_errors_gold.append(msg)

            result['feature_status']['gold']['extracted'] = extracted_count_gold
            step_status = {
                'step': 'check_gold_features',
                'status': 'success',
                'total_files': len(gold_recordings),
                'files_with_features': extracted_count_gold
            }
            if feature_check_errors_gold:
                 step_status['warnings'] = feature_check_errors_gold
            result['steps'].append(step_status)

        except Exception as e:
            # Critical error if we can't even check gold recordings/features
            msg = f"Critical error retrieving/checking GOLD recordings: {e}"
            self.logger.error(msg, exc_info=True)
            result['steps'].append({'step': 'check_gold_features', 'status': 'error', 'error': msg})
            result['data_ready'] = False
            return result

        # --- Step 2: Augmentation (Only if Forced) --- 
        augmentation_run_status = 'skipped' # Default status
        if include_augmented and force_augmentation:
            self.logger.info(f"FORCE_AUGMENTATION enabled: Running augmentation workflow for dict {dictionary_id}")
            total_augs_created = 0
            total_augs_failed = 0
            augmentation_errors = []
            augmentation_step_success = True

            # TODO: Implement deletion logic for existing augmented data if needed
            self.logger.warning(f"Force augmentation: Deleting existing augmented data first.")
            # Placeholder for deletion:
            try:
                existing_augmented = self.recording_repo.get_all_for_dictionary(dictionary_id=dictionary_id, user_id=user_id, rec_type=RecordingType.AUGMENTED)
                self.logger.info(f"Found {len(existing_augmented)} existing augmented recordings to delete.")
                for rec_to_delete in existing_augmented:
                    # Delete recording metadata
                    self.recording_repo.delete(rec_to_delete, rec_to_delete.user_id)
                    # Delete associated feature metadata and files (more complex - needs FeatureService method or careful repo/FM calls)
                    # For now, just logging the need
                    self.logger.debug(f"Need to delete features for deleted augmented recording {rec_to_delete.id}")
            except Exception as del_e:
                self.logger.error(f"Error during pre-augmentation deletion: {del_e}")
                # Decide if this error should halt the process

            # Only loop and augment if force_augmentation is true
            for gold_rec in gold_recordings:
                 class_name = class_id_to_name.get(gold_rec.class_id)
                 if not class_name:
                     msg = f"Skipping augmentation for {gold_rec.id}: Cannot find class name for ID {gold_rec.class_id}."
                     self.logger.warning(msg)
                     augmentation_errors.append(msg)
                     continue
                 try:
                     aug_result = self.augmentation_service.augment_single_recording(
                         user_id=gold_rec.user_id,
                         dictionary_id=dictionary_id,
                         class_name=class_name,
                         recording_id=gold_rec.id,
                         num_augmentations=num_augmentations_per_file
                     )
                     total_augs_created += aug_result.get('augmentations_created', 0)
                     total_augs_failed += aug_result.get('failures', 0)
                     if aug_result.get('failures', 0) > 0:
                         augmentation_errors.append(f"Failures during augmentation for {gold_rec.id}: {aug_result.get('message')}")
                 except Exception as aug_e:
                     msg = f"Error augmenting gold recording {gold_rec.id}: {aug_e}"
                     self.logger.error(msg, exc_info=True)
                     augmentation_errors.append(msg)
                     total_augs_failed += num_augmentations_per_file
                     augmentation_step_success = False

            augmentation_run_status = 'success' if augmentation_step_success else 'partial_error'
            if not augmentation_step_success and not augmentation_errors: # Catch case where loop didn't run
                 augmentation_run_status = 'error'

            step_status_aug = {
                 'step': 'generate_augmentations',
                 'status': augmentation_run_status,
                 'gold_files_processed': len(gold_recordings),
                 'augmentations_created': total_augs_created,
                 'augmentations_failed': total_augs_failed
            }
            if augmentation_errors:
                 step_status_aug['errors_or_warnings'] = augmentation_errors
            result['steps'].append(step_status_aug)

        elif include_augmented:
            # If augmentation is included but not forced, just mark as skipped
            self.logger.info("Augmentation included but not forced. Skipping generation.")
            augmentation_run_status = 'skipped (not forced)'
            result['steps'].append({'step': 'generate_augmentations', 'status': augmentation_run_status})
        else:
             # If augmentation is not included at all
             self.logger.info("Augmentation not included. Skipping generation.")
             augmentation_run_status = 'skipped (not included)'
             result['steps'].append({'step': 'generate_augmentations', 'status': augmentation_run_status})

        # --- Step 3: Check AUGMENTED Features (if included) --- 
        # This check runs regardless of whether augmentation was *run*, 
        # as features might exist from a previous run.
        if include_augmented:
            self.logger.info(f"Checking AUGMENTED features for dict {dictionary_id}, version {feature_version}")
            feature_check_errors_aug = []
            try:
                augmented_recordings = self.recording_repo.get_all_for_dictionary(
                    dictionary_id=dictionary_id,
                    user_id=user_id,
                    rec_type=RecordingType.AUGMENTED
                )
                result['feature_status']['augmented']['total'] = len(augmented_recordings)
                extracted_count_aug = 0
                for rec in augmented_recordings:
                    try:
                        extractions = self.feature_repo.get_extractions_for_recording(user_id, rec.id)
                        if any(ext.feature_set_id == feature_version for ext in extractions):
                            extracted_count_aug += 1
                    except Exception as check_exc_aug:
                        msg = f"Error checking features for augmented recording {rec.id}: {check_exc_aug}"
                        self.logger.warning(msg)
                        feature_check_errors_aug.append(msg)

                result['feature_status']['augmented']['extracted'] = extracted_count_aug
                step_status_check_aug = {
                    'step': 'check_augmented_features',
                    'status': 'success',
                    'total_files': len(augmented_recordings),
                    'files_with_features': extracted_count_aug
                }
                if feature_check_errors_aug:
                    step_status_check_aug['warnings'] = feature_check_errors_aug
                result['steps'].append(step_status_check_aug)

            except Exception as e_check_aug:
                msg = f"Error retrieving/checking augmented recordings: {e_check_aug}"
                self.logger.error(msg, exc_info=True)
                result['steps'].append({'step': 'check_augmented_features', 'status': 'error', 'error': msg})
                # Even if checking augmented fails, we might proceed if gold is okay

        # Determine overall readiness based on gold standard features
        result['data_ready'] = result['feature_status']['gold']['extracted'] > 0
        if not result['data_ready']:
             self.logger.warning(f"Data preparation failed: No usable GOLD features found for version {feature_version}. Cannot train.")

        # Final status reflects whether augmentation was included (even if it partially failed but gold is OK)
        result['include_augmented'] = include_augmented and augmentation_run_status == 'success' and result['feature_status']['augmented']['extracted'] > 0
        return result
    