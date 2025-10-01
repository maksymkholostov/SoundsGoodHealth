"""
Volume initialization for Railway persistent storage
"""
import os
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def init_data_volume():
    """
    Initialize data volume structure for Railway deployment.
    Creates necessary directories if they don't exist.
    """
    # Check if we're using a volume
    use_volume = os.environ.get('USE_VOLUME', 'false').lower() == 'true'
    
    if use_volume:
        data_root = Path(os.environ.get('DATA_VOLUME_PATH', '/app/backend/data'))
        logger.info(f"Using Railway volume at: {data_root}")
    else:
        # Default to relative path for local development
        data_root = Path('backend/data')
        logger.info(f"Using local data directory at: {data_root}")
    
    # Create directory structure if it doesn't exist
    directories = [
        'sounds/gold',
        'sounds/augmented', 
        'features/v0.1/gold',
        'features/v0.1/augmented',
        'models',
        'metadata/feature_extractions',
        'metadata/augmentations',
        'metadata/feature_sets',
        'users'
    ]
    
    for dir_path in directories:
        full_path = data_root / dir_path
        if not full_path.exists():
            full_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {full_path}")
    
    # Initialize default files if they don't exist
    _init_default_files(data_root)
    
    return data_root

def _init_default_files(data_root: Path):
    """Initialize default JSON files if they don't exist"""
    
    # Default dictionary
    dict_file = data_root / 'dictionary.json'
    if not dict_file.exists():
        default_dict = {
            "id": "main",
            "name": "Main Dictionary",
            "classes": {},
            "metadata": {
                "created_at": "2024-01-01T00:00:00",
                "last_modified": "2024-01-01T00:00:00",
                "version": "1.0"
            }
        }
        with open(dict_file, 'w') as f:
            json.dump(default_dict, f, indent=2)
        logger.info("Created default dictionary.json")
    
    # Default feature set
    feature_set_dir = data_root / 'metadata' / 'feature_sets'
    feature_set_file = feature_set_dir / 'v0.1.json'
    if not feature_set_file.exists():
        default_feature_set = {
            "id": "v0.1",
            "name": "Default Feature Set v0.1",
            "features": [
                "mfcc",
                "spectral_centroid", 
                "spectral_bandwidth",
                "spectral_rolloff",
                "zero_crossing_rate",
                "spectral_contrast",
                "tonnetz"
            ],
            "description": "Standard audio features for classification",
            "created_at": "2024-01-01T00:00:00"
        }
        with open(feature_set_file, 'w') as f:
            json.dump(default_feature_set, f, indent=2)
        logger.info("Created default feature set v0.1.json")
    
    # Model registry
    model_registry_file = data_root / 'models' / 'model_registry.json'
    if not model_registry_file.exists():
        model_registry_file.parent.mkdir(parents=True, exist_ok=True)
        default_registry = {
            "models": [],
            "last_updated": "2024-01-01T00:00:00"
        }
        with open(model_registry_file, 'w') as f:
            json.dump(default_registry, f, indent=2)
        logger.info("Created default model_registry.json")

def check_volume_status():
    """Check and report volume status"""
    use_volume = os.environ.get('USE_VOLUME', 'false').lower() == 'true'
    
    if use_volume:
        volume_path = Path(os.environ.get('DATA_VOLUME_PATH', '/app/backend/data'))
        
        status = {
            "using_volume": True,
            "volume_path": str(volume_path),
            "exists": volume_path.exists(),
            "is_dir": volume_path.is_dir() if volume_path.exists() else False,
            "writable": os.access(volume_path, os.W_OK) if volume_path.exists() else False
        }
        
        if volume_path.exists():
            # Count files in volume
            try:
                all_files = list(volume_path.rglob('*'))
                status["total_files"] = len([f for f in all_files if f.is_file()])
                status["total_dirs"] = len([f for f in all_files if f.is_dir()])
            except Exception as e:
                status["error"] = str(e)
    else:
        status = {
            "using_volume": False,
            "volume_path": "Not configured",
            "message": "Using local data directory"
        }
    
    return status