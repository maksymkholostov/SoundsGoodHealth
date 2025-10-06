"""
Audio file validation utilities.
"""
import os
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import soundfile as sf
import librosa
import numpy as np

logger = logging.getLogger(__name__)

# Supported audio formats
SUPPORTED_EXTENSIONS = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.wma', '.aiff', '.au'}

def validate_audio_file(file_path: Path) -> Dict[str, Any]:
    """
    Validate an audio file and return its properties.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Dictionary with validation results and audio properties
    """
    result = {
        'valid': False,
        'error': None,
        'properties': {}
    }
    
    try:
        # Check if file exists
        if not file_path.exists():
            result['error'] = "File does not exist"
            return result
            
        # Check file size
        file_size = file_path.stat().st_size
        if file_size == 0:
            result['error'] = "Empty file"
            return result
            
        if file_size > 50 * 1024 * 1024:  # 50MB
            result['error'] = "File too large (max 50MB)"
            return result
            
        # Check file extension
        file_extension = file_path.suffix.lower()
        if file_extension not in SUPPORTED_EXTENSIONS:
            result['error'] = f"Unsupported format: {file_extension}"
            return result
            
        # Try to load audio
        try:
            audio_data, sample_rate = sf.read(str(file_path))
        except Exception:
            try:
                audio_data, sample_rate = librosa.load(str(file_path), sr=None)
            except Exception as e:
                result['error'] = f"Cannot load audio file: {str(e)}"
                return result
                
        # Validate audio properties
        if len(audio_data) == 0:
            result['error'] = "No audio data found"
            return result
            
        duration = len(audio_data) / sample_rate if sample_rate > 0 else 0
        if duration < 0.1:  # Less than 100ms
            result['error'] = "Audio too short (minimum 100ms)"
            return result
            
        if sample_rate < 8000:  # Too low sample rate
            result['error'] = f"Sample rate too low: {sample_rate}Hz (minimum 8kHz)"
            return result
            
        # Audio is valid
        result['valid'] = True
        result['properties'] = {
            'duration': duration,
            'sample_rate': sample_rate,
            'channels': 1 if len(audio_data.shape) == 1 else audio_data.shape[1],
            'file_size': file_size,
            'format': file_extension
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error validating audio file {file_path}: {e}")
        result['error'] = f"Validation error: {str(e)}"
        return result

def get_audio_info(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Get audio file information without validation.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Dictionary with audio properties or None if error
    """
    try:
        audio_data, sample_rate = sf.read(str(file_path))
        duration = len(audio_data) / sample_rate if sample_rate > 0 else 0
        
        return {
            'duration': duration,
            'sample_rate': sample_rate,
            'channels': 1 if len(audio_data.shape) == 1 else audio_data.shape[1],
            'file_size': file_path.stat().st_size,
            'format': file_path.suffix.lower()
        }
    except Exception as e:
        logger.error(f"Error getting audio info for {file_path}: {e}")
        return None
