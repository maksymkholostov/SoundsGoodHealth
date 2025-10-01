import logging
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from pathlib import Path
from datetime import datetime # Import datetime

from backend.app.core.models.dictionary import Dictionary, SoundClass
from backend.app.core.repositories.dictionary_repo import DictionaryRepository
# REMOVED: from backend.app.services.recording_service import RecordingService

# Use for type hinting only to avoid circular import at runtime
if TYPE_CHECKING:
    from backend.app.services.recording_service import RecordingService


class DictionaryService:
    """
    Service for dictionary management.
    
    Provides business logic for working with dictionaries and sound classes.
    """
    
    def __init__(self, dictionary_repo: DictionaryRepository, recording_service: Optional['RecordingService'] = None):
        """
        Initialize the dictionary service.
        
        Args:
            dictionary_repo: Repository for dictionary operations
            recording_service: Service for recording operations (optional, can be set later)
        """
        self.dictionary_repo = dictionary_repo
        self.recording_service = recording_service
        self.logger = logging.getLogger(__name__)
    
    def set_recording_service(self, recording_service: 'RecordingService'):
        """Set the recording service after initialization."""
        if not self.recording_service:
            self.recording_service = recording_service
            self.logger.info("RecordingService successfully set for DictionaryService.")
        else:
            self.logger.warning("Attempted to reset recording_service when it was already set.")
    
    # DB-OPERATION: create user
    def create_dictionary(self, name: str, user_id: str, description: Optional[str] = None) -> Dictionary:
        """
        Create a new dictionary.
        
        Args:
            name: Name of the dictionary
            user_id: ID of the user creating the dictionary
            description: Optional description
            
        Returns:
            Created Dictionary
        """
        dictionary = Dictionary(
            name=name,
            creator_user_id=user_id,
            description=description
        )
        
        if self.dictionary_repo.save_dictionary(dictionary):
            self.logger.info(f"Created dictionary {dictionary.id} for user {user_id}")
        else:
            self.logger.error(f"Failed to save dictionary {dictionary.id}")
        
        return dictionary
    
    # DB-OPERATION: read user
    def get_dictionary(self, user_id: str, dict_id: str) -> Optional[Dictionary]:
        """
        Get a dictionary by ID, ensuring the user has permission.
        
        Args:
            user_id: User ID requesting access.
            dict_id: Dictionary ID.
            
        Returns:
            Dictionary if found and user has access, None otherwise.
        """
        # Use V10 repo method to get dictionary by ID
        dictionary = self.dictionary_repo.get_dictionary_by_id(dict_id)
        
        if not dictionary:
            self.logger.warning(f"Dictionary {dict_id} not found.")
            return None

        # Universal access policy: all users can access any dictionary
        # Keep creator_user_id for auditing/ownership display
        # No ownership restriction enforced here
        
        self.logger.debug(f"User {user_id} granted access to dictionary {dict_id}.")
        return dictionary
    
    # DB-OPERATION: read user
    def get_all_dictionaries(self, user_id: Optional[str] = None) -> List[Dict]:
        """
        Gets all dictionaries.
        NOTE: Ignores user_id argument if provided (for compatibility with potential stale calls).

        Returns:
            List of dictionary data (as dictionaries).
        """
        try:
            self.logger.info("Service calling repository's get_all_dictionaries...")
            all_dictionary_objects = self.dictionary_repo.get_all_dictionaries()
            self.logger.info(f"Repository returned {len(all_dictionary_objects)} dictionary objects.")

            # Convert to dict format for consistent return type
            result = []
            for d_obj in all_dictionary_objects:
                 if hasattr(d_obj, 'to_dict'):
                     result.append(d_obj.to_dict())
                 elif isinstance(d_obj, dict):
                      self.logger.warning("Repository returned a dict instead of an object.")
                      result.append(d_obj)
                 else:
                      self.logger.warning(f"Found item in repository result that is not a Dictionary object or dict: {type(d_obj)}")

            self.logger.info(f"Service returning {len(result)} dictionaries as dicts.")
            return result

        except Exception as e:
            self.logger.error(f"Error getting all dictionaries from service: {e}", exc_info=True)
            return [] # Return empty list on error
    
    # DB-OPERATION: update dictionary
    def update_dictionary(self, dictionary: Dictionary) -> bool:
        """
        Update a dictionary.
        
        Args:
            dictionary: Dictionary to update
            
        Returns:
            True if updated successfully, False otherwise
        """
        success = self.dictionary_repo.save_dictionary(dictionary)
        
        if success:
            self.logger.info(f"Updated dictionary {dictionary.id}")
        else:
            self.logger.error(f"Failed to update dictionary {dictionary.id}")
        
        return success
    
    # DB-OPERATION: delete user
    def delete_dictionary(self, user_id: str, dict_id: str) -> bool:
        """
        Delete a dictionary, ensuring the user has permission.
        
        Args:
            user_id: User ID requesting deletion.
            dict_id: Dictionary ID to delete.
            
        Returns:
            True if deleted successfully, False otherwise.
        """
        # First, check if dictionary exists and user has permission
        dictionary = self.dictionary_repo.get_dictionary_by_id(dict_id)
        if not dictionary:
            self.logger.warning(f"Attempt to delete non-existent dictionary {dict_id} by user {user_id}.")
            return False # Not found

        # Universal access policy: allow any user to delete
        # Keep creator_user_id metadata but do not restrict deletion by owner

        # If checks pass, call the V10 repository delete method
        success = self.dictionary_repo.delete_dictionary(dict_id)
        
        if success:
            self.logger.info(f"Deleted dictionary {dict_id} (requested by user {user_id}).")
            # Consider triggering stats update here if not done by caller
        else:
            self.logger.error(f"Repository failed to delete dictionary {dict_id}.")
        
        return success
    
    def add_sound_class(self, user_id: str, dictionary_id: str, class_name: str, description: str = None) -> Tuple[bool, Optional[SoundClass]]:
        """
        Add a sound class to a dictionary.
        (Assumes permission check was done by caller based on user_id)
        
        Args:
            user_id: User ID (owner of dict or admin acting as owner)
            dictionary_id: Dictionary ID
            class_name: Name of the class
            description: Optional description
            
        Returns:
            Tuple of (success, SoundClass)
        """
        try:
            # Get the dictionary using the V10 method (no user check needed here)
            dictionary = self.dictionary_repo.get_dictionary_by_id(dictionary_id)
            if not dictionary:
                self.logger.warning(f"Dictionary {dictionary_id} not found when trying to add class.")
                return False, None
            
            # Find or create the global class
            # This method handles checking name and saving to registry if new
            # Pass user_id for tracking who creates new classes
            sound_class = self.find_or_create_global_class(class_name, description, user_id)
            if not sound_class:
                # find_or_create raises Exception on save failure, so this case shouldn't be hit
                # unless there's another issue. Log just in case.
                self.logger.error(f"Failed to find or create global class '{class_name}'") 
                return False, None

            # Check if class ID is already in the dictionary
            if sound_class.id in dictionary.class_ids:
                 self.logger.info(f"Class '{class_name}' (ID: {sound_class.id}) already exists in dictionary {dictionary_id}.")
                 return True, sound_class # Indicate success, class already present

            # Add the class ID to the dictionary object
            dictionary.add_class(sound_class.id)
            dictionary.updated_at = datetime.utcnow() # Update timestamp
            
            # Save the dictionary using the V10 method
            success = self.dictionary_repo.save_dictionary(dictionary)
            if not success:
                self.logger.error(f"Failed to save dictionary {dictionary_id} after adding new class {class_name}")
                return False, None
            
            self.logger.info(f"Added sound class '{class_name}' (ID: {sound_class.id}) to dictionary {dictionary_id}")
            return True, sound_class
        
        except Exception as e:
            self.logger.error(f"Error adding sound class '{class_name}' to dictionary {dictionary_id}: {str(e)}", exc_info=True)
            return False, None
    
    # DB-OPERATION: delete user
    def remove_sound_class(self, user_id: str, dict_id: str, class_id: str) -> bool:
        """
        Remove a sound class association from a dictionary.
        
        Args:
            user_id: User ID requesting the removal.
            dict_id: Dictionary ID.
            class_id: ID of the sound class to remove.
            
        Returns:
            True if removed successfully, False otherwise.
        """
        # Get dictionary using V10 method
        dictionary = self.dictionary_repo.get_dictionary_by_id(dict_id)
        
        if not dictionary:
            self.logger.warning(f"Dictionary {dict_id} not found when attempting to remove class {class_id}.")
            return False

        # Universal access policy: allow any user to modify dictionaries
        
        # Remove the class ID
        if class_id in dictionary.class_ids:
            dictionary.class_ids.remove(class_id)
            dictionary.updated_at = datetime.utcnow()
            
            # Save the updated dictionary using V10 method
            success = self.dictionary_repo.save_dictionary(dictionary)
            
            if success:
                self.logger.info(f"Removed sound class {class_id} from dictionary {dict_id}")
                return True
            else:
                self.logger.error(f"Failed to save dictionary {dict_id} after removing sound class {class_id}")
                return False
        else:
            self.logger.warning(f"Sound class {class_id} not found in dictionary {dict_id}")
            return False
    
    # DB-OPERATION: read user
    def get_sound_class(self, user_id: str, dict_id: str, class_id: str) -> Optional[SoundClass]:
        """
        Get a sound class associated with a specific dictionary, checking permissions.
        
        Args:
            user_id: User ID requesting access.
            dict_id: Dictionary ID.
            class_id: ID of the sound class to retrieve.
            
        Returns:
            SoundClass if found in the dictionary and user has access, None otherwise.
        """
        # Get the dictionary first, checking permissions
        dictionary = self.get_dictionary(user_id, dict_id)
        
        if not dictionary:
            # get_dictionary already logs permission/not found issues
            return None
        
        # Check if the class ID is actually part of this dictionary
        if class_id not in dictionary.class_ids:
             self.logger.warning(f"Class {class_id} is not associated with dictionary {dict_id}.")
             return None

        # If associated, get the global class definition
        # (We already know user can access the dictionary containing it)
        sound_class = self.dictionary_repo.get_class_by_id(class_id)
        if not sound_class:
             # This would be unusual - class ID in dict but not in global registry
             self.logger.error(f"Data inconsistency: Class ID {class_id} found in dictionary {dict_id} but not in global registry!")
             return None
             
        return sound_class

    def dictionary_name_exists(self, user_id: str, name: str, exclude_id: Optional[str] = None) -> bool:
        """Checks if a dictionary with the given name exists for the user, optionally excluding one ID."""
        try:
            # Use the corrected service method to get ALL dictionaries first
            all_dictionaries = self.get_all_dictionaries() # This now correctly calls the repo

            # Filter for the specific user AFTER getting all
            user_dictionaries = []
            for item in all_dictionaries:
                 # Service get_all_dictionaries returns dicts now
                 owner_id = item.get('creator_user_id')
                 if owner_id and str(owner_id) == str(user_id):
                      user_dictionaries.append(item)

            search_name = name.lower()
            for dic_data in user_dictionaries: # Iterate through the filtered list
                if dic_data.get('name','').lower() == search_name:
                    if exclude_id and dic_data.get('id') == exclude_id:
                        continue
                    return True
            return False
        except Exception as e:
             self.logger.error(f"Error checking dictionary name '{name}' for user {user_id}: {e}", exc_info=True)
             # Consider returning False instead of True on error for safety
             return False # Return False if check fails

    def _create_global_class(self, user_id: str, class_name: str, description: str = None) -> Optional[SoundClass]:
        """
        Create a global sound class without attaching it to a dictionary.
        
        Args:
            user_id: User ID
            class_name: Name of the class
            description: Optional description
            
        Returns:
            Created SoundClass object or None if failed
        """
        try:
            # First, check if a class with this name already exists
            sound_class = self._find_global_class(user_id, class_name)
            if sound_class:
                self.logger.debug(f"Class {class_name} already exists globally for user {user_id}")
                return sound_class
            
            # Create new sound class
            sound_class = SoundClass(
                name=class_name,
                description=description
            )
            
            # Create a registry file if it doesn't exist
            registry_file = self._get_global_class_registry_path(user_id)
            registry_dir = registry_file.parent
            registry_dir.mkdir(exist_ok=True, parents=True)
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            
            # Load existing registry or create a new one
            if registry_file.exists():
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                registry = self.dictionary_repo.file_manager.load_json(registry_file)
                # STORAGE-OPERATION: Will be replaced by DatabaseManager
                if not registry:
                    registry = {"classes": []}
            else:
                registry = {"classes": []}
            
            # Add class to registry
            registry["classes"].append(sound_class.to_dict())
            
            # Save registry
            success = self.dictionary_repo.file_manager.save_json(registry, registry_file)
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            if success:
                self.logger.info(f"Created global sound class {sound_class.id} ({sound_class.name}) for user {user_id}")
                return sound_class
            else:
                self.logger.error(f"Failed to save global class registry for user {user_id}")
                return None
        
        except Exception as e:
            self.logger.error(f"Error creating global sound class: {str(e)}")
            return None

    def _find_global_class(self, user_id: str, class_name: str) -> Optional[SoundClass]:
        """
        Find a sound class in the global registry by name (using the repository).

        Args:
            user_id: User ID (kept for backward compatibility, not used).
            class_name: Name of the class to find.

        Returns:
            SoundClass if found, None otherwise.
        """
        try:
            # Use repository method to find class by name
            return self.dictionary_repo.get_class_by_name(class_name)
        except Exception as e:
            self.logger.error(f"Error finding global class '{class_name}': {e}", exc_info=True)
            return None

    def _get_global_class_registry_path(self, user_id: str) -> Path:
        """Get the path to the global class registry file (via repository)."""
        # Delegate path finding to repository
        return self.dictionary_repo.get_global_class_registry_path()
        
    def get_all_unique_class_names(self) -> List[Dict[str, Any]]:
        """
        Get a list of all unique global sound classes, formatted as simple dictionaries.

        Returns:
            List of unique classes, each represented as a dictionary {'id': str, 'name': str}.
        """
        try:
            self.logger.info("Retrieving all unique global classes from repository...")
            all_classes = self.dictionary_repo.get_all_classes()
            # Convert to simple dict format for API/frontend if needed
            unique_classes_list = [
                {'id': cls.id, 'name': cls.name} for cls in all_classes
            ]
            self.logger.info(f"Found {len(unique_classes_list)} unique classes.")
            return unique_classes_list
        except Exception as e:
            self.logger.error(f"Error retrieving unique classes: {e}", exc_info=True)
            return []

    def get_all_classes(self) -> List[SoundClass]:
        """Gets a list of all unique global class definition objects."""
        self.logger.debug("Getting all unique global class objects via repository.")
        return self.dictionary_repo.get_all_classes()

    def find_or_create_global_class(self, name: str, description: Optional[str] = None, creator_uid: Optional[str] = None) -> SoundClass:
        """
        Finds a class by name (case-insensitive) in the global registry.
        If not found, creates and saves a new global class.

        Args:
            name: The name of the class to find or create.
            description: Optional description if creating a new class.

        Returns:
            The found or newly created SoundClass object.

        Raises:
            Exception: If saving the new class fails.
        """
        self.logger.debug("Attempting to find or create global class: '%s'", name)
        existing_class = self.dictionary_repo.get_class_by_name(name)
        if existing_class:
            self.logger.debug("Found existing global class '%s' (ID: %s)", name, existing_class.id)
            return existing_class
        else:
            self.logger.info("Global class '%s' not found. Creating new one.", name)
            # Normalize empty string description to None
            if description == "":
                description = None
            new_class = SoundClass(name=name, description=description)
            success = self.dictionary_repo.save_class(new_class, creator_uid)
            if success:
                self.logger.info("Successfully created and saved new global class '%s' (ID: %s)", new_class.name, new_class.id)
                return new_class
            else:
                self.logger.error("Failed to save new global class '%s'", name)
                raise Exception(f"Failed to save new global class '{name}'") 

    def get_global_class_by_id(self, class_id: str) -> Optional[SoundClass]:
        """Gets a global class definition by its unique ID."""
        self.logger.debug("Getting global class by ID: %s", class_id)
        return self.dictionary_repo.get_class_by_id(class_id)

    def get_dictionary_by_id(self, dictionary_id: str) -> Optional[Dictionary]:
        """
        Get a dictionary solely by its ID, irrespective of user.
        
        Args:
            dictionary_id: The ID of the dictionary to retrieve.
            
        Returns:
            Dictionary if found, None otherwise.
        """
        self.logger.debug(f"Attempting to get dictionary by ID: {dictionary_id}")
        try:
            # Use the repository method that finds by ID from the system file
            dictionary = self.dictionary_repo.get_dictionary_by_id(dictionary_id)
            if not dictionary:
                self.logger.warning(f"Dictionary with ID {dictionary_id} not found in repository.")
                return None
            self.logger.debug(f"Found dictionary {dictionary_id}")
            return dictionary
        except Exception as e:
            self.logger.error(f"Error getting dictionary by ID {dictionary_id}: {e}", exc_info=True)
            return None

    def delete_global_class(self, class_name: str, requesting_user_id: str) -> Tuple[bool, str]:
        """
        Deletes a global sound class definition, only if it meets safety criteria:
        1. It's not used by any dictionary.
        2. It has no associated sound files (raw, pending, gold, augmented).

        Args:
            class_name: The name of the class to delete.
            requesting_user_id: The ID of the user attempting the deletion (for logging/future permissions).

        Returns:
            Tuple[bool, str]: (success status, message)
        """
        self.logger.info(f"Attempting deletion of global class '{class_name}' by user {requesting_user_id}")

        # 1. Find the class by name to get its ID
        sound_class = self.dictionary_repo.get_class_by_name(class_name)
        if not sound_class:
            msg = f"Class '{class_name}' not found."
            self.logger.warning(msg)
            return False, msg
        
        class_id = sound_class.id
        self.logger.debug(f"Found class '{class_name}' with ID: {class_id}")

        # 2. Check if any dictionaries contain this class
        try:
            associated_dictionaries = self.dictionary_repo.find_dictionaries_containing_class(class_id)
            if associated_dictionaries:
                dict_names = [d.name for d in associated_dictionaries]
                msg = f"Cannot delete class '{class_name}' because it is used by dictionaries: {', '.join(dict_names)}"
                self.logger.warning(msg)
                return False, msg
        except Exception as e:
            msg = f"Error checking dictionary associations for class '{class_name}': {e}"
            self.logger.error(msg, exc_info=True)
            return False, msg # Fail safe

        # 3. Check if any sound files exist for this class
        if not self.recording_service:
             msg = f"RecordingService not available. Cannot check for associated sounds for class '{class_name}'."
             self.logger.error(msg)
             # Fail safe: Do not allow deletion if we cannot check sounds
             return False, msg
             
        try:
            sounds_exist = self.recording_service.check_if_sounds_exist_for_class(class_name)
            if sounds_exist:
                msg = f"Cannot delete class '{class_name}' because associated sound files exist."
                self.logger.warning(msg)
                return False, msg
        except Exception as e:
            msg = f"Error checking sound existence for class '{class_name}': {e}"
            self.logger.error(msg, exc_info=True)
            return False, msg # Fail safe

        # 4. If checks pass, proceed with deletion from the repository
        self.logger.info(f"Class '{class_name}' passed deletion checks. Proceeding with deletion.")
        try:
            deleted = self.dictionary_repo.delete_class(class_id)
            if deleted:
                msg = f"Global class '{class_name}' deleted successfully."
                self.logger.info(msg)
                return True, msg
            else:
                # This might happen if the class was deleted between check and delete (race condition) or repo error
                msg = f"Repository failed to delete class '{class_name}' (ID: {class_id}). It might have been deleted already or a repository error occurred."
                self.logger.warning(msg)
                return False, msg
        except Exception as e:
             msg = f"Unexpected error during repository deletion for class '{class_name}': {e}"
             self.logger.error(msg, exc_info=True)
             return False, msg

    def remove_class_from_dictionary(self, user_id: str, dictionary_id: str, class_id: str) -> bool:
        """
        Removes the association of a global class from a specific dictionary.
        Does not delete the global class itself.

        Args:
            user_id: ID of the user making the request (for permission check).
            dictionary_id: ID of the dictionary to modify.
            class_id: ID of the class to remove from the dictionary.

        Returns:
            True if the class was successfully removed from the dictionary, False otherwise.
        """
        self.logger.info(f"User {user_id} attempting to remove class {class_id} from dictionary {dictionary_id}")
        # Get the dictionary, ensuring user has access (if repo method enforces it)
        # Using get_dictionary_by_id which doesn't check user, so check owner here.
        dictionary = self.dictionary_repo.get_dictionary_by_id(dictionary_id)

        if not dictionary:
            self.logger.warning(f"Dictionary {dictionary_id} not found.")
            return False
        
        # Universal access policy: allow any user to modify dictionaries

        # Attempt to remove the class ID from the dictionary object
        if class_id in dictionary.class_ids:
            dictionary.class_ids.remove(class_id)
            # Update the timestamp
            dictionary.updated_at = datetime.utcnow()
            
            # Save the updated dictionary back to the repository
            success = self.dictionary_repo.save_dictionary(dictionary)
            if success:
                self.logger.info(f"Successfully removed class {class_id} from dictionary {dictionary_id}")
                return True
            else:
                self.logger.error(f"Failed to save dictionary {dictionary_id} after removing class {class_id}")
                # Attempt to add the class back if save failed? Or just report error.
                return False
        else:
            self.logger.warning(f"Class {class_id} was not found in dictionary {dictionary_id}. No action taken.")
            return False # Indicate class wasn't present

    def get_class_by_name(self, name: str) -> Optional[SoundClass]:
        """Gets a global class definition by its name (case-insensitive)."""
        self.logger.debug(f"Getting global class by name: {name}")
        return self.dictionary_repo.get_class_by_name(name)