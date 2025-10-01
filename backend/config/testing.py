"""
Testing Configuration

This module contains the configuration settings for the testing environment.
"""
import logging
import tempfile
import os
from . import Config, BASE_DIR

class TestingConfig(Config):
    """Testing configuration settings"""
    ENV = 'testing'
    DEBUG = False
    TESTING = True
    
    # Use a predictable secret key for testing
    SECRET_KEY = 'test-key'
    
    # Logging settings
    LOG_LEVEL = logging.ERROR
    
    # Use temporary directories for data to avoid modifying real data
    _temp_dir_obj = tempfile.TemporaryDirectory(prefix='soundclass_test_')
    DATA_DIR = _temp_dir_obj.name
    DATA_ROOT = DATA_DIR
    
    FEATURES_DIR = f"{DATA_DIR}/features/v0.1"
    MODELS_DIR = f"{DATA_DIR}/models"
    
    # Feature extraction settings for testing
    AUGMENTATION_FACTOR = 1
    
    # Training settings
    EPOCHS = 1
    BATCH_SIZE = 16
    LEARNING_RATE = 0.01
    
    # Override the init_directories method to use test directories
    @classmethod
    def init_directories(cls):
        """Create test directories"""
        test_dirs = [
            cls.DATA_DIR,
            f"{cls.DATA_DIR}/sounds",
            f"{cls.DATA_DIR}/sounds/discarded",
            f"{cls.DATA_DIR}/features",
            f"{cls.DATA_DIR}/features/v0.1",
            f"{cls.DATA_DIR}/models",
            f"{cls.DATA_DIR}/metadata",
            f"{cls.DATA_DIR}/metadata/stats",
            f"{cls.DATA_DIR}/metadata/feature_extractions",
            f"{cls.DATA_DIR}/metadata/feature_sets",
            f"{cls.DATA_DIR}/dictionaries",
            f"{cls.DATA_DIR}/classes",
            f"{cls.DATA_DIR}/users",
            f"{cls.DATA_DIR}/inference",
        ]
        
        for dir_path in test_dirs:
            os.makedirs(dir_path, exist_ok=True)

    @classmethod
    def cleanup_directories(cls):
        if hasattr(cls, '_temp_dir_obj'):
            cls._temp_dir_obj.cleanup()
            print(f"Cleaned up temporary test directory: {cls.DATA_DIR}")
