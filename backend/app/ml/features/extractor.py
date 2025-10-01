import logging
import numpy as np
import librosa
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

class FeatureExtractor(ABC):
    """Base abstract class for audio feature extraction."""
    
    @abstractmethod
    def extract_features(self, audio_data: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """
        Extract features from audio data.
        
        Args:
            audio_data: Audio data as numpy array
            sample_rate: Sample rate of the audio
            
        Returns:
            Dictionary of extracted features
        """
        pass
    
    @abstractmethod
    def get_feature_names(self) -> List[str]:
        """
        Get the names of features this extractor produces.
        
        Returns:
            List of feature names
        """
        pass


class FullFeatureExtractor(FeatureExtractor):
    """
    Extracts a comprehensive set of audio features including:
    - MFCCs and their derivatives
    - Mel spectrograms
    - Spectral features (centroid, bandwidth, rolloff)
    - Zero-crossing rate
    - RMS energy
    """
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """
        Initialize the feature extractor with specific parameters.
        
        Args:
            params: Dictionary of parameters for feature extraction
        """
        # Default parameters
        self.default_params = {
            "sample_rate": 16000,
            "n_mfcc": 40,
            "n_mels": 128,
            "n_fft": 160,
            "hop_length": 80,
            "win_length": 160,
            "window": "hann",
            "center": True,
            "pad_mode": "reflect"
        }
        
        # Update with custom parameters if provided
        self.params = self.default_params.copy()
        if params:
            self.params.update(params)
        
        logger.debug(f"Initialized FullFeatureExtractor with parameters: {self.params}")
    
    def get_feature_names(self) -> List[str]:
        """Get names of all features this extractor produces."""
        return [
            "mfcc",
            "mfcc_delta",
            "mfcc_delta2", 
            "mel_spectrogram",
            "spectral_centroid",
            "spectral_bandwidth",
            "spectral_rolloff",
            "zero_crossing_rate",
            "rms_energy"
        ]
    
    def extract_features(self, audio_data: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """
        Extract all features from audio data.
        
        Args:
            audio_data: Audio data as numpy array
            sample_rate: Sample rate of the audio
            
        Returns:
            Dictionary of extracted features
        """
        # Ensure audio is mono
        if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
            logger.warning("Converting stereo audio to mono")
            audio_data = np.mean(audio_data, axis=1)
        
        # Resample if necessary
        if sample_rate != self.params["sample_rate"]:
            logger.info(f"Resampling audio from {sample_rate}Hz to {self.params['sample_rate']}Hz")
            audio_data = librosa.resample(
                audio_data, orig_sr=sample_rate, target_sr=self.params["sample_rate"]
            )
            sample_rate = self.params["sample_rate"]
        
        # Extract all features
        features = {}
        
        # Extract mel spectrogram (needed for MFCCs too)
        mel_spec = self._extract_mel_spectrogram(audio_data)
        features['mel_spectrogram'] = mel_spec
        
        # Extract MFCCs and derivatives
        mfcc = self._extract_mfcc(mel_spec)
        features['mfcc'] = mfcc
        
        mfcc_delta = self._extract_mfcc_delta(mfcc)
        features['mfcc_delta'] = mfcc_delta
        
        mfcc_delta2 = self._extract_mfcc_delta2(mfcc)
        features['mfcc_delta2'] = mfcc_delta2
        
        # Extract spectral features
        spectral_centroid = self._extract_spectral_centroid(audio_data)
        features['spectral_centroid'] = spectral_centroid
        
        spectral_bandwidth = self._extract_spectral_bandwidth(audio_data)
        features['spectral_bandwidth'] = spectral_bandwidth
        
        spectral_rolloff = self._extract_spectral_rolloff(audio_data)
        features['spectral_rolloff'] = spectral_rolloff
        
        # Extract time-domain features
        zcr = self._extract_zero_crossing_rate(audio_data)
        features['zero_crossing_rate'] = zcr
        
        rms = self._extract_rms_energy(audio_data)
        features['rms_energy'] = rms
        
        # Add metadata
        features['metadata'] = {
            'duration': len(audio_data) / sample_rate,
            'sample_rate': sample_rate,
            'n_frames': mel_spec.shape[1],
            'extraction_params': self.params
        }
        
        logger.info(f"Successfully extracted {len(features) - 1} feature types")
        return features
    
    def _extract_mel_spectrogram(self, audio_data: np.ndarray) -> np.ndarray:
        """Extract mel spectrogram from audio data."""
        return librosa.feature.melspectrogram(
            y=audio_data, 
            sr=self.params["sample_rate"],
            n_fft=self.params["n_fft"],
            hop_length=self.params["hop_length"],
            win_length=self.params["win_length"],
            window=self.params["window"],
            center=self.params["center"],
            pad_mode=self.params["pad_mode"],
            n_mels=self.params["n_mels"]
        )
    
    def _extract_mfcc(self, mel_spec: np.ndarray) -> np.ndarray:
        """Extract MFCCs from mel spectrogram."""
        return librosa.feature.mfcc(
            S=librosa.power_to_db(mel_spec),
            n_mfcc=self.params["n_mfcc"]
        )
    
    def _extract_mfcc_delta(self, mfcc: np.ndarray) -> np.ndarray:
        """Calculate first-order derivatives of MFCCs."""
        return librosa.feature.delta(mfcc)
    
    def _extract_mfcc_delta2(self, mfcc: np.ndarray) -> np.ndarray:
        """Calculate second-order derivatives of MFCCs."""
        return librosa.feature.delta(mfcc, order=2)
    
    def _extract_spectral_centroid(self, audio_data: np.ndarray) -> np.ndarray:
        """Extract spectral centroid from audio data."""
        return librosa.feature.spectral_centroid(
            y=audio_data,
            sr=self.params["sample_rate"],
            n_fft=self.params["n_fft"],
            hop_length=self.params["hop_length"],
            pad_mode=self.params["pad_mode"]
        )
    
    def _extract_spectral_bandwidth(self, audio_data: np.ndarray) -> np.ndarray:
        """Extract spectral bandwidth from audio data."""
        return librosa.feature.spectral_bandwidth(
            y=audio_data,
            sr=self.params["sample_rate"],
            n_fft=self.params["n_fft"],
            hop_length=self.params["hop_length"],
            pad_mode=self.params["pad_mode"]
        )
    
    def _extract_spectral_rolloff(self, audio_data: np.ndarray) -> np.ndarray:
        """Extract spectral rolloff from audio data."""
        return librosa.feature.spectral_rolloff(
            y=audio_data,
            sr=self.params["sample_rate"],
            n_fft=self.params["n_fft"],
            hop_length=self.params["hop_length"],
            pad_mode=self.params["pad_mode"]
        )
    
    def _extract_zero_crossing_rate(self, audio_data: np.ndarray) -> np.ndarray:
        """Extract zero crossing rate from audio data."""
        return librosa.feature.zero_crossing_rate(
            y=audio_data,
            hop_length=self.params["hop_length"]
        )
    
    def _extract_rms_energy(self, audio_data: np.ndarray) -> np.ndarray:
        """Extract RMS energy from audio data."""
        return librosa.feature.rms(
            y=audio_data,
            hop_length=self.params["hop_length"],
            pad_mode=self.params["pad_mode"]
        )


class CustomFeatureExtractor(FeatureExtractor):
    """
    Custom feature extractor that allows selecting specific features.
    Can be configured with specific features to extract.
    """
    
    def __init__(self, feature_names: List[str], params: Optional[Dict[str, Any]] = None):
        """
        Initialize with selected features.
        
        Args:
            feature_names: List of feature names to extract
            params: Parameters for feature extraction
        """
        self.full_extractor = FullFeatureExtractor(params)
        self.feature_names = feature_names
        
        # Validate feature names
        available_features = self.full_extractor.get_feature_names()
        for name in feature_names:
            if name not in available_features:
                raise ValueError(f"Unknown feature: {name}. Available features: {available_features}")
        
        logger.debug(f"Initialized CustomFeatureExtractor for features: {feature_names}")
    
    # DB-OPERATION: read feature
    def get_feature_names(self) -> List[str]:
        """Get the names of features this extractor will produce."""
        return self.feature_names
    
    def extract_features(self, audio_data: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """
        Extract only the requested features.
        
        Args:
            audio_data: Audio data as numpy array
            sample_rate: Sample rate of the audio
            
        Returns:
            Dictionary of extracted features
        """
        # Extract all features using the full extractor
        all_features = self.full_extractor.extract_features(audio_data, sample_rate)
        
        # Filter to only the requested features
        features = {name: all_features[name] for name in self.feature_names if name in all_features}
        
        # Keep metadata
        features['metadata'] = all_features['metadata']
        
        return features
