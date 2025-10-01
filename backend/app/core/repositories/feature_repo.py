import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from datetime import datetime

from backend.app.core.models.feature import FeatureSet, FeatureExtraction
from backend.app.storage.file_manager import FileManager


class FeatureRepository:
    """
    Repository for Feature domain objects.
    
    Handles persistence of feature sets and feature extractions to the file system.
    """
    
    def __init__(self, file_manager: FileManager):
        """
        Initialize the feature repository.
        
        Args:
            file_manager: FileManager instance for storage operations
        """
        self.file_manager = file_manager
        self.logger = logging.getLogger(__name__)
        
        # Create feature metadata directories if they don't exist
        self.feature_sets_dir = Path(self.file_manager.data_root) / 'metadata' / 'feature_sets'
        self.feature_sets_dir.mkdir(exist_ok=True, parents=True)
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
        
        self.feature_extractions_dir = Path(self.file_manager.data_root) / 'metadata' / 'feature_extractions'
        self.feature_extractions_dir.mkdir(exist_ok=True, parents=True)
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
    
    # Feature Set methods
    
    def _get_feature_set_path(self, feature_set_id: str) -> Path:
        """Get the file path for a specific feature set"""
        return self.feature_sets_dir / f"{feature_set_id}.json"
    
    # DB-OPERATION: create feature
    def save_feature_set(self, feature_set: FeatureSet) -> bool:
        """
        Save a feature set to the file system.
        
        Args:
            feature_set: FeatureSet to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            path = self._get_feature_set_path(feature_set.id)
            data = feature_set.to_dict()
            
            return self.file_manager.save_json(data, path)
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
        except Exception as e:
            self.logger.error(f"Error saving feature set {feature_set.id}: {str(e)}")
            return False
    
    # DB-OPERATION: read feature
    def get_feature_set(self, feature_set_id: str) -> Optional[FeatureSet]:
        """
        Get a feature set by ID.
        
        Args:
            feature_set_id: Feature set ID
            
        Returns:
            FeatureSet if found, None otherwise
        """
        try:
            path = self._get_feature_set_path(feature_set_id)
            data = self.file_manager.load_json(path)
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            
            if data:
                return FeatureSet.from_dict(data)
            return None
        except Exception as e:
            self.logger.error(f"Error loading feature set {feature_set_id}: {str(e)}")
            return None
    
    # DB-OPERATION: read feature
    def get_all_feature_sets(self) -> List[FeatureSet]:
        """
        Get all feature sets.
        
        Returns:
            List of feature sets
        """
        try:
            set_files = list(self.feature_sets_dir.glob("*.json"))
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            
            feature_sets = []
            for set_file in set_files:
                data = self.file_manager.load_json(set_file)
                # STORAGE-OPERATION: Will be replaced by DatabaseManager
                if data:
                    feature_sets.append(FeatureSet.from_dict(data))
            
            return feature_sets
        except Exception as e:
            self.logger.error(f"Error loading feature sets: {str(e)}")
            return []
    
    # Feature Extraction methods
    
    def _get_user_extraction_dir(self, user_id: str) -> Path:
        """Get the directory for a user's feature extractions"""
        user_dir = self.feature_extractions_dir / user_id
        user_dir.mkdir(exist_ok=True, parents=True)
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
        return user_dir
    
    def _get_extraction_path(self, user_id: str, extraction_id: str) -> Path:
        """Get the file path for a specific feature extraction"""
        return self._get_user_extraction_dir(user_id) / f"{extraction_id}.json"
    
    # DB-OPERATION: create user
    def save_extraction(self, extraction: FeatureExtraction, user_id: str) -> bool:
        """
        Save a feature extraction to the file system.
        
        Args:
            extraction: FeatureExtraction to save
            user_id: User ID for the extraction
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            path = self._get_extraction_path(user_id, extraction.id)
            data = extraction.to_dict()
            
            return self.file_manager.save_json(data, path)
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
        except Exception as e:
            self.logger.error(f"Error saving feature extraction {extraction.id}: {str(e)}")
            return False
    
    # DB-OPERATION: read user
    def get_extraction(self, user_id: str, extraction_id: str) -> Optional[FeatureExtraction]:
        """
        Get a feature extraction by ID.
        
        Args:
            user_id: User ID
            extraction_id: Feature extraction ID
            
        Returns:
            FeatureExtraction if found, None otherwise
        """
        try:
            path = self._get_extraction_path(user_id, extraction_id)
            data = self.file_manager.load_json(path)
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            
            if data:
                return FeatureExtraction.from_dict(data)
            return None
        except Exception as e:
            self.logger.error(f"Error loading feature extraction {extraction_id}: {str(e)}")
            return None
    
    # DB-OPERATION: read user
    def get_extractions_for_recording(self, user_id: str, recording_id: str) -> List[FeatureExtraction]:
        """
        Get all feature extractions for a specific recording.
        
        Args:
            user_id: User ID
            recording_id: Recording ID
            
        Returns:
            List of feature extractions
        """
        try:
            user_dir = self._get_user_extraction_dir(user_id)
            extraction_files = list(user_dir.glob("*.json"))
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            
            extractions = []
            for ext_file in extraction_files:
                data = self.file_manager.load_json(ext_file)
                # STORAGE-OPERATION: Will be replaced by DatabaseManager
                if data and data.get('recording_id') == recording_id:
                    extractions.append(FeatureExtraction.from_dict(data))
            
            return extractions
        except Exception as e:
            self.logger.error(f"Error loading feature extractions for recording {recording_id}: {str(e)}")
            return []
    
    # DB-OPERATION: read user
    def get_extractions_for_feature_set(self, user_id: Optional[str], feature_set_id: str) -> List[FeatureExtraction]:
        """
        Get all feature extractions for a specific feature set.
        
        Args:
            user_id: User ID (if None, gets extractions from all users)
            feature_set_id: Feature set ID
            
        Returns:
            List of feature extractions
        """
        try:
            if user_id is None:
                # Get extractions from all users
                extraction_files = list(self.feature_extractions_dir.glob("*/*.json"))  # All users' extraction files
            else:
                # Get extractions for specific user
                user_dir = self._get_user_extraction_dir(user_id)
                extraction_files = list(user_dir.glob("*.json"))
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            
            extractions = []
            for ext_file in extraction_files:
                data = self.file_manager.load_json(ext_file)
                # STORAGE-OPERATION: Will be replaced by DatabaseManager
                if data and data.get('feature_set_id') == feature_set_id:
                    extractions.append(FeatureExtraction.from_dict(data))
            
            return extractions
        except Exception as e:
            self.logger.error(f"Error loading feature extractions for feature set {feature_set_id}: {str(e)}")
            return []
    
    # DB-OPERATION: delete user
    def delete_extraction(self, user_id: str, extraction_id: str) -> bool:
        """
        Delete a feature extraction metadata.
        Note: This does not delete the actual feature file.
        
        Args:
            user_id: User ID
            extraction_id: Feature extraction ID
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            path = self._get_extraction_path(user_id, extraction_id)
            if path.exists():
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                path.unlink()
                # STORAGE-OPERATION: Will be replaced by DatabaseManager
                self.logger.info(f"Deleted feature extraction metadata {extraction_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error deleting feature extraction {extraction_id}: {str(e)}")
            return False
    
