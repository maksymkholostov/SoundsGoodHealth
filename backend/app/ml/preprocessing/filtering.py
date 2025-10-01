import logging
import numpy as np
from typing import Dict, Any, Optional, Tuple
from scipy import signal

logger = logging.getLogger(__name__)

class AudioFilter:
    """
    Class for filtering audio data.
    Provides methods for bandpass filtering, pre-emphasis, and noise reduction.
    """
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """
        Initialize the audio filter.
        
        Args:
            params: Parameters for filtering
        """
        # Default parameters
        self.default_params = {
            "bandpass_low": 80.0,        # Low cutoff frequency for bandpass (Hz)
            "bandpass_high": 7800.0,     # High cutoff frequency for bandpass (Hz)
            "pre_emphasis": 0.97,        # Pre-emphasis coefficient
            "use_bandpass": True,        # Whether to apply bandpass filtering
            "use_pre_emphasis": True,    # Whether to apply pre-emphasis
            "bandpass_order": 5,         # Filter order for bandpass
            "noise_reduction_factor": 2.0  # Factor for noise reduction
        }
        
        # Update with custom parameters if provided
        self.params = self.default_params.copy()
        if params:
            self.params.update(params)
        
        logger.debug(f"Initialized AudioFilter with parameters: {self.params}")
    
    def apply_filters(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Apply all configured filters to audio.
        
        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate of the audio
            
        Returns:
            Filtered audio
        """
        # Make a copy to avoid modifying the verified
        audio_out = audio.copy()
        
        # Apply bandpass filtering if enabled
        # --- TEMP DISABLED for debugging silence issue ---
        if self.params["use_bandpass"]:
            audio_out = self.bandpass_filter(
                audio_out, sample_rate, 
                self.params["bandpass_low"], 
                self.params["bandpass_high"]
            )
        
        # Apply pre-emphasis if enabled
        # --- TEMP DISABLED for debugging silence issue ---
        # if self.params["use_pre_emphasis"]:
        #     audio_out = self.pre_emphasis(audio_out, self.params["pre_emphasis"])
        
        # Return original if both disabled for debugging
        # logger.debug("Both bandpass and pre-emphasis are disabled for debugging.")
        # return audio_out # Return the unmodified audio
        return audio_out # Return filtered audio
    
    def bandpass_filter(self, audio: np.ndarray, sample_rate: int, 
                       low_freq: float, high_freq: float) -> np.ndarray:
        """
        Apply bandpass filter to audio.
        
        Args:
            audio: Audio data
            sample_rate: Sample rate
            low_freq: Low cutoff frequency (Hz)
            high_freq: High cutoff frequency (Hz)
            
        Returns:
            Filtered audio
        """
        # Normalize frequencies to Nyquist frequency
        nyquist = sample_rate / 2.0
        low = low_freq / nyquist
        high = high_freq / nyquist
        
        # Ensure frequencies are within valid range
        low = max(0.0, min(low, 1.0))
        high = max(low, min(high, 1.0))
        
        # Create filter
        b, a = signal.butter(
            self.params["bandpass_order"], 
            [low, high], 
            btype='band'
        )
        
        # Apply filter
        return signal.filtfilt(b, a, audio)
    
    def pre_emphasis(self, audio: np.ndarray, coefficient: float = 0.97) -> np.ndarray:
        """
        Apply pre-emphasis filter to audio.
        
        Args:
            audio: Audio data
            coefficient: Pre-emphasis coefficient
            
        Returns:
            Filtered audio
        """
        # Create emphasized signal: y[n] = x[n] - coefficient * x[n-1]
        emphasized = np.append(audio[0], audio[1:] - coefficient * audio[:-1])
        return emphasized
    
    def lowpass_filter(self, audio: np.ndarray, sample_rate: int, cutoff_freq: float) -> np.ndarray:
        """
        Apply lowpass filter to audio.
        
        Args:
            audio: Audio data
            sample_rate: Sample rate
            cutoff_freq: Cutoff frequency (Hz)
            
        Returns:
            Filtered audio
        """
        # Normalize frequency to Nyquist frequency
        nyquist = sample_rate / 2.0
        cutoff = cutoff_freq / nyquist
        
        # Ensure frequency is within valid range
        cutoff = max(0.0, min(cutoff, 1.0))
        
        # Create filter
        b, a = signal.butter(self.params["bandpass_order"], cutoff, btype='low')
        
        # Apply filter
        return signal.filtfilt(b, a, audio)
    
    def highpass_filter(self, audio: np.ndarray, sample_rate: int, cutoff_freq: float) -> np.ndarray:
        """
        Apply highpass filter to audio.
        
        Args:
            audio: Audio data
            sample_rate: Sample rate
            cutoff_freq: Cutoff frequency (Hz)
            
        Returns:
            Filtered audio
        """
        # Normalize frequency to Nyquist frequency
        nyquist = sample_rate / 2.0
        cutoff = cutoff_freq / nyquist
        
        # Ensure frequency is within valid range
        cutoff = max(0.0, min(cutoff, 1.0))
        
        # Create filter
        b, a = signal.butter(self.params["bandpass_order"], cutoff, btype='high')
        
        # Apply filter
        return signal.filtfilt(b, a, audio)
    
    def noise_reduction(self, audio: np.ndarray, noise_profile: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Apply simple spectral subtraction for noise reduction.
        
        Args:
            audio: Audio data
            noise_profile: Noise profile (if None, estimate from audio)
            
        Returns:
            Noise-reduced audio
        """
        from scipy import fft
        
        # If no noise profile provided, estimate from first 200ms of audio
        if noise_profile is None:
            # Assuming 16kHz sample rate, 200ms = 3200 samples
            noise_length = min(3200, len(audio) // 10)
            if noise_length < 100:  # Too short to estimate noise
                return audio
            noise_profile = audio[:noise_length]
        
        # Compute FFT of audio and noise
        n = len(audio)
        audio_fft = fft.rfft(audio)
        
        if len(noise_profile) < n:
            # Zero-pad noise profile if needed
            noise_profile = np.pad(noise_profile, (0, n - len(noise_profile)))
        elif len(noise_profile) > n:
            # Truncate noise profile if needed
            noise_profile = noise_profile[:n]
            
        noise_fft = fft.rfft(noise_profile)
        
        # Compute noise power spectrum
        noise_power = np.abs(noise_fft) ** 2
        
        # Scale noise power by factor
        noise_power = noise_power * self.params["noise_reduction_factor"]
        
        # Compute audio power spectrum
        audio_power = np.abs(audio_fft) ** 2
        
        # Apply spectral subtraction with flooring
        power_diff = np.maximum(audio_power - noise_power, 0.01 * audio_power)
        
        # Compute scaling factor
        scaling = np.sqrt(power_diff / np.maximum(audio_power, 1e-10))
        
        # Apply scaling to audio FFT
        audio_fft_clean = audio_fft * scaling
        
        # Inverse FFT
        audio_clean = fft.irfft(audio_fft_clean)
        
        return audio_clean
        
    def estimate_noise_profile(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Estimate noise profile from quiet parts of audio.
        
        Args:
            audio: Audio data
            sample_rate: Sample rate
            
        Returns:
            Estimated noise profile
        """
        from scipy.signal import find_peaks
        
        # Calculate short-time energy
        frame_length = int(0.025 * sample_rate)  # 25ms frames
        hop_length = int(0.010 * sample_rate)    # 10ms hop
        
        # Calculate energy for each frame
        energy = []
        for i in range(0, len(audio) - frame_length, hop_length):
            frame = audio[i:i+frame_length]
            energy.append(np.sum(frame**2))
        
        energy = np.array(energy)
        
        # Normalize energy
        if np.max(energy) > 0:
            energy = energy / np.max(energy)
        
        # Find the lowest 10% of energy frames
        threshold = np.percentile(energy, 10)
        quiet_indices = np.where(energy <= threshold)[0]
        
        if len(quiet_indices) == 0:
            logger.warning("Could not find quiet segments for noise estimation")
            return np.zeros(min(3200, len(audio) // 10))
        
        # Extract quiet frames
        noise_frames = []
        for idx in quiet_indices:
            start = idx * hop_length
            end = start + frame_length
            if end <= len(audio):
                noise_frames.append(audio[start:end])
        
        # Concatenate frames
        if noise_frames:
            noise_profile = np.concatenate(noise_frames)
            return noise_profile
        else:
            logger.warning("Could not extract noise frames")
            return np.zeros(min(3200, len(audio) // 10))
