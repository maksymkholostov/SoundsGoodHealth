"""
Audio augmentation module for creating variations of processed audio.

This module provides classes and functions for augmenting audio recordings
to increase the size and diversity of the training dataset.
"""
import os
import numpy as np
import librosa
import soundfile as sf
import random
from typing import List, Dict, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class AudioAugmentor:
    """
    Class to apply various augmentation techniques to audio recordings.
    
    This class implements methods to create variations of audio recordings
    to enhance model training by increasing the diversity of the dataset.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the AudioAugmentor with configuration parameters.
        
        Args:
            config: Dictionary containing configuration parameters for augmentation.
                   If None, default parameters will be used.
        """
        self.config = config or {}
        
        # Default configuration values
        self.default_config = {
            'pitch_shift_range': (-2, 2),  # Semitones
            'volume_adjust_range': (-6, 6),  # dB
            'time_shift_range': (-50, 50),  # Milliseconds
            'noise_level_range': (0.001, 0.01),  # Amplitude
            'eq_boost_range': (-6, 6),  # dB
            'reverb_level_range': (0.1, 0.3),  # Level
            'num_augmentations_per_sample': 5,  # Number of augmentations to create per sample
        }
        
        # Update default config with provided config
        for key, value in self.config.items():
            if key in self.default_config:
                self.default_config[key] = value
        
        self.config = self.default_config

    def augment_audio(self, audio: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Apply a random combination of augmentation techniques to an audio sample.
        
        Args:
            audio: Audio signal as numpy array
            sample_rate: Sample rate of the audio
            
        Returns:
            Tuple containing:
                - Augmented audio as numpy array
                - Dictionary of applied augmentation parameters
        """
        # Copy the audio to avoid modifying the original
        augmented = np.copy(audio)
        params = {}
        
        # Create a list of available augmentation methods based on enabled flags
        augmentation_methods = []
        method_names = []
        
        # Only add methods that are enabled in the config
        if self.config.get('pitch_shift_enabled', True):
            augmentation_methods.append(self._pitch_shift)
            method_names.append('pitch_shift')
        
        if self.config.get('volume_adjust_enabled', True):
            augmentation_methods.append(self._adjust_volume)
            method_names.append('volume_adjust')
        
        if self.config.get('time_shift_enabled', True):
            augmentation_methods.append(self._time_shift)
            method_names.append('time_shift')
        
        if self.config.get('background_noise_enabled', True):
            augmentation_methods.append(self._add_background_noise)
            method_names.append('background_noise')
        
        if self.config.get('eq_boost_enabled', True):
            augmentation_methods.append(self._apply_eq)
            method_names.append('eq_boost')
        
        if self.config.get('reverb_enabled', True):
            augmentation_methods.append(self._add_reverb)
            method_names.append('reverb')
            
        # If no methods are enabled, return the original audio unchanged
        if not augmentation_methods:
            logger.warning("No augmentation methods are enabled. Returning original audio unchanged.")
            return augmented, {"warning": "No augmentation methods enabled"}
        
        # Calculate all possible non-empty subsets of augmentation methods
        # We use binary representation to enumerate all subsets
        num_methods = len(augmentation_methods)
        # 2^N - 1 possible non-empty subsets (excluding empty set)
        num_subsets = (1 << num_methods) - 1
        
        # Select a random non-empty subset with equal probability
        # Note: random.randint is inclusive of both endpoints
        subset_index = random.randint(1, num_subsets)
        
        # Convert to binary to determine which methods to include
        selected_methods = []
        selected_names = []
        for i in range(num_methods):
            # Check if the i-th bit is set in subset_index
            if subset_index & (1 << i):
                selected_methods.append(augmentation_methods[i])
                selected_names.append(method_names[i])
        
        logger.info(f"Applying augmentation methods: {', '.join(selected_names)}")
        
        # Apply selected methods
        for method in selected_methods:
            augmented, method_params = method(augmented, sample_rate)
            params.update(method_params)
        
        return augmented, params
    
    def _pitch_shift(self, audio: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Apply pitch shifting to audio."""
        # Get the min and max values, ensuring we use the full range
        min_shift, max_shift = self.config['pitch_shift_range']
        
        # Generate a random value from uniform distribution
        n_steps = random.uniform(min_shift, max_shift)
        
        # Use librosa for pitch shifting
        augmented = librosa.effects.pitch_shift(
            y=audio, 
            sr=sample_rate, 
            n_steps=n_steps
        )
        
        return augmented, {'pitch_shift_steps': n_steps}
    
    def _adjust_volume(self, audio: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Adjust the volume of audio."""
        # Get the min and max values, ensuring we use the full range
        min_db, max_db = self.config['volume_adjust_range']
        
        # Generate a random value from uniform distribution
        db_change = random.uniform(min_db, max_db)
        
        # Convert dB to amplitude factor
        factor = 10 ** (db_change / 20)
        augmented = audio * factor
        
        # Clip to avoid distortion
        if np.max(np.abs(augmented)) > 1.0:
            augmented = augmented / np.max(np.abs(augmented))
        
        return augmented, {'volume_adjust_db': db_change}
    
    def _time_shift(self, audio: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Apply time shifting to audio."""
        # Get the min and max values, ensuring we use the full range
        min_shift, max_shift = self.config['time_shift_range']
        
        # Generate a random value from uniform distribution
        shift_ms = random.uniform(min_shift, max_shift)
        
        # Convert milliseconds to samples
        shift_samples = int(shift_ms * sample_rate / 1000)
        
        # Create shifted audio
        augmented = np.zeros_like(audio)
        if shift_samples > 0:
            augmented[shift_samples:] = audio[:len(audio)-shift_samples]
        else:
            augmented[:len(audio)+shift_samples] = audio[-shift_samples:]
        
        return augmented, {'time_shift_ms': shift_ms}
    
    def _add_background_noise(self, audio: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Add random background noise to audio."""
        # Get the min and max values, ensuring we use the full range
        min_level, max_level = self.config['noise_level_range']
        
        # Generate a random value from uniform distribution
        noise_level = random.uniform(min_level, max_level)
        
        # Generate random noise
        noise = np.random.randn(len(audio))
        
        # Adjust noise level relative to audio
        signal_power = np.mean(audio ** 2)
        noise_power = np.mean(noise ** 2)
        noise = noise * np.sqrt(signal_power / noise_power) * noise_level
        
        # Add noise to audio
        augmented = audio + noise
        
        # Normalize if needed
        if np.max(np.abs(augmented)) > 1.0:
            augmented = augmented / np.max(np.abs(augmented))
        
        return augmented, {'noise_level': noise_level}
    
    def _apply_eq(self, audio: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Apply simple equalization by boosting/cutting random frequency bands."""
        # Get the min and max values, ensuring we use the full range
        min_boost, max_boost = self.config['eq_boost_range']
        
        # Generate a random value from uniform distribution
        boost_db = random.uniform(min_boost, max_boost)
        
        # Convert to frequency domain
        D = librosa.stft(audio)
        
        # Select random frequency band to adjust
        band_start = random.randint(0, D.shape[0]//2)
        band_width = random.randint(D.shape[0]//10, D.shape[0]//4)
        band_end = min(band_start + band_width, D.shape[0])
        
        # Apply boost/cut (convert dB to linear scale)
        factor = 10 ** (boost_db / 20)
        D[band_start:band_end, :] *= factor
        
        # Convert back to time domain
        augmented = librosa.istft(D, length=len(audio))
        
        return augmented, {
            'eq_band_start': band_start,
            'eq_band_end': band_end,
            'eq_boost_db': boost_db
        }
    
    def _add_reverb(self, audio: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Add simple reverb effect to audio."""
        # Get the min and max values, ensuring we use the full range
        min_level, max_level = self.config['reverb_level_range']
        
        # Generate a random value from uniform distribution
        reverb_level = random.uniform(min_level, max_level)
        
        # Create a simple impulse response (IR) for reverb
        ir_duration = int(sample_rate * 0.5)  # 500ms impulse response
        ir = np.exp(-np.arange(ir_duration) / (sample_rate * 0.1))
        ir = ir / np.sum(ir)  # Normalize
        
        # Apply convolution for reverb
        reverb = np.convolve(audio, ir)[:len(audio)]
        
        # Mix dry and wet signals
        augmented = (1 - reverb_level) * audio + reverb_level * reverb
        
        return augmented, {'reverb_level': reverb_level}
    
    def generate_augmentations(self, 
                              audio_path: str, 
                              output_dir: str,
                              num_augmentations: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Generate multiple augmented versions of an audio file.
        
        Args:
            audio_path: Path to the input audio file
            output_dir: Directory to save augmented files
            num_augmentations: Number of augmented versions to create
                              (if None, uses config default)
        
        Returns:
            List of dictionaries containing metadata for each augmentation
        """
        if num_augmentations is None:
            num_augmentations = self.config['num_augmentations_per_sample']
        
        # Load audio
        audio, sample_rate = librosa.load(audio_path, sr=None)
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Get base filename
        base_filename = os.path.basename(audio_path)
        name, ext = os.path.splitext(base_filename)
        
        augmentation_metadata = []
        
        # Generate augmentations
        for i in range(num_augmentations):
            # Apply augmentation
            augmented_audio, params = self.augment_audio(audio, sample_rate)
            
            # Create output path
            output_filename = f"{name}_aug{i+1}{ext}"
            output_path = os.path.join(output_dir, output_filename)
            
            # Save augmented audio
            sf.write(output_path, augmented_audio, sample_rate)
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            
            # Store metadata
            metadata = {
                'verified_file': audio_path,
                'augmented_file': output_path,
                'augmentation_id': i+1,
                'parameters': params
            }
            augmentation_metadata.append(metadata)
            
            logger.info(f"Created augmentation {i+1}/{num_augmentations} for {base_filename}")
        
        return augmentation_metadata


class BatchAugmentor:
    """
    Class to handle batch augmentation of multiple audio files.
    
    This class coordinates augmentation of entire directories of audio files,
    organizing the output according to the project's file structure.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the BatchAugmentor.
        
        Args:
            config: Configuration parameters for augmentation
        """
        self.augmentor = AudioAugmentor(config)
    
    def augment_directory(self, 
                        input_dir: str, 
                        output_dir: str,
                        num_augmentations_per_file: Optional[int] = None) -> Dict[str, Any]:
        """
        Augment all audio files in a directory.
        
        Args:
            input_dir: Directory containing audio files to augment
            output_dir: Directory to save augmented files
            num_augmentations_per_file: Number of augmentations to create per file
        
        Returns:
            Dictionary containing metadata about all augmentations
        """
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Find all audio files
        audio_files = []
        for ext in ['.wav', '.mp3', '.flac']:
            audio_files.extend([os.path.join(input_dir, f) for f in os.listdir(input_dir) 
                              if f.lower().endswith(ext)])
        
        logger.info(f"Found {len(audio_files)} audio files in {input_dir}")
        
        all_metadata = []
        
        # Process each file
        for audio_file in audio_files:
            metadata = self.augmentor.generate_augmentations(
                audio_file, 
                output_dir, 
                num_augmentations_per_file
            )
            all_metadata.extend(metadata)
        
        return {
            'input_directory': input_dir,
            'output_directory': output_dir,
            'num_verified_files': len(audio_files),
            'num_augmented_files': len(all_metadata),
            'augmentations': all_metadata
        }
    
    def augment_user_dictionary(self,
                              base_data_dir: str,
                              user_id: str,
                              dictionary_id: str,
                              num_augmentations_per_file: Optional[int] = None) -> Dict[str, Any]:
        """
        Augment all gold standard recordings for a specific user dictionary.
        
        Args:
            base_data_dir: Base data directory
            user_id: User ID
            dictionary_id: Dictionary ID
            num_augmentations_per_file: Number of augmentations per file
            
        Returns:
            Metadata about the augmentation process
        """
        # Define input/output directories based on project structure
        gold_dir = os.path.join(base_data_dir, 'processed', user_id, dictionary_id, 'gold')
        augmented_dir = os.path.join(base_data_dir, 'processed', user_id, dictionary_id, 'augmented')
        
        # Check if gold directory exists
        if not os.path.exists(gold_dir):
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
            error_msg = f"Gold standard directory not found: {gold_dir}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        # Augment all gold standard recordings
        logger.info(f"Augmenting gold standard recordings for user {user_id}, dictionary {dictionary_id}")
        return self.augment_directory(gold_dir, augmented_dir, num_augmentations_per_file)
