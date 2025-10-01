import os
import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from ...auth.models import User
from ...storage.file_manager import FileManager

logger = logging.getLogger(__name__)

class UserRepository:
    """Repository for User domain objects."""
    
    def __init__(self, file_manager: FileManager):
        """
        Initialize the user repository.
        
        Args:
            file_manager: FileManager instance for storage operations
        """
        self.file_manager = file_manager
        self.users_dir = Path(file_manager.data_root) / "users"
        self.users_dir.mkdir(exist_ok=True, parents=True)
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
    
    def _get_user_path(self, user_id: str) -> Path:
        """Get path to user metadata file."""
        # Use same structure as FileManager: users/{user_id}/user_profile.json
        user_dir = self.users_dir / user_id
        user_dir.mkdir(exist_ok=True, parents=True)
        return user_dir / "user_profile.json"
    
    
    def _get_email_index_path(self) -> Path:
        """Get path to email index file."""
        return self.users_dir / "email_index.json"
    
    def _load_index(self, index_path: Path) -> Dict[str, str]:
        """Load an index file or create empty one if doesn't exist."""
        if not index_path.exists():
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
            return {}
        
        try:
            with open(index_path, 'r') as f:
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading index {index_path}: {e}")
            return {}
    
    def _save_index(self, index: Dict[str, str], index_path: Path) -> bool:
        """Save an index file."""
        try:
            with open(index_path, 'w') as f:
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                json.dump(index, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving index {index_path}: {e}")
            return False
    
    def save(self, user: User) -> bool:
        """
        Save a user to the repository, handling index updates for both
        new users and updates to existing users (username/email changes).

        - Usernames are stored and looked up case-sensitively.
        - Emails are stored and looked up case-insensitively (using lowercase).

        Args:
            user: User object to save

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Attempting to save user ID: {user.id}, Username: {user.username}, Email: {user.email}")
        try:
            user_path = self._get_user_path(user.id)
            old_user_data = {}
            user_existed = user_path.exists()

            # --- Step 1: Load old data if user exists (to check for changes) ---
            if user_existed:
                try:
                    # Use file_manager if available, otherwise direct open
                    if hasattr(self.file_manager, 'load_json'):
                        old_user_data = self.file_manager.load_json(user_path)
                    else: # Fallback
                        with open(user_path, 'r') as f:
                            old_user_data = json.load(f)
                    if not old_user_data: # Handle empty file case
                        old_user_data = {}
                        logger.warning(f"Existing user file was empty or failed to load: {user_path}")
                except Exception as load_err:
                    logger.warning(f"Could not load existing user data for {user.id} during save, index cleanup might be incomplete: {load_err}")
                    # Proceed without old data, might leave stale index entries if username/email changed

            # --- Step 2: Load current indices ---
            # Username index no longer needed since username IS the user ID
            
            email_index_path = self._get_email_index_path()
            email_index = self._load_index(email_index_path)

            # --- Step 3: Prepare new and old values for index comparison ---
            old_username = old_user_data.get('username')
            old_email_lower = old_user_data.get('email', '').lower()

            new_username = user.username # Case-sensitive
            new_email_lower = user.email.lower() # Case-insensitive (lowercase)

            # --- Step 4: Username Index No Longer Needed ---
            # Since username IS the ID now, we don't need a username index
            # The username index file can be kept empty for backward compatibility
            # or removed entirely in a future update

            # --- Step 5: Update Email Index (Case-Insensitive - Lowercase Key) ---
            email_changed = user_existed and old_email_lower and old_email_lower != new_email_lower
            if email_changed:
                 # Remove old email entry if it exists and changed
                 if old_email_lower in email_index:
                     logger.debug(f"Removing old email index entry: {old_email_lower}")
                     del email_index[old_email_lower]
                 else:
                     logger.warning(f"Old email '{old_email_lower}' not found in index during update for user {user.id}")

            # Add/update the new email entry if it's new or changed
            if not user_existed or email_changed or email_index.get(new_email_lower) != user.id:
                 logger.debug(f"Adding/Updating email index entry: {new_email_lower} -> {user.id}")
                 email_index[new_email_lower] = user.id

            # --- Step 6: Save updated email index only ---
            # We no longer need to save username index since username IS the ID
            email_save_ok = self._save_index(email_index, email_index_path)

            if not email_save_ok:
                 logger.error(f"Failed to save email index for user {user.id}. Data inconsistency possible.")
                 return False

            # --- Step 7: Save main user data file (using FileManager preferably) ---
            user_data_to_save = user.to_dict(include_private=True)
            logger.debug(f"Saving user data to {user_path}")
            if hasattr(self.file_manager, 'save_json'):
                save_main_ok = self.file_manager.save_json(user_data_to_save, user_path)
            else: # Fallback
                 with open(user_path, 'w') as f:
                     json.dump(user_data_to_save, f, indent=2)
                 save_main_ok = True # Assume success if no exception

            if not save_main_ok:
                 logger.error(f"Failed to save main user data file for {user.id} after indices were updated.")
                 # Potentially try to revert index changes here? Complex.
                 return False

            logger.info(f"Successfully saved user {user.id} (Username: {user.username})")
            return True

        except Exception as e:
            logger.error(f"Error saving user {user.id}: {e}", exc_info=True) # Log full traceback
            return False
    
    # DB-OPERATION: read user
    def get_by_id(self, user_id: str) -> Optional[User]:
        """
        Get a user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            User if found, None otherwise
        """
        try:
            user_path = self._get_user_path(user_id)
            if not user_path.exists():
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                return None
            
            with open(user_path, 'r') as f:
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                user_data = json.load(f)
            
            return User.from_dict(user_data)
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None
    
    # DB-OPERATION: read user
    def get_by_username(self, username: str) -> Optional[User]:
        """
        Get a user by username.
        Since username IS the user ID now, this is the same as get_by_id.
        
        Args:
            username: Username (case-sensitive)
            
        Returns:
            User if found, None otherwise
        """
        # Username is now the ID, so just call get_by_id
        return self.get_by_id(username)
    
    # DB-OPERATION: read user
    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get a user by email.
        
        Args:
            email: Email address (case-insensitive)
            
        Returns:
            User if found, None otherwise
        """
        try:
            email_index_path = self._get_email_index_path()
            email_index = self._load_index(email_index_path)
            user_id = email_index.get(email.lower())
            
            if not user_id:
                return None
            
            return self.get_by_id(user_id)
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return None
    
    # DB-OPERATION: read user
    def get_by_token(self, token: str) -> Optional[User]:
        """
        Get a user by API token.
        
        Args:
            token: API token
            
        Returns:
            User if found, None otherwise
        """
        try:
            # This is inefficient but simple. In a real app, we'd have a token index.
            for user_file in self.users_dir.glob("*.json"):
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                if user_file.name.endswith("_index.json"):
                    continue
                
                try:
                    with open(user_file, 'r') as f:
                    # STORAGE-OPERATION: Will be replaced by DatabaseManager
                        user_data = json.load(f)
                    
                    if user_data.get('api_token') == token:
                        return User.from_dict(user_data)
                except:
                    continue
            
            return None
        except Exception as e:
            logger.error(f"Error getting user by token: {e}")
            return None
    
    # DB-OPERATION: read user
    def list_users(self) -> List[User]:
        """
        List all users.
        
        Returns:
            List of users
        """
        users = []
        
        try:
            for user_file in self.users_dir.glob("*.json"):
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                if user_file.name.endswith("_index.json"):
                    continue
                
                try:
                    with open(user_file, 'r') as f:
                    # STORAGE-OPERATION: Will be replaced by DatabaseManager
                        user_data = json.load(f)
                    
                    users.append(User.from_dict(user_data))
                except:
                    continue
            
            return users
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return []
    
    def delete(self, user_id: str) -> bool:
        """
        Delete a user.
        
        Args:
            user_id: User ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get user first to update indices
            user = self.get_by_id(user_id)
            if not user:
                return False
            
            # Delete user file
            user_path = self._get_user_path(user_id)
            if user_path.exists():
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                user_path.unlink()
                # STORAGE-OPERATION: Will be replaced by DatabaseManager
            
            # Username index no longer needed since username IS the ID
            
            # Update email index (Case-Insensitive Key)
            email_index_path = self._get_email_index_path()
            email_index = self._load_index(email_index_path)
            if user.email.lower() in email_index: # <-- Use lower()
                del email_index[user.email.lower()] # <-- Use lower()
                self._save_index(email_index, email_index_path)
            
            return True
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False

    def username_exists(self, username: str) -> bool:
        """
        Check if a username already exists.
        Since username IS the user ID now, we just check if the user file exists.
        
        Args:
            username: Username to check
            
        Returns:
            True if username exists, False otherwise
        """
        try:
            # Username is the ID, so check if user file exists
            user_path = self._get_user_path(username)
            return user_path.exists()
        except Exception as e:
            logger.error(f"Error checking username existence {username}: {e}")
            return False
    
    def email_exists(self, email: str) -> bool:
        """
        Check if an email already exists.
        
        Args:
            email: Email to check
            
        Returns:
            True if email exists, False otherwise
        """
        try:
            email_index_path = self._get_email_index_path()
            email_index = self._load_index(email_index_path)
            return email.lower() in email_index
        except Exception as e:
            logger.error(f"Error checking email existence {email}: {e}")
            return False
            
    def verify_password_reset_token(self, token: str) -> Optional[str]:
        """
        Verify a password reset token and return the associated user ID if valid.
        
        Args:
            token: Reset token
            
        Returns:
            User ID if token is valid, None otherwise
        """
        import time
        
        # Iterate through all users to find the token
        # This is inefficient but simple for now
        try:
            current_time = int(time.time())
            
            for user_file in self.users_dir.glob("*.json"):
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                if user_file.name.endswith("_index.json"):
                    continue
                
                try:
                    with open(user_file, 'r') as f:
                    # STORAGE-OPERATION: Will be replaced by DatabaseManager
                        user_data = json.load(f)
                    
                    # Check if user has reset tokens
                    preferences = user_data.get('preferences', {})
                    reset_tokens = preferences.get('reset_tokens', {})
                    
                    # Check if this token exists and is not expired
                    if token in reset_tokens:
                        expiration = reset_tokens[token]
                        
                        if expiration > current_time:
                            # Token is valid, return user ID
                            user_id = user_data['id']
                            
                            # Load user to remove the used token
                            user = self.get_by_id(user_id)
                            if user and 'reset_tokens' in user.preferences and token in user.preferences['reset_tokens']:
                                # Remove the used token (one-time use)
                                del user.preferences['reset_tokens'][token]
                                self.save(user)
                            
                            return user_id
                except Exception as e:
                    logger.error(f"Error checking reset token in user file {user_file}: {e}")
                    continue
            
            return None
        except Exception as e:
            logger.error(f"Error verifying password reset token: {e}")
            return None
