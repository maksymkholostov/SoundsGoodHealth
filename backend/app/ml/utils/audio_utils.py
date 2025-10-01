"""
Audio utility functions for SoundClassifiers.

This module provides centralized utilities for audio processing tasks:
- Loading audio files with fallback methods
- Extracting audio properties
- Standardizing audio formats
"""
import os
import io
import logging
import numpy as np
import soundfile as sf
import librosa
from typing import Dict, Any, Optional, Tuple, Union, BinaryIO

logger = logging.getLogger(__name__)

# DB-OPERATION: read file
def load_audio_from_file(file_path: str, fallback_to_ffmpeg: bool = True) -> Tuple[np.ndarray, int]:
    """
    Load audio data from a file with multiple fallback methods.
    
    Args:
        file_path: Path to the audio file
        fallback_to_ffmpeg: Whether to try ffmpeg as a last resort
        
    Returns:
        Tuple of (audio_data, sample_rate)
        
    Raises:
        ValueError: If the audio file cannot be loaded
    """
    # Try multiple libraries for reading the audio file to ensure compatibility
    try_methods = [
        ('soundfile', lambda: sf.read(file_path)),
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
        ('librosa', lambda: librosa.load(file_path, sr=None)),
        ('scipy', lambda: _load_with_scipy(file_path))
    ]
    
    for method_name, method_func in try_methods:
        try:
            logger.debug(f"Attempting to load audio with {method_name}")
            
            if method_name == 'scipy':
                audio_data, sample_rate = method_func()
            else:
                audio_data, sample_rate = method_func()
                
            logger.debug(f"Successfully loaded with {method_name}: SR={sample_rate}Hz, shape={audio_data.shape}")
            return audio_data, sample_rate
                
        except Exception as e:
            logger.warning(f"Error loading audio with {method_name}: {str(e)}")
    
    # If all standard methods fail and fallback is enabled, try ffmpeg
    if fallback_to_ffmpeg:
        try:
            import subprocess
            import tempfile
            
            logger.debug(f"All standard methods failed, attempting conversion with ffmpeg")
            
            # Create a temporary file for the converted audio
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                # Use ffmpeg to convert the audio to a standard format
                ffmpeg_cmd = [
                    'ffmpeg', '-y', 
                    '-i', file_path,
                    '-acodec', 'pcm_s16le',  # 16-bit PCM
                    '-ar', '16000',          # 16kHz sample rate
                    '-ac', '1',              # mono
                    temp_path
                ]
                
                # Run ffmpeg
                subprocess.run(ffmpeg_cmd, check=True, stderr=subprocess.PIPE)
                
                # Load the converted file
                audio_data, sample_rate = librosa.load(temp_path, sr=None)
                logger.info(f"Successfully converted with ffmpeg: SR={sample_rate}Hz, length={len(audio_data)}")
                
                return audio_data, sample_rate
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_path):
                # STORAGE-OPERATION: Will be replaced by DatabaseManager
                    os.unlink(temp_path)
                    # STORAGE-OPERATION: Will be replaced by DatabaseManager
                    
        except Exception as e:
            logger.error(f"Failed to use ffmpeg for conversion: {str(e)}")
    
    # If we get here, all methods failed
    raise ValueError(f"Could not load audio file: {file_path}")

# DB-OPERATION: read unknown
def load_audio_from_bytes(audio_bytes: bytes) -> Tuple[np.ndarray, int]:
    """
    Load audio data from bytes.
    
    Args:
        audio_bytes: Binary audio data
        
    Returns:
        Tuple of (audio_data, sample_rate)
        
    Raises:
        ValueError: If the audio bytes cannot be loaded
    """
    try:
        # Create in-memory file object
        audio_io = io.BytesIO(audio_bytes)
        
        # Try loading with soundfile first
        try:
            audio_data, sample_rate = sf.read(audio_io)
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            return audio_data, sample_rate
        except Exception as e:
            logger.warning(f"Could not load audio bytes with soundfile: {str(e)}")
            
            # Try with librosa as fallback
            audio_io.seek(0)
            try:
                audio_data, sample_rate = librosa.load(audio_io, sr=None)
                return audio_data, sample_rate
            except Exception as e:
                logger.warning(f"Could not load audio bytes with librosa: {str(e)}")
                raise ValueError(f"Could not load audio from bytes: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error loading audio from bytes: {str(e)}")
        raise ValueError(f"Could not load audio from bytes: {str(e)}")

