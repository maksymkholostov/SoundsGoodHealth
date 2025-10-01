"""
Production Configuration

This module contains the configuration settings for the production environment.
"""
import os
import logging
from . import Config

class ProductionConfig(Config):
    """Production configuration settings"""
    ENV = 'production'
    DEBUG = False
    TESTING = False
    
    # Use a strong secret key in production
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'CHANGE-ME-IN-PRODUCTION'
    
    # Logging settings
    LOG_LEVEL = logging.INFO
    
    # Feature extraction settings for production
    # Use more augmentation samples for better model performance
    AUGMENTATION_FACTOR = 10
    
    # Training settings
    EPOCHS = 50
    BATCH_SIZE = 64
    LEARNING_RATE = 0.001
    
    # Session settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
