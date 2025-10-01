import json
import logging
from pathlib import Path
from typing import List, Optional, Iterator

from backend.app.core.models.recording import Recording, RecordingType
from backend.app.core.repositories.dictionary_repo import DictionaryRepository # Assuming correct import path
from backend.app.storage.file_manager import FileManager

logger = logging.getLogger(__name__)

class RecordingRepository:
    """
    Repository for managing Recording metadata (.json files) stored alongside audio files.

    Relies on FileManager for path construction and file I/O according to the structure:
    data/sounds/<class_name>/<user_id>/<type>/<sound_id>_<timestamp>.json

    Relies on DictionaryRepository to map class_id to class_name.
    """

    def __init__(self, file_manager: FileManager, dictionary_repo: DictionaryRepository):
        """Initialize the repository."""
        self.file_manager = file_manager
        self.dictionary_repo = dictionary_repo
        self.logger = logging.getLogger(__name__) # Initialize instance logger
        self.logger.info("RecordingRepository initialized.")

    def _get_class_name(self, class_id: str) -> Optional[str]:
        """Helper to get class name from class ID."""
        sound_class = self.dictionary_repo.get_class_by_id(class_id)
        if not sound_class:
            self.logger.error(f"Could not find class name for class_id: {class_id}")
            return None
        return sound_class.name

    def save(self, recording: Recording, user_id: str) -> bool:
        """
        Saves the metadata of a Recording object to its corresponding JSON file.

        Args:
            recording: The Recording object to save.
            user_id: The UUID of the user (for path generation).

        Returns:
            True if saving was successful, False otherwise.
        """
        class_name = self._get_class_name(recording.class_id)
        if not class_name:
            return False # Error already logged in _get_class_name

        metadata_path = None # Initialize path for logging in case of early failure
        try:
            # Pass UserID UUID, Type (for dir AND filename part)
            metadata_path = self.file_manager.get_sound_metadata_path(
                class_name=class_name,
                user_id=user_id,
                recording_type=recording.recording_type, # Pass type
                recording_id=recording.id
                # Status no longer needed for path/filename
            )
            recording_dict = recording.to_dict()
            # Ensure username and class_name are in the dict to be saved
            if 'username' not in recording_dict and hasattr(self, 'uuid_to_username'): # Add lookup if missing
                 recording_dict['username'] = self.uuid_to_username.get(user_id, 'unknown_user')
            if 'class_name' not in recording_dict:
                 recording_dict['class_name'] = class_name

            # --- Ensure absolute 'path' is included in the saved JSON ---
            if 'path' not in recording_dict and recording.relative_wav_path:
                 try:
                     absolute_path = self.file_manager.get_data_root() / recording.relative_wav_path
                     recording_dict['path'] = str(absolute_path)
                     if not absolute_path.exists():
                          self.logger.warning(f"[RepoSave] Calculated path {absolute_path} for {recording.id} does not exist during save.")
                 except Exception as path_e:
                     self.logger.error(f"[RepoSave] Error constructing absolute path for {recording.id} during save: {path_e}")
                     # Decide if save should fail if path cannot be determined/added
            # --- End path addition ---

            # --- Add Logging ---
            self.logger.debug(f"[RepoSave] Attempting to save JSON for ID {recording.id} to path: {metadata_path}")
            save_success = self.file_manager.save_json(recording_dict, metadata_path)
            self.logger.debug(f"[RepoSave] FileManager.save_json result: {save_success}")
            # --- End Logging ---
            return save_success # Return the result from FileManager

        except AttributeError as e:
            self.logger.error(f"[RepoSave] FileManager missing required method (e.g., get_sound_metadata_path)? Error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"[RepoSave] Error saving recording metadata for {recording.id} ({class_name}/{user_id}) to {metadata_path}: {e}", exc_info=True)
            return False

    def find_by_id(self, recording_id: str) -> Optional[Recording]:
        """
        Finds a recording by its unique ID by searching metadata files.

        Args:
            recording_id: The ID of the recording to find.

        Returns:
            The Recording object if found, None otherwise.
        """
        self.logger.debug(f"Attempting to find recording by ID: {recording_id}")
        try:
            # Iterate through all .json files within the sounds directory recursively
            search_root = self.file_manager.sounds_dir
            self.logger.debug(f"Searching for ID '{recording_id}' in JSON files under {search_root}")

            # Special handling for segment IDs - check if this is a segment ID format
            is_segment = recording_id.startswith('seg_')
            self.logger.debug(f"ID '{recording_id}' determined to be segment? {is_segment}")

            for metadata_path in search_root.rglob('*.json'):
                # Skip files in 'discarded' for this primary search
                if self.file_manager.discarded_sounds_dir in metadata_path.parents:
                    continue
                
                try:
                    # Attempt to load the JSON data
                    recording_dict = self.file_manager.load_json(metadata_path)

                    # Check if loading succeeded
                    if not recording_dict:
                        continue

                    # For debug - log the found ID in the file
                    file_id = recording_dict.get('id')
                    if is_segment and 'seg_' in str(file_id):
                        self.logger.debug(f"Found segment ID in {metadata_path}: {file_id}")

                    # Check if the 'id' field matches exactly or if this is a segment ID
                    if recording_dict and (recording_dict.get('id') == recording_id):
                        self.logger.debug(f"Found exact matching ID {recording_id} in file: {metadata_path}")
                        # Attempt to create the Recording object
                        try:
                            recording_obj = Recording.from_dict(recording_dict)
                            if recording_obj:
                                return recording_obj
                            else:
                                self.logger.warning(f"Failed to create Recording object from matched file: {metadata_path}")
                                # Continue searching just in case, though this implies data/model issues
                        except Exception as parse_e:
                            self.logger.warning(f"Error creating Recording object from {metadata_path}: {parse_e}")
                            # Continue searching
                            
                except Exception as load_e:
                    # Log errors during loading but continue searching other files
                    self.logger.debug(f"Skipping file {metadata_path} due to load error: {load_e}", exc_info=False)
                    continue
            
            # If the loop completes without finding the recording
            self.logger.warning(f"Recording ID {recording_id} not found in any metadata file.")
            return None

        except Exception as e:
            self.logger.error(f"Error during find_by_id search for {recording_id}: {e}", exc_info=True)
            return None

    def find(self,
             class_id: Optional[str] = None,
             user_id: Optional[str] = None,
             recording_type: Optional[RecordingType] = None,
             recording_type__in: Optional[List[RecordingType]] = None,
             class_id__in: Optional[List[str]] = None,
             status: Optional[RecordingType] = None
             ) -> List[Recording]:
        """
        Finds recordings based on specified criteria.

        Args:
            class_id: Filter by class ID.
            user_id: Filter by user UUID.
            recording_type: Filter by a single recording type (enum).
            recording_type__in: Filter by a list of recording types (enum).
            class_id__in: Filter by a list of class IDs.
            status: Filter by recording status.

        Returns:
            A list of matching Recording objects.

        Raises:
            ValueError: If both 'recording_type' and 'recording_type__in' are provided,
                        or if both 'class_id' and 'class_id__in' are provided.
        """
        # --- Input Validation ---
        if recording_type and recording_type__in:
            raise ValueError("Cannot specify both 'recording_type' and 'recording_type__in'")
        if class_id and class_id__in:
             raise ValueError("Cannot specify both 'class_id' and 'class_id__in'")

        results: List[Recording] = []
        class_name: Optional[str] = None # Used only if single class_id provided

        # Log the provided parameters for debugging
        self.logger.debug(f"Find method called with params: class_id={class_id}, user_id={user_id}, " +
                          f"recording_type={recording_type}, recording_type__in={recording_type__in}, " +
                          f"status={status}")

        # If we're explicitly looking for PENDING recordings, log it
        is_pending_search = (recording_type == RecordingType.PENDING) or \
                            (recording_type__in and RecordingType.PENDING in recording_type__in) or \
                            (status == RecordingType.PENDING)
        if is_pending_search:
            self.logger.info(f"Searching for PENDING recordings with class_id={class_id}, user_id={user_id}")

        # Only get class name if single class_id is specified for potential FileManager optimization
        if class_id:
            class_name = self._get_class_name(class_id)
            if not class_name:
                self.logger.warning(f"Invalid class_id provided: {class_id}. Returning empty list.")
                return [] # Cannot search without class name if class_id is provided but invalid

        try:
            # Determine type for FileManager search (pass single type if possible for efficiency)
            fm_recording_type = recording_type if not recording_type__in else None
            # Determine class_name for FileManager search (only pass if single ID provided)
            fm_class_name = class_name if not class_id__in else None

            # Pass UserID, potentially single RecordingType and single Class Name to FileManager search
            # If class_id__in is used, we might need to search broader initially (e.g., just by user_id).
            # Let's assume find_sound_metadata_files can handle None for class_name gracefully.
            self.logger.debug(f"Calling find_sound_metadata_files with: class_name={fm_class_name}, user_id={user_id}, type={fm_recording_type}")
            found_files = self.file_manager.find_sound_metadata_files(
                class_name=fm_class_name,
                user_id=user_id,
                recording_type=fm_recording_type
            )

            # Track which files were examined for debugging
            examined_files_count = 0
            matched_files_count = 0

            for metadata_path in found_files:
                examined_files_count += 1
                try:
                    recording_dict = self.file_manager.load_json(metadata_path)
                    if not recording_dict:
                        continue
                    
                    # If debugging pending recordings, log the file details
                    if is_pending_search:
                        file_type = recording_dict.get('recording_type')
                        file_id = recording_dict.get('id')
                        self.logger.debug(f"Examining potential pending file: {metadata_path.name}, " +
                                          f"id={file_id}, type={file_type}")

                    recording = Recording.from_dict(recording_dict)

                    # Filter by single class_id (if provided)
                    if class_id and recording.class_id != class_id:
                        continue

                    # Filter by list of class_ids (if provided)
                    if class_id__in and recording.class_id not in class_id__in: # <-- THIS IS THE NEW BIT
                        continue

                    # Filter by user_id (double-check, though FileManager might have handled it)
                    if user_id and recording.user_id != user_id:
                        continue

                    # --- Apply type filtering (either single type or list) --- # ADDED FILTERING
                    type_match = True # Assume match unless filtered out
                    if recording_type and recording.recording_type != recording_type:
                        if is_pending_search:
                            self.logger.debug(f"Type mismatch for {recording.id}: expected {recording_type}, got {recording.recording_type}")
                        type_match = False
                    elif recording_type__in and recording.recording_type not in recording_type__in:
                        if is_pending_search:
                            self.logger.debug(f"Type not in list for {recording.id}: expected one of {recording_type__in}, got {recording.recording_type}")
                        type_match = False

                    if not type_match:
                        continue # Skip if type doesn't match filter
                    # --- End type filtering --- #

                    # --- ADDED: Filter by status (checking nested metadata dict) ---
                    status_match = True # Assume match unless filtered out
                    if status:
                        # Check the status field within the loaded metadata dictionary
                        metadata_dict = recording_dict.get('metadata', {})
                        if metadata_dict.get('status') != status.value:
                            status_match = False
                    
                    if not status_match:
                        continue # Skip if status doesn't match filter
                    # --- END Status Filtering ---

                    # If all filters pass, add to results
                    matched_files_count += 1
                    if is_pending_search:
                        self.logger.info(f"MATCH! Found pending recording: {recording.id} at {metadata_path}")
                    results.append(recording)

                except Exception as load_exc:
                    self.logger.error(f"Error loading or processing recording from {metadata_path}: {load_exc}", exc_info=False)
                    continue # Skip this file

            log_types = ""
            if recording_type:
                log_types = f"type={recording_type.name}"
            elif recording_type__in:
                type_names = [t.name for t in recording_type__in]
                log_types = f"type_in={type_names}"
                
            self.logger.info(f"Examined {examined_files_count} files, matched {matched_files_count} recordings " +
                             f"(class_id={class_id}, user_id={user_id}, {log_types}, status={status.name if status else None})")
            return results

        except AttributeError as e:
            self.logger.error(f"FileManager missing required method (e.g., find_sound_metadata_files)? Error: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error finding recordings: {e}", exc_info=True)
            return []

    def delete(self, recording: Recording, user_id: str) -> bool:
        """
        Deletes the metadata JSON file associated with a Recording object.
        Note: This does NOT delete the corresponding audio (.wav) file.

        Args:
            recording: The Recording object whose metadata should be deleted.
            user_id: The UUID associated with the recording (for path).

        Returns:
            True if deletion was successful, False otherwise.
        """
        class_name = self._get_class_name(recording.class_id)
        if not class_name:
            return False

        try:
            # Pass UserID UUID and Type
            metadata_path = self.file_manager.get_sound_metadata_path(
                class_name=class_name,
                user_id=user_id,
                recording_type=recording.recording_type,
                recording_id=recording.id
                # Status removed
            )

            if not metadata_path.exists():
                self.logger.warning(f"Metadata file not found for deletion: {metadata_path}")
                return False # Or True if we consider non-existence as success?

            return self.file_manager.delete_file(metadata_path)

        except AttributeError as e:
            self.logger.error(f"FileManager missing required method? Error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error deleting recording metadata for {recording.id}: {e}", exc_info=True)
            return False

    def get_all_for_dictionary(self, dictionary_id: str, 
                               user_id: Optional[str] = None, 
                               rec_type: Optional[RecordingType] = None,
                               # status: Optional[RecordingStatus] = None # REMOVED
                               ) -> List[Recording]:
        """
        Retrieves all recordings associated with a specific dictionary by iterating
        through its classes. Can filter by user UUID.

        Args:
            dictionary_id: The ID of the dictionary.
            user_id: Optional filter by user UUID.
            rec_type: Optional filter by recording type.
            # status: Optional filter by recording status.

        Returns:
            A list of matching Recording objects.
        """
        dictionary = self.dictionary_repo.get_dictionary_by_id(dictionary_id)
        if not dictionary:
            self.logger.warning(f"Dictionary not found: {dictionary_id}")
            return []

        all_recordings: List[Recording] = []
        for class_id in dictionary.class_ids:
            class_recordings = self.find(
                class_id=class_id,
                user_id=user_id, 
                recording_type=rec_type
                # status=status # REMOVED
            )
            all_recordings.extend(class_recordings)
        
        self.logger.info(f"Found {len(all_recordings)} recordings for dictionary {dictionary_id} (filter: user_id={user_id}, type={rec_type})") # Removed status from log
        return all_recordings 