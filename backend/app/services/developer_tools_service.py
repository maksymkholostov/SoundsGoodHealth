import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

# Use filelock for safe writing to the shared JSON map
# Install: pip install filelock
try:
    import filelock
except ImportError:
    filelock = None # Handle case where it's not installed
    logging.getLogger(__name__).warning(
        "filelock library not found. "
        "Developer ID map writing will not be locked (minor risk in debug mode)."
    )


from backend.app.storage.file_manager import FileManager
from backend.app.core.repositories.user_repo import UserRepository
from backend.app.core.repositories.dictionary_repo import DictionaryRepository
# Import other repos as needed (Feature, Model) if you expand the map later
# from backend.app.core.repositories.feature_repo import FeatureRepository
# from backend.app.core.repositories.model_repo import ModelRepository

class DeveloperToolsService:
    """Service for developer-specific tools like ID map generation."""

    def __init__(self,
                 file_manager: FileManager,
                 user_repo: UserRepository,
                 dictionary_repo: DictionaryRepository
                 # Add other repos here if expanding the map:
                 # feature_repo: FeatureRepository,
                 # model_repo: ModelRepository,
                 ):
        self.file_manager = file_manager
        self.user_repo = user_repo
        self.dictionary_repo = dictionary_repo
        # self.feature_repo = feature_repo # Uncomment if adding features
        # self.model_repo = model_repo     # Uncomment if adding models
        self.logger = logging.getLogger(__name__)
        self._map_file_path = self.file_manager.get_data_root() / "developer_id_map.json"
        self._lock_file_path = self.file_manager.get_data_root() / "developer_id_map.json.lock"

    def get_developer_id_map_path(self) -> Path:
        """Returns the path to the developer ID map file."""
        return self._map_file_path

    def get_map(self) -> Dict[str, Any]:
        """Reads the current developer ID map file."""
        if not self._map_file_path.exists():
            return {"error": "Map file does not exist. Regenerate it first."}
        try:
            # No lock needed for simple read if writes are controlled
            map_data = self.file_manager.load_json(self._map_file_path)
            return map_data if map_data else {}
        except Exception as e:
            self.logger.error(f"Error reading developer ID map: {e}", exc_info=True)
            return {"error": f"Failed to read map file: {e}"}

    def generate_developer_id_map(self) -> bool:
        """
        Rebuilds the developer ID map by querying repositories.
        Overwrites the existing map file.
        Does NOT delete any other data.
        Excludes detailed recording info to keep the map size manageable.
        """
        self.logger.info("Starting regeneration of developer ID map...")
        start_time = datetime.now(timezone.utc)
        # Define structure with explicit list types
        new_map: Dict[str, List[Dict[str, Any]] | str] = {
            "users": [],
            "classes": [],
            "dictionaries": [],
            # Add keys for other types if needed later:
            # "feature_sets": [],
            # "models": [],
        }

        try:
            # 1. Get Users
            users = self.user_repo.list_users()
            for user in users:
                new_map["users"].append({ # type: ignore
                    "id": user.id,
                    "username": user.username,
                    "email": user.email
                })

            # 2. Get Classes
            classes = self.dictionary_repo.get_all_classes()
            for cls in classes:
                 # Ensure we handle potential dictionary vs object from repo
                cls_id = cls.id if hasattr(cls, 'id') else cls.get('id')
                cls_name = cls.name if hasattr(cls, 'name') else cls.get('name')
                if cls_id and cls_name:
                    new_map["classes"].append({"id": cls_id, "name": cls_name}) # type: ignore

            # 3. Get Dictionaries
            dictionaries = self.dictionary_repo.get_all_dictionaries() # Includes system dicts? Yes.
            for dictionary in dictionaries:
                 # Ensure we handle potential dictionary vs object from repo
                dict_id = dictionary.id if hasattr(dictionary, 'id') else dictionary.get('id')
                dict_name = dictionary.name if hasattr(dictionary, 'name') else dictionary.get('name')
                owner_id = dictionary.creator_user_id if hasattr(dictionary, 'creator_user_id') else dictionary.get('creator_user_id')
                if dict_id and dict_name and owner_id:
                    new_map["dictionaries"].append({ # type: ignore
                        "id": dict_id,
                        "name": dict_name,
                        "owner_user_id": owner_id
                    })

            # --- Add other entities here if needed in the future ---
            # Example: Feature Sets
            # if hasattr(self, 'feature_repo'):
            #     feature_sets = self.feature_repo.get_all_feature_sets()
            #     new_map["feature_sets"] = []
            #     for fs in feature_sets:
            #         new_map["feature_sets"].append({
            #             "id": fs.id,
            #             "name": fs.name,
            #             "parameters": fs.parameters
            #         })

            # Example: Models (Might need to iterate users/dicts)
            # if hasattr(self, 'model_repo'):
            #     all_models = []
            #     for user_entry in new_map.get("users",[]):
            #         user_id = user_entry.get("id")
            #         for dict_entry in new_map.get("dictionaries", []):
            #             dict_id = dict_entry.get("id")
            #             if user_id and dict_id and dict_entry.get("owner_user_id") == user_id:
            #                  models = self.model_repo.get_for_dictionary(user_id, dict_id)
            #                  for m in models:
            #                     all_models.append({
            #                         "id": m.id,
            #                         "name": f"{m.type.value}_{m.version}", # Example name
            #                         "type": m.type.value,
            #                         "version": m.version,
            #                         "dictionary_id": m.dictionary_id,
            #                         "user_id": m.user_id
            #                     })
            #     new_map["models"] = all_models
            # --------------------------------------------------------

            # Add timestamp
            new_map["last_updated"] = start_time.isoformat(timespec='seconds').replace("+00:00", "Z")

            # Write the file with a simple lock
            save_ok = False
            error_msg = "An unknown error occurred during save."
            if filelock:
                lock = filelock.FileLock(str(self._lock_file_path), timeout=10) # 10 sec timeout
                try:
                    with lock:
                        self.logger.info(f"Acquired lock, writing developer ID map to {self._map_file_path}")
                        save_ok = self.file_manager.save_json(new_map, self._map_file_path)
                        if not save_ok: error_msg = "FileManager failed to save JSON"
                        self.logger.info(f"Released lock. Save successful: {save_ok}")
                except filelock.Timeout:
                     error_msg = "Could not acquire lock (timeout). File may be locked by another process."
                     self.logger.error(error_msg)
                except Exception as e:
                    error_msg = f"Error during locked write: {e}"
                    self.logger.error(error_msg, exc_info=True)
            else:
                 # Fallback without locking if filelock is not installed
                 self.logger.warning("filelock library not installed. Writing developer ID map without locking.")
                 try:
                     save_ok = self.file_manager.save_json(new_map, self._map_file_path)
                     if not save_ok: error_msg = "FileManager failed to save JSON (no lock)."
                 except Exception as e:
                    error_msg = f"Error during non-locked write: {e}"
                    self.logger.error(error_msg, exc_info=True)

            if not save_ok:
                 self.logger.error(f"Failed to save developer ID map: {error_msg}")
                 return False

            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            self.logger.info(f"Finished regenerating developer ID map in {duration:.2f} seconds.")
            return True

        except Exception as e:
            self.logger.error(f"Error regenerating developer ID map: {e}", exc_info=True)
            return False
