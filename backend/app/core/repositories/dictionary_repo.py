import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.app.core.models.dictionary import Dictionary, SoundClass
from backend.app.storage.file_manager import FileManager

class DictionaryRepository:
    """
    Repository for Dictionary domain objects.
    
    Handles persistence of dictionaries and sound classes to the file system.
    Uses a single JSON file (`system_dictionaries.json`) to store all dictionary metadata.
    """
    # Define central file paths using pathlib
    CLASSES_REGISTRY_FILENAME = "global_registry.json"
    DICTIONARIES_FILENAME = "system_dictionaries.json" # Single file for all dicts
    CLASSES_DIR_NAME = "classes"
    DICTIONARIES_DIR_NAME = "dictionaries" # Directory containing the system file

    def __init__(self, file_manager: FileManager):
        """
        Initialize the dictionary repository.
        
        Args:
            file_manager: FileManager instance for storage operations
        """
        self.file_manager = file_manager
        self.logger = logging.getLogger(__name__)
        
        # Construct the full paths using the file manager's root
        self._classes_registry_path = ( 
            Path(self.file_manager.data_root) / self.CLASSES_DIR_NAME / self.CLASSES_REGISTRY_FILENAME
        )
        # Path to the SINGLE system dictionary file
        self._dictionaries_system_file_path = (
            Path(self.file_manager.data_root) / self.DICTIONARIES_DIR_NAME / self.DICTIONARIES_FILENAME
        )
        # Path to the directory containing the system file
        self._dictionaries_dir_path = self._dictionaries_system_file_path.parent
        
        self.logger.info("DictionaryRepository initialized.")
        self.logger.info("Using global classes registry: %s", self._classes_registry_path)
        self.logger.info("Using system dictionaries file: %s", self._dictionaries_system_file_path)
        self.logger.info("Using individual dictionaries directory: %s", self._dictionaries_dir_path)
        
        # Create directories if they don't exist
        self._classes_registry_path.parent.mkdir(exist_ok=True, parents=True)
        self._dictionaries_dir_path.mkdir(exist_ok=True, parents=True)
        
        # Initialize empty files if they don't exist
        if not self._classes_registry_path.exists():
            self.file_manager.save_json({"classes": []}, str(self._classes_registry_path))
            self.logger.info("Created empty global classes registry")
        
        # Initialize the system dictionaries file if it doesn't exist
        if not self._dictionaries_system_file_path.exists():
            self.file_manager.save_json({"dictionaries": []}, str(self._dictionaries_system_file_path))
            self.logger.info("Created empty system dictionaries file")

    # --- Helper methods for loading/saving central files ---

    def _load_class_registry_data(self) -> dict:
        """Loads the entire class registry file, returning default structure if not found."""
        self.logger.debug("Attempting to load class registry from %s", self._classes_registry_path)
        data = self.file_manager.load_json(str(self._classes_registry_path))
        if data is None:
            self.logger.warning("Class registry file not found or empty at %s. Returning default structure.", self._classes_registry_path)
            return {"classes": []} # Default structure
        if "classes" not in data or not isinstance(data["classes"], list):
             self.logger.warning("Class registry file at %s has invalid format. Returning default structure.", self._classes_registry_path)
             return {"classes": []}
        self.logger.debug("Successfully loaded class registry data.")
        return data

    def _save_class_registry_data(self, data: dict) -> bool:
        """Saves the entire class registry data structure."""
        self.logger.debug("Attempting to save class registry to %s", self._classes_registry_path)
        success = self.file_manager.save_json(data, str(self._classes_registry_path))
        if success:
            self.logger.debug("Successfully saved class registry data.")
        else:
             self.logger.error("Failed to save class registry data to %s", self._classes_registry_path)
        return success

    # --- Methods for the SINGLE system dictionary file ---
    def _load_dictionary_data(self) -> dict:
        """Loads the entire system dictionaries file, returning default structure if not found."""
        self.logger.debug("Attempting to load system dictionaries from %s", self._dictionaries_system_file_path)
        data = self.file_manager.load_json(str(self._dictionaries_system_file_path))
        if data is None:
            self.logger.warning("System dictionaries file not found or empty at %s. Returning default structure.", self._dictionaries_system_file_path)
            return {"dictionaries": []} # Default structure
        if "dictionaries" not in data or not isinstance(data["dictionaries"], list):
             self.logger.warning("System dictionaries file at %s has invalid format. Returning default structure.", self._dictionaries_system_file_path)
             return {"dictionaries": []}
        self.logger.debug("Successfully loaded system dictionary data.")
        return data

    def _save_dictionary_data(self, data: dict) -> bool:
        """Saves the entire system dictionaries data structure."""
        self.logger.debug("Attempting to save system dictionaries to %s", self._dictionaries_system_file_path)
        success = self.file_manager.save_json(data, str(self._dictionaries_system_file_path))
        if success:
            self.logger.debug("Successfully saved system dictionary data.")
        else:
             self.logger.error("Failed to save system dictionary data to %s", self._dictionaries_system_file_path)
        return success

    # --- Class Persistence Methods (V10) ---
    def get_all_classes(self) -> List[SoundClass]:
        """Loads all classes from the global registry."""
        registry_data = self._load_class_registry_data()
        classes = []
        for class_data in registry_data.get("classes", []):
            try:
                classes.append(SoundClass.from_dict(class_data))
            except Exception as e:
                self.logger.error("Error parsing class data from registry: %s\nData: %s", e, class_data, exc_info=True)
        return classes

    def get_class_by_id(self, class_id: str) -> Optional[SoundClass]:
        """Finds a class by its ID in the global registry."""
        all_classes = self.get_all_classes()
        for cls in all_classes:
            if cls.id == class_id:
                return cls
        self.logger.debug("Class with ID %s not found in registry.", class_id)
        return None

    def get_class_by_name(self, name: str) -> Optional[SoundClass]:
        """Finds a class by its name (case-insensitive) in the global registry."""
        all_classes = self.get_all_classes()
        search_name = name.lower()
        for cls in all_classes:
            if hasattr(cls, 'name') and cls.name and cls.name.lower() == search_name:
                return cls
        self.logger.debug("Class with name '%s' not found in registry.", name)
        return None

    def save_class(self, sound_class: SoundClass, creator_uid: Optional[str] = None) -> bool:
        """
        Saves (adds or updates) a class in the global registry.
        Ensures class names are unique case-insensitively before adding.
        """
        registry_data = self._load_class_registry_data()
        class_list = registry_data.get("classes", [])
        found_by_id = False
        existing_class_with_same_name = self.get_class_by_name(sound_class.name) # Case-insensitive check

        for i, existing_class_data in enumerate(class_list):
            if existing_class_data.get('id') == sound_class.id:
                # --- Update existing class by ID ---
                # Optional: Check if name is changing to one that already exists with a DIFFERENT ID
                if (existing_class_with_same_name and
                        existing_class_with_same_name.id != sound_class.id):
                    self.logger.error(f"Cannot update class ID {sound_class.id}: "
                                      f"New name '{sound_class.name}' conflicts with existing class ID {existing_class_with_same_name.id}.")
                    return False # Prevent saving if name change causes collision

                self.logger.info(f"Updating class ID {sound_class.id} ('{sound_class.name}') in registry.")
                class_dict = sound_class.to_dict() # Save with original case
                # Preserve existing creator_uid if it exists and no new one provided
                if 'creator_uid' in existing_class_data and creator_uid is None:
                    class_dict['creator_uid'] = existing_class_data['creator_uid']
                elif creator_uid:
                    class_dict['creator_uid'] = creator_uid
                class_list[i] = class_dict
                found_by_id = True
                break

        # --- Add new class only if ID wasn't found AND name doesn't already exist ---
        if not found_by_id:
            if existing_class_with_same_name:
                # Name exists, but with a different ID. Prevent adding duplicate name.
                self.logger.warning(f"Cannot add new class '{sound_class.name}': "
                                    f"A class with this name (case-insensitive) already exists with ID {existing_class_with_same_name.id}.")
                # Decide behaviour: return False (prevent add) or return True (treat as success - name exists)
                # Returning False is safer to indicate the explicit add failed due to conflict.
                return False
            else:
                # Add the new class (ID and Name are unique)
                self.logger.info(f"Adding new class '{sound_class.name}' (ID: {sound_class.id}) to registry.")
                class_dict = sound_class.to_dict() # Save with original case
                # Add creator_uid if provided
                if creator_uid:
                    class_dict['creator_uid'] = creator_uid
                class_list.append(class_dict)

        # --- Save updated registry data ---
        registry_data["classes"] = class_list
        return self._save_class_registry_data(registry_data)

    def delete_class(self, class_id: str) -> bool:
        """Deletes a class from the global registry by its ID."""
        registry_data = self._load_class_registry_data()
        class_list = registry_data.get("classes", [])
        initial_len = len(class_list)
        
        # Filter out the class to delete
        updated_class_list = [cls for cls in class_list if cls.get('id') != class_id]
        
        if len(updated_class_list) < initial_len:
            registry_data["classes"] = updated_class_list
            if self._save_class_registry_data(registry_data):
                self.logger.info("Deleted class ID %s from registry.", class_id)
                return True
            else:
                self.logger.error("Failed to save registry after deleting class ID %s.", class_id)
                return False # Save failed
        else:
            self.logger.warning("Attempted to delete non-existent class ID %s from registry.", class_id)
            return False # Class not found
        
    # --- Dictionary Persistence Methods (V10) ---

    def get_all_dictionaries(self) -> List[Dictionary]:
        """Loads all dictionaries from the system dictionaries file."""
        self.logger.info(f"--- Attempting to load dictionaries from: {self._dictionaries_system_file_path} ---")
        dictionary_data = self._load_dictionary_data() # This helper already logs loading attempts/errors
        dictionaries = []

        if not dictionary_data or "dictionaries" not in dictionary_data:
             self.logger.warning("No 'dictionaries' key found or data is empty after loading.")
             return dictionaries # Return empty list early if structure is wrong

        dict_list = dictionary_data.get("dictionaries", [])
        self.logger.info(f"Found {len(dict_list)} dictionary entries in the loaded file data.")

        for i, dict_data in enumerate(dict_list):
            self.logger.debug(f"Processing raw dictionary entry #{i+1}: {dict_data}") # Log raw data for each entry
            try:
                # Convert dict data to Dictionary object
                dictionary_obj = Dictionary.from_dict(dict_data)
                dictionaries.append(dictionary_obj)
                self.logger.debug(f" Successfully parsed dictionary entry #{i+1}: ID={dictionary_obj.id}")
            except Exception as e:
                # Log the specific error AND the data that caused it
                self.logger.error(f"Error parsing dictionary entry #{i+1}: {e}", exc_info=True)
                self.logger.error(f" Failed dictionary data: {dict_data}") # Log the problematic data

        self.logger.info(f"Finished parsing. Successfully parsed {len(dictionaries)} out of {len(dict_list)} entries.")
        return dictionaries

    def get_dictionary_by_id(self, dictionary_id: str) -> Optional[Dictionary]:
        """Finds a dictionary by its ID by reading the system file."""
        all_dictionaries = self.get_all_dictionaries()
        for dct in all_dictionaries:
            if dct.id == dictionary_id:
                return dct
        self.logger.debug("Dictionary with ID %s not found in system file.", dictionary_id)
        return None

    def get_dictionary_by_name(self, name: str) -> Optional[Dictionary]:
        """Finds a dictionary by its name (case-insensitive) by reading the system file."""
        all_dictionaries = self.get_all_dictionaries()
        search_name = name.lower()
        for dct in all_dictionaries:
            if hasattr(dct, 'name') and dct.name and dct.name.lower() == search_name:
                return dct
        self.logger.debug("Dictionary with name '%s' not found in system file.", name)
        return None

    def save_dictionary(self, dictionary: Dictionary) -> bool:
        """Saves (adds or updates) a dictionary in the system dictionaries file."""
        try:
            dictionary_data = self._load_dictionary_data()
            dict_list = dictionary_data.get("dictionaries", [])
            found = False
            for i, existing_dict_data in enumerate(dict_list):
                if existing_dict_data.get('id') == dictionary.id:
                    # Update existing dictionary
                    dict_list[i] = dictionary.to_dict()
                    found = True
                    self.logger.info("Updating dictionary ID %s in system file.", dictionary.id)
                    break

            if not found:
                # Add new dictionary
                dict_list.append(dictionary.to_dict())
                self.logger.info("Adding new dictionary '%s' (ID: %s) to system file.", dictionary.name, dictionary.id)

            dictionary_data["dictionaries"] = dict_list
            return self._save_dictionary_data(dictionary_data)
        except Exception as e:
            self.logger.error(f"Error saving dictionary {dictionary.id} to system file: {e}", exc_info=True)
            return False

    def delete_dictionary(self, dictionary_id: str) -> bool:
        """Deletes a dictionary by its ID from the system dictionaries file."""
        try:
            dictionary_data = self._load_dictionary_data()
            dict_list = dictionary_data.get("dictionaries", [])
            initial_len = len(dict_list)

            # Filter out the dictionary to delete
            updated_dict_list = [dct for dct in dict_list if dct.get('id') != dictionary_id]

            if len(updated_dict_list) < initial_len:
                dictionary_data["dictionaries"] = updated_dict_list
                if self._save_dictionary_data(dictionary_data):
                    self.logger.info("Deleted dictionary ID %s from system file.", dictionary_id)
                    return True
                else:
                    self.logger.error("Failed to save system dictionary data after deleting ID %s.", dictionary_id)
                    return False # Save failed
            else:
                self.logger.warning("Attempted to delete non-existent dictionary ID %s from system file.", dictionary_id)
                return False # Dictionary not found
        except Exception as e:
            self.logger.error(f"Error deleting dictionary {dictionary_id} from system file: {e}", exc_info=True)
            return False

    def find_dictionaries_containing_class(self, class_id: str) -> List[Dictionary]:
        """Finds all dictionaries that include the given class ID."""
        associated_dictionaries = []
        all_dictionaries = self.get_all_dictionaries()
        for dictionary in all_dictionaries:
            if class_id in dictionary.class_ids:
                associated_dictionaries.append(dictionary)
        self.logger.debug("Found %d dictionaries associated with class ID %s", len(associated_dictionaries), class_id)
        return associated_dictionaries

    def get_global_class_registry_path(self) -> Path:
        """Gets the path to the global class registry file via FileManager."""
        # Ensure file_manager is initialized
        if not hasattr(self, 'file_manager') or not self.file_manager:
            logger.error("FileManager not available in DictionaryRepository.")
            # Handle error appropriately, maybe raise or return a default/error path
            # For now, raising an error might be clearest
            raise AttributeError("FileManager not initialized in DictionaryRepository")
        return self.file_manager.get_global_classes_registry_path()