def extract_audio_properties(audio_data: np.ndarray, sample_rate: int) -> Dict[str, Any]:
    """
    Extract basic properties from audio data.
    
    Args:
        audio_data: Audio data as numpy array
        sample_rate: Sample rate of the audio
        
    Returns:
        Dictionary of audio properties
    """
    try:
        # Calculate duration
        duration = len(audio_data) / sample_rate
        
        # Determine number of channels
        channels = 1
        if len(audio_data.shape) > 1:
            channels = audio_data.shape[1]
        
        # Calculate amplitude metrics
        max_amplitude = float(np.max(np.abs(audio_data)))
        rms = float(np.sqrt(np.mean(audio_data**2)))
        
        # Determine sample width (assume float32)
        sample_width = 4
        if audio_data.dtype == np.int16:
            sample_width = 2
        elif audio_data.dtype == np.uint8 or audio_data.dtype == np.int8:
            sample_width = 1
        
        return {
            'duration': duration,
            'sample_rate': sample_rate,
            'channels': channels,
            'n_frames': len(audio_data),
            'max_amplitude': max_amplitude,
            'rms': rms,
            'sample_width': sample_width
        }
        
    except Exception as e:
        logger.error(f"Error extracting audio properties: {str(e)}")
        return {
            'duration': 0,
            'sample_rate': sample_rate,
            'channels': 1,
            'n_frames': 0,
            'max_amplitude': 0,
            'rms': 0,
            'sample_width': 2,
            'error': str(e)
        }

def ensure_audio_format(audio_data: np.ndarray, sample_rate: int, 
                        target_sr: int = 16000, mono: bool = True, 
                        normalize: bool = True) -> Tuple[np.ndarray, int]:
    """
    Ensure audio is in a standard format (sample rate, channels, etc.)
    
    Args:
        audio_data: Audio data as numpy array
        sample_rate: Current sample rate of the audio
        target_sr: Target sample rate
        mono: Whether to convert to mono
        normalize: Whether to normalize amplitude
        
    Returns:
        Tuple of (standardized_audio, new_sample_rate)
    """
    # Make a copy to avoid modifying the verified
    audio_out = audio_data.copy()
    
    # Convert to mono if needed
    if mono and len(audio_out.shape) > 1 and audio_out.shape[1] > 1:
        audio_out = np.mean(audio_out, axis=1)
    
    # Resample if needed
    if sample_rate != target_sr:
        audio_out = librosa.resample(audio_out, orig_sr=sample_rate, target_sr=target_sr)
        sample_rate = target_sr
    
    # Normalize if requested
    if normalize and np.max(np.abs(audio_out)) > 0:
        audio_out = audio_out / np.max(np.abs(audio_out))
    
    return audio_out, sample_rate

def analyze_audio_file(file_path: str) -> Dict[str, Any]:
    """
    Comprehensive analysis of an audio file.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Dictionary of audio properties
    """
    try:
        # Load audio
        audio_data, sample_rate = load_audio_from_file(file_path)
        
        # Extract properties
        properties = extract_audio_properties(audio_data, sample_rate)
        
        return properties
        
    except Exception as e:
        logger.error(f"Error analyzing audio file {file_path}: {str(e)}")
        return {
            'error': str(e),
            'duration': 0,
            'sample_rate': 0,
            'channels': 0,
            'n_frames': 0,
            'max_amplitude': 0,
            'rms': 0,
            'sample_width': 0
        }

