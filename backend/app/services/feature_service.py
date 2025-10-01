import os
import logging
import numpy as np
import librosa
import json
import io
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from backend.app.core.models.feature import FeatureSet, FeatureExtraction
from backend.app.core.models.recording import Recording, RecordingType
from backend.app.core.repositories.feature_repo import FeatureRepository
from backend.app.core.repositories.recording_repo import RecordingRepository
from backend.app.core.repositories.dictionary_repo import DictionaryRepository
from backend.app.services.file_service import FileService
from backend.app.ml.features.extractor import FullFeatureExtractor, CustomFeatureExtractor


class FeatureService:
    """
    Service for feature extraction.
    
    Provides business logic for extracting features from audio recordings
    and managing feature sets.
    Focuses on extracting features for individual recordings.
    """
    
    def __init__(self, feature_repo: FeatureRepository, 
                recording_repo: RecordingRepository,
                file_service: FileService,
                dictionary_repo: DictionaryRepository):
        """
        Initialize the feature service.
        
        Args:
            feature_repo: Repository for feature operations
            recording_repo: Repository for recording operations
            file_service: Service for file operations
            dictionary_repo: Repository for dictionary operations
        """
        self.feature_repo = feature_repo
        self.recording_repo = recording_repo
        self.file_service = file_service
        self.dictionary_repo = dictionary_repo
        self.logger = logging.getLogger(__name__)
        
        # Default feature set configuration
        self.default_feature_params = {
            "sample_rate": 16000,
            "n_mfcc": 40,
            "n_mels": 128,
            "n_fft": 160,
            "hop_length": 80,
            "win_length": 160,
            "window": "hann",
            "center": True,
            "pad_mode": "reflect"
        }
        
        # Initialize the feature extractor
        self.feature_extractor = FullFeatureExtractor(self.default_feature_params)
    
    # DB-OPERATION: create feature
    def create_feature_set(self, id: str, name: str, description: str, 
                          features: List[str], parameters: Optional[Dict[str, Any]] = None) -> FeatureSet:
        """
        Create a new feature set.
        
        Args:
            id: Version identifier for the feature set (e.g., 'v0.1')
            name: Human-readable name
            description: Description of the feature set
            features: List of feature names included in this set
            parameters: Parameters for feature extraction (defaults to self.default_feature_params)
            
        Returns:
            Created FeatureSet
        """
        if parameters is None:
            parameters = self.default_feature_params
        
        feature_set = FeatureSet.create(id, name, description, features, parameters)
        
        if self.feature_repo.save_feature_set(feature_set):
            self.logger.info(f"Created feature set {feature_set.id}")
        else:
            self.logger.error(f"Failed to save feature set {feature_set.id}")
        
        return feature_set
    
    # DB-OPERATION: read feature
    def get_feature_set(self, feature_set_id: str) -> Optional[FeatureSet]:
        """
        Get a feature set by ID.
        
        Args:
            feature_set_id: Feature set ID
            
        Returns:
            FeatureSet if found, None otherwise
        """
        return self.feature_repo.get_feature_set(feature_set_id)
    
    # DB-OPERATION: read feature
    def get_all_feature_sets(self) -> List[FeatureSet]:
        """
        Get all feature sets.
        
        Returns:
            List of feature sets
        """
        return self.feature_repo.get_all_feature_sets()
    
    # DB-OPERATION: create feature
    def create_default_feature_set(self) -> FeatureSet:
        """
        Create the default v0.1 feature set.
        
        Returns:
            Created FeatureSet
        """
        return self.create_feature_set(
            id="v0.1",
            name="Full Feature Set v0.1",
            description="Complete feature set containing all audio features for model training",
            features=self.feature_extractor.get_feature_names(),
            parameters=self.default_feature_params
        )
    
    def extract_features(self, audio_data: np.ndarray, sample_rate: int, 
                        feature_set_id: str = "v0.1") -> Dict[str, Any]:
        """
        Extract features from audio data using the appropriate extractor.
        
        Args:
            audio_data: Audio data as numpy array
            sample_rate: Sample rate of the audio
            feature_set_id: Feature set ID to use
            
        Returns:
            Dictionary of extracted features
        """
        try:
            # Get the feature set
            feature_set = self.feature_repo.get_feature_set(feature_set_id)
            
            if not feature_set:
                self.logger.warning(f"Feature set {feature_set_id} not found, using default parameters")
                extractor = self.feature_extractor
            else:
                # Create a feature extractor based on the feature set
                extractor = CustomFeatureExtractor(feature_set.features, feature_set.parameters)
            
            # Extract features using the ML component
            features = extractor.extract_features(audio_data, sample_rate)
            
            # Add feature set info to metadata
            features['metadata']['feature_set_id'] = feature_set_id
            
            self.logger.info(f"Successfully extracted features with feature set {feature_set_id}")
            return features
        except Exception as e:
            self.logger.error(f"Error extracting features: {str(e)}")
            return {'error': str(e)}
    
    def extract_features_from_file(self, audio_file_path: str, 
                                feature_set_id: str = "v0.1") -> Dict[str, Any]:
        """
        Extract features from an audio file.
        
        Args:
            audio_file_path: Path to the audio file
            feature_set_id: Feature set ID to use
            
        Returns:
            Dictionary of extracted features
        """
        try:
            # Load the audio file
            audio_data, sample_rate = librosa.load(audio_file_path, sr=None)
            
            # Extract features using the ML component
            return self.extract_features(audio_data, sample_rate, feature_set_id)
        except Exception as e:
            self.logger.error(f"Error extracting features from file {audio_file_path}: {str(e)}")
            return {'error': str(e)}
    
    def extract_features_from_bytes(self, audio_bytes: bytes,
                                  feature_set_id: str = "v0.1") -> Dict[str, Any]:
        """
        Extract features from audio data in bytes.
        
        Args:
            audio_bytes: Binary audio data
            feature_set_id: Feature set ID to use
            
        Returns:
            Dictionary of extracted features
        """
        try:
            # Convert audio bytes to in-memory file
            audio_io = io.BytesIO(audio_bytes)
            
            # Load audio with librosa
            audio_data, sample_rate = librosa.load(audio_io, sr=None)
            
            # Extract features using the ML component
            return self.extract_features(audio_data, sample_rate, feature_set_id)
        except Exception as e:
            self.logger.error(f"Error extracting features from bytes: {str(e)}")
            return {'error': str(e)}
    
    def extract_features_for_recording(self,
                                     user_id: str,
                                     dictionary_id: Optional[str],
                                     recording_id: str,
                                     feature_set_id: str = "v0.1"
                                     ) -> Tuple[bool, Optional[FeatureExtraction]]:
        """
        Extract features for a specific recording using V10 paths and save as NPZ.
        Dictionary ID is used for metadata context, not for the file path.
        """
        self.logger.info(f"Starting feature extraction for recording: {recording_id}, user: {user_id}, dict: {dictionary_id}, set: {feature_set_id}")
        try:
            # --- 1. Get Recording Metadata ---
            recording = self.recording_repo.find_by_id(recording_id)
            if not recording:
                self.logger.warning(f"Recording {recording_id} not found via repository.")
                return False, None

            if recording.user_id != user_id:
                self.logger.warning(f"User mismatch: Recording {recording_id} belongs to {recording.user_id}, requested by {user_id}.")
                # Allow for now, but consider if admin/shared access rules apply

            class_name = recording.metadata.get('class_name')
            if not class_name:
                 class_name = self.recording_repo._get_class_name(recording.class_id)
            
            if not class_name:
                self.logger.error(f"Cannot determine class name for recording {recording_id} (class_id: {recording.class_id}).")
                return False, None

            # --- 2. Get Correct V10 Audio Path ---
            # Use the path from metadata if available (most reliable), or relative_wav_path
            from pathlib import Path
            if recording.metadata and 'path' in recording.metadata:
                audio_path = Path(recording.metadata['path'])
                self.logger.info(f"Using path from recording.metadata['path']: {audio_path}")
            elif recording.relative_wav_path:
                audio_path = self.file_service.file_manager.data_root / recording.relative_wav_path
                self.logger.info(f"Using relative_wav_path: {audio_path}")
            else:
                # Fallback: construct path from ID components
                audio_filename = f"{recording.id}.wav"
                audio_path = self.file_service.file_manager.data_root / "sounds" / class_name / recording.user_id / recording.recording_type.value / audio_filename
                self.logger.info(f"Using direct path construction (fallback): {audio_path}")

            # --- 3. Load Audio ---
            try:
                audio_data, sample_rate = librosa.load(str(audio_path), sr=None, mono=True)
                self.logger.debug(f"Audio loaded: sr={sample_rate}, shape={audio_data.shape}")
            except FileNotFoundError:
                self.logger.error(f"Audio file not found at path: {audio_path}")
                return False, None
            except Exception as load_err:
                self.logger.error(f"Failed to load audio from {audio_path}: {load_err}", exc_info=True)
                return False, None

            # --- 4. Extract Features ---
            feature_set = self.feature_repo.get_feature_set(feature_set_id)
            target_sr = self.default_feature_params.get('sample_rate', 16000)
            if feature_set and feature_set.parameters and 'sample_rate' in feature_set.parameters:
                target_sr = feature_set.parameters['sample_rate']
            elif feature_set_id != "v0.1":
                self.logger.warning(f"Could not load feature set '{feature_set_id}' to get target sample rate. Using default {target_sr}Hz.")

            if sample_rate != target_sr:
                self.logger.warning(f"Resampling audio from {sample_rate}Hz to {target_sr}Hz for feature extraction.")
                audio_data = librosa.resample(audio_data, orig_sr=sample_rate, target_sr=target_sr)
                sample_rate = target_sr

            features_dict = self.extract_features(audio_data, sample_rate, feature_set_id)
            if 'error' in features_dict:
                self.logger.error(f"Feature extraction step failed for recording {recording_id}: {features_dict['error']}")
                return False, None
 
            # --- 5. Determine Correct V10 Feature Save Path and Filename (.npz) ---
            # Determine subset based on recording type
            subset = 'gold' if recording.recording_type == RecordingType.GOLD else \
                     'augmented' if recording.recording_type == RecordingType.AUGMENTED else \
                     'unknown_subset'

            if subset == 'unknown_subset':
                 self.logger.warning(f"Feature extraction for recording type '{recording.recording_type.value}' "
                                     f"not mapped to 'gold' or 'augmented' subset. Saving path might be incorrect.")
                 subset = recording.recording_type.value # Use type name as subset placeholder

            # Extract base ID without _segX if present for cleaner filename grouping
            recording_id_base = recording.id.split('_seg')[0]
            npz_filename = f"{recording_id_base}_features.npz"

            # Get dictionary ID from metadata - ONLY for FeatureExtraction record context, NOT for path
            dictionary_id_context = recording.metadata.get('dictionary_id', dictionary_id)
            if not dictionary_id_context:
                self.logger.debug(f"Recording {recording.id} has no dictionary_id in metadata and none was passed to function.")

            # Get V10 Path using FileManager method (WITHOUT dictionary_id)
            try:
                 feature_npz_path = self.file_service.file_manager.get_feature_data_path(
                     feature_version=feature_set_id,
                     user_id=recording.user_id, # Use owner's ID for path
                     subset=subset,
                     class_name=class_name,
                     filename=npz_filename
                 )
                 self.logger.debug(f"Determined feature NPZ save path: {feature_npz_path}")
            except AttributeError:
                 self.logger.error("FileManager missing V10 'get_feature_data_path' method! Cannot determine save location.")
                 return False, None # Cannot proceed without path logic
            except Exception as path_err:
                 self.logger.error(f"Error getting V10 feature data path for {recording.id}: {path_err}", exc_info=True)
                 return False, None # Cannot proceed without path logic


            # --- 6. Save Features to NPZ File ---
            try:
                feature_npz_path.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(str(feature_npz_path), **features_dict)
            except Exception as save_err:
                self.logger.error(f"Failed to save feature NPZ file for recording {recording_id} to {feature_npz_path}: {save_err}", exc_info=True)
                return False, None

            # --- 7. Create and Save FeatureExtraction Metadata ---
            feature_extraction = FeatureExtraction.create(
                recording_id=recording.id,
                feature_set_id=feature_set_id,
                filename=str(feature_npz_path.relative_to(self.file_service.file_manager.get_data_root())),
                metadata={
                    'dictionary_id': dictionary_id_context,
                    'class_id': recording.class_id,
                    'class_name': class_name,
                    'recording_type': recording.recording_type.value,
                    'subset': subset,
                    'duration': features_dict.get('metadata', {}).get('duration'),
                    'n_frames': features_dict.get('metadata', {}).get('n_frames')
                }
            )

            # Save metadata to the RECORDING owner's directory, not the requesting user's
            if not self.feature_repo.save_extraction(feature_extraction, recording.user_id):
                self.logger.error(f"Failed to save feature extraction metadata for recording {recording_id}. Feature file was saved to {feature_npz_path}.")
            else:
                self.logger.info(f"Saved feature extraction metadata for ID: {feature_extraction.id} to user {recording.user_id}")

            self.logger.info(f"Successfully extracted and saved features for recording {recording_id}")
            return True, feature_extraction

        except Exception as e:
            self.logger.error(f"Error extracting features for recording {recording_id}: {e}", exc_info=True)
            return False, None

    def get_dictionary_feature_status(self, user_id: str, dictionary_id: str, feature_set_id: str = "v0.1") -> Dict[str, int]:
        """
        Calculates the feature extraction status for a given dictionary and feature set.

        Args:
            user_id: The ID of the user requesting the status.
            dictionary_id: The ID of the dictionary to check.
            feature_set_id: The ID of the feature set to check against (defaults to "v0.1").

        Returns:
            A dictionary containing counts:
            {
                "total_files": int,
                "files_with_features": int,
                "files_missing_features": int
            }
            Returns counts of 0 if the dictionary is not found or inaccessible.
        """
        self.logger.info(f"Calculating feature status for dict: {dictionary_id}, user: {user_id}, set: {feature_set_id}")
        status = {
            "total_files": 0,
            "files_with_features": 0,
            "files_missing_features": 0
        }

        try:
            # 1. Get the dictionary to find its associated class IDs
            # Assuming dictionary_repo has a method like get_dictionary_by_id
            # Note: This assumes the dictionary_repo doesn't need user_id for *this* lookup,
            # or that permission checks happen elsewhere if needed.
            dictionary = self.dictionary_repo.get_dictionary_by_id(dictionary_id)
            if not dictionary:
                self.logger.warning(f"Dictionary {dictionary_id} not found for feature status check.")
                return status # Return zeros if dictionary doesn't exist

            # Optional: Add permission check here if repo didn't do it
            # if dictionary.creator_user_id != user_id:
            #    self.logger.warning(f"User {user_id} permission denied for dictionary {dictionary_id}.")
            #    return status # Return zeros if no permission

            class_ids = dictionary.class_ids
            if not class_ids:
                self.logger.info(f"Dictionary {dictionary_id} has no associated classes.")
                return status # Return zeros if no classes

            # 2. Get all relevant recordings for these classes
            # Find GOLD and AUGMENTED recordings matching the class IDs
            # Check config to see if we should include all users' recordings
            from flask import current_app
            include_all_users = current_app.config.get('INCLUDE_ALL_USER_RECORDINGS', False)
            
            if include_all_users:
                # Get recordings from all users for these classes
                relevant_recordings = self.recording_repo.find(
                    class_id__in=class_ids, # Filter by classes in the dictionary
                    recording_type__in=[RecordingType.GOLD, RecordingType.AUGMENTED] # Only check relevant types
                )
            else:
                # Get recordings only from this user
                relevant_recordings = self.recording_repo.find(
                    user_id=user_id, # Filter by user
                    class_id__in=class_ids, # Filter by classes in the dictionary
                    recording_type__in=[RecordingType.GOLD, RecordingType.AUGMENTED] # Only check relevant types
                )

            if not relevant_recordings:
                self.logger.info(f"No GOLD or AUGMENTED recordings found for user {user_id} and classes in dictionary {dictionary_id}.")
                return status # Return zeros if no relevant recordings

            status["total_files"] = len(relevant_recordings)
            relevant_recording_ids = {rec.id for rec in relevant_recordings} # Set for efficient lookup

            # 3. Get existing feature extraction metadata for the specified feature set
            # If viewing all users' recordings, get all users' extractions too
            if include_all_users:
                existing_extractions = self.feature_repo.get_extractions_for_feature_set(
                    user_id=None,  # Get all users' extractions
                    feature_set_id=feature_set_id
                )
            else:
                existing_extractions = self.feature_repo.get_extractions_for_feature_set(
                    user_id=user_id,
                    feature_set_id=feature_set_id
                )

            # 4. Count how many relevant recordings have existing extraction metadata
            found_count = 0
            if existing_extractions:
                # Create a set of recording IDs that *have* features for faster checking
                recording_ids_with_features = {ext.recording_id for ext in existing_extractions}
                # Count the intersection
                found_count = len(relevant_recording_ids.intersection(recording_ids_with_features))

            status["files_with_features"] = found_count
            status["files_missing_features"] = status["total_files"] - found_count

            self.logger.info(f"Feature status for dict {dictionary_id}: {status}")
            return status

        except Exception as e:
            self.logger.error(f"Error calculating feature status for dictionary {dictionary_id}: {e}", exc_info=True)
            # Return zeros or re-raise depending on desired error handling
            return { "total_files": 0, "files_with_features": 0, "files_missing_features": 0 } # Default to 0 on error

# End of class FeatureService
