"""
Custom exceptions for the SoundClassifiers application.
"""

class SoundClassifierError(Exception):
    """Base class for exceptions in this application."""

class DatabaseError(SoundClassifierError):
    """Exception raised for errors related to database operations."""

class FileError(SoundClassifierError):
    """Exception raised for errors related to file operations."""

class ProcessingError(SoundClassifierError):
    """Exception raised for errors during audio processing."""

class ProcessingServiceError(ProcessingError):
    """Exception raised for errors specific to the ProcessingService."""

class RecordingServiceError(SoundClassifierError):
    """Exception raised for errors specific to the RecordingService."""

class AugmentationError(SoundClassifierError):
    """Exception raised for errors during data augmentation."""

class FeatureExtractionError(SoundClassifierError):
    """Exception raised for errors during feature extraction."""

class TrainingError(SoundClassifierError):
    """Exception raised for errors during model training."""

class InferenceError(SoundClassifierError):
    """Exception raised for errors during model inference."""

class ConfigurationError(SoundClassifierError):
    """Exception raised for configuration-related errors."""

class ValidationError(SoundClassifierError):
    """Exception raised for data validation errors.""" 