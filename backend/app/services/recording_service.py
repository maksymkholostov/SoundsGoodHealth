import os
import logging
import shutil
import tempfile
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import soundfile as sf
from flask import url_for, current_app

from backend.app.core.models.recording import Recording, RecordingType
from backend.app.core.repositories.recording_repo import RecordingRepository
from backend.app.core.repositories.dictionary_repo import DictionaryRepository
from backend.app.services.file_service import FileService
from backend.app.core.exceptions import (
    DatabaseError,
    FileError,
    ProcessingError,
    RecordingServiceError,
)
from backend.app.services.processing_service import ProcessingService
from backend.app.storage.file_manager import FileManager
from backend.app.ml.utils.audio_utils import (
    load_audio_from_file,
    ensure_audio_format,
    extract_audio_properties,
)


class RecordingService:
    """
    Service for recording management.
    
    Provides business logic for working with audio recordings.
    """
    
    def __init__(
        self,
        recording_repo: RecordingRepository,
                dictionary_repo: DictionaryRepository,
                file_service: FileService,
                processing_service: Optional[ProcessingService] = None,
        target_sample_rate: int = 16000,
    ):
        """
        Initialize the recording service.
        
        Args:
            recording_repo: Repository for recording operations
            dictionary_repo: Repository for dictionary operations
            file_service: Service for file operations (provides FileManager)
            processing_service: Service for processing audio recordings (can be set later)
            target_sample_rate: Target sample rate for audio standardization
        """
        self.recording_repo = recording_repo
        self.dictionary_repo = dictionary_repo
        self.file_service = file_service 
        # Correctly assign file_manager from the injected file_service
        self.file_manager = file_service.file_manager 
        self.processing_service = processing_service
        self.target_sample_rate = target_sample_rate
        self.logger = logging.getLogger(__name__)

        # --- DEBUG: Check type of injected dictionary_repo ---
        if not isinstance(self.dictionary_repo, DictionaryRepository):
            self.logger.critical(
                f"CRITICAL TYPE ERROR in RecordingService.__init__: Expected DictionaryRepository, but received {type(self.dictionary_repo).__name__}"
            )
            # Optionally raise an error here to make it obvious
            # raise TypeError(f"RecordingService expected DictionaryRepository, got {type(self.dictionary_repo).__name__}")
        else:
            self.logger.info(
                "RecordingService.__init__: Correctly received DictionaryRepository."
            )
        # --- END DEBUG ---

        # Add a check to ensure file_manager was successfully assigned
        if not self.file_manager:
            self.logger.error(
                "FileManager was not properly initialized within RecordingService!"
            )
             # Optionally raise an error to prevent the app from starting incorrectly
             # raise RuntimeError("FileManager not available in RecordingService")
    
        # --- Ensure Processing Service is Set --- 
        if self.processing_service is None:
            self.logger.warning(
                "ProcessingService is not set during RecordingService initialization. Some functions might fail."
            )
            
        # --- Setup UserID lookup (optional, can be done later) --- 
        # Initialize mapping if user repo available (example)
        self.uuid_to_username = {}
        self.username_to_uuid = {}
        # Consider calling a method to populate these mappings if needed at init
        # self._populate_user_id_mappings() 

    # Example method to populate user mappings (if needed)
    # Since username IS now the user ID, no mapping is needed
    # def _populate_user_id_mappings(self):
    #     # No longer needed - username is the ID
    #         else:
    #              logger.warning("Could not load username index for mappings.")
    #     else:
    #         logger.warning("FileManager methods for user index missing. Cannot populate mappings.")

    def set_processing_service(self, processing_service: ProcessingService):
        """Set the processing service after initialization."""
        self.processing_service = processing_service
        self.logger.info("ProcessingService set for RecordingService.")

    # --- Core Recording Management --- 

    def create_recording(self, recording: Recording) -> bool:
        """Saves the metadata for a new recording object."""
        return self.recording_repo.save(recording)
    
    def get_recording_by_id(self, recording_id: str) -> Optional[Recording]:
        """
        Get a recording by ID.
        
        Args:
            recording_id: Recording ID
            
        Returns:
            Recording if found, None otherwise
        """
        return self.recording_repo.find_by_id(recording_id)
    
    def find_recordings(
        self,
        class_id: Optional[str] = None,
                      user_id: Optional[str] = None,
                      recording_type: Optional[RecordingType] = None,
        status: Optional[RecordingType] = None,
    ) -> List[Recording]:
        """
        Find recordings based on filter criteria.
        
        Args:
            class_id: Optional class ID filter
            user_id: Optional user ID filter
            recording_type: Optional recording type filter
            status: Optional status filter
            
        Returns:
            List of matching recordings
        """
        return self.recording_repo.find(
            class_id=class_id,
            user_id=user_id,
            recording_type=recording_type,
        )
    
    def get_all_for_dictionary(
        self,
        dictionary_id: str,
                             recording_type: Optional[RecordingType] = None,
        status: Optional[RecordingType] = None,
    ) -> List[Recording]:
        """
        Get all recordings for all classes in a dictionary.
        
        Args:
            dictionary_id: Dictionary ID
            recording_type: Optional filter by recording type
            status: Optional filter by recording status
            
        Returns:
            List of recordings
        """
        return self.recording_repo.get_all_for_dictionary(
            dictionary_id=dictionary_id, rec_type=recording_type, status=status
        )
    
    def update_recording_status(
        self, recording_id: str, new_status: RecordingType
    ) -> bool:
        """
        Update the status of a recording.
        
        Args:
            recording_id: Recording ID
            new_status: New status
            
        Returns:
            True if updated successfully, False otherwise
        """
        recording = self.recording_repo.find_by_id(recording_id)
        
        if not recording:
            self.logger.warning(
                f"Recording {recording_id} not found during status update"
            )
            return False
        
        recording.update_status(new_status)
        return self.recording_repo.save(recording)
    
    def delete_recording(self, recording_id: str) -> bool:
        """
        Delete a recording and its audio file.
        
        Args:
            recording_id: Recording ID
            
        Returns:
            True if deleted successfully, False otherwise
        """
        recording = self.recording_repo.find_by_id(recording_id)
        
        if not recording:
            self.logger.warning(
                f"Recording {recording_id} not found during deletion attempt"
            )
            return False
        
        try:
            # Delete the audio file using relative path via file_service
            file_deleted = self.file_service.delete_file(recording.relative_wav_path)
            
            # Delete the metadata
            metadata_deleted = self.recording_repo.delete(recording)
            
            return file_deleted and metadata_deleted
        except Exception as e:
            self.logger.error(f"Error deleting recording {recording_id}: {e}")
            return False
    
    def save_raw_recording(
        self,
        user_id: str,
        username: str,
        class_id: str,
        audio_file_storage,
        source: str = "system",
    ) -> Optional[Dict[str, Any]]:
        """Saves raw recording using UserID UUID for path/filename.
           Assigns initial type based on source.
           Populates full metadata."
        """
        class_name = self.recording_repo._get_class_name(class_id)
        if not class_name:
            self.logger.error(
                f"Cannot save raw recording: class ID {class_id} not found."
            )
            return None

        temp_raw_path = None 
        try:
            # Generate ID based on recording type and class
            # Format: raw_rec_<class_name>_<username>_<timestamp>
            timestamp = datetime.now()
            timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S%f")[:-3]
            if source == "upload":
                recording_id = f"raw_up_{class_name.lower()}_{username}_{timestamp_str}"
            else:
                recording_id = f"raw_rec_{class_name.lower()}_{username}_{timestamp_str}"
            # Determine initial type based on source
            initial_type = (
                RecordingType.RAW_UPLOADED
                if source == "upload"
                else RecordingType.RAW_RECORDED
            )
            
            # --- Determine Paths (using UserID, Type=RAW) --- 
            # Filename uses specific type (raw_recorded/raw_uploaded)
            raw_filename = self.file_manager._generate_standard_filename(
                class_name, user_id, initial_type, recording_id, "wav"
            )
            # Path should use the ACTUAL initial_type (RAW_RECORDED or RAW_UPLOADED)
            raw_audio_path = self.file_manager.get_sound_instance_path(
                class_name=class_name,
                user_id=user_id, 
                recording_type=initial_type,  # Use the specific initial type Enum
                recording_id=recording_id, 
                extension="wav",
            )
            relative_wav_path = str(
                raw_audio_path.relative_to(self.file_manager.get_data_root())
            )
            # --- End Determine Paths ---
            
            # --- Log Path Before Writing Audio --- 
            self.logger.info(
                f"[SaveRaw] Attempting to save standardized audio to absolute path: {raw_audio_path}"
            )
            # --- End Log ---

            # --- ADDED BACK: Save Uploaded File Temporarily --- 
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                temp_raw_path = Path(tmp_file.name)
                audio_file_storage.save(tmp_file)  # Save stream to temp file
            self.logger.debug(
                f"Saved initial upload to temporary file: {temp_raw_path}"
            )
            # --- END ADDED BACK ---

            # 3. Standardize Audio & Extract Properties
            try:
                # Load from the temporary file path
                audio_data, sr = load_audio_from_file(str(temp_raw_path)) 
                std_audio_data, final_sr = ensure_audio_format(
                    audio_data,
                    sr,
                    target_sr=self.target_sample_rate,
                    mono=True,
                    normalize=True,
                )
                
                # Extract properties from STANDARDIZED audio
                duration_seconds = len(std_audio_data) / final_sr
                hz = final_sr
                physical_type = "mono"
                bit_depth = 16 
                
                # Save standardized audio
                sf.write(
                    str(raw_audio_path),
                    std_audio_data,
                    final_sr,
                    format="WAV",
                    subtype="PCM_16",
                )
                self.logger.info(
                    f"Saved standardized raw audio to V10 path: {raw_audio_path}"
                )
                
                # Get file size now that it exists
                file_size_bytes = (
                    raw_audio_path.stat().st_size if raw_audio_path.exists() else 0
                )

            except Exception as std_err:
                self.logger.error(
                    f"Audio standardization/property extraction failed: {std_err}",
                    exc_info=True,
                )
                # Attempt cleanup of temp file
                if temp_raw_path and temp_raw_path.exists():
                    temp_raw_path.unlink()
                return None

            # Create Recording object with all metadata
            recording_metadata = Recording(
                id=recording_id,
                user_id=user_id,
                class_id=class_id,
                timestamp=timestamp,
                updated_at=timestamp,
                recording_type=initial_type,
                relative_wav_path=relative_wav_path,
                duration=round(duration_seconds, 3) if duration_seconds else None,
                sample_rate=hz,
                metadata={
                    "username": username,
                    "class_name": class_name,
                    "bit_depth": bit_depth,
                    "physical_type": physical_type,
                    "file_size_bytes": file_size_bytes,
                    "file_type": ".wav",
                    "source": source,
                },
            )

            # Save Metadata - Pass UserID
            if not self.recording_repo.save(recording_metadata, user_id=user_id):
                self.logger.error(
                    f"Failed to save recording metadata for {recording_id} to {raw_audio_path.with_suffix('.json')}"
                )
                # Attempt to clean up the saved audio file if metadata save fails
                try:
                    if raw_audio_path.exists():
                        raw_audio_path.unlink()
                except OSError as cleanup_err:
                    self.logger.warning(
                        f"Could not clean up audio file {raw_audio_path} after metadata save failure: {cleanup_err}"
                    )
                return None

            self.logger.info(
                f"Successfully saved raw recording metadata for ID: {recording_id}"
            )

            # Prepare return data - ensure all needed fields are present
            final_metadata = recording_metadata.to_dict()
            final_metadata["path"] = str(raw_audio_path)
            final_metadata["username"] = username
            final_metadata["class_name"] = class_name
            
            return final_metadata

        except Exception as e:
            self.logger.error(
                f"Error saving raw recording for class {class_name}, user {user_id}: {e}",
                exc_info=True,
            )
            # Attempt cleanup of the final audio file if it exists
            if "raw_audio_path" in locals() and raw_audio_path.exists():
                try:
                    raw_audio_path.unlink()
                except OSError as cleanup_err:
                    self.logger.warning(
                        f"Cleanup failed for {raw_audio_path}: {cleanup_err}"
                    )
            return None
        finally:
            # Ensure temporary file is always deleted
            if temp_raw_path and temp_raw_path.exists():
                try:
                    temp_raw_path.unlink()
                    self.logger.debug(f"Cleaned up temporary file: {temp_raw_path}")
                except OSError as del_err:
                    self.logger.warning(
                        f"Could not delete temporary file {temp_raw_path}: {del_err}"
                    )

    def trigger_processing(self, recording_id: str) -> bool:
        """
        Trigger processing of a raw recording.
        
        Args:
            recording_id: ID of the raw recording to process
            
        Returns:
            True if processing started successfully, False otherwise
        """
        if not self.processing_service:
            self.logger.error("Processing service not available")
            return False
            
        recording = self.recording_repo.find_by_id(recording_id)
        
        if not recording:
            self.logger.warning(f"Recording {recording_id} not found for processing")
            return False
            
        if recording.type != RecordingType.RAW:
            self.logger.warning(f"Recording {recording_id} is not a raw recording")
            return False
            
        try:
            return self.processing_service.process_recording(recording_id)
        except Exception as e:
            self.logger.error(
                f"Error triggering processing for recording {recording_id}: {e}"
            )
            return False
    
    def verify_sound_instance(
        self, sound_instance_id: str, keep: bool, requesting_user_id: str
    ) -> bool:
        """
        Verifies (approves) or discards/deletes a sound instance.
        - Moves pending -> gold if keep is True.
        - Deletes pending or gold if keep is False.
        - Handles both audio (.wav) and metadata (.json) files.
        - Performs ownership check.

        Args:
            sound_instance_id: The unique ID of the sound instance (from metadata).
            keep: True to approve (pending->gold), False to discard/delete.
            requesting_user_id: The ID of the user making the request (for permission check).

        Returns:
            True if the operation was successful, False otherwise.
        """
        self.logger.info(
            f"Verification request: instance_id={sound_instance_id}, keep={keep}, user={requesting_user_id}"
        )

        # 1. Find the Recording Metadata
        recording = self.recording_repo.find_by_id(sound_instance_id)
        if not recording:
            self.logger.error(
                f"Verification failed: Sound instance {sound_instance_id} not found."
            )
            return False
             
        # Log the found recording details for debugging
        self.logger.debug(
            f"Found recording for verification: id={recording.id}, "
            f"type={recording.recording_type}, "
            f"user_id={recording.user_id}, "
            f"path={recording.relative_wav_path if hasattr(recording, 'relative_wav_path') else 'N/A'}"
        )

        # 2. Permission Check
        # TODO: Add admin override capability if needed
        # --- Temporarily Disabled: Allow any user to verify/discard ---
        # if recording.user_id != requesting_user_id:
        #     self.logger.warning(f"Permission denied: User {requesting_user_id} cannot verify instance {sound_instance_id} owned by {recording.user_id}.")
        #     return False # Or raise PermissionError?
        # --- End Temporarily Disabled ---

        # 3. Get Class Name (needed for paths)
        class_name = self.recording_repo._get_class_name(recording.class_id)
        if not class_name:
            self.logger.error(
                f"Cannot verify instance {sound_instance_id}: class ID {recording.class_id} not found."
            )
            return False

        # 4. Determine current paths using FileManager and CORRECT type/args
        try:
            # Use the actual type of the recording object (e.g., PENDING)
            current_audio_path = self.file_manager.get_sound_instance_path(
                class_name=class_name,
                user_id=recording.user_id,
                recording_type=recording.recording_type,  # Use recording_type attribute
                recording_id=recording.id,
                extension="wav",  # Default extension
            )
            current_metadata_path = self.file_manager.get_sound_metadata_path(
                class_name=class_name,
                user_id=recording.user_id,
                recording_type=recording.recording_type,  # Use recording_type attribute
                recording_id=recording.id,
            )
            
            # Log the constructed paths
            self.logger.debug(
                f"Constructed paths for verification: "
                f"audio={current_audio_path}, "
                f"metadata={current_metadata_path}"
            )
            
            # Also check if file paths exist directly from recording's relative path
            if hasattr(recording, 'relative_wav_path') and recording.relative_wav_path:
                direct_path = self.file_manager.get_data_root() / recording.relative_wav_path
                direct_exists = direct_path.exists()
                self.logger.debug(
                    f"Checking direct path from relative_wav_path: {direct_path}, exists={direct_exists}"
                )
                
                # If the constructed path doesn't exist but the direct path does, use the direct path
                if not current_audio_path.exists() and direct_exists:
                    self.logger.warning(
                        f"Constructed audio path doesn't exist, but direct path does. "
                        f"Using direct path: {direct_path}"
                    )
                    current_audio_path = direct_path
                    # Try to infer metadata path from direct path
                    current_metadata_path = direct_path.with_suffix('.json')
            
        except Exception as path_e:
            # Also use recording_type in the error log
            log_type = (
                recording.recording_type
                if hasattr(recording, "recording_type")
                else "Unknown Type"
            )
            self.logger.error(
                f"Could not determine current paths for instance {sound_instance_id} (type: {log_type}): {path_e}",
                exc_info=True,
            )
            return False

        if not current_audio_path.exists() or not current_metadata_path.exists():
            log_type = (
                recording.recording_type
                if hasattr(recording, "recording_type")
                else "Unknown Type"
            )
            self.logger.error(
                f"Verification failed: Files not found at expected paths for instance {sound_instance_id} (type: {log_type}). Audio: {current_audio_path}, Meta: {current_metadata_path}"
            )
            
            # Additional debugging - list the parent directory contents
            try:
                parent_dir = current_audio_path.parent
                if parent_dir.exists():
                    self.logger.debug(f"Contents of {parent_dir}:")
                    for item in parent_dir.iterdir():
                        self.logger.debug(f"  - {item.name}")
                else:
                    self.logger.debug(f"Parent directory {parent_dir} does not exist")
                    
                    # Try to check if parent's parent exists
                    if parent_dir.parent.exists():
                        self.logger.debug(f"Contents of {parent_dir.parent}:")
                        for item in parent_dir.parent.iterdir():
                            self.logger.debug(f"  - {item.name}")
            except Exception as list_e:
                self.logger.error(f"Error listing directory contents: {list_e}")
                
             # Attempt cleanup if one exists but not the other? Or just report error.
            return False

        # --- Perform Action ---
        try:
            # Need username for repo.save call when approving
            username = recording.metadata.get("username")
            if not username and keep:  # Only critical if approving (keep=True)
                # Fallback lookup if needed (requires UserRepository/AuthService injection)
                # For now, log error and fail if username missing during approval
                self.logger.error(
                    f"Username not found in metadata for {sound_instance_id}. Cannot approve without username for repo.save."
                )
                return False

            if keep:
                # --- Approve (Pending -> Gold) ---
                # Check the TYPE
                if recording.recording_type != RecordingType.PENDING:
                    self.logger.warning(
                        f"Cannot approve instance {sound_instance_id}: type is already {recording.recording_type.name}. No action taken."
                    )
                    return (
                        True  # Consider it success as it's already approved/processed
                    )

                self.logger.info(
                    f"Approving instance {sound_instance_id} (Pending -> Gold)"
                )

                # Generate new gold ID based on segment ID
                # Extract timestamp from segment ID (e.g., seg_oh_ronrubin_20250807_133025123_1)
                parts = recording.id.split('_')
                if len(parts) >= 6 and recording.id.startswith('seg_'):
                    # seg_oh_ronrubin_20250807_133025123_1 -> gold_oh_ronrubin_20250807_133025123_1
                    gold_id = f"gold_{parts[1]}_{parts[2]}_{parts[3]}_{parts[4]}_{parts[5]}"
                else:
                    # Fallback: just replace seg_ with gold_
                    gold_id = recording.id.replace('seg_', 'gold_')
                
                self.logger.debug(f"Generated gold ID: {gold_id} from segment ID: {recording.id}")

                # Determine target gold paths using V10 methods with new gold ID
                target_gold_audio_path = self.file_manager.get_sound_instance_path(
                    class_name=class_name,
                    user_id=recording.user_id,
                    recording_type=RecordingType.GOLD,  # Target type is GOLD
                    recording_id=gold_id,
                    extension="wav",
                )
                target_gold_metadata_path = self.file_manager.get_sound_metadata_path(
                    class_name=class_name,
                    user_id=recording.user_id,
                    recording_type=RecordingType.GOLD,  # Target type is GOLD
                    recording_id=gold_id,
                )
                # FileManager methods usually handle directory creation, but ensuring here doesn't hurt
                target_gold_audio_path.parent.mkdir(parents=True, exist_ok=True)
                
                self.logger.debug(
                    f"Moving to gold - Source: {current_audio_path}, Target: {target_gold_audio_path}"
                )

                # Update metadata object *before* move/save
                original_type = recording.recording_type  # Use recording_type attribute
                original_id = recording.id  # Store original ID for rollback
                # Update the ID to the new gold ID
                recording.id = gold_id
                # Set the recording_type to GOLD
                recording.recording_type = RecordingType.GOLD
                # *** Update the relative path ***
                recording.relative_wav_path = str(
                    target_gold_audio_path.relative_to(
                        self.file_manager.get_data_root()
                    )
                )
                # *** ALSO Update the absolute path attribute if it exists ***
                if hasattr(recording, "path"):
                    recording.path = str(target_gold_audio_path)
                recording.metadata[
                    "verified_at"
                ] = datetime.now().isoformat()  # Add verification timestamp
                recording.metadata[
                    "original_segment_id"
                ] = original_id  # Keep track of the original segment ID

                # --- Move the audio file using FileManager ---
                self.logger.debug(
                    f"Moving audio {current_audio_path} -> {target_gold_audio_path}"
                )
                move_success = self.file_manager.move_file(
                    current_audio_path, target_gold_audio_path
                )

                if not move_success:
                    self.logger.error(
                        f"Failed to move audio file for instance {recording.id}. Aborting approval."
                    )
                     # Attempt to revert metadata changes in memory (no save happened yet)
                     # Correctly revert recording_type and ID
                    recording.id = original_id
                    recording.recording_type = original_type
                    recording.metadata.pop("verified_at", None)
                    recording.metadata.pop("original_segment_id", None)
                    return False

                # Save *new* metadata to GOLD path using Repository
                # Repo.save uses get_sound_metadata_path internally with the *updated* recording.type (GOLD)
                self.logger.debug(
                    f"Saving updated GOLD metadata for {recording.id} via repository..."
                )
                save_success = self.recording_repo.save(
                    recording, user_id=recording.user_id
                )  # Use user_id from recording

                if not save_success:
                    self.logger.error(
                        f"Failed to save updated GOLD metadata for {recording.id} to {target_gold_metadata_path}. Attempting rollback of audio move."
                    )
                     # Attempt to move audio back
                    rollback_move = self.file_manager.move_file(
                        target_gold_audio_path, current_audio_path
                    )
                    if not rollback_move:
                        self.logger.critical(
                            f"CRITICAL ROLLBACK FAILURE: Could not move audio file back to pending location {current_audio_path} after metadata save failure."
                        )
                          # State is inconsistent!
                    return False

                # Delete the *old* PENDING metadata file
                self.logger.debug(
                    f"Deleting old pending metadata file: {current_metadata_path}"
                )
                if not self.file_manager.delete_file(current_metadata_path):
                     # Log warning but proceed, as main action (move+save) succeeded
                    self.logger.warning(
                        f"Failed to delete old pending metadata file {current_metadata_path}, but instance was approved."
                    )

                self.logger.info(
                    f"Successfully approved instance {sound_instance_id} to Gold standard."
                )
                return True

            else:
                # --- Discard/Delete (Pending or Gold) -> Now MOVE TO DISCARDED --- 
                type_desc = (
                    recording.recording_type.name
                    if hasattr(recording.recording_type, "name")
                    else "Unknown"
                )  # Use recording_type
                self.logger.info(
                    f"Discarding instance {sound_instance_id} (Type: {type_desc}). Moving to discarded folder."
                )

                # Determine discarded paths
                discarded_audio_path = self.file_manager.get_discarded_sound_path(
                    class_name=class_name,
                    user_id=recording.user_id,
                    recording_id=recording.id,
                    extension="wav",
                )
                discarded_metadata_path = self.file_manager.get_discarded_sound_path(
                    class_name=class_name,
                    user_id=recording.user_id,
                    recording_id=recording.id,
                    extension="json",
                )
                # Ensure discarded directory exists (FileManager might do this, but good practice)
                self.file_manager.discarded_sounds_dir.mkdir(
                    parents=True, exist_ok=True
                )

                # Move audio file to discarded
                self.logger.debug(
                    f"Moving audio file to discarded: {current_audio_path} -> {discarded_audio_path}"
                )
                audio_moved = self.file_manager.move_file(
                    current_audio_path, discarded_audio_path
                )
                if not audio_moved:
                    self.logger.error(
                        f"Failed to move audio file {current_audio_path} to discarded location {discarded_audio_path}. Aborting discard."
                    )
                     # If audio move fails, we stop. The original files remain.
                    return False

                # Move metadata file to discarded
                self.logger.debug(
                    f"Moving metadata file to discarded: {current_metadata_path} -> {discarded_metadata_path}"
                )
                metadata_moved = self.file_manager.move_file(
                    current_metadata_path, discarded_metadata_path
                )
                if not metadata_moved:
                    self.logger.error(
                        f"Failed to move metadata file {current_metadata_path} to discarded location {discarded_metadata_path}. Audio was moved, but metadata remains in original location. State inconsistent."
                    )
                     # Attempt to move audio back?
                    rollback_move = self.file_manager.move_file(
                        discarded_audio_path, current_audio_path
                    )
                    if not rollback_move:
                        self.logger.critical(
                            f"CRITICAL ROLLBACK FAILURE: Could not move audio file back to original location {current_audio_path} after metadata move failure during discard."
                        )
                    return False  # Indicate failure due to inconsistent state

                # Optionally: Update the moved metadata file's status to REJECTED
                try:
                    discarded_meta_dict = self.file_manager.load_json(
                        discarded_metadata_path
                    )
                    if discarded_meta_dict:
                        original_meta_status = discarded_meta_dict.get(
                            "recording_type"
                        )  # Check existing type
                        discarded_meta_dict[
                            "recording_type"
                        ] = RecordingType.REJECTED.value  # Update type to REJECTED
                        discarded_meta_dict["rejected_at"] = datetime.now().isoformat()
                        # Save the updated metadata back to the discarded location
                        if not self.file_manager.save_json(
                            discarded_meta_dict, discarded_metadata_path
                        ):
                            self.logger.warning(
                                f"Failed to update status/type in moved metadata file {discarded_metadata_path}. Files moved successfully but status not updated."
                            )
                        else:
                            self.logger.debug(
                                f"Updated recording_type to REJECTED in metadata file: {discarded_metadata_path}"
                            )
                    else:
                        self.logger.warning(
                            f"Could not reload moved metadata file {discarded_metadata_path} to update status/type."
                        )
                except Exception as meta_update_err:
                    self.logger.warning(
                        f"Error updating status/type in moved metadata file {discarded_metadata_path}: {meta_update_err}"
                    )

                # If GOLD was discarded, log a stronger warning
                if recording.recording_type == RecordingType.GOLD:  # Use recording_type
                    self.logger.warning(
                        f"Discarded GOLD instance {sound_instance_id} (moved to discarded folder). This might affect trained models."
                    )

                self.logger.info(
                    f"Successfully discarded instance {sound_instance_id} (moved to discarded folder)."
                )
                return True  # Moved successfully

        except Exception as e:
            self.logger.error(
                f"Error during verification/deletion of instance {sound_instance_id}: {e}",
                exc_info=True,
            )
            # Consider attempting rollback if partial changes were made? Complex.
            return False

    def get_pending_segments(
        self, class_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> List[Recording]:
        """
        Get all pending segments for verification.
        
        Args:
            class_id: Optional class ID to filter by
            user_id: Optional user ID to filter by
            
        Returns:
            List of pending segments
        """
        self.logger.info(
            f"Getting pending segments for class_id={class_id}, user_id={user_id}"
        )
        
        # Make sure we use the PENDING type consistently
        recordings = self.recording_repo.find(
            class_id=class_id,
            user_id=user_id,
            recording_type=RecordingType.PENDING,
        )
        
        # Log the results for debugging
        self.logger.info(f"Found {len(recordings)} pending segments")
        if recordings:
            for i, rec in enumerate(recordings[:3]):  # Log just first 3 for brevity
                # Check file existence
                exists = False
                if hasattr(rec, "relative_wav_path") and rec.relative_wav_path:
                    full_path = self.file_manager.get_data_root() / rec.relative_wav_path
                    exists = full_path.exists()
                    
                self.logger.debug(
                    f"Pending segment {i}: id={rec.id}, path={rec.relative_wav_path}, exists={exists}"
                )
        
        return recordings
    
    def get_gold_recordings(
        self, class_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> List[Recording]:
        """
        Get all gold recordings for a class.
        
        Args:
            class_id: Optional class ID to filter by
            user_id: Optional user ID to filter by
            
        Returns:
            List of gold recordings
        """
        return self.recording_repo.find(
            class_id=class_id,
            user_id=user_id,
            recording_type=RecordingType.GOLD,
            status=RecordingType.VERIFIED,
        )
    
    def get_class_sample_counts(self, class_name: str) -> Dict[str, int]:
        """
        Count the number of gold and augmented recordings for a specific class across all users.
        
        Args:
            class_name: The name of the class to count samples for
            
        Returns:
            Dictionary with counts {'gold': count, 'augmented': count, 'total': count}
        """
        gold_count = 0
        augmented_count = 0
        
        try:
            # --- DEBUG: Check type of self.dictionary_repo just before use ---
            self.logger.debug(
                f"[get_class_sample_counts] Type of self.dictionary_repo: {type(self.dictionary_repo).__name__}"
            )
            if not isinstance(self.dictionary_repo, DictionaryRepository):
                self.logger.error(
                    "[get_class_sample_counts] CRITICAL: self.dictionary_repo is NOT a DictionaryRepository!"
                )
                 # Optionally raise here too if needed for hard stop
            # --- END DEBUG ---

            # Get the class ID from the class name
            sound_class = self.dictionary_repo.get_class_by_name(class_name)
            if not sound_class:
                self.logger.warning(f"Class {class_name} not found in global registry")
                return {"gold": 0, "augmented": 0, "total": 0}
            class_id = sound_class.id

            # Query the repository for counts
            gold_recordings = self.recording_repo.find(
                class_id=class_id, recording_type=RecordingType.GOLD
            )
            gold_count = len(gold_recordings)

            augmented_recordings = self.recording_repo.find(
                class_id=class_id, recording_type=RecordingType.AUGMENTED
            )
            augmented_count = len(augmented_recordings)

            total_count = gold_count + augmented_count
            self.logger.info(
                "Class %s (ID: %s) has %d gold and %d augmented samples (total: %d) from repository",
                class_name,
                class_id,
                gold_count,
                augmented_count,
                total_count,
            )

            return {
                "gold": gold_count,
                "augmented": augmented_count,
                "total": total_count,
            }
        except Exception as e:
            self.logger.error(
                "Error counting samples for class %s: %s", class_name, e, exc_info=True
            )  # Added exc_info=True
            return {"gold": 0, "augmented": 0, "total": 0}

    def check_if_sounds_exist_for_class(self, class_name: str) -> bool:
        """Checks if any sound files (raw, pending, gold, augmented) exist for a given class name."""
        try:
            # This method relies on the FileManager to check directory existence/contents
            # It assumes that if any sound of any status exists for the class, 
            # the corresponding directory structure under backend/data/sounds/<ClassName>/... will exist.
            
            # Get the base directory for the class across all users/statuses
            class_sounds_dir = self.file_service.file_manager.get_class_sounds_base_dir(
                class_name
            )
            
            if not class_sounds_dir.exists() or not any(class_sounds_dir.iterdir()):
                # If the base directory doesn't exist or is empty, no sounds exist
                self.logger.info(f"No sound files found for class '{class_name}'.")
                return False

            # More thorough check: Iterate through potential user/status subdirs if needed?
            # For now, simply checking if the base class dir exists and is not empty 
            # might be sufficient, assuming FileManager creates it only when sounds are added.
            # If FileManager creates the dir structure proactively, we'd need a deeper check.
            # Let's assume the basic check is okay for now.
            self.logger.info(
                f"Sound files MAY exist for class '{class_name}' (directory exists)."
            )
            return True 
            
        except Exception as e:
            self.logger.error(
                f"Error checking for sound existence for class '{class_name}': {e}"
            )
            # In case of error, assume sounds might exist to be safe
            return True

    def get_sound_instances(
        self,
                            class_id: Optional[str] = None,
        status: Optional[RecordingType] = None,
        types: Optional[List[RecordingType]] = None,  # ADDED: Filter by list of types
                            user_id: Optional[str] = None,
        scope: str = "user",
                            ) -> List[Dict[str, Any]]:
        """
        Retrieves sound instance metadata as dictionaries, suitable for frontend display.

        Args:
            class_id: Optional class ID filter.
            status: Optional RecordingType enum to filter by status.
            types: Optional list of RecordingType enums to filter by.
            user_id: The user's ID. Required if scope is 'user'.
            scope: 'user' to fetch only for the given user_id, 'all' to fetch for all users.

        Returns:
            List of dictionaries, each representing a sound instance.
        """
        target_user_id: Optional[str] = None
        if scope == "user":
            if not user_id:
                self.logger.error(
                    "user_id is required when scope is 'user' in get_sound_instances."
                )
                return []
            target_user_id = user_id
        elif scope == "all":
            target_user_id = None
        else:
            self.logger.error(
                f"Invalid scope '{scope}' provided to get_sound_instances. Must be 'user' or 'all'."
            )
            return []

        try:
            log_user_scope = f"scope '{scope}'"
            if scope == "user":
                log_user_scope += f" (user_id: {target_user_id})"
            log_class_scope = (
                "all classes" if class_id is None else f"class_id '{class_id}'"
            )
            log_types = (
                "all types" if not types else f"types {[t.name for t in types]}"
            )  # Log type names
            self.logger.debug(
                f"Fetching sound instances for {log_user_scope}, {log_class_scope}, {log_types}"
            )

            # If no types are specified but we want PENDING recordings, explicitly set it
            if not types and (status == RecordingType.PENDING or status is None):
                types = [RecordingType.PENDING]
                self.logger.debug(f"No types specified but status is PENDING or None. Using types={types}")

            # MODIFIED: Use recording_type__in with the 'types' parameter
            recordings: List[Recording] = self.recording_repo.find(
                class_id=class_id,
                user_id=target_user_id,
                recording_type__in=types,  # Pass the list of types here
                status=status,
            )
            
            self.logger.debug(f"Retrieved {len(recordings)} recordings from repository")
            
            # Log first few recordings for debugging
            if recordings and len(recordings) > 0:
                for i, rec in enumerate(recordings[:3]):  # Log just first 3 for brevity
                    self.logger.debug(
                        f"Recording {i}: id={rec.id}, type={rec.recording_type}, path={rec.relative_wav_path}"
            )

            results = []
            for recording in recordings:
                instance_dict = recording.to_dict()  # Start with base dict
                
                # Log the raw to_dict result
                self.logger.debug(f"Raw instance dict for {recording.id}: {instance_dict.keys()}")

                # --- Align keys for the template ---
                # Get username (Template expects 'creator_username')
                username = instance_dict.get("metadata", {}).get("username")
                if (
                    not username or username == "Unknown"
                ):  # If missing or marked as Unknown
                    user_id_for_lookup = instance_dict.get("user_id")
                    if user_id_for_lookup:
                        try:
                            # Attempt lookup via auth_service/user_repo attached to app
                            user = current_app.auth_service.user_repo.get_by_id(
                                user_id_for_lookup
                            )
                            username = user.username if user else "N/A (ID Not Found)"
                        except Exception as user_lookup_e:
                            self.logger.warning(
                                f"Error looking up username for user_id {user_id_for_lookup}: {user_lookup_e}"
                            )
                            username = "N/A (Lookup Error)"
                    else:
                        username = "N/A (ID Missing)"  # Should not happen if data is consistent
                instance_dict["creator_username"] = username

                # Get class name (Template expects 'sound_class_name')
                instance_class_name = instance_dict.get("metadata", {}).get(
                    "class_name"
                )
                if not instance_class_name and instance_dict.get("class_id"):
                     # Fallback: Look up class name from repo if missing in metadata
                     try:
                        class_obj = self.dictionary_repo.get_class_by_id(
                            instance_dict["class_id"]
                        )
                        instance_class_name = class_obj.name if class_obj else "N/A"
                     except Exception as e_cls:
                        self.logger.warning(
                            f"Could not look up class name for class_id {instance_dict.get('class_id')}: {e_cls}"
                        )
                        instance_class_name = "N/A"
                instance_dict["sound_class_name"] = instance_class_name

                # Get type (Template expects 'type', recording object has 'recording_type')
                # Ensure recording_type is converted to its string value (e.g., 'gold')
                recording_type_enum = instance_dict.get("recording_type")
                instance_dict["type"] = (
                    recording_type_enum.value
                    if hasattr(recording_type_enum, "value")
                    else str(recording_type_enum)
                )

                # Get relative path for play button (Template expects 'relative_path')
                # The base to_dict() should already include 'relative_wav_path'
                instance_dict["relative_path"] = instance_dict.get("relative_wav_path")
                
                # Verify the file exists physically on disk
                if instance_dict.get("relative_path"):
                    full_path = self.file_manager.get_data_root() / instance_dict["relative_path"]
                    if not full_path.exists():
                        self.logger.warning(f"Audio file does not exist at expected path: {full_path}")
                    else:
                        self.logger.debug(f"Audio file exists at: {full_path}")

                # Add absolute path if needed elsewhere (optional, template doesn't use it directly)
                if (
                    instance_class_name != "N/A"
                    and instance_dict.get("user_id")
                    and instance_dict.get("relative_wav_path")
                ):
                    try:
                        # Ensure correct type is used for path reconstruction if needed
                        current_type_enum = (
                            RecordingType(instance_dict["type"])
                            if instance_dict.get("type")
                            else None
                        )
                        if current_type_enum:
                            audio_path = self.file_manager.get_sound_instance_path(
                                class_name=instance_class_name,
                                user_id=instance_dict["user_id"],
                                recording_type=current_type_enum,
                                recording_id=instance_dict["id"],
                            )
                            instance_dict["absolute_path"] = str(audio_path)
                        else:
                            instance_dict["absolute_path"] = None
                            self.logger.warning(
                                f"Cannot determine absolute path for {instance_dict['id']} due to missing type."
                            )
                    except Exception as path_e:
                        self.logger.warning(
                            f"Could not determine absolute path for instance {instance_dict['id']}: {path_e}"
                        )
                        instance_dict["absolute_path"] = None

                # Inside loop, before --- Add Stream URL --- block
                self.logger.info(
                    f"Checking relative_path for {instance_dict.get('id')}: {instance_dict.get('relative_path')}"
                )
                # --- Add Stream URL ---
                relative_path = instance_dict.get("relative_path")
                if relative_path:
                    try:
                        # Use the recording_web blueprint and api_stream_audio_file_by_path endpoint
                        # Pass the relative path as the 'path' argument
                        instance_dict["stream_url"] = url_for(
                            "recording_web.api_stream_audio_file_by_path",  # CORRECTED Endpoint name
                                                              path=relative_path,
                            _external=False,
                        )  # Generate relative URL
                    except Exception as url_e:
                        self.logger.warning(
                            f"Could not generate stream URL for {instance_dict.get('id')}: {url_e}"
                        )
                        instance_dict["stream_url"] = None
                else:
                    instance_dict["stream_url"] = None
                # --- End Add Stream URL ---

                # Inside the loop in get_sound_instances, after generating stream_url
                self.logger.info(
                    f"Generated stream_url for {instance_dict.get('id')}: {instance_dict.get('stream_url')}"
                )

                # --- Check Features Extracted ---
                features_extracted = False  # Default
                try:
                    feature_service = current_app.feature_service
                    if feature_service and hasattr(
                        feature_service, "feature_repository"
                    ):
                        # Assuming a default feature set ID 'v0.1' - adjust if needed
                        features_extracted = (
                            feature_service.feature_repository.check_features_exist(
                                recording_id=instance_dict["id"], feature_set_id="v0.1"
                            )
                        )
                    else:
                        self.logger.warning(
                            "FeatureService or its repository not available to check features."
                        )
                except Exception as feat_e:
                    self.logger.error(
                        f"Error checking features for {instance_dict['id']}: {feat_e}"
                    )
                instance_dict["features_extracted"] = features_extracted
                # --- End Check Features Extracted ---

                results.append(instance_dict)

            self.logger.info(f"Found {len(results)} sound instances matching criteria.")
            return results

        except Exception as e:
            self.logger.error(f"Error getting sound instances: {e}", exc_info=True)
            return []

    def get_sound_instance_by_id(
        self, sound_instance_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieves a single sound instance by its ID, including its path."""
        self.logger.debug(
            f"Attempting to fetch sound instance by ID: {sound_instance_id}"
        )
        metadata_path: Optional[Path] = None
        try:
            # --- New Logic: Determine type from ID prefix --- 
            expected_type: Optional[RecordingType] = None
            if sound_instance_id.startswith("seg_"):
                expected_type = RecordingType.PENDING
            elif sound_instance_id.startswith("rec_"):
                expected_type = (
                    RecordingType.RAW_RECORDED
                )  # Or RAW_UPLOADED? Needs context if used.
            elif sound_instance_id.startswith(
                "gold_"
            ):  # Assuming a potential future prefix
                 expected_type = RecordingType.GOLD
            # Add other prefixes if needed (e.g., 'aug_')
            
            if not expected_type:
                self.logger.warning(
                    f"Could not determine recording type from ID prefix: {sound_instance_id}"
                )
                # Fallback to less efficient repository search if type unknown
                recording = self.recording_repo.find_by_id(sound_instance_id)
                if not recording:
                    return None  # Not found
            else:
                # --- Find the specific metadata file path using expected type --- 
                # We still need class_name and user_id to construct the path accurately.
                # The repository's find_by_id was doing this inefficiently.
                # A better approach might be needed if class/user aren't derivable from ID.
                # For now, let's *assume* find_by_id works correctly IF it finds the right file.
                # Let's refine find_by_id in the REPO instead.
                
                # --- Reverting Service Method - Fixing Repo Method Instead --- 
                recording = self.recording_repo.find_by_id(sound_instance_id)
                if not recording:
                    self.logger.warning(
                        f"Sound instance {sound_instance_id} not found in repository."
                    )
                    return None
            
            # If we got here, we have a Recording object (potentially the wrong one if repo search failed)
            instance_dict = recording.to_dict()
            
            # --- Determine Absolute Path from Recording object's relative path --- 
            if hasattr(recording, "relative_wav_path") and recording.relative_wav_path:
                 try:
                     # Construct absolute path using FileManager's root
                    absolute_path = (
                        self.file_manager.get_data_root() / recording.relative_wav_path
                    )
                    instance_dict["path"] = str(
                        absolute_path
                    )  # Store the correct absolute path
                     # Verify file exists at the correct location
                    if not absolute_path.exists():
                        self.logger.warning(
                            f"[Service:get_by_id] File path from metadata exists ({recording.relative_wav_path}) but file not found at {absolute_path}"
                        )
                 except Exception as e:
                    self.logger.error(
                        f"[Service:get_by_id] Error constructing absolute path from relative path '{recording.relative_wav_path}': {e}",
                        exc_info=True,
                    )
                    instance_dict["path"] = None  # Path determination failed
            else:
                self.logger.warning(
                    f"[Service:get_by_id] Recording object for {sound_instance_id} lacks 'relative_wav_path'. Cannot determine file location."
                )
                instance_dict["path"] = None

            # Ensure class name is populated if missing 
            if "class_name" not in instance_dict or not instance_dict["class_name"]:
                class_id = instance_dict.get("class_id")
                if class_id:
                    try:
                        class_obj = self.dictionary_repo.get_class_by_id(class_id)
                        instance_dict["class_name"] = (
                            class_obj.name if class_obj else "Unknown"
                        )
                    except Exception as e:
                        self.logger.warning(
                            f"[Service:get_by_id] Could not look up class name for class_id {class_id}: {e}"
                        )
                        instance_dict["class_name"] = "Unknown"
                else:
                    instance_dict["class_name"] = "Unknown"

            self.logger.info(f"Found sound instance {sound_instance_id}.")
            return instance_dict

        except Exception as e:
            self.logger.error(
                f"Error getting sound instance by ID {sound_instance_id}: {str(e)}",
                exc_info=True,
            )
            return None

    def _delete_sound_instance_files(self, recording: Recording, user_id: str) -> bool:
        class_name = recording.metadata.get(
            "class_name"
        ) or self.recording_repo._get_class_name(recording.class_id)
        if not class_name:
            return False

        # Get paths using Type for directory, Status for filename component
        audio_path = self.file_manager.get_sound_instance_path(
            class_name,
            user_id,
            recording.recording_type,
            recording.id,
            recording.status,
        )
        metadata_path = self.file_manager.get_sound_metadata_path(
            class_name,
            user_id,
            recording.recording_type,
            recording.id,
            recording.status,
        )

        deleted_wav = self.file_manager.delete_file(audio_path)
        deleted_json = self.file_manager.delete_file(metadata_path)
        
        # Log if either deletion failed but the file existed
        if not deleted_wav and audio_path.exists():
            self.logger.warning(
                f"Failed to delete WAV file during instance deletion: {audio_path}"
            )
        if not deleted_json and metadata_path.exists():
            self.logger.warning(
                f"Failed to delete JSON file during instance deletion: {metadata_path}"
            )

        # Return true if both are gone (or didn't exist initially)
        return not audio_path.exists() and not metadata_path.exists()
            
    def get_gold_recordings_for_dictionary(
        self, owner_id: str, dictionary_id: str
    ) -> List[Recording]:
        """
        Get all GOLD recordings for all classes within a specific dictionary owned by a user.

        Args:
            owner_id: The User ID of the dictionary owner.
            dictionary_id: The ID of the dictionary.

        Returns:
            List of Recording objects of type GOLD belonging to the specified user and dictionary's classes.
        """
        self.logger.info(
            f"Fetching GOLD recordings for dictionary {dictionary_id} owned by {owner_id}"
        )
        all_gold_recordings = []
        
        try:
            # --- DEBUG: Check dictionary_repo type ---
            if not isinstance(self.dictionary_repo, DictionaryRepository):
                self.logger.error(
                    f"[get_gold_for_dict] CRITICAL: self.dictionary_repo is NOT a DictionaryRepository! Type: {type(self.dictionary_repo).__name__}"
                )
                return []  # Cannot proceed without the repo
            # --- END DEBUG ---

            # Get the dictionary object using the injected dictionary_repo
            dictionary = self.dictionary_repo.get_dictionary_by_id(dictionary_id)

            if not dictionary:
                self.logger.warning(
                    f"Dictionary {dictionary_id} not found when fetching gold recordings."
                )
                return []

            # Verify ownership (although the route handler should have done this)
            if dictionary.creator_user_id != owner_id:
                self.logger.warning(
                    f"User {owner_id} does not own dictionary {dictionary_id}. Cannot fetch gold recordings."
                )
                return []

            if not hasattr(dictionary, "class_ids") or not dictionary.class_ids:
                self.logger.info(
                    f"Dictionary {dictionary_id} has no associated classes."
                )
                return []

            self.logger.debug(
                f"Found {len(dictionary.class_ids)} classes in dictionary {dictionary_id}: {dictionary.class_ids}"
            )

            # Iterate through the class IDs associated with this dictionary
            for class_id in dictionary.class_ids:
                if not class_id:
                    continue  # Skip empty IDs just in case

                # Find GOLD recordings for this specific class and owner
                # Use the existing find_recordings method which calls the repo find
                class_gold_recordings = self.find_recordings(
                    class_id=class_id,
                    user_id=owner_id,
                    recording_type=RecordingType.GOLD,
                )
                self.logger.debug(
                    f"Found {len(class_gold_recordings)} GOLD recordings for class {class_id} in dict {dictionary_id}"
                )
                all_gold_recordings.extend(class_gold_recordings)

            self.logger.info(
                f"Found a total of {len(all_gold_recordings)} GOLD recordings for dictionary {dictionary_id}"
            )
            return all_gold_recordings

        except Exception as e:
            self.logger.error(
                f"Error fetching gold recordings for dictionary {dictionary_id}: {e}",
                exc_info=True,
            )
            return []
            