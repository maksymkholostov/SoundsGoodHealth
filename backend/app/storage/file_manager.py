import os
import shutil
import json
import logging
import re  # Import re for sanitization
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple, Iterator, TYPE_CHECKING
from datetime import datetime
import sys
import soundfile as sf
from werkzeug.datastructures import FileStorage
import numpy as np  # Added import for numpy

from backend.app.core.models.recording import RecordingType

# Keep TYPE_CHECKING block for type hints only
if TYPE_CHECKING:
    from backend.app.core.models.recording import RecordingType


class FileManager:
    """
    Manages file operations for the SoundClassifiers application following V10 structure.

    Handles the organization of files according to the defined structure:
    - Sound instances (raw, pending, gold, augmented) metadata (.json) and audio (.wav)
    - Features
    - Models
    - Central class/dictionary definitions
    - Other metadata

    All paths are relative to the DATA_ROOT directory.
    """

    def __init__(self, data_root: str):
        """
        Initialize the FileManager with the root data directory.

        Args:
            data_root: The root directory for all data files
        """
        self.data_root = Path(data_root).resolve()  # Use resolved absolute path
        self.logger = logging.getLogger(__name__)

        # Define the base structure directories
        self.sounds_dir = self.data_root / "sounds"
        self.discarded_sounds_dir = (
            self.sounds_dir / "discarded"
        )  # NEW Discarded Dir Path
        self.features_dir = self.data_root / "features"
        self.models_dir = self.data_root / "models"
        self.metadata_dir = self.data_root / "metadata"
        self.dictionaries_dir = self.data_root / "dictionaries"
        self.classes_dir = self.data_root / "classes"
        self.users_dir = self.data_root / "users"  # Added for user data
        self.inference_dir = self.data_root / "inference"  # Added for inference results

        # Ensure the main V10 data directories exist
        # KEEP legacy dirs here FOR NOW due to deprecated methods
        self._ensure_directories(
            [
                self.data_root,
                self.sounds_dir,
                self.discarded_sounds_dir,  # Ensure discarded exists
                self.features_dir,
                self.models_dir,
                self.metadata_dir,
                self.dictionaries_dir,
                self.classes_dir,
                self.users_dir,
                self.inference_dir,
            ]
        )

        self.logger.info(f"FileManager initialized with data root: {self.data_root}")

    def _ensure_directories(self, directories: List[Path]) -> None:
        """
        Ensure that the given directories exist.

        Args:
            directories: List of directory paths to ensure
        """
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                self.logger.debug(f"Ensured directory exists: {directory}")
            except OSError as e:
                self.logger.error(f"Error creating directory {directory}: {e}")
                # Decide if this should raise an exception or just log

    def get_class_sounds_base_dir(self, class_name: str) -> Path:
        """Gets the base directory for a specific class within the sounds structure.
        Structure: data/sounds/<class_name>/
        """
        # Note: We don't ensure this directory exists here, as its existence
        # is used as a proxy for whether any sounds exist for the class.
        # The specific user/status subdirs are created when sounds are saved.
        return self.sounds_dir / str(class_name)

    def get_sound_instance_dir(
        self, class_name: str, user_id: str, recording_type: Union[RecordingType, str]
    ) -> Path:
        """
        Get the directory for sound files.
        Current structure: data/sounds/<class_name>/<username>/<type_str>/
        Where username is 'ronrubin' (not UUID)
        """
        # Handle both Enum and String inputs for type
        if isinstance(recording_type, RecordingType):
            type_str = recording_type.value
        elif isinstance(recording_type, str):
            type_str = (
                recording_type  # Assume it's the correct string value (e.g., "raw")
            )
        else:
            self.logger.error(
                f"Invalid recording_type provided: {recording_type} ({type(recording_type)}). Using 'unknown'."
            )
            type_str = "unknown"

        # Use the ACTUAL current structure: class_name/ronrubin/type
        # user_id is passed but we use 'ronrubin' as the actual directory name
        username = "ronrubin"  # This is what's actually used in the file system
        path = self.sounds_dir / class_name / username / type_str
        self._ensure_directories([path])
        return path

    def _get_uuid_part(self, recording_id: str) -> str:
        """Extracts the UUID part from IDs like rec_uuid or rec_uuid_segX."""
        if not recording_id:
            return "unknownid"
        parts = recording_id.split("_")
        uuid_candidate = None
        for part in parts:
            if "-" in part and len(part) > 30:
                if re.match(
                    r"^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$", part
                ):
                    uuid_candidate = part
                    break
        if not uuid_candidate and "-" in recording_id and len(recording_id) > 30:
            if re.match(
                r"^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$", recording_id
            ):
                uuid_candidate = recording_id
        if uuid_candidate:
            return uuid_candidate
        self.logger.warning(
            f"Could not reliably extract UUID from '{recording_id}'. Using sanitized full ID."
        )
        return re.sub(r"[^a-zA-Z0-9_\\-]+", "_", recording_id)

    def _generate_standard_filename(
        self,
        class_name: str,
        user_id: str,
        recording_type: Union[RecordingType, str],
        recording_id: str,
        extension: str,
    ) -> str:
        """
        Generates filename based on our documented ID format.
        The recording_id already contains all necessary information.
        Format: <recording_id>.<ext>
        Examples:
        - raw_rec_oh_ronrubin_20250807_133025123.wav
        - seg_oh_ronrubin_20250807_133025123_1.wav
        - gold_oh_ronrubin_20250807_133025123_1.wav
        - aug_oh_ronrubin_20250807_133025123.wav
        """
        # Simply use the recording_id as the filename base
        # The ID already contains all the necessary information
        return f"{recording_id}.{extension}"

    def get_sound_instance_path(
        self,
        class_name: str,
        user_id: str,
        recording_type: Union[RecordingType, str],
        recording_id: str,
        extension: str = "wav",
    ) -> Path:
        """
        Get V10 full path for audio file. Uses Type for directory, Status for filename.
        Filename: <ClassName>_<UserID>_<RecordingTypeValue>_<UUID>.<ext>
        """
        directory = self.get_sound_instance_dir(class_name, user_id, recording_type)
        filename = self._generate_standard_filename(
            class_name, user_id, recording_type, recording_id, extension
        )
        return directory / filename

    def get_sound_metadata_path(
        self,
        class_name: str,
        user_id: str,
        recording_type: Union[RecordingType, str],
        recording_id: str,
    ) -> Path:
        """
        Get V10 full path for metadata file. Uses Type for directory, Status for filename.
        Filename: <ClassName>_<UserID>_<RecordingTypeValue>_<UUID>.json
        """
        directory = self.get_sound_instance_dir(class_name, user_id, recording_type)
        filename = self._generate_standard_filename(
            class_name, user_id, recording_type, recording_id, "json"
        )
        return directory / filename

    def get_discarded_sound_path(
        self, class_name: str, user_id: str, recording_id: str, extension: str
    ) -> Path:
        """
        Gets path for discarded file.
        Filename: <ClassName>_<UserID>_rejected_<UUID>.<ext>
        """
        filename = self._generate_standard_filename(
            class_name, user_id, RecordingType.REJECTED, recording_id, extension
        )
        return self.discarded_sounds_dir / filename

    def find_sound_metadata_files(
        self,
        class_name: Optional[str] = None,
        user_id: Optional[str] = None,
        recording_type: Optional[RecordingType] = None,
        recording_id_part: Optional[str] = None,
    ) -> Iterator[Path]:
        """
        Finds sound metadata JSON files based on V10 structure.
        Filters by path components (ClassName, UserID, TypeDir) and filename components (Status, UUID).
        """
        search_paths = []
        base_search_dir = self.sounds_dir

        # Build path pattern parts (uses RecordingType for dir)
        class_part = str(class_name) if class_name else "*"
        user_part = str(user_id) if user_id else "*"
        type_dir_part = recording_type.value if recording_type else "*"

        # Record if we're looking for pending files specifically
        is_pending_search = recording_type and recording_type == RecordingType.PENDING

        # Build filename pattern parts (uses RecordingType value in filename)
        type_file_part = recording_type.value if recording_type else "*"
        if recording_id_part:
            uuid_part = self._get_uuid_part(recording_id_part)
            user_file_part = str(user_id) if user_id else "*"
            class_file_part = str(class_name) if class_name else "*"
            # This pattern ASSUMES the old format: Class_User_Type_UUID.json
            file_pattern = (
                f"{class_file_part}_{user_file_part}_{type_file_part}_{uuid_part}.json"
            )
        else:
            # New format: files start with type prefix (e.g., gold_*, raw_rec_*, aug_*)
            # Map recording types to their file prefixes
            if recording_type:
                if recording_type == RecordingType.RAW_RECORDED:
                    file_pattern = "raw_rec_*.json"
                elif recording_type == RecordingType.RAW_UPLOADED:
                    file_pattern = "raw_up_*.json"  # Per COMPLETE_NAMING_SYSTEM.md
                elif recording_type == RecordingType.GOLD:
                    file_pattern = "gold_*.json"  # Gold files start with gold_ per COMPLETE_NAMING_SYSTEM.md
                elif recording_type == RecordingType.AUGMENTED:
                    file_pattern = "aug_*.json"
                elif recording_type == RecordingType.REJECTED:
                    file_pattern = "disc_*.json"
                elif recording_type == RecordingType.PENDING:
                    file_pattern = "seg_*.json"  # Segments start with seg_ per COMPLETE_NAMING_SYSTEM.md
                else:
                    file_pattern = f"*_{type_file_part}_*.json"  # Fallback
            else:
                file_pattern = "*.json"  # Match all JSON files

        # Construct the main search path glob
        # For pending, becomes: */*/pending/*_pending_*.json
        main_glob = f"{class_part}/{user_part}/{type_dir_part}/{file_pattern}"
        search_paths.append(main_glob)

        # If searching for pending, also try with 'pending' directly in the filename
        if is_pending_search:
            self.logger.debug(
                f"Searching specifically for PENDING sounds with glob: {main_glob}"
            )
            segment_glob = (
                f"{class_part}/{user_part}/{type_dir_part}/*_pending_seg_*.json"
            )
            search_paths.append(segment_glob)
            self.logger.debug(f"Also adding segment search glob: {segment_glob}")
        else:
            # Log the standard search pattern when not doing a pending-specific search
            self.logger.debug(f"Searching sounds dir with glob: {main_glob}")

        # Search discarded directory (uses REJECTED type in filename)
        if not recording_type or recording_type == RecordingType.REJECTED:
            type_file_part = RecordingType.REJECTED.value
            if recording_id_part:
                uuid_part = self._get_uuid_part(recording_id_part)
                discarded_file_pattern = f"*_{type_file_part}_{uuid_part}.json"
            else:
                discarded_file_pattern = f"*_{type_file_part}_*.json"

            # Simplify the glob pattern for discarded files
            # Assume files are directly in discarded, not in subdirs like class/user
            discarded_glob = f"discarded/{discarded_file_pattern}"
            search_paths.append(discarded_glob)
            self.logger.debug(
                f"Also searching discarded dir with glob: {discarded_glob}"
            )

        # Execute searches
        found_files = set()
        for pattern in search_paths:
            try:
                pattern_count = 0
                self.logger.debug(f"Executing pattern search: {pattern}")
                
                # Use glob.glob instead of rglob for proper pattern matching
                import glob as glob_module
                full_pattern = str(base_search_dir / pattern)
                
                for f_path_str in glob_module.glob(full_pattern):
                    f_path = Path(f_path_str)
                    if f_path.is_file():
                        pattern_count += 1
                        found_files.add(f_path)
                self.logger.debug(f"Pattern '{pattern}' found {pattern_count} files")
            except Exception as e:
                self.logger.error(f"Error during glob search: {e}", exc_info=True)

        self.logger.info(f"Found total of {len(found_files)} files across all patterns")
        yield from iter(found_files)

    # --- V10 Feature Paths ---
    # Confirm final feature storage structure. Assuming class/sound_id based for now.
    def get_feature_set_dir(self, feature_version: str) -> Path:
        """Gets the base directory for a specific feature set version."""
        path = self.features_dir / feature_version
        self._ensure_directories([path])
        return path

    def get_feature_instance_dir(
        self, feature_version: str, class_name: str, sound_id: str
    ) -> Path:
        """Gets the directory for features of a specific sound instance."""
        # Example: data/features/<version>/<class_name>/<sound_id>/
        path = self.get_feature_set_dir(feature_version) / class_name / sound_id
        self._ensure_directories([path])
        return path

    def get_feature_file_path(
        self,
        feature_version: str,
        class_name: str,
        sound_id: str,
        filename: str = "features.npy",
    ) -> Path:
        """Gets the full path for a specific feature file (e.g., .npy, metadata.json)."""
        return (
            self.get_feature_instance_dir(feature_version, class_name, sound_id)
            / filename
        )

    def get_feature_data_path(
        self,
        feature_version: str,
        user_id: str,
        subset: str,
        class_name: str,
        filename: str,
    ) -> Path:
        """
        Gets the V10 path for storing feature data files (.npz, .metadata.json).
        Structure: data/features/<version>/<user_id>/<subset>/<class_name>/<filename>
        """
        # Basic validation
        if subset not in ["gold", "augmented"]:
            self.logger.warning(
                f"Invalid subset '{subset}' requested for feature path. Defaulting to 'unknown'."
            )
            subset = "unknown"  # Or raise ValueError

        # Path no longer includes dictionary_id
        path = (
            self.features_dir
            / feature_version
            / user_id
            / subset
            / class_name
            / filename
        )
        # Ensure the specific directory for this file exists *before* returning the path
        # Note: Saving methods also call mkdir, but doing it here ensures consistency for path retrieval too.
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.logger.error(
                f"Error ensuring feature data directory exists {path.parent}: {e}"
            )
            # Optionally raise an exception here if directory creation failure is critical
        return path

    # --- V10 Model Paths ---
    # Models are likely trained per dictionary
    def get_dictionary_models_dir(self, dictionary_id: str) -> Path:
        """Gets the base directory for all models related to a dictionary."""
        # Example: data/models/<dictionary_id>/
        path = self.models_dir / dictionary_id
        self._ensure_directories([path])
        return path

    def get_specific_model_dir(
        self, dictionary_id: str, model_type_version: str
    ) -> Path:
        """Gets the directory for a specific trained model version for a dictionary."""
        # Example: data/models/<dictionary_id>/<model_type_version>/
        path = self.get_dictionary_models_dir(dictionary_id) / model_type_version
        self._ensure_directories([path])
        return path

    def get_specific_model_path(
        self, dictionary_id: str, model_type_version: str, filename: str
    ) -> Path:
        """Gets the path to a specific file within a model directory (e.g., model.h5, config.json)."""
        return self.get_specific_model_dir(dictionary_id, model_type_version) / filename

    # --- V10 Central Registries ---
    def get_global_classes_registry_path(self) -> Path:
        """Gets the path to the single source of truth for class definitions."""
        return self.classes_dir / "global_registry.json"

    def get_system_dictionaries_path(self) -> Path:
        """Gets the path to the single source of truth for dictionary definitions."""
        return self.dictionaries_dir / "system_dictionaries.json"

    # --- V10 User Data ---
    def get_user_data_path(
        self, user_id: str, filename: str = "user_profile.json"
    ) -> Path:
        """Gets the path for a user-specific data file."""
        user_dir = self.users_dir / user_id
        self._ensure_directories([user_dir])
        return user_dir / filename

    def get_user_email_index_path(self) -> Path:
        """Gets the path for the email-to-user-id index."""
        return self.users_dir / "email_index.json"


    def get_user_noise_profile_path(self, user_id: str) -> Path:
        """Gets the path for the user's recorded noise profile WAV file."""
        user_dir = self.users_dir / user_id
        self._ensure_directories([user_dir])  # Ensure user dir exists
        return user_dir / "noise_profile.wav"

    # --- Other Paths ---
    def get_inference_results_dir(
        self, user_id: str, dictionary_id: str, model_id: str
    ) -> Path:
        """Gets the directory for storing inference results."""
        path = self.inference_dir / user_id / dictionary_id / model_id
        self._ensure_directories([path])
        return path

    def get_stats_cache_path(self) -> Path:
        """Gets the path for the global dashboard stats cache file."""
        stats_dir = self.metadata_dir / "stats"
        self._ensure_directories([stats_dir])
        return stats_dir / "global_stats.json"

    def get_metadata_sub_dir(self, sub_dir_name: str) -> Path:
        """Gets a subdirectory within the main metadata folder."""
        path = self.metadata_dir / sub_dir_name
        self._ensure_directories([path])
        return path

    def get_data_root(self) -> Path:
        """Returns the configured data root path."""
        return self.data_root

    # --- Basic File Operations ---
    def save_file(self, content: bytes, path: Path) -> bool:
        """Saves binary content to the specified path, ensuring directory exists."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                f.write(content)
            self.logger.info(f"File saved: {path}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving file {path}: {str(e)}")
            return False

    def save_json(self, data: Dict[str, Any], path: Path) -> bool:
        """Saves a dictionary as JSON to the specified path, ensuring directory exists."""
        # Convert string path to Path object if needed
        if isinstance(path, str):
            path = Path(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:  # Ensure utf-8 encoding
                json.dump(data, f, indent=2)
            self.logger.info(f"JSON saved: {path}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving JSON {path}: {str(e)}")
            return False

    def load_file(self, path: Path) -> Optional[bytes]:
        """Loads binary content from the specified path."""
        try:
            if not path.is_file():  # Check if it's a file
                self.logger.warning(f"File not found or is a directory: {path}")
                return None
            with open(path, "rb") as f:
                content = f.read()
            self.logger.debug(f"File loaded: {path}")
            return content
        except Exception as e:
            self.logger.error(f"Error loading file {path}: {str(e)}")
            return None

    def load_json(self, path: Path) -> Optional[Dict[str, Any]]:
        """Loads JSON data from the specified path."""
        try:
            if isinstance(path, str):  # Allow string paths
                path = Path(path)
            if not path.is_file():  # Check if it's a file
                self.logger.warning(f"JSON file not found or is a directory: {path}")
                return None
            with open(path, "r", encoding="utf-8") as f:  # Ensure utf-8 encoding
                data = json.load(f)
            self.logger.debug(f"JSON loaded: {path}")
            return data
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding JSON from {path}: {e}")
            return None  # Specific error for bad JSON
        except Exception as e:
            self.logger.error(f"Error loading JSON {path}: {str(e)}")
            return None

    def delete_file(self, path: Path) -> bool:
        """Deletes a file at the specified path."""
        try:
            if not path.exists():
                self.logger.warning(
                    f"Cannot delete non-existent file/directory: {path}"
                )
                return True  # Or False depending on desired behavior
            if path.is_file():
                os.remove(path)
                self.logger.info(f"File deleted: {path}")
                return True
            else:
                self.logger.warning(
                    f"Attempted to delete a directory with delete_file: {path}"
                )
                return False
        except Exception as e:
            self.logger.error(f"Error deleting file {path}: {str(e)}")
            return False

    def delete_directory(self, path: Path) -> bool:
        """Recursively deletes a directory and its contents."""
        try:
            if not path.is_dir():
                self.logger.warning(f"Directory not found for deletion: {path}")
                return True  # Or False?
            shutil.rmtree(path)
            self.logger.info(f"Directory deleted: {path}")
            return True
        except Exception as e:
            self.logger.error(f"Error deleting directory {path}: {str(e)}")
            return False

    def list_files(self, directory: Path, pattern: str = "*") -> List[Path]:
        """Lists files in a directory matching a pattern (non-recursive)."""
        try:
            if not directory.is_dir():
                self.logger.warning(
                    f"Directory does not exist for listing: {directory}"
                )
                return []
            # Use glob for non-recursive listing
            files = list(directory.glob(pattern))
            self.logger.debug(
                f"Listed {len(files)} files in {directory} matching '{pattern}'"
            )
            return files
        except Exception as e:
            self.logger.error(f"Error listing files in {directory}: {str(e)}")
            return []

    def copy_file(self, source: Path, destination: Path) -> bool:
        """Copies a file, ensuring destination directory exists."""
        try:
            if not source.is_file():
                self.logger.warning(
                    f"Source file does not exist or is directory: {source}"
                )
                return False
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)  # copy2 preserves metadata
            self.logger.info(f"File copied from {source} to {destination}")
            return True
        except Exception as e:
            self.logger.error(
                f"Error copying file from {source} to {destination}: {str(e)}"
            )
            return False

    def move_file(self, source: Path, destination: Path) -> bool:
        """Moves a file, ensuring destination directory exists."""
        try:
            if not source.is_file():
                self.logger.warning(
                    f"Source file does not exist or is directory: {source}"
                )
                return False
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))  # Use shutil.move
            self.logger.info(f"File moved from {source} to {destination}")
            return True
        except Exception as e:
            self.logger.error(
                f"Error moving file from {source} to {destination}: {str(e)}"
            )
            return False

    def load_npz(self, path: Path) -> Optional[Dict[str, np.ndarray]]:
        """Loads data from a .npz file.

        Args:
            path: Path to the .npz file.

        Returns:
            A dictionary-like object containing arrays if successful, None otherwise.
            Uses np.load, so the return type is technically NpzFile.
        """
        try:
            if not path.is_file():
                self.logger.warning(f"NPZ file not found or is a directory: {path}")
                return None

            # Load the file, disable pickle loading for security unless explicitly needed.
            data = np.load(str(path), allow_pickle=False)
            self.logger.debug(f"NPZ file loaded successfully: {path}")
            return data
        except Exception as e:
            self.logger.error(f"Error loading NPZ file {path}: {str(e)}", exc_info=True)
            return None

    # --- Metadata Path Methods ---
