import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

from backend.app.core.models.model import ModelVersion, ModelType, ModelStatus
from backend.app.storage.file_manager import FileManager


class ModelRepository:
    """
    Repository for ML Model domain objects.
    
    Handles persistence of model metadata to the file system.
    The actual model files are managed by the FileManager.
    """
    
    def __init__(self, file_manager: FileManager):
        """
        Initialize the model repository.
        
        Args:
            file_manager: FileManager instance for storage operations
        """
        self.file_manager = file_manager
        self.logger = logging.getLogger(__name__)
        
        # Create model metadata directory if it doesn't exist
        self.models_meta_dir = Path(self.file_manager.data_root) / 'metadata' / 'models'
        self.models_meta_dir.mkdir(exist_ok=True, parents=True)
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
    
    def _get_user_models_dir(self, user_id: str) -> Path:
        """Get the directory for a user's model metadata"""
        user_dir = self.models_meta_dir / user_id
        user_dir.mkdir(exist_ok=True, parents=True)
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
        return user_dir
    
    def _get_dict_models_dir(self, user_id: str, dict_id: str) -> Path:
        """Get the directory for a dictionary's model metadata"""
        dict_dir = self._get_user_models_dir(user_id) / dict_id
        dict_dir.mkdir(exist_ok=True, parents=True)
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
        return dict_dir
    
    def _get_model_path(self, user_id: str, dict_id: str, model_id: str) -> Path:
        """Get the file path for a specific model metadata"""
        return self._get_dict_models_dir(user_id, dict_id) / f"{model_id}.json"
    
    def save(self, model: ModelVersion) -> bool:
        """
        Save model metadata to the file system.
        
        Args:
            model: Model metadata to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            model_path = self._get_model_path(model.user_id, model.dictionary_id, model.id)
            model_data = model.to_dict()
            
            return self.file_manager.save_json(model_data, model_path)
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
        except Exception as e:
            self.logger.error(f"Error saving model {model.id}: {str(e)}")
            return False
    
    # DB-OPERATION: read user
    def get_by_id(self, user_id: str, dict_id: str, model_id: str) -> Optional[ModelVersion]:
        """
        Get model metadata by ID, requiring user and dictionary context.
        
        Args:
            user_id: User ID
            dict_id: Dictionary ID
            model_id: Model ID
            
        Returns:
            ModelVersion if found, None otherwise
        """
        try:
            model_path = self._get_model_path(user_id, dict_id, model_id)
            model_data = self.file_manager.load_json(model_path)
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            
            if model_data:
                return ModelVersion.from_dict(model_data)
            return None
        except Exception as e:
            self.logger.error(f"Error loading model {model_id} for user {user_id}, dict {dict_id}: {str(e)}")
            return None
    
    # DB-OPERATION: read model (searches across users/dicts)
    def find_model_by_id(self, model_id_to_find: str) -> Optional[ModelVersion]:
        """
        Finds a model metadata file by its ID by searching across all user/dictionary
        subdirectories within the metadata/models directory.
        
        Args:
            model_id_to_find: The unique ID of the model to find.
            
        Returns:
            ModelVersion if found, None otherwise. Returns the first match found.
        """
        self.logger.debug(f"Attempting to find model metadata for ID: {model_id_to_find}")
        target_filename = f"{model_id_to_find}.json"
        
        if not self.models_meta_dir.is_dir():
            self.logger.warning(f"Base model metadata directory does not exist: {self.models_meta_dir}")
            return None
        
        try:
            # Use rglob to search recursively for the filename
            # **/*.json would find all json, then we filter
            # */*/*.json finds json 2 levels down (user_id/dict_id/model_id.json)
            search_pattern = f"*/*/{target_filename}"
            found_files = list(self.models_meta_dir.rglob(search_pattern))
            
            if not found_files:
                self.logger.warning(f"No metadata file found for model ID {model_id_to_find} using pattern {search_pattern}")
                return None
            
            if len(found_files) > 1:
                # This shouldn't happen if model IDs are truly unique, but log it.
                self.logger.warning(f"Found multiple metadata files for model ID {model_id_to_find}: {found_files}. Using the first one.")
            
            model_path = found_files[0]
            self.logger.info(f"Found model metadata file at: {model_path}")
            model_data = self.file_manager.load_json(model_path)
            
            if model_data:
                # Construct and return the ModelVersion object
                return ModelVersion.from_dict(model_data)
            else:
                self.logger.error(f"Found metadata file for {model_id_to_find} at {model_path}, but failed to load JSON data.")
                return None
            
        except Exception as e:
            self.logger.error(f"Error searching for model {model_id_to_find}: {str(e)}", exc_info=True)
            return None
    
    # DB-OPERATION: read user
    def get_for_dictionary(self, user_id: str, dict_id: str,
                          model_type: Optional[ModelType] = None,
                          status: Optional[ModelStatus] = None) -> List[ModelVersion]:
        """
        Get all models for a dictionary.
        
        Args:
            user_id: User ID
            dict_id: Dictionary ID
            model_type: Optional filter by model type
            status: Optional filter by model status
            
        Returns:
            List of models
        """
        try:
            dict_dir = self._get_dict_models_dir(user_id, dict_id)
            model_files = list(dict_dir.glob("*.json"))
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            
            models = []
            for model_file in model_files:
                model_data = self.file_manager.load_json(model_file)
                # STORAGE-OPERATION: Will be replaced by DatabaseManager
                if not model_data:
                    continue
                
                # Filter by type if specified
                if model_type and ModelType(model_data.get('type')) != model_type:
                    continue
                
                # Filter by status if specified
                if status and ModelStatus(model_data.get('status')) != status:
                    continue
                
                models.append(ModelVersion.from_dict(model_data))
            
            return models
        except Exception as e:
            self.logger.error(f"Error loading models for dictionary {dict_id}: {str(e)}")
            return []
    
    # DB-OPERATION: read user
    def get_latest_for_dictionary(self, user_id: str, dict_id: str,
                                 model_type: Optional[ModelType] = None,
                                 status: Optional[List[ModelStatus]] = None) -> Optional[ModelVersion]:
        """
        Get the latest model for a dictionary.
        
        Args:
            user_id: User ID
            dict_id: Dictionary ID
            model_type: Optional filter by model type
            status: Optional list of acceptable statuses
            
        Returns:
            Latest ModelVersion if found, None otherwise
        """
        models = self.get_for_dictionary(user_id, dict_id, model_type)
        
        if not models:
            return None
        
        # Filter by status if specified
        if status:
            models = [m for m in models if m.status in status]
        
        # Return the most recently created model
        return max(models, key=lambda m: m.created_at) if models else None
    
    def delete(self, user_id: str, dict_id: str, model_id: str) -> bool:
        """
        Delete model metadata.
        Note: This does not delete the actual model file.
        
        Args:
            user_id: User ID
            dict_id: Dictionary ID
            model_id: Model ID
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            model_path = self._get_model_path(user_id, dict_id, model_id)
            if model_path.exists():
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                model_path.unlink()
                # STORAGE-OPERATION: Will be replaced by DatabaseManager
                self.logger.info(f"Deleted model metadata {model_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error deleting model {model_id}: {str(e)}")
            return False
    
    # DB-OPERATION: delete model
    def delete_with_file(self, model: ModelVersion) -> bool:
        """
        Delete model metadata and the associated model file.
        
        Args:
            model: Model to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Delete metadata
            metadata_deleted = self.delete(model.user_id, model.dictionary_id, model.id)
            
            # Delete model artifact(s)
            # CNN/CNN1D are saved as a directory at: data/models/<dict_id>/<model_id>/
            # RF/SVM are saved as a file inside that directory: <filename>
            artifact_deleted = True
            try:
                # Base model directory for this specific model version
                model_dir = self.file_manager.get_specific_model_dir(
                    dictionary_id=model.dictionary_id,
                    model_type_version=model.id
                )

                # If filename is empty or model is a CNN variant, remove the whole directory
                if model.type in [ModelType.CNN, ModelType.CNN1D] or not model.filename:
                    artifact_deleted = self.file_manager.delete_directory(model_dir)
                else:
                    # Delete only the artifact file (e.g., .pkl)
                    artifact_path = model_dir / model.filename
                    artifact_deleted = self.file_manager.delete_file(artifact_path)
            except Exception as delete_e:
                self.logger.error(f"Error deleting model artifacts for {model.id}: {delete_e}")
                artifact_deleted = False

            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            return metadata_deleted and artifact_deleted
        except Exception as e:
            self.logger.error(f"Error deleting model with file {model.id}: {str(e)}")
            return False
