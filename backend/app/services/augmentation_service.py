"""
Service for audio augmentation functionality.

This module provides a service layer for audio augmentation operations,
integrating with the AudioAugmentor class for core augmentation functionality,
focusing specifically on augmenting single recordings.
"""

import os
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
import uuid

from ..core.repositories.recording_repo import RecordingRepository
from ..storage.file_manager import FileManager
from ..ml.augmentation.augmentor import AudioAugmentor
from ..core.models.recording import Recording, RecordingType
from ..services.dictionary_service import DictionaryService
from ..auth.models import User
from ..core.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)

class AugmentationService:
    """Service for managing single audio recording augmentation operations."""
    
    def __init__(
        self,
        file_manager: FileManager,
        recording_repo: RecordingRepository,
        dictionary_service: DictionaryService,
        user_repository: UserRepository,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the AugmentationService.
        
        Args:
            file_manager: File manager instance for accessing the file system
            recording_repo: Repository for accessing recording data
            dictionary_service: Service for accessing dictionaries
            user_repository: Repository for accessing user data
            config: Optional configuration parameters for the AudioAugmentor
        """
        self.file_manager = file_manager
        self.recording_repo = recording_repo
        self.dictionary_service = dictionary_service
        self.user_repository = user_repository
        self.config = config or {}
        # Initialize the core augmentor with the service's base config
        self.augmentor = AudioAugmentor(self.config)
        
    def _get_user_info(self, user_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Helper to get username and email from user_id."""
        user_data = self.user_repository.get_by_id(user_id)
        if user_data:
            # Assuming get_by_id returns a dict or User object
            if isinstance(user_data, dict):
                return user_data.get('username'), user_data.get('email')
            elif hasattr(user_data, 'username') and hasattr(user_data, 'email'):
                return user_data.username, user_data.email
        logger.warning(f"Could not find user info for user_id: {user_id}")
        return None, None

    def augment_single_recording(
        self,
        user_id: str,
        dictionary_id: str, # Keep context, might be useful later
        class_name: str,
        recording_id: str,
        num_augmentations: int = 5,
        augmentation_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate augmented versions of a single recording using specific config.

        Args:
            user_id: User ID
            dictionary_id: Dictionary ID (context)
            class_name: Class name
            recording_id: Recording ID of the GOLD instance to augment
            num_augmentations: Number of augmentations to generate
            augmentation_config: User-provided config for this run (enabled types, ranges)

        Returns:
            Dictionary with augmentation results
        """
        logger.info(f"Augmenting single recording: user={user_id}, dict={dictionary_id}, "
                    f"class={class_name}, recording={recording_id}, num_augs={num_augmentations}")
        if augmentation_config:
            logger.info(f"Using custom augmentation config: {augmentation_config}")
        else:
            logger.info("Using default augmentation config from service.")

        # --- Find the Gold Recording Metadata ---
        try:
            # Find GOLD recording by ID
            # Assuming recording object has `recording_type`, `class_id`, `relative_wav_path`
            recording = self.recording_repo.find_by_id(recording_id)
            if not recording:
                logger.error(f"Recording {recording_id} not found in repository.")
                raise ValueError(f"Recording {recording_id} not found")

            # Verify it's a GOLD recording
            # Ensure recording object has `recording_type` attribute
            if not hasattr(recording, 'recording_type') or recording.recording_type != RecordingType.GOLD:
                actual_type = getattr(recording, 'recording_type', 'Attribute Missing')
                logger.error(f"Recording {recording_id} is not a GOLD standard recording (Type: {actual_type}). Cannot augment.")
                raise ValueError(f"Recording {recording_id} is not GOLD standard.")

            # Verify class_name matches or update if necessary
            if recording.class_id:
                # Assuming a helper exists to get class name from ID
                pass # Keep structure, class_name is validated/updated later if needed.
                # Example validation logic was here previously, but class_name is handled
                # when getting class_obj from dictionary_service later.
            else:
                logger.error(f"Recording {recording_id} does not have a class_id.")
                raise ValueError(f"Missing class_id for recording {recording_id}")

            # Check for relative_wav_path
            if not recording.relative_wav_path:
                logger.error(f"Recording {recording_id} does not have a relative_wav_path.")
                raise ValueError(f"Missing path for recording {recording_id}")

        except AttributeError as ae:
            logger.error(f"Attribute error while accessing recording {recording_id} details: {ae}", exc_info=True)
            raise ValueError(f"Missing expected attribute on recording object {recording_id}: {ae}") from ae
        except Exception as e:
            logger.error(f"Error finding gold recording {recording_id}: {e}", exc_info=True)
            raise ValueError(f"Failed to find or validate gold recording {recording_id}: {e}") from e

        # --- Set up Augmented Directory ---
        try:
            class_obj = self.dictionary_service.get_class_by_name(class_name)
            if not class_obj:
                # If class_name is valid but object not found globally, proceed carefully
                logger.warning(f"Class '{class_name}' not found via dictionary_service. Proceeding with directory setup using class name.")
                # Fallback or alternative logic might be needed if class_obj.id is strictly required later
            
            # Use the correct file manager method to get the directory path
            augmented_dir = self.file_manager.get_sound_instance_dir(
                class_name=class_name, # Use the potentially corrected class_name
                user_id=user_id,
                recording_type=RecordingType.AUGMENTED
            )
            # Ensure the directory exists
            augmented_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured augmented directory exists: {augmented_dir}")

        except Exception as e:
            logger.error(f"Error setting up augmented directory for class {class_name}: {e}", exc_info=True)
            # Consider using a custom ProcessingError if defined elsewhere, otherwise stick to ValueError/RuntimeError
            raise ValueError(f"Failed to setup augmented directory: {e}") from e

        # --- Get Absolute Path to Gold Recording ---
        try:
            recording_path = self.file_manager.get_data_root() / recording.relative_wav_path
            if not recording_path.is_file():
                logger.error(f"Gold recording file not found at resolved path {recording_path} for ID {recording.id}")
                raise ValueError(f"Source recording file not found: {recording_path}")
        except Exception as e:
            logger.error(f"Error resolving gold recording path {recording.relative_wav_path}: {e}", exc_info=True)
            raise ValueError(f"Failed to resolve source recording path: {e}") from e

        # --- Instantiate Augmentor ---
        try:
            # Use user's config if provided, otherwise use the service's default config
            effective_config = augmentation_config if augmentation_config else self.augmentor.config
            augmentor_to_use = AudioAugmentor(config=effective_config)
            logger.debug(f"Augmentor instantiated with effective config: {augmentor_to_use.config}")
        except Exception as e:
            logger.error(f"Failed to instantiate AudioAugmentor: {e}", exc_info=True)
            raise RuntimeError(f"Failed to setup augmentor: {e}") from e

        # --- Generate Augmentations ---
        try:
            # Call generate_augmentations on the correctly configured instance
            # It returns a list of dicts: [{'augmented_file': '/path/to/temp_aug.wav', 'params': {...}}, ...]
            augmentations = augmentor_to_use.generate_augmentations(
                recording_path, augmented_dir, num_augmentations)
            logger.info(f"Augmentor generated {len(augmentations)} augmentations for {recording_id}")
        except Exception as e:
            logger.error(f"Error during augmentor.generate_augmentations for {recording_id}: {str(e)}", exc_info=True)
            raise RuntimeError(f"Augmentation generation failed: {str(e)}") from e

        # --- Register Augmentations ---
        created_augmentations = []
        failed_count = 0
        for aug_metadata in augmentations:
            aug_absolute_path_str = aug_metadata.get('augmented_file')
            aug_params = aug_metadata.get('params', {}) # Use 'params' key as per augmentor output example
            if not aug_absolute_path_str:
                logger.warning("Augmentor did not return an absolute path for an augmentation. Skipping.")
                failed_count += 1
                continue

            aug_absolute_path = Path(aug_absolute_path_str)
            if not aug_absolute_path.exists():
                logger.warning(f"Augmented file path from augmentor does not exist: {aug_absolute_path}. Skipping.")
                failed_count += 1
                continue

            # Generate unique ID for the new augmented recording
            # Format: aug_<class>_<username>_<timestamp>
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")[:-3]  # Remove last 3 digits of microseconds
            
            # In our system, user_id IS the username (e.g., "ronrubin")
            # Per COMPLETE_NAMING_SYSTEM.md
            username = user_id
            
            augmented_recording_id = f"aug_{class_name.lower()}_{username}_{timestamp}"

            # Construct the final expected filename and path based on V10 convention
            # Filename: <type>_<uuid>.wav
            # Path: <class_name>/<user_id>/<type>/<filename>
            try:
                # Generate the standard filename expected by the system
                expected_filename = self.file_manager._generate_standard_filename(
                    class_name=class_name, # Use validated class_name
                    user_id=user_id,
                    recording_type=RecordingType.AUGMENTED,
                    recording_id=augmented_recording_id, # Use the new UUID
                    extension="wav"
                )
                expected_absolute_path = augmented_dir / expected_filename

                # Construct the relative path for metadata storage using the new ID
                aug_relative_path_obj = self.file_manager.get_sound_instance_path(
                    class_name=class_name,
                    user_id=user_id,
                    recording_type=RecordingType.AUGMENTED,
                    recording_id=augmented_recording_id # Pass the new UUID here
                )
                # Ensure it's relative to data root
                aug_relative_path = aug_relative_path_obj.relative_to(self.file_manager.get_data_root())

            except Exception as path_e:
                logger.error(f"Failed to construct path/filename for augmented recording {augmented_recording_id}: {path_e}", exc_info=True)
                # Clean up the temporary file from the augmentor if it still exists
                aug_absolute_path.unlink(missing_ok=True)
                failed_count += 1
                continue

            # --- Rename/Move the file ---
            # Move the file generated by the augmentor to the standard V10 path/filename
            if aug_absolute_path != expected_absolute_path:
                logger.debug(f"Moving augmented file: {aug_absolute_path} -> {expected_absolute_path}")
                try:
                    # Ensure parent directory exists (should already, but safety check)
                    expected_absolute_path.parent.mkdir(parents=True, exist_ok=True)
                    # Use os.rename for atomic move if possible, or shutil.move
                    os.rename(aug_absolute_path, expected_absolute_path)
                    # Update path variables to the final location
                    aug_absolute_path = expected_absolute_path
                    # Update string path as well if needed elsewhere
                    aug_absolute_path_str = str(expected_absolute_path)
                except OSError as rename_err:
                    logger.error(f"Failed to move/rename augmented file {aug_absolute_path} to {expected_absolute_path}: {rename_err}")
                    # Clean up the temporary file if it exists at the source
                    # Use the original path string here for cleanup
                    if Path(aug_metadata.get('augmented_file')).exists():
                        Path(aug_metadata.get('augmented_file')).unlink(missing_ok=True)
                    failed_count += 1
                    continue
            else:
                logger.debug(f"Augmented file already at expected path: {expected_absolute_path}")

            # --- Analyze the final audio file ---
            audio_properties = {}
            try:
                # Analyze the file at its *final* location
                analyzed_props = self.file_manager.analyze_audio_file_path(aug_absolute_path)
                if analyzed_props:
                    audio_properties = analyzed_props
                else:
                    # Log warning but proceed with empty properties
                    logger.warning(f"Could not analyze augmented file, metadata may be incomplete: {aug_absolute_path}")
            except Exception as analyze_e:
                # Log warning but proceed with empty properties
                logger.warning(f"Error analyzing augmented file {aug_absolute_path}: {analyze_e}", exc_info=True)

            # --- Create and Save Recording Metadata ---
            try:
                # Need class_obj.id, handle case where it wasn't found
                current_class_id = class_obj.id if class_obj else None
                if not current_class_id:
                    # Maybe try to find class ID again, or log error and skip?
                    logger.error(f"Cannot save recording metadata: Class object/ID for '{class_name}' is missing.")
                    aug_absolute_path.unlink(missing_ok=True) # Clean up audio file
                    failed_count += 1
                    continue
                
                # --- Get Username for metadata ---
                # In our system, user_id IS the username (e.g., "ronrubin")
                # Per COMPLETE_NAMING_SYSTEM.md
                owner_username = user_id
                # --- End Get Username ---

                new_augmented_recording = Recording(
                    id=augmented_recording_id, # Use the generated UUID
                    class_id=current_class_id, # Use the global class ID
                    user_id=user_id,
                    relative_wav_path=str(aug_relative_path), # Use final relative path
                    recording_type=RecordingType.AUGMENTED,
                    source_sound_id=recording_id, # Link to GOLD recording ID
                    timestamp=datetime.now(),
                    updated_at=datetime.now(),
                    duration=audio_properties.get('duration'),
                    sample_rate=audio_properties.get('sample_rate'),
                    metadata={
                        'augmentation_params': aug_params,
                        'original_filename': Path(recording.relative_wav_path).name,
                        'class_name': class_name, # Ensure class_name is included here
                        'username': owner_username, # ADDED username here
                        **(audio_properties.get('metadata', {})) # Include analysis metadata if available
                    }
                )

                # --- Save Recording and Handle Result ---
                if self.recording_repo.save(new_augmented_recording, user_id=user_id):
                    # Append metadata of successfully saved recording
                    # Use to_dict() if available, otherwise construct dict manually
                    if hasattr(new_augmented_recording, 'to_dict'):
                        created_augmentations.append(new_augmented_recording.to_dict())
                    else:
                        # Manual dict creation as fallback
                        created_augmentations.append({
                            'id': new_augmented_recording.id,
                            'class_id': new_augmented_recording.class_id,
                            'user_id': new_augmented_recording.user_id,
                            'relative_wav_path': new_augmented_recording.relative_wav_path,
                            'recording_type': new_augmented_recording.recording_type.value, # Use value for JSON
                            'source_sound_id': new_augmented_recording.source_sound_id,
                            'timestamp': new_augmented_recording.timestamp.isoformat(),
                            'updated_at': new_augmented_recording.updated_at.isoformat(),
                            'duration': new_augmented_recording.duration,
                            'sample_rate': new_augmented_recording.sample_rate,
                            'metadata': new_augmented_recording.metadata
                        })
                    logger.info(f"Saved augmented recording metadata: {new_augmented_recording.id} (source: {recording_id})")
                else:
                    logger.error(f"Failed to save metadata via repo for augmented recording: {new_augmented_recording.id}. Cleaning up audio file.")
                    # Clean up the audio file if metadata saving fails
                    aug_absolute_path.unlink(missing_ok=True)
                    failed_count += 1
            
            except Exception as save_err:
                logger.error(f"Error creating/saving augmented metadata for {augmented_recording_id}: {save_err}", exc_info=True)
                # Clean up the audio file if metadata creation/saving fails
                # Ensure path exists before unlinking
                if aug_absolute_path and aug_absolute_path.exists():
                   aug_absolute_path.unlink(missing_ok=True)
                failed_count += 1
        # --- End Loop ---

        # --- Return Results ---
        total_attempted = len(augmentations)
        success_count = len(created_augmentations)
        final_message = f"Successfully created {success_count}/{total_attempted} augmentations for recording {recording_id}."
        if failed_count > 0:
            final_message += f" {failed_count} failed."
        
        # Indentation fixed here
        return {
            "original_id": recording_id,
            "augmentations_requested": num_augmentations, # How many were asked for
            "augmentations_attempted": total_attempted, # How many the augmentor returned
            "augmentations_created": success_count, # How many were successfully saved
            "failures": failed_count,
            "message": final_message,
            "details": created_augmentations # List of successfully created metadata dicts
        }

    def get_augmentation_options(self):
        """
        Get all available augmentation options based on the current augmentor config.
        
        Returns:
            Dictionary of augmentation options suitable for UI rendering.
        """
        options = {}
        # Use the config from the initialized augmentor instance
        augmentor_config = self.augmentor.config
        
        # Define the mapping from config keys to UI elements
        # Include absolute bounds and step for sliders where applicable
        option_definitions = {
            'pitch_shift': {
                'config_key': 'pitch_shift_range', 
                'enabled_key': 'pitch_shift_enabled',
                'name': 'Pitch Shift', 
                'description': 'Adjusts the pitch up or down.', 
                'unit': 'semitones', 
                'icon': 'graphic_eq',
                'abs_min': -12, 'abs_max': 12, 'step': 0.5
            },
            'volume_adjust': {
                'config_key': 'volume_adjust_range', 
                'enabled_key': 'volume_adjust_enabled',
                'name': 'Volume Adjustment', 
                'description': 'Changes the volume loudness.', 
                'unit': 'dB', 
                'icon': 'volume_up',
                'abs_min': -12, 'abs_max': 12, 'step': 0.5
            },
            'time_shift': {
                'config_key': 'time_shift_range', 
                'enabled_key': 'time_shift_enabled',
                'name': 'Time Shift', 
                'description': 'Shifts audio earlier or later.', 
                'unit': 'ms', 
                'icon': 'timer',
                'abs_min': -500, 'abs_max': 500, 'step': 10
            },
            'background_noise': {
                'config_key': 'noise_level_range', 
                'enabled_key': 'background_noise_enabled',
                'name': 'Background Noise', 
                'description': 'Adds random background noise.', 
                'unit': 'level', 
                'icon': 'waves',
                'abs_min': 0.0, 'abs_max': 0.1, 'step': 0.001
            },
            'eq_boost': {
                'config_key': 'eq_boost_range', 
                'enabled_key': 'eq_boost_enabled',
                'name': 'EQ Boost/Cut', 
                'description': 'Boosts/cuts random frequency band.', 
                'unit': 'dB', 
                'icon': 'equalizer',
                'abs_min': -12, 'abs_max': 12, 'step': 0.5
            },
            'reverb': {
                'config_key': 'reverb_level_range', 
                'enabled_key': 'reverb_enabled',
                'name': 'Reverb', 
                'description': 'Adds room echo effect.', 
                'unit': 'level', 
                'icon': 'surround_sound',
                'abs_min': 0.0, 'abs_max': 1.0, 'step': 0.01
            }
            # Add other augmentation types here if the augmentor supports them
        }

        for key, definition in option_definitions.items():
            config_range = augmentor_config.get(definition['config_key'])
            enabled = augmentor_config.get(definition['enabled_key'], True) # Default enabled

            if config_range and isinstance(config_range, (list, tuple)) and len(config_range) == 2:
                min_val, max_val = config_range
                # Determine step dynamically if not explicitly defined
                default_step = 0.01 if isinstance(min_val, float) else 1
                options[key] = {
                    'name': definition['name'],
                    'description': definition['description'],
                    'min': min_val,
                    'max': max_val,
                    'unit': definition.get('unit', ''),
                    'icon': definition.get('icon', 'settings'),
                    'enabled': enabled,
                    'abs_min': definition.get('abs_min', min_val), 
                    'abs_max': definition.get('abs_max', max_val),
                    'step': definition.get('step', default_step)
                }
            else:
                logger.warning(f"Config range key '{definition['config_key']}' not found or invalid in augmentor config for '{key}'. Skipping option.")

        logger.debug(f"Generated augmentation options for UI: {options}")
        return options
    
# --- End of AugmentationService Class ---