def analyze_audio_bytes(audio_bytes: bytes) -> Dict[str, Any]:
    """
    Analyze audio data from bytes.
    
    Args:
        audio_bytes: Binary audio data
        
    Returns:
        Dictionary of audio properties
    """
    try:
        # Load audio
        audio_data, sample_rate = load_audio_from_bytes(audio_bytes)
        
        # Extract properties
        properties = extract_audio_properties(audio_data, sample_rate)
        
        return properties
        
    except Exception as e:
        logger.error(f"Error analyzing audio bytes: {str(e)}")
        return {
            'error': str(e),
            'duration': 0,
            'sample_rate': 0,
            'channels': 0,
            'n_frames': 0,
            'max_amplitude': 0,
            'rms': 0,
            'sample_width': 0
        }

def _load_with_scipy(file_path: str) -> Tuple[np.ndarray, int]:
    """Helper to load audio with scipy"""
    import scipy.io.wavfile as wav
    try:
        sample_rate, audio_data = wav.read(file_path)
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
        # Convert to float32 if not already
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32) / 32768.0
        return audio_data, sample_rate
    except Exception as e:
        raise ValueError(f"Could not load audio with scipy: {str(e)}")

def pad_audio(audio: np.ndarray, sr: int, target_length: float = 1.25, 
              start_silence_ms: float = 100.0, 
              end_silence_ms: float = 100.0) -> Optional[np.ndarray]:
    """
    Pads or trims audio to a target length, ensuring specific start/end silence.
    
    1. Ensures minimum start_silence_ms at the beginning.
    2. Ensures minimum end_silence_ms at the end.
    3. Pads/Trims the END SILENCE ONLY to reach the exact target_length.
    Trimming prioritizes removing end silence first.

    Args:
        audio: Audio data (assumed to be the core segment with ~20ms margins from segmenter)
        sr: Sample rate
        target_length: Target length in seconds
        start_silence_ms: Milliseconds of silence required at the start.
        end_silence_ms: Milliseconds of silence required at the end.
        
    Returns:
        Padded/trimmed audio as numpy array, or None if excessive trimming required.
    """
    try:
        # Ensure input is float32
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        target_samples = int(target_length * sr)
        start_pad_samples = int(start_silence_ms * sr / 1000)
        end_pad_samples = int(end_silence_ms * sr / 1000)
        core_audio_samples = len(audio)

        min_total_needed = start_pad_samples + core_audio_samples + end_pad_samples
        
        if min_total_needed == target_samples:
            logger.debug(f"Segment fits target length exactly with min padding.")
            return np.pad(audio, (start_pad_samples, end_pad_samples), mode='constant')
            
        elif min_total_needed < target_samples:
            additional_end_padding = target_samples - min_total_needed
            logger.debug(f"Padding: Adding {start_pad_samples} start, {end_pad_samples} min end, + {additional_end_padding} extra end samples.")
            return np.pad(audio, (start_pad_samples, end_pad_samples + additional_end_padding), mode='constant')
            
        else: # min_total_needed > target_samples - Requires trimming
            samples_to_trim = min_total_needed - target_samples
            logger.warning(f"Segment ({core_audio_samples/sr:.3f}s) with required padding ({start_silence_ms+end_silence_ms}ms) exceeds target length ({target_length}s). Needs to trim {samples_to_trim} samples.")
            
            # Trim from end padding first
            trimmed_end_padding = max(0, end_pad_samples - samples_to_trim)
            samples_still_to_trim = max(0, samples_to_trim - end_pad_samples)
            
            # Trim from the end of the core audio if necessary
            trimmed_core_audio_samples = core_audio_samples - samples_still_to_trim
            
            if trimmed_core_audio_samples <= 0:
                 logger.error(f"Trimming requires removing ALL core audio ({core_audio_samples} samples). Discarding segment.")
                 return None # Discard if trimming removes all core audio
            else:
                logger.info(f"Trimming {samples_still_to_trim} samples from end of core audio and using {trimmed_end_padding} samples of end padding.")
                # Take the required part from the end of the core audio
                trimmed_audio = audio[:trimmed_core_audio_samples] 
                # Pad with start silence and the (potentially zero) remaining end silence
                return np.pad(trimmed_audio, (start_pad_samples, trimmed_end_padding), mode='constant')

    except Exception as e:
        logger.error(f"Error padding/trimming audio to length {target_length}s: {e}", exc_info=True)
        return None 