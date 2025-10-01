"""
Recording analyzer for audio quality assessment and visualization.

This module provides tools for analyzing the quality of audio recordings,
generating visualizations, and computing statistics.
"""
import os
import numpy as np
import librosa
import librosa.display
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from io import BytesIO
import base64
from typing import Dict, List, Any, Tuple, Optional
import json
import logging
import soundfile as sf
from backend.app.ml.utils.audio_utils import load_audio_from_file

logger = logging.getLogger(__name__)

class RecordingAnalyzer:
    """
    Analyzer for audio recordings, providing quality metrics and visualizations.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the RecordingAnalyzer.
        
        Args:
            config: Configuration parameters for analysis
        """
        self.config = config or {}
    
    def analyze_recording(self, audio_path: str) -> Dict[str, Any]:
        """
        Analyze a single audio recording for quality and characteristics.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            # Load audio using robust loader
            y, sr = load_audio_from_file(audio_path)
            
            # Basic metrics
            duration = librosa.get_duration(y=y, sr=sr)
            rms = np.sqrt(np.mean(y**2))
            zero_crossings = librosa.zero_crossings(y).sum()
            zero_crossing_rate = zero_crossings / len(y)
            
            # Signal-to-noise ratio estimation
            # We'll use a simple method: compare energy in the signal to energy in 
            # what we assume are silence regions (lowest 5% amplitude frames)
            y_abs = np.abs(y)
            y_sorted = np.sort(y_abs)
            noise_threshold = y_sorted[int(len(y_sorted) * 0.05)]
            noise_mask = y_abs <= noise_threshold
            signal_mask = ~noise_mask
            
            if noise_mask.sum() > 0 and signal_mask.sum() > 0:
                noise_power = np.mean(y[noise_mask] ** 2)
                signal_power = np.mean(y[signal_mask] ** 2)
                
                if noise_power > 0:
                    snr = 10 * np.log10(signal_power / noise_power)
                else:
                    snr = 100.0  # High value to indicate very little noise
            else:
                snr = 0.0
            
            # Spectral centroid
            spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr).mean()
            
            # Spectral bandwidth
            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr).mean()
            
            # Spectral rolloff
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr).mean()
            
            # MFCC statistics (for overall timbral characteristics)
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            mfcc_mean = mfcc.mean(axis=1)
            mfcc_var = mfcc.var(axis=1)
            
            # Silence detection
            silence_threshold = 0.01  # Adjustable threshold for silence
            is_silence = np.abs(y) < silence_threshold
            silence_ratio = np.sum(is_silence) / len(y)
            
            # Prepare results
            results = {
                "file_path": audio_path,
                "duration_seconds": float(duration),
                "rms_amplitude": float(rms),
                "zero_crossing_rate": float(zero_crossing_rate),
                "signal_to_noise_ratio_db": float(snr),
                "spectral_centroid_hz": float(spectral_centroid),
                "spectral_bandwidth_hz": float(spectral_bandwidth),
                "spectral_rolloff_hz": float(spectral_rolloff),
                "mfcc_means": [float(x) for x in mfcc_mean],
                "mfcc_variances": [float(x) for x in mfcc_var],
                "silence_ratio": float(silence_ratio),
                "quality_score": self._calculate_quality_score(
                    rms, snr, silence_ratio, spectral_bandwidth
                )
            }
            
            return results
            
        except Exception as e:
            logger.error(f"Error analyzing recording {audio_path}: {str(e)}")
            return {
                "file_path": audio_path,
                "error": str(e)
            }
    
    def _calculate_quality_score(self, 
                                rms: float, 
                                snr: float, 
                                silence_ratio: float,
                                spectral_bandwidth: float) -> float:
        """
        Calculate an overall quality score based on various metrics.
        
        Args:
            rms: Root mean square amplitude
            snr: Signal-to-noise ratio
            silence_ratio: Ratio of silence to total duration
            spectral_bandwidth: Spectral bandwidth
            
        Returns:
            Quality score from 0 to 100
        """
        # Normalize each component to contribute to a 0-100 score
        # These weights and normalizations can be tuned based on empirical results
        
        # RMS should be in a good range (not too quiet, not clipping)
        # Ideal range around 0.1 to 0.5
        rms_score = 100 * (1 - abs(min(rms, 0.5) - 0.2) / 0.2)
        rms_score = max(0, min(100, rms_score))
        
        # SNR should be as high as possible, with diminishing returns after 25dB
        snr_score = 100 * min(snr, 25) / 25
        snr_score = max(0, min(100, snr_score))
        
        # Silence ratio should be low but not zero for speech
        # Ideal around 0.1-0.2 for speech with natural pauses
        silence_score = 100 * (1 - abs(silence_ratio - 0.15) / 0.15)
        silence_score = max(0, min(100, silence_score))
        
        # Spectral bandwidth should be in a range typical for clear speech
        # For speech, 2-4kHz is typical
        bandwidth_khz = spectral_bandwidth / 1000
        bandwidth_score = 100 * (1 - abs(min(bandwidth_khz, 5) - 3) / 3)
        bandwidth_score = max(0, min(100, bandwidth_score))
        
        # Weight the components
        weights = {
            "rms": 0.2, 
            "snr": 0.4,
            "silence": 0.2, 
            "bandwidth": 0.2
        }
        
        weighted_score = (
            weights["rms"] * rms_score +
            weights["snr"] * snr_score +
            weights["silence"] * silence_score +
            weights["bandwidth"] * bandwidth_score
        )
        
        return round(weighted_score, 1)
    
    def generate_waveform_image(self, 
                              audio_path: str, 
                              width: int = 800, 
                              height: int = 300) -> Optional[str]:
        """
        Generate a waveform visualization for an audio file.
        
        Args:
            audio_path: Path to the audio file
            width: Image width in pixels
            height: Image height in pixels
            
        Returns:
            Base64-encoded PNG image or None if generation fails
        """
        try:
            # Load audio using robust loader
            y, sr = load_audio_from_file(audio_path)
            
            # Create plot
            fig = Figure(figsize=(width/100, height/100), dpi=100)
            ax = fig.add_subplot(1, 1, 1)
            librosa.display.waveshow(y, sr=sr, ax=ax)
            ax.set_title('Waveform')
            fig.tight_layout()
            
            # Convert to base64 image
            buf = BytesIO()
            fig.savefig(buf, format='png')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            plt.close(fig)
            
            return img_base64
            
        except Exception as e:
            logger.error(f"Error generating waveform for {audio_path}: {str(e)}")
            return None
    
    def generate_spectrogram_image(self, 
                                 audio_path: str, 
                                 width: int = 800, 
                                 height: int = 300) -> Optional[str]:
        """
        Generate a spectrogram visualization for an audio file.
        
        Args:
            audio_path: Path to the audio file
            width: Image width in pixels
            height: Image height in pixels
            
        Returns:
            Base64-encoded PNG image or None if generation fails
        """
        try:
            # Load audio using robust loader
            y, sr = load_audio_from_file(audio_path)
            
            # Create spectrogram
            D = librosa.amplitude_to_db(
                np.abs(librosa.stft(y)), ref=np.max
            )
            
            # Create plot
            fig = Figure(figsize=(width/100, height/100), dpi=100)
            ax = fig.add_subplot(1, 1, 1)
            img = librosa.display.specshow(
                D, sr=sr, x_axis='time', y_axis='log', ax=ax
            )
            ax.set_title('Spectrogram')
            fig.colorbar(img, ax=ax, format='%+2.0f dB')
            fig.tight_layout()
            
            # Convert to base64 image
            buf = BytesIO()
            fig.savefig(buf, format='png')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            plt.close(fig)
            
            return img_base64
            
        except Exception as e:
            logger.error(f"Error generating spectrogram for {audio_path}: {str(e)}")
            return None
    
    def compare_recordings(self, 
                          audio_paths: List[str], 
                          metrics: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Compare multiple recordings based on selected metrics.
        
        Args:
            audio_paths: List of paths to audio files
            metrics: List of metrics to compare (if None, compare all)
            
        Returns:
            Dictionary containing comparison results
        """
        if not metrics:
            metrics = ["duration_seconds", "rms_amplitude", "signal_to_noise_ratio_db", 
                      "spectral_centroid_hz", "silence_ratio", "quality_score"]
        
        results = []
        for audio_path in audio_paths:
            analysis = self.analyze_recording(audio_path)
            if "error" not in analysis:
                # Extract just the requested metrics
                filtered_analysis = {
                    "file_path": os.path.basename(audio_path),
                    **{k: analysis[k] for k in metrics if k in analysis}
                }
                results.append(filtered_analysis)
        
        return {
            "metrics": metrics,
            "recordings": results
        }
    
    def analyze_recordings_in_directory(self, 
                                      directory: str,
                                      include_visualizations: bool = False) -> Dict[str, Any]:
        """
        Analyze all recordings in a directory.
        
        Args:
            directory: Directory containing audio files
            include_visualizations: Whether to include waveform and spectrogram visualizations
            
        Returns:
            Dictionary containing analysis results for all recordings
        """
        if not os.path.exists(directory):
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
            return {"error": f"Directory not found: {directory}"}
        
        audio_files = [
            os.path.join(directory, f) 
            for f in os.listdir(directory) 
            if f.endswith(('.wav', '.mp3', '.flac'))
        ]
        
        if not audio_files:
            return {"error": f"No audio files found in: {directory}"}
        
        results = []
        for audio_file in audio_files:
            analysis = self.analyze_recording(audio_file)
            
            if include_visualizations:
                analysis["waveform_image"] = self.generate_waveform_image(audio_file)
                analysis["spectrogram_image"] = self.generate_spectrogram_image(audio_file)
            
            results.append(analysis)
        
        # Calculate aggregate statistics
        metrics = ["duration_seconds", "rms_amplitude", "signal_to_noise_ratio_db", 
                  "silence_ratio", "quality_score"]
        
        summary = {}
        for metric in metrics:
            values = [r[metric] for r in results if metric in r and "error" not in r]
            if values:
                summary[f"{metric}_mean"] = float(np.mean(values))
                summary[f"{metric}_median"] = float(np.median(values))
                summary[f"{metric}_min"] = float(np.min(values))
                summary[f"{metric}_max"] = float(np.max(values))
                summary[f"{metric}_std"] = float(np.std(values))
        
        return {
            "directory": directory,
            "file_count": len(results),
            "summary_statistics": summary,
            "recordings": results
        }
    
    # DB-OPERATION: create unknown
    def save_analysis_results(self, 
                            results: Dict[str, Any], 
                            output_path: str) -> bool:
        """
        Save analysis results to a JSON file.
        
        Args:
            results: Analysis results dictionary
            output_path: Path to save the results
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w') as f:
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                json.dump(results, f, indent=2)
            
            return True
        
        except Exception as e:
            logger.error(f"Error saving analysis results: {str(e)}")
            return False
