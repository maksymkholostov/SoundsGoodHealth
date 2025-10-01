"""
API package for SoundClassifiers v10.

This package contains all API endpoints for the application.
"""
from flask import Blueprint

# Import all API blueprint modules
from .augmentation import augmentation_api
from .inference import inference_api_bp  # Import inference blueprint
from .training import training_bp        # Import training blueprint
# TODO: Import other blueprints as needed (e.g., auth, dictionaries, recordings, admin, analysis)

# List of all API blueprints
__all__ = [
    'augmentation_api',
    'inference_api_bp',  # Add inference blueprint to the list
    'training_bp',       # Add training blueprint to the list
]
