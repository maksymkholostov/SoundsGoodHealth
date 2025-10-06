"""
Configuration Package

This package contains configuration classes for different environments.
"""
import os
from pathlib import Path

# Base directory for the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Backend directory
BACKEND_DIR = BASE_DIR / "backend"

# Logs directory
LOGS_DIR = BASE_DIR / "logs"

# Data directory
DATA_DIR = BACKEND_DIR / "data"

class Config:
    """Base configuration class with common settings"""
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-please-change-in-production')
    DEBUG = False
    TESTING = False
    
        # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    WTF_CSRF_SSL_STRICT = False  # Set to True in production with HTTPS
    
    # Static and template folders
    STATIC_FOLDER = str(BASE_DIR / "frontend" / "static")
    TEMPLATE_FOLDER = str(BASE_DIR / "frontend" / "templates")
    
    # Logging settings
    LOG_LEVEL = 'INFO'
    LOGS_DIR = str(LOGS_DIR)
    
    # Data storage settings
    DATA_ROOT = str(DATA_DIR)
    
    # Calculate paths from DATA_DIR before converting to strings
    FEATURES_PATH = DATA_DIR / "features" / "v0.1"
    MODELS_PATH = DATA_DIR / "models"
    
    # Convert to strings for config
    FEATURES_DIR = str(FEATURES_PATH)
    MODELS_DIR = str(MODELS_PATH)
    
    # Audio settings
    AUDIO_SAMPLE_RATE = 16000
    AUDIO_MAX_DURATION = 10  # Maximum recording duration in seconds
    
    # Feature extraction settings
    FEATURE_VERSION = "v0.1"
    
    # Model settings
    DEFAULT_MODEL_TYPE = "cnn"
    MODEL_VERSION = "v0.1"
    
    # User interaction settings
    INCLUDE_ALL_USER_DICTIONARIES = True  # Whether to include dictionaries from all users
    INCLUDE_ALL_USER_RECORDINGS = True    # Whether to include recordings from all users
    ALLOW_ALL_USERS_VIEW_FOR_NON_ADMINS = True  # Allow all users to view all data
    
    # Ensure directories exist
    @classmethod
    def init_directories(cls):
        """Create necessary directories if they don't exist"""
        # Create base directories
        for dir_path in [LOGS_DIR, DATA_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Create data subdirectories - V10 Structure + used metadata dirs
        # NOTE: These are also created by FileManager.__init__ and Repo __init__ methods.
        # Consider removing duplicates if initialization order is guaranteed.
        data_dirs = [
            # Top Level V10 Dirs (also done by FileManager)
            DATA_DIR / "sounds",
            DATA_DIR / "features",
            DATA_DIR / "models",
            DATA_DIR / "metadata",
            DATA_DIR / "dictionaries",
            DATA_DIR / "classes",
            DATA_DIR / "users",
            DATA_DIR / "inference",
            # Specific V10 Subdirs needed early or consistently
            DATA_DIR / "sounds" / "discarded",
            DATA_DIR / "metadata" / "stats", # Used by stats route
            # Specific Feature/Model dirs (may be redundant if repos create them)
            DATA_DIR / "features" / "v0.1", # Assuming FEATURES_PATH uses v0.1
            # Potentially add DATA_DIR / 'uploads' if needed for UPLOAD_FOLDER
        ]
        
        for dir_path in data_dirs:
            # Use Path object's mkdir directly
            dir_path.mkdir(parents=True, exist_ok=True)
