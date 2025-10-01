"""
Development Configuration

This module contains the configuration settings for the development environment.
"""
import logging
from . import Config

class DevelopmentConfig(Config):
    """Development configuration settings"""
    ENV = 'development'
    DEBUG = True
    TESTING = False
    LOG_LEVEL = logging.DEBUG
    
    # Development-specific settings
    USE_RELOADER = True
    
    # Feature extraction settings for development
    # Use fewer augmentation samples to speed up development
    AUGMENTATION_FACTOR = 3
    
    # Training settings
    EPOCHS = 10
    BATCH_SIZE = 32
    LEARNING_RATE = 0.001
