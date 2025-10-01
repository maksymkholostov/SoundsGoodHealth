import logging
import numpy as np
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class AudioNormalizer:
    """
    Class for normalizing audio levels.
    Provides methods for peak normalization, RMS normalization, and DC offset removal.
    """
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """
        Initialize the audio normalizer.
        
        Args:
            params: Parameters for normalization
        """
        # Default parameters
        self.default_params = {
            "target_peak": 0.9,         # Target peak amplitude (0-1)
            "target_rms": 0.2,          # Target RMS level (0-1)
            "normalization_type": "peak",  # 'peak' or 'rms'
            "remove_dc_offset": True,   # Whether to remove DC offset
            "clip_threshold": 1.0       # Threshold for clipping prevention
        }
        
        # Update with custom parameters if provided
        self.params = self.default_params.copy()
        if params:
            self.params.update(params)
        
        logger.debug(f"Initialized AudioNormalizer with parameters: {self.params}")
    
    def normalize(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply normalization to audio.
        
        Args:
            audio: Audio data as numpy array
            
        Returns:
            Normalized audio
        """
        # Make a copy to avoid modifying the verified
        audio_out = audio.copy()
        
        # Remove DC offset if requested
        if self.params["remove_dc_offset"]:
            audio_out = self.remove_dc_offset(audio_out)
        
        # Apply normalization based on type
        if self.params["normalization_type"] == "peak":
            audio_out = self.peak_normalize(audio_out)
        elif self.params["normalization_type"] == "rms":
            audio_out = self.rms_normalize(audio_out)
        else:
            logger.warning(f"Unknown normalization type: {self.params['normalization_type']}")
        
        return audio_out
    
    # DB-OPERATION: delete unknown
    def remove_dc_offset(self, audio: np.ndarray) -> np.ndarray:
        """
        Remove DC offset from audio.
        
        Args:
            audio: Audio data
            
        Returns:
            Audio with DC offset removed
        """
        # Calculate mean value (DC offset)
        dc_offset = np.mean(audio)
        
        # Remove DC offset
        return audio - dc_offset
    
    def peak_normalize(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply peak normalization to audio.
        
        Args:
            audio: Audio data
            
        Returns:
            Peak-normalized audio
        """
        # Calculate current peak
        current_peak = np.max(np.abs(audio))
        
        # Avoid division by zero
        if current_peak > 0:
            # Calculate normalization factor
            norm_factor = self.params["target_peak"] / current_peak
            
            # Apply normalization
            return audio * norm_factor
        else:
            logger.warning("Audio is silent (all zeros), cannot perform peak normalization")
            return audio
    
    def rms_normalize(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply RMS normalization to audio.
        
        Args:
            audio: Audio data
            
        Returns:
            RMS-normalized audio
        """
        # Calculate current RMS
        current_rms = np.sqrt(np.mean(audio**2))
        
        # Avoid division by zero
        if current_rms > 0:
            # Calculate normalization factor
            norm_factor = self.params["target_rms"] / current_rms
            
            # Apply normalization
            normalized = audio * norm_factor
            
            # Prevent clipping
            max_abs = np.max(np.abs(normalized))
            if max_abs > self.params["clip_threshold"]:
                logger.warning(f"RMS normalization would cause clipping, scaling down to prevent it")
                normalized = normalized * (self.params["clip_threshold"] / max_abs)
            
            return normalized
        else:
            logger.warning("Audio is silent (all zeros), cannot perform RMS normalization")
            return audio
    
    def adaptive_normalize(self, audio: np.ndarray, method: str = "auto") -> np.ndarray:
        """
        Apply adaptive normalization based on audio characteristics.
        
        Args:
            audio: Audio data
            method: Normalization method ('auto', 'peak', or 'rms')
            
        Returns:
            Normalized audio
        """
        # Remove DC offset
        audio = self.remove_dc_offset(audio)
        
        if method == "auto":
            # Calculate crest factor (peak to RMS ratio)
            peak = np.max(np.abs(audio))
            rms = np.sqrt(np.mean(audio**2))
            
            if rms > 0:
                crest_factor = peak / rms
            else:
                crest_factor = 0
            
            # Choose method based on crest factor
            if crest_factor > 6.0:  # High dynamic range audio
                logger.debug(f"High crest factor ({crest_factor:.2f}), using RMS normalization")
                method = "rms"
            else:
                logger.debug(f"Normal crest factor ({crest_factor:.2f}), using peak normalization")
                method = "peak"
        
        # Apply the selected normalization
        if method == "peak":
            return self.peak_normalize(audio)
        elif method == "rms":
            return self.rms_normalize(audio)
        else:
            logger.warning(f"Unknown normalization method: {method}")
            return audio
