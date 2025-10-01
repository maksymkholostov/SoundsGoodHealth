import os
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.app.storage.file_manager import FileManager
from backend.app.core.repositories.dictionary_repo import DictionaryRepository
from backend.app.core.repositories.user_repo import UserRepository
from backend.app.core.repositories.recording_repo import RecordingRepository


class SystemService:
    """
    Service for system-wide operations like reset and backup.
    """
    
    RESET_PASSCODE = "3141"  # Current passcode for system reset
    
    def __init__(
        self,
        file_manager: FileManager,
        dictionary_repo: DictionaryRepository,
        user_repo: UserRepository,
        recording_repo: RecordingRepository
    ):
        """
        Initialize the system service.
        
        Args:
            file_manager: FileManager instance for file operations
            dictionary_repo: DictionaryRepository for dictionary operations
            user_repo: UserRepository for user operations
            recording_repo: RecordingRepository for recording operations
        """
        self.file_manager = file_manager
        self.dictionary_repo = dictionary_repo
        self.user_repo = user_repo
        self.recording_repo = recording_repo
        self.logger = logging.getLogger(__name__)
    
    def reset_system(
        self,
        passcode: str,
        reset_dictionaries: bool = True,
        reset_classes: bool = True,
        reset_stats: bool = True,
        reset_recordings: bool = True,
        preserve_user_accounts: bool = True,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Reset system data files to initial state.
        
        Args:
            passcode: Security passcode to confirm reset (must match RESET_PASSCODE)
            reset_dictionaries: Whether to reset dictionary data
            reset_classes: Whether to reset class registry
            reset_stats: Whether to reset stats data
            reset_recordings: Whether to delete all recordings
            preserve_user_accounts: Whether to preserve user accounts
            dry_run: If True, only report what would be reset without making changes
            
        Returns:
            Dictionary with reset status and actions taken
        """
        # Verify passcode
        if passcode != self.RESET_PASSCODE:
            self.logger.warning("System reset attempted with incorrect passcode")
            return {
                "success": False,
                "error": "Incorrect passcode",
                "actions": []
            }
        
        if dry_run:
            self.logger.info("DRY RUN: System reset simulation started")
        else:
            self.logger.warning("ACTUAL RESET: System reset started")
        
        actions_taken = []
        data_root = self.file_manager.get_data_root()
        
        try:
            # 1. Reset dictionary data if requested
            if reset_dictionaries:
                dict_path = data_root / "dictionaries" / "system_dictionaries.json"
                if dict_path.exists():
                    if not dry_run:
                        # Initialize with empty data
                        empty_dicts = []
                        self.file_manager.save_json(empty_dicts, dict_path)
                    actions_taken.append(f"Reset dictionaries at {dict_path}")
            
            # 2. Reset class registry if requested
            if reset_classes:
                class_registry_path = data_root / "classes" / "global_registry.json"
                if class_registry_path.exists():
                    if not dry_run:
                        # Initialize with empty data
                        empty_classes = []
                        self.file_manager.save_json(empty_classes, class_registry_path)
                    actions_taken.append(f"Reset class registry at {class_registry_path}")
            
            # 3. Reset statistics if requested
            if reset_stats:
                stats_path = data_root / "metadata" / "stats" / "global_stats.json"
                if stats_path.exists():
                    if not dry_run:
                        # Initialize with zeroed stats
                        empty_stats = {
                            'models': 0, 
                            'classes': 0, 
                            'dictionaries': 0,
                            'original_recordings': 0,
                            'augmented_recordings': 0,
                            'pending_recordings': 0,
                            'total_recordings': 0
                        }
                        stats_path.parent.mkdir(parents=True, exist_ok=True)
                        self.file_manager.save_json(empty_stats, stats_path)
                    actions_taken.append(f"Reset statistics at {stats_path}")
            
            # 4. Reset recordings if requested
            if reset_recordings:
                sounds_dir = data_root / "sounds"
                if sounds_dir.exists():
                    if not dry_run:
                        # Create backup of recordings before deletion
                        backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                        backup_dir = data_root / "backups" / f"sounds_backup_{backup_time}"
                        backup_dir.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Copy sounds dir to backup
                        try:
                            shutil.copytree(sounds_dir, backup_dir)
                            actions_taken.append(f"Created backup of sounds at {backup_dir}")
                        except Exception as backup_err:
                            self.logger.error(f"Failed to create backup: {backup_err}")
                            actions_taken.append(f"WARNING: Failed to create backup of sounds")
                        
                        # Delete all sound files
                        try:
                            shutil.rmtree(sounds_dir)
                            sounds_dir.mkdir(parents=True, exist_ok=True)
                            actions_taken.append(f"Deleted all recordings from {sounds_dir}")
                        except Exception as del_err:
                            self.logger.error(f"Failed to delete sounds directory: {del_err}")
                            actions_taken.append(f"WARNING: Failed to delete recordings")
                    else:
                        actions_taken.append(f"Would delete all recordings from {sounds_dir}")
            
            # 5. Handle user accounts based on preference
            if not preserve_user_accounts:
                users_dir = data_root / "users"
                if users_dir.exists():
                    if not dry_run:
                        # Create backup of user data before deletion
                        backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                        users_backup_dir = data_root / "backups" / f"users_backup_{backup_time}"
                        users_backup_dir.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Copy users dir to backup
                        try:
                            shutil.copytree(users_dir, users_backup_dir)
                            actions_taken.append(f"Created backup of users at {users_backup_dir}")
                        except Exception as backup_err:
                            self.logger.error(f"Failed to create user backup: {backup_err}")
                        
                        # Initialize empty user indices
                        try:
                            email_index_path = users_dir / "email_index.json"
                            # username_index.json no longer needed since username IS the ID
                            
                            # Create empty indices
                            self.file_manager.save_json({}, email_index_path)
                            # self.file_manager.save_json({}, username_index_path)  # No longer needed
                            
                            # Delete all user files (keeping directory structure)
                            for user_file in users_dir.glob("*.json"):
                                if user_file.name not in ["email_index.json"]:
                                    user_file.unlink()
                            
                            actions_taken.append(f"Reset user accounts (deleted all users)")
                        except Exception as user_err:
                            self.logger.error(f"Failed to reset user accounts: {user_err}")
                    else:
                        actions_taken.append(f"Would reset all user accounts")
            
            # Log completion
            if dry_run:
                self.logger.info(f"DRY RUN: System reset simulation completed. {len(actions_taken)} actions would be taken.")
            else:
                self.logger.warning(f"ACTUAL RESET: System reset completed. {len(actions_taken)} actions taken.")
            
            return {
                "success": True,
                "dry_run": dry_run,
                "actions_taken": actions_taken,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error during system reset: {e}")
            return {
                "success": False,
                "error": str(e),
                "actions_taken": actions_taken,
                "timestamp": datetime.now().isoformat()
            } 