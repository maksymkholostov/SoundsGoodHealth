"""
Model Registry Service

Purpose: Automatically maintains a central model registry
Updated: August 9, 2025

This service automatically updates the model registry whenever:
- A new model is trained
- A model is deleted
- Model metadata is updated
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ModelRegistryService:
    """Service for maintaining the central model registry"""
    
    def __init__(self, data_root: str):
        """Initialize the registry service
        
        Args:
            data_root: Path to the data directory
        """
        self.data_root = Path(data_root)
        self.registry_path = self.data_root / 'models' / 'model_registry.json'
        self.metadata_base = self.data_root / 'metadata' / 'models'
        self.models_base = self.data_root / 'models'
        
        # Ensure registry directory exists
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize registry if it doesn't exist
        if not self.registry_path.exists():
            self._initialize_registry()
    
    def _initialize_registry(self):
        """Create an empty registry file"""
        registry = {
            'last_updated': datetime.now().isoformat(),
            'total_models': 0,
            'models': [],
            'users': [],
            'dictionaries': [],
            'model_types': []
        }
        self._save_registry(registry)
        logger.info(f"Initialized model registry at {self.registry_path}")
    
    def _load_registry(self) -> Dict:
        """Load the current registry"""
        try:
            with open(self.registry_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading registry: {e}")
            self._initialize_registry()
            with open(self.registry_path, 'r') as f:
                return json.load(f)
    
    def _save_registry(self, registry: Dict):
        """Save the registry to file"""
        try:
            registry['last_updated'] = datetime.now().isoformat()
            with open(self.registry_path, 'w') as f:
                json.dump(registry, f, indent=2)
            logger.debug(f"Registry saved with {len(registry.get('models', []))} models")
        except Exception as e:
            logger.error(f"Error saving registry: {e}")
    
    def add_model(self, model_id: str, user_id: str, dict_id: str, 
                  metadata_path: str = None) -> bool:
        """Add a new model to the registry
        
        Args:
            model_id: Model identifier
            user_id: User who trained the model
            dict_id: Dictionary ID
            metadata_path: Path to model metadata file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            registry = self._load_registry()
            
            # Check if model already exists
            existing_models = [m for m in registry['models'] if m['id'] == model_id]
            if existing_models:
                logger.info(f"Model {model_id} already in registry, updating...")
                return self.update_model(model_id, user_id, dict_id, metadata_path)
            
            # Read metadata if provided
            metadata = {}
            if metadata_path and Path(metadata_path).exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
            
            # Determine model type from metadata or model ID
            model_type = metadata.get('model_type', 'Unknown')
            
            # If metadata doesn't have type, try to infer from model_id
            if model_type == 'Unknown' and model_id:
                if model_id.startswith('rf_'):
                    model_type = 'Random Forest'
                elif model_id.startswith('svm_'):
                    model_type = 'SVM'
                elif model_id.startswith('cnn_'):
                    model_type = 'CNN'
                elif model_id.startswith('cnn1d_'):
                    model_type = 'CNN1D'
                elif model_id.startswith('ensemble_'):
                    model_type = 'Ensemble'
            
            # Normalize model type names
            if model_type == 'cnn':
                model_type = 'CNN'
            elif model_type == 'rf' or model_type == 'random_forest':
                model_type = 'Random Forest'
            elif model_type == 'svm':
                model_type = 'SVM'
            elif model_type == 'cnn1d':
                model_type = 'CNN1D'
            elif model_type == 'ensemble':
                model_type = 'Ensemble'
            
            # Extract training statistics
            training_ids = metadata.get('training_ids', [])
            validation_ids = metadata.get('validation_ids', [])
            classes = metadata.get('classes', [])
            metrics = metadata.get('metrics', {})
            
            # Count samples per class
            class_counts = {}
            for class_name in classes:
                clean_name = class_name.replace('cls_', '').upper() if class_name.startswith('cls_') else class_name.upper()
                class_count = sum(1 for tid in training_ids if clean_name.lower() in tid.lower())
                class_counts[clean_name] = class_count
            
            # Build model info
            model_info = {
                'id': model_id,
                'user_id': user_id,
                'dictionary_id': dict_id,
                'name': metadata.get('name', f"Model {model_id[:8]}"),
                'type': model_type,
                'created_at': metadata.get('created_at', datetime.now().isoformat()),
                'accuracy': metrics.get('accuracy'),
                'status': metadata.get('status', 'active'),
                'metadata_path': str(Path(metadata_path).relative_to(self.data_root)) if metadata_path else None,
                'model_path': f"models/{dict_id}/{model_id}",
                'training_stats': {
                    'total_samples': len(training_ids),
                    'validation_samples': len(validation_ids),
                    'class_counts': class_counts,
                    'classes': classes,
                    'num_train_samples': metrics.get('num_train_samples', len(training_ids)),
                    'num_val_samples': metrics.get('num_val_samples', len(validation_ids))
                }
            }
            
            # Add to registry
            registry['models'].append(model_info)
            
            # Update summary fields
            registry['total_models'] = len(registry['models'])
            registry['users'] = list(set(m['user_id'] for m in registry['models']))
            registry['dictionaries'] = list(set(m['dictionary_id'] for m in registry['models']))
            registry['model_types'] = list(set(m['type'] for m in registry['models']))
            
            # Sort by creation date
            registry['models'].sort(key=lambda m: m.get('created_at', ''), reverse=True)
            
            # Save
            self._save_registry(registry)
            logger.info(f"Added model {model_id} to registry")
            return True
            
        except Exception as e:
            logger.error(f"Error adding model {model_id} to registry: {e}")
            return False
    
    def update_model(self, model_id: str, user_id: str = None, 
                    dict_id: str = None, metadata_path: str = None) -> bool:
        """Update an existing model in the registry
        
        Args:
            model_id: Model identifier
            user_id: User ID (optional)
            dict_id: Dictionary ID (optional)
            metadata_path: Path to updated metadata (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            registry = self._load_registry()
            
            # Find model
            model_index = None
            for i, model in enumerate(registry['models']):
                if model['id'] == model_id:
                    model_index = i
                    break
            
            if model_index is None:
                logger.warning(f"Model {model_id} not found for update, adding new...")
                return self.add_model(model_id, user_id, dict_id, metadata_path)
            
            # Update model info
            if metadata_path and Path(metadata_path).exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                # Update with new metadata
                model = registry['models'][model_index]
                model['name'] = metadata.get('name', model.get('name'))
                model['accuracy'] = metadata.get('metrics', {}).get('accuracy', model.get('accuracy'))
                model['status'] = metadata.get('status', model.get('status'))
                model['updated_at'] = datetime.now().isoformat()
                
                # Update training stats
                training_ids = metadata.get('training_ids', [])
                validation_ids = metadata.get('validation_ids', [])
                classes = metadata.get('classes', [])
                
                class_counts = {}
                for class_name in classes:
                    clean_name = class_name.replace('cls_', '').upper() if class_name.startswith('cls_') else class_name.upper()
                    class_count = sum(1 for tid in training_ids if clean_name.lower() in tid.lower())
                    class_counts[clean_name] = class_count
                
                model['training_stats'] = {
                    'total_samples': len(training_ids),
                    'validation_samples': len(validation_ids),
                    'class_counts': class_counts,
                    'classes': classes
                }
            
            # Save
            self._save_registry(registry)
            logger.info(f"Updated model {model_id} in registry")
            return True
            
        except Exception as e:
            logger.error(f"Error updating model {model_id}: {e}")
            return False
    
    def remove_model(self, model_id: str) -> bool:
        """Remove a model from the registry
        
        Args:
            model_id: Model identifier to remove
            
        Returns:
            True if successful, False otherwise
        """
        try:
            registry = self._load_registry()
            
            # Filter out the model
            original_count = len(registry['models'])
            registry['models'] = [m for m in registry['models'] if m['id'] != model_id]
            
            if len(registry['models']) == original_count:
                logger.warning(f"Model {model_id} not found in registry")
                return False
            
            # Update summary fields
            registry['total_models'] = len(registry['models'])
            if registry['models']:
                registry['users'] = list(set(m['user_id'] for m in registry['models']))
                registry['dictionaries'] = list(set(m['dictionary_id'] for m in registry['models']))
                registry['model_types'] = list(set(m['type'] for m in registry['models']))
            else:
                registry['users'] = []
                registry['dictionaries'] = []
                registry['model_types'] = []
            
            # Save
            self._save_registry(registry)
            logger.info(f"Removed model {model_id} from registry")
            return True
            
        except Exception as e:
            logger.error(f"Error removing model {model_id}: {e}")
            return False
    
    def refresh_registry(self) -> int:
        """Perform a full scan and rebuild the registry
        
        Returns:
            Number of models found
        """
        try:
            logger.info("Starting full registry refresh...")
            models = []
            
            if not self.metadata_base.exists():
                logger.warning(f"Metadata directory not found: {self.metadata_base}")
                return 0
            
            # Scan all user directories
            for user_dir in self.metadata_base.iterdir():
                if not user_dir.is_dir() or user_dir.name.startswith('.'):
                    continue
                
                user_id = user_dir.name
                
                # Scan all dictionary directories
                for dict_dir in user_dir.iterdir():
                    if not dict_dir.is_dir():
                        continue
                    
                    dict_id = dict_dir.name
                    
                    # Scan all model metadata files
                    for metadata_file in dict_dir.glob('*.json'):
                        model_id = metadata_file.stem
                        
                        # Check if model files exist
                        model_dir = self.models_base / dict_id / model_id
                        if not model_dir.exists():
                            logger.warning(f"Model directory missing for {model_id}")
                            continue
                        
                        # Add to list for batch update
                        models.append({
                            'model_id': model_id,
                            'user_id': user_id,
                            'dict_id': dict_id,
                            'metadata_path': str(metadata_file)
                        })
            
            # Clear and rebuild registry
            self._initialize_registry()
            
            # Add all models
            for model_data in models:
                self.add_model(**model_data)
            
            logger.info(f"Registry refresh complete: {len(models)} models")
            return len(models)
            
        except Exception as e:
            logger.error(f"Error refreshing registry: {e}")
            return 0
    
    def get_registry_stats(self) -> Dict:
        """Get summary statistics from the registry
        
        Returns:
            Dictionary with registry statistics
        """
        try:
            registry = self._load_registry()
            return {
                'total_models': registry.get('total_models', 0),
                'users': registry.get('users', []),
                'dictionaries': registry.get('dictionaries', []),
                'model_types': registry.get('model_types', []),
                'last_updated': registry.get('last_updated', 'Unknown')
            }
        except Exception as e:
            logger.error(f"Error getting registry stats: {e}")
            return {}