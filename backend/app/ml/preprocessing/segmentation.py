import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from backend.app.ml.utils.audio_utils import load_audio_from_file, ensure_audio_format

logger = logging.getLogger(__name__)

class AudioSegmenter:
    """
    Class for segmenting audio into individual utterances.
    Uses energy-based methods to detect start and end points of speech.
    """
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """
        Initialize the audio segmenter.
        
        Args:
            params: Parameters for segmentation
        """
        # Default parameters
        self.default_params = {
            "min_segment_length": 0.2,    # Minimum segment length in seconds
            "max_segment_length": 2.0,    # Maximum segment length in seconds
            "silence_threshold": 0.02,    # Threshold for silence detection (0-1)
            "min_silence_length": 0.1,    # Minimum silence length in seconds to split segments
            "frame_length": 0.025,        # Frame length in seconds for energy calculation
            "pad_silence": 0.1,           # Amount of silence to pad at start/end (seconds)
            "smooth_window_length": 5,    # Window length for energy smoothing
            "overlap": 0.5                # Overlap percentage (0-1)
        }
        
        # Update with custom parameters if provided
        self.params = self.default_params.copy()
        if params:
            self.params.update(params)
        
        logger.debug(f"Initialized AudioSegmenter with parameters: {self.params}")
    
    def segment_audio(self, audio: np.ndarray, sample_rate: int) -> List[Tuple[np.ndarray, Dict[str, Any]]]:
        """
        Segment audio into individual utterances.
        
        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate of the audio
            
        Returns:
            List of tuples containing (segment_audio, metadata)
        """
        # Ensure audio is mono
        if len(audio.shape) > 1 and audio.shape[1] > 1:
            logger.warning("Converting stereo audio to mono")
            audio = np.mean(audio, axis=1)
        
        # Calculate energy profile
        energy = self._calculate_energy(audio, sample_rate)
        
        # Smooth energy to reduce noise
        energy_smooth = self._smooth_energy(energy)
        
        # Find segments based on energy
        segments_times = self._find_segments(energy_smooth, sample_rate)
        
        # Extract segments from audio
        segments = []
        for start_time, end_time in segments_times:
            # Convert frame indices to sample indices
            start_sample = int(start_time * sample_rate)
            end_sample = int(end_time * sample_rate)

            # Apply 20ms margin
            margin_ms = 20.0
            margin_samples = int(margin_ms * sample_rate / 1000)
            
            # Calculate adjusted start/end based on the 100ms padding
            adjusted_start_sample = max(0, start_sample - margin_samples)
            adjusted_end_sample = min(len(audio), end_sample + margin_samples) # Ensure we don't exceed audio length

            # --- FIX: Cast indices to int before slicing ---
            start_idx = int(adjusted_start_sample)
            end_idx = int(adjusted_end_sample)
            # --- END FIX ---

            # Extract the segment with the added margin
            # Check if indices are valid before slicing
            if start_idx >= end_idx:
                logger.warning(f"Skipping segment due to invalid indices after margin: start={start_idx}, end={end_idx} (orig time: {start_time:.3f}-{end_time:.3f})")
                continue
            segment = audio[start_idx:end_idx]
            
            # Pad the segment with silence (using the margin-included segment)
            padded_segment = self._pad_segment(segment, sample_rate)
            
            # Create metadata for the segment
            segment_meta = {
                "start_time": adjusted_start_sample / sample_rate, # Store adjusted start/end times
                "end_time": adjusted_end_sample / sample_rate,
                "original_start_time": start_time, # Original times from _find_segments
                "original_end_time": end_time,
                "duration": (adjusted_end_sample - adjusted_start_sample) / sample_rate,
                "samples": len(segment),
                "max_amplitude": np.max(np.abs(segment)),
                "rms": np.sqrt(np.mean(segment**2))
            }
            
            segments.append((padded_segment, segment_meta))
        
        logger.info(f"Segmented audio into {len(segments)} segments")
        return segments
    
    def _calculate_energy(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Calculate frame-by-frame energy of audio.
        
        Args:
            audio: Audio data
            sample_rate: Sample rate
            
        Returns:
            Array of energy values
        """
        # Calculate frame parameters
        frame_length_samples = int(self.params["frame_length"] * sample_rate)
        hop_length_samples = int(self.params["frame_length"] * (1 - self.params["overlap"]) * sample_rate)
        
        # Pad audio to ensure even framing
        pad_length = (len(audio) // hop_length_samples + 1) * hop_length_samples - len(audio)
        audio_padded = np.pad(audio, (0, pad_length))
        
        # Calculate number of frames
        num_frames = (len(audio_padded) - frame_length_samples) // hop_length_samples + 1
        
        # Initialize energy array
        energy = np.zeros(num_frames)
        
        # Calculate energy for each frame
        for i in range(num_frames):
            start = i * hop_length_samples
            end = start + frame_length_samples
            frame = audio_padded[start:end]
            energy[i] = np.sum(frame**2) / frame_length_samples
        
        # Normalize energy to 0-1 range
        if np.max(energy) > 0:
            energy = energy / np.max(energy)
        
        return energy
    
    def _smooth_energy(self, energy: np.ndarray) -> np.ndarray:
        """
        Apply smoothing to energy profile.
        
        Args:
            energy: Energy profile
            
        Returns:
            Smoothed energy profile
        """
        window_length = self.params["smooth_window_length"]
        
        # Use uniform filter for smoothing
        if window_length > 1:
            from scipy.ndimage import uniform_filter1d
            energy_smooth = uniform_filter1d(energy, size=window_length)
        else:
            energy_smooth = energy
        
        return energy_smooth
    
    def _find_segments(self, energy: np.ndarray, sample_rate: int) -> List[Tuple[float, float]]:
        """
        Find segments based on energy profile.
        
        Args:
            energy: Energy profile
            sample_rate: Sample rate
            
        Returns:
            List of (start_time, end_time) tuples
        """
        # Calculate parameters in frames
        min_segment_frames = int(self.params["min_segment_length"] / self.params["frame_length"] * 2)
        max_segment_frames = int(self.params["max_segment_length"] / self.params["frame_length"] * 2)
        min_silence_frames = int(self.params["min_silence_length"] / self.params["frame_length"] * 2)
        
        # --- DEBUG: Log energy profile --- 
        logger.debug(f"[_find_segments] Smoothed energy profile (first 50 values): {energy[:50]}")
        logger.debug(f"[_find_segments] Energy stats: Min={np.min(energy):.4f}, Max={np.max(energy):.4f}, Mean={np.mean(energy):.4f}")
        logger.debug(f"[_find_segments] Silence threshold param: {self.params['silence_threshold']}")
        # --- END DEBUG ---

        # Find frames above threshold
        active_frames = energy > self.params["silence_threshold"]
        
        # Find transitions (0->1 or 1->0)
        transitions = np.diff(active_frames.astype(int))
        rise_frames = np.where(transitions == 1)[0] + 1
        fall_frames = np.where(transitions == -1)[0] + 1
        
        # Handle edge cases
        if active_frames[0]:
            # Audio starts with active frame
            rise_frames = np.insert(rise_frames, 0, 0)
        
        if active_frames[-1]:
            # Audio ends with active frame
            fall_frames = np.append(fall_frames, len(active_frames))
        
        # Pair rises and falls to form segments
        segments = []
        logger.debug(f"[_find_segments] Rise frames: {rise_frames}")
        logger.debug(f"[_find_segments] Fall frames: {fall_frames}")
        logger.debug(f"[_find_segments] Min segment frames: {min_segment_frames}")
        for i in range(min(len(rise_frames), len(fall_frames))):
            start_frame = rise_frames[i]
            end_frame = fall_frames[i]
            segment_length = end_frame - start_frame
            logger.debug(f"[_find_segments] Potential segment {i+1}: start={start_frame}, end={end_frame}, length={segment_length}") # Log potential segment
            
            # Skip segments that are too short
            if segment_length < min_segment_frames:
                continue
            
            # Split segments that are too long
            if segment_length > max_segment_frames:
                # Find low energy points within the segment
                segment_energy = energy[start_frame:end_frame]
                
                # Potential split points are low energy frames
                # that are surrounded by at least min_silence_frames/2 frames of low energy
                potential_splits = []
                for j in range(min_silence_frames, len(segment_energy) - min_silence_frames):
                    if (segment_energy[j] < self.params["silence_threshold"] and
                        np.all(segment_energy[j-min_silence_frames//2:j+min_silence_frames//2] < 
                              self.params["silence_threshold"])):
                        potential_splits.append(j)
                
                # Group adjacent split points
                split_groups = []
                current_group = []
                for j in potential_splits:
                    if not current_group or j - current_group[-1] <= min_silence_frames:
                        current_group.append(j)
                    else:
                        split_groups.append(current_group)
                        current_group = [j]
                if current_group:
                    split_groups.append(current_group)
                
                # Use the middle point of each group as a split point
                split_points = [int(np.mean(group)) for group in split_groups]
                
                # If we found split points, use them to split the segment
                if split_points:
                    # Convert split points to absolute frame indices
                    split_points = [start_frame + p for p in split_points]
                    
                    # Create subsegments
                    subsegments = [(start_frame, split_points[0])]
                    for j in range(len(split_points) - 1):
                        subsegments.append((split_points[j], split_points[j+1]))
                    subsegments.append((split_points[-1], end_frame))
                    
                    # Only keep subsegments that are long enough
                    for sub_start, sub_end in subsegments:
                        if sub_end - sub_start >= min_segment_frames:
                            segments.append((sub_start, sub_end))
                else:
                    # If no good split points, just keep the full segment
                    segments.append((start_frame, end_frame))
            else:
                # Segment is within acceptable length
                segments.append((start_frame, end_frame))
        
        # --- MODIFIED: Convert frame indices to time --- 
        hop_time = self.params["frame_length"] * (1.0 - self.params["overlap"])
        frame_time = self.params["frame_length"]
        segments_time = []
        for start_frame, end_frame in segments:
            st = start_frame * hop_time
            et = end_frame * hop_time + frame_time # Add frame duration to end time
            segments_time.append((st, et))
        logger.debug(f"[_find_segments] Returning time segments: {segments_time}")
        # --- END MODIFICATION ---
        
        return segments_time
    
    def _pad_segment(self, segment: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Add silence padding to segment.
        
        Args:
            segment: Audio segment
            sample_rate: Sample rate
            
        Returns:
            Padded segment
        """
        # Calculate padding in samples
        pad_samples = int(self.params["pad_silence"] * sample_rate)
        
        # Pad with zeros
        padded_segment = np.pad(segment, (pad_samples, pad_samples), mode='constant')
        
        return padded_segment

def save_segment(segment_data, filename, sample_rate=16000):
    """Save a segment to a WAV file with optional normalization.
    
    Args:
        segment_data (np.ndarray): The audio data to save
        filename (str): The output filename
        sample_rate (int): The sample rate of the audio
        
    Returns:
        str: The path to the saved file
    """
    from backend.app.ml.utils.audio_utils import ensure_audio_format
    import soundfile as sf
    
    # Ensure segment_data is properly formatted
    segment_data, sample_rate = ensure_audio_format(
        segment_data, sample_rate, target_sr=sample_rate, mono=True, normalize=True
    )
    
    # Convert target to path if needed
    filename = str(filename)
    
    # Save as WAV file
    sf.write(filename, segment_data, sample_rate, subtype='PCM_16')
    # STORAGE-OPERATION: Will be replaced by DatabaseManager
    
    # Optionally create MP3 version for better browser compatibility
    try:
        import os
        import subprocess
        from pathlib import Path
        
        # Create MP3 version for browser compatibility if ffmpeg is available
        mp3_filename = os.path.splitext(filename)[0] + '.mp3'
        ogg_filename = os.path.splitext(filename)[0] + '.ogg'
        
        # Only create if source WAV exists and is valid
        if os.path.exists(filename) and os.path.getsize(filename) > 44:  # WAV header is 44 bytes
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
            
            # Check if ffmpeg is installed
            try:
                # Try MP3 conversion
                subprocess.run(
                    ['ffmpeg', '-y', '-i', filename, 
                     '-codec:a', 'libmp3lame', '-qscale:a', '2', 
                     '-ar', '44100', '-ac', '1', mp3_filename],
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    check=True
                )
                
                # Try OGG conversion
                subprocess.run(
                    ['ffmpeg', '-y', '-i', filename, 
                     '-codec:a', 'libvorbis', '-qscale:a', '3', 
                     '-ar', '44100', ogg_filename],
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    check=True
                )
            except (subprocess.SubprocessError, FileNotFoundError) as e:
                # Just log the error but continue - WAV file still works
                print(f"Error creating MP3/OGG version: {str(e)}")
    except Exception as e:
        # Silently ignore errors in conversion - WAV file is still available
        print(f"Could not create MP3/OGG versions: {str(e)}")
    
    return filename

def segment_on_silence(audio: np.ndarray, sample_rate: int, **kwargs) -> List[Tuple[np.ndarray, Dict[str, Any]]]:
    """
    Segment an audio signal based on silence.
    
    A convenience function that uses AudioSegmenter internally.
    
    Args:
        audio: Audio data as numpy array
        sample_rate: Sample rate of the audio
        **kwargs: Parameters to override defaults
        
    Returns:
        List of tuples containing (segment_audio, metadata)
    """
    segmenter = AudioSegmenter(kwargs)
    return segmenter.segment_audio(audio, sample_rate)

# Helper function to save segments
# DB-OPERATION: create file
def save_segment(segment_data, filename, sample_rate=16000):
    """
    Save an audio segment to a file.
    
    Args:
        segment_data: Audio data as numpy array
        filename: Path to save the file
        sample_rate: Sample rate to use
    """
    import soundfile as sf
    sf.write(filename, segment_data, sample_rate)
    # STORAGE-OPERATION: Will be replaced by DatabaseManager
