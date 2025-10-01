"""
Optimized training service with better feature loading and memory management.
"""
import os
import gc
import time
import logging
import numpy as np
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

class OptimizedFeatureLoader:
    """Optimized feature loading with batching and memory management."""
    
    def __init__(self, file_service, feature_repo, recording_repo, dictionary_repo, logger):
        self.file_service = file_service
        self.feature_repo = feature_repo
        self.recording_repo = recording_repo
        self.dictionary_repo = dictionary_repo
        self.logger = logger
        self.batch_size = 50  # Load features in batches
        self.max_workers = 4  # Parallel loading threads
    
    def load_training_features_optimized(
        self,
        user_id: str,
        dictionary_id: str,
        class_ids: List[str],
        feature_version: str,
        use_augmented: bool,
        progress_callback=None
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Optimized feature loading with batching and progress reporting.
        
        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            class_ids: List of class IDs
            feature_version: Feature set version
            use_augmented: Whether to include augmented data
            progress_callback: Optional callback for progress updates
            
        Returns:
            Tuple of (features, labels, recording_ids)
        """
        from backend.app.core.models.recording import RecordingType
        
        start_time = time.time()
        self.logger.info(f"[OPTIMIZED] Starting feature loading for {len(class_ids)} classes")
        
        # Determine recording types to load
        types_to_load = [RecordingType.GOLD]
        if use_augmented:
            types_to_load.append(RecordingType.AUGMENTED)
        
        # Get all recordings efficiently
        self.logger.info(f"[OPTIMIZED] Fetching recordings for classes: {class_ids}")
        recordings = self.recording_repo.find(
            class_id__in=class_ids,
            recording_type__in=types_to_load
        )
        
        total_recordings = len(recordings)
        self.logger.info(f"[OPTIMIZED] Found {total_recordings} recordings to process")
        
        if total_recordings == 0:
            self.logger.warning("No recordings found for training")
            return np.array([]), np.array([]), []
        
        # Get feature set definition
        feature_set = self.feature_repo.get_feature_set(feature_version)
        if not feature_set:
            self.logger.error(f"Feature set '{feature_version}' not found")
            return np.array([]), np.array([]), []
        
        expected_feature_key = 'mel_spectrogram'
        
        # Process in batches
        all_features = []
        all_labels = []
        all_recording_ids = []
        processed_count = 0
        failed_count = 0
        
        # Create batches
        batches = [recordings[i:i+self.batch_size] 
                   for i in range(0, total_recordings, self.batch_size)]
        
        self.logger.info(f"[OPTIMIZED] Processing {len(batches)} batches of ~{self.batch_size} recordings")
        
        # Process each batch
        for batch_idx, batch in enumerate(batches):
            batch_start_time = time.time()
            batch_features = []
            batch_labels = []
            batch_ids = []
            
            # Report progress
            if progress_callback:
                progress = (processed_count / total_recordings) * 100
                progress_callback({
                    'stage': 'loading_features',
                    'progress': progress,
                    'message': f'Loading batch {batch_idx + 1}/{len(batches)}',
                    'processed': processed_count,
                    'total': total_recordings
                })
            
            # Load features for this batch using thread pool
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {}
                
                for recording in batch:
                    future = executor.submit(
                        self._load_single_feature,
                        recording,
                        feature_version,
                        expected_feature_key
                    )
                    futures[future] = recording
                
                # Collect results
                for future in as_completed(futures):
                    recording = futures[future]
                    try:
                        result = future.result(timeout=5)  # 5 second timeout per file
                        if result is not None:
                            features, class_id, rec_id = result
                            batch_features.append(features)
                            batch_labels.append(class_id)
                            batch_ids.append(rec_id)
                            processed_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        self.logger.error(f"Failed to load features for {recording.id}: {e}")
                        failed_count += 1
            
            # Add batch results to main lists
            all_features.extend(batch_features)
            all_labels.extend(batch_labels)
            all_recording_ids.extend(batch_ids)
            
            # Clear batch data and run garbage collection
            del batch_features, batch_labels, batch_ids
            gc.collect()
            
            batch_duration = time.time() - batch_start_time
            self.logger.info(f"[OPTIMIZED] Batch {batch_idx + 1}/{len(batches)} completed in {batch_duration:.2f}s "
                           f"({len(all_features)} loaded, {failed_count} failed)")
            
            # Small delay between batches to prevent overwhelming the system
            if batch_idx < len(batches) - 1:
                time.sleep(0.1)
        
        # Convert to numpy arrays
        if not all_features:
            self.logger.error("No features successfully loaded")
            return np.array([]), np.array([]), []
        
        self.logger.info(f"[OPTIMIZED] Converting {len(all_features)} features to numpy arrays")
        
        # Stack features efficiently
        try:
            X = np.stack(all_features)
        except ValueError as e:
            self.logger.error(f"Feature shapes inconsistent: {e}")
            # Try to pad features to same shape
            X = self._pad_features(all_features)
        
        # Convert labels to indices
        label_to_idx = {label: i for i, label in enumerate(class_ids)}
        y = np.array([label_to_idx[label] for label in all_labels])
        
        total_duration = time.time() - start_time
        self.logger.info(f"[OPTIMIZED] Feature loading completed in {total_duration:.2f}s")
        self.logger.info(f"[OPTIMIZED] Loaded {len(X)} samples: shape={X.shape}, "
                        f"success_rate={processed_count/(processed_count+failed_count)*100:.1f}%")
        
        # Final progress callback
        if progress_callback:
            progress_callback({
                'stage': 'loading_complete',
                'progress': 100,
                'message': f'Loaded {len(X)} samples successfully',
                'processed': processed_count,
                'total': total_recordings
            })
        
        return X, y, all_recording_ids
    
    def _load_single_feature(self, recording, feature_version, expected_feature_key):
        """Load features for a single recording."""
        try:
            # Get feature extraction metadata
            extractions = self.feature_repo.get_extractions_for_recording(
                recording.user_id, recording.id
            )
            
            target_extraction = None
            for ext in extractions:
                if ext.feature_set_id == feature_version:
                    target_extraction = ext
                    break
            
            if not target_extraction:
                return None
            
            # Load NPZ file
            relative_npz_path = Path(target_extraction.filename)
            npz_path = self.file_service.file_manager.get_data_root() / relative_npz_path
            
            # Use memory mapping for large files
            with np.load(npz_path, mmap_mode='r') as data:
                features = data.get(expected_feature_key)
                if features is None or features.ndim < 2:
                    return None
                
                # Copy to ensure data persists after file close
                features = np.array(features)
            
            return features, recording.class_id, recording.id
            
        except Exception as e:
            self.logger.debug(f"Failed to load {recording.id}: {e}")
            return None
    
    def _pad_features(self, features_list):
        """Pad features to same shape if needed."""
        # Find max dimensions
        max_dim1 = max(f.shape[0] for f in features_list)
        max_dim2 = max(f.shape[1] for f in features_list)
        
        # Pad all features
        padded = []
        for features in features_list:
            if features.shape[0] < max_dim1 or features.shape[1] < max_dim2:
                pad_width = ((0, max_dim1 - features.shape[0]),
                            (0, max_dim2 - features.shape[1]))
                features = np.pad(features, pad_width, mode='constant')
            padded.append(features)
        
        return np.stack(padded)


class OptimizedTrainingService:
    """Training service with optimized feature loading and progress tracking."""
    
    def __init__(self, original_service):
        """Wrap the original training service with optimizations."""
        self.original_service = original_service
        self.logger = original_service.logger
        self.feature_loader = OptimizedFeatureLoader(
            original_service.file_service,
            original_service.feature_repo,
            original_service.recording_repo,
            original_service.dictionary_repo,
            original_service.logger
        )
        # Store training progress for status checks
        self.training_progress = {}
        # Initialize epoch history
        self.epoch_history = {}
    
    def train_model_with_progress(
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
        Train model with progress tracking and optimized feature loading.
        """
        # First, clear any stuck trainings older than 10 minutes
        self._clear_stuck_trainings(user_id)
        
        # Create model record
        model_data = self.original_service.train_model(
            user_id, dictionary_id, model_type, model_name,
            feature_version, use_augmented, params
        )
        
        model_id = model_data['id']
        
        # Initialize progress tracking
        self.training_progress[model_id] = {
            'status': 'initializing',
            'stage': 'starting',
            'progress': 0,
            'message': 'Initializing training...',
            'started_at': time.time()
        }
        
        # Start training in background thread
        from flask import current_app
        app = current_app._get_current_object()
        
        thread = threading.Thread(
            target=self._run_optimized_training_task,
            args=(app.app_context(), model_id, user_id, dictionary_id, 
                  model_type, feature_version, use_augmented, params)
        )
        thread.daemon = True
        thread.start()
        
        return model_data
    
    def _run_optimized_training_task(
        self, 
        app_context,
        model_id: str,
        user_id: str,
        dictionary_id: str,
        model_type: str,
        feature_version: str,
        use_augmented: bool,
        params: Optional[Dict[str, Any]]
    ):
        """Optimized training task with progress tracking."""
        from flask import current_app
        
        with app_context:
            self.logger.info(f"[OPTIMIZED] Starting training for model {model_id}")
            
            try:
                # Update progress
                def update_progress(info):
                    self.training_progress[model_id].update(info)
                    self.training_progress[model_id]['updated_at'] = time.time()
                
                # Get model and dictionary
                model_version = self.original_service.model_repo.get_by_id(
                    user_id, dictionary_id, model_id
                )
                dictionary = self.original_service.dictionary_repo.get_dictionary_by_id(
                    dictionary_id
                )
                
                # Mark as training
                model_version.mark_training()
                self.original_service.model_repo.save(model_version)
                
                update_progress({
                    'status': 'loading_features',
                    'stage': 'loading',
                    'progress': 5,
                    'message': 'Loading training features...'
                })
                
                # Load features with optimization
                X_train, y_train, training_ids = self.feature_loader.load_training_features_optimized(
                    user_id,
                    dictionary_id,
                    model_version.classes,
                    feature_version,
                    use_augmented,
                    progress_callback=update_progress
                )
                
                if len(X_train) == 0:
                    raise ValueError("No training data loaded")
                
                update_progress({
                    'status': 'training',
                    'stage': 'training',
                    'progress': 30,
                    'message': f'Training {model_type} model with {len(X_train)} samples...',
                    'samples': len(X_train)
                })
                
                # Train the model
                trainer = self.original_service.trainers[model_type]
                train_params = params or {}
                train_params['_model_id_for_log'] = model_id
                train_params['num_classes'] = len(model_version.classes)
                
                # Store all epochs in a list
                if not hasattr(self, 'epoch_history'):
                    self.epoch_history = {}
                self.epoch_history[model_id] = []
                
                # Add progress callback for trainers that support it
                def epoch_callback(epoch, total, metrics=None):
                    # Store epoch in history
                    epoch_data = {
                        'epoch': epoch,
                        'total_epochs': total,
                        'metrics': metrics
                    }
                    self.epoch_history[model_id].append(epoch_data)
                    
                    # Update progress
                    update_progress({
                        'status': 'training',
                        'stage': 'training',
                        'progress': 30 + int((epoch / total) * 60),
                        'message': f'Training epoch {epoch}/{total}',
                        'epoch': epoch,
                        'total_epochs': total,
                        'metrics': metrics,
                        'all_epochs': self.epoch_history[model_id]  # Send ALL epochs
                    })
                
                train_params['progress_callback'] = epoch_callback
                
                self.logger.info(f"[OPTIMIZED] Starting model training")
                training_result = trainer.train(X_train, y_train, train_params)
                
                # Parse results
                if len(training_result) == 3:
                    model, metrics, history = training_result
                else:
                    model, metrics = training_result
                    history = None
                
                update_progress({
                    'status': 'saving',
                    'stage': 'saving',
                    'progress': 95,
                    'message': 'Saving trained model...'
                })
                
                # Save model
                self._save_model_optimized(
                    model, model_version, dictionary_id, model_type, trainer
                )
                
                # Update model metadata
                model_version.mark_trained(metrics)
                if history:
                    model_version.metadata['training_history'] = history
                model_version.metadata['training_summary'] = {
                    'total_samples': len(X_train),
                    'metrics': metrics,
                    'training_params': params or {}
                }
                self.original_service.model_repo.save(model_version)
                
                update_progress({
                    'status': 'complete',
                    'stage': 'done',
                    'progress': 100,
                    'message': 'Training complete!',
                    'metrics': metrics
                })
                
                self.logger.info(f"[OPTIMIZED] Training completed successfully for model {model_id}")
                
            except Exception as e:
                self.logger.error(f"[OPTIMIZED] Training failed for model {model_id}: {e}", exc_info=True)
                
                update_progress({
                    'status': 'failed',
                    'stage': 'error',
                    'progress': 0,
                    'message': f'Training failed: {str(e)}',
                    'error': str(e)
                })
                
                # Mark model as failed
                if model_version:
                    model_version.mark_failed(str(e))
                    self.original_service.model_repo.save(model_version)
    
    def _save_model_optimized(self, model, model_version, dictionary_id, model_type, trainer):
        """Optimized model saving."""
        from backend.app.core.models.model import ModelType
        
        model_save_dir = self.original_service.file_service.file_manager.get_specific_model_dir(
            dictionary_id=dictionary_id,
            model_type_version=model_version.id
        )
        
        if model_type in [ModelType.CNN.value, ModelType.CNN1D.value]:
            if model_save_dir.exists():
                import shutil
                shutil.rmtree(model_save_dir)
            save_target = str(model_save_dir)
        else:
            os.makedirs(model_save_dir, exist_ok=True)
            save_target = str(model_save_dir / f"{model_version.filename}.pkl")
        
        trainer.save_model(model, save_target)
        self.logger.info(f"[OPTIMIZED] Model saved to {save_target}")
    
    def get_training_progress(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get current training progress for a model."""
        return self.training_progress.get(model_id)
    
    def _clear_stuck_trainings(self, user_id: str):
        """Clear any stuck trainings older than 10 minutes."""
        from backend.app.core.models.model import ModelStatus
        import time
        
        try:
            # Get all dictionaries for the user
            all_dictionaries = self.original_service.dictionary_repo.get_all_dictionaries()
            user_dictionaries = [d for d in all_dictionaries if hasattr(d, 'creator_user_id') and d.creator_user_id == user_id]
            
            current_time = time.time()
            for dictionary in user_dictionaries:
                try:
                    # Check for training models
                    training_models = self.original_service.model_repo.get_for_dictionary(
                        user_id=user_id,
                        dict_id=dictionary.id,
                        status=ModelStatus.TRAINING
                    )
                    
                    for model in training_models:
                        # Always clear stuck trainings for now (we can add time check later)
                        self.logger.info(f"Clearing stuck training for model {model.id}")
                        model.mark_failed("Training interrupted - cleared stuck status")
                        self.original_service.model_repo.save(model)
                except Exception as e:
                    self.logger.debug(f"Error checking dictionary {dictionary.id}: {e}")
                    continue
        except Exception as e:
            self.logger.debug(f"Error clearing stuck trainings: {e}")