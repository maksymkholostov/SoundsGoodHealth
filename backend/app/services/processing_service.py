import os
import logging
import numpy as np
import soundfile as sf
import librosa
from scipy import signal
import io
from enum import Enum
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, BinaryIO, Union
from pathlib import Path
import pyloudnorm as pyln

from backend.app.core.models.recording import Recording, RecordingType
from backend.app.core.repositories.recording_repo import RecordingRepository
from backend.app.core.repositories.dictionary_repo import DictionaryRepository
from backend.app.services.file_service import FileService
from backend.app.ml.preprocessing.segmentation import AudioSegmenter
from backend.app.ml.preprocessing.normalization import AudioNormalizer
from backend.app.ml.preprocessing.filtering import AudioFilter
from backend.app.ml.utils.audio_utils import load_audio_from_file, ensure_audio_format, load_audio_from_bytes, pad_audio
from backend.app.core.exceptions import ProcessingServiceError
from backend.app.services.augmentation_service import AugmentationService
from backend.app.storage.file_manager import FileManager

# Forward declaration to resolve circular import for type hinting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from backend.app.services.recording_service import RecordingService


class NoiseProfile:
    """
    Represents the background noise profile.
    
    Used to calibrate silence detection and noise reduction.
    """
    def __init__(self, audio_data: np.ndarray, sample_rate: int):
        self.audio_data = audio_data
        self.sample_rate = sample_rate
        self.rms = np.sqrt(np.mean(audio_data**2))
        self.max_amplitude = np.max(np.abs(audio_data))
        self.spectral_profile = None
        
        # Calculate spectral profile if there's enough data
        if len(audio_data) > 256:
            # Simple averaged FFT as noise profile
            stft = np.abs(librosa.stft(audio_data))
            self.spectral_profile = np.mean(stft, axis=1)
    
    def get_silence_threshold(self, multiplier: float = 2.5) -> float:
        """
        Calculate a recommended silence threshold based on noise floor.
        
        Args:
            multiplier: Factor to multiply the RMS by
            
        Returns:
            Recommended silence threshold
        """
        return self.rms * multiplier


class ProcessingService:
    """
    Service for audio processing.
    
    Provides business logic for processing audio recordings including:
    - Segmentation
    - Normalization
    - Filtering
    - User verification workflow
    """
    
    def __init__(self, recording_repo: RecordingRepository, file_service: FileService, dictionary_repo: DictionaryRepository):
        """
        Initialize the processing service.
        
        Args:
            recording_repo: Repository for recording operations
            file_service: Service for file operations
            dictionary_repo: Repository for dictionary operations
        """
        self.recording_repo = recording_repo
        self.file_service = file_service
        self.dictionary_repo = dictionary_repo
        self.logger = logging.getLogger(__name__)
        
        # --- ADDED: Assign file_manager from file_service --- 
        self.file_manager = file_service.file_manager
        if not self.file_manager: # Add check
            self.logger.error("FileManager was not properly initialized within ProcessingService!")
            # raise RuntimeError("FileManager not available in ProcessingService")
        # --- END ADDED ---
        
        # Initialize ML components with default parameters
        self.segmenter = AudioSegmenter()
        self.normalizer = AudioNormalizer()
        self.filter = AudioFilter()
        
        # Added: Initialize recording_service reference
        self.recording_service: Optional['RecordingService'] = None
        
        # Store data root (already existing)
        self.data_root = self.file_service.file_manager.data_root
    
    # Added: Setter method for RecordingService
    def set_recording_service(self, recording_service: 'RecordingService'):
        """Set the recording service after initialization to resolve circular dependency."""
        if not self.recording_service:
            self.recording_service = recording_service
            self.logger.info("RecordingService successfully set for ProcessingService.")
        else:
            self.logger.warning("Attempted to reset recording_service when it was already set.")
    
    def _get_class_name(self, class_id: str) -> Optional[str]:
        """Helper to get class name from class ID."""
        sound_class = self.dictionary_repo.get_class_by_id(class_id)
        if not sound_class:
            self.logger.error(f"Could not find class name for class_id: {class_id}")
            return None
        return sound_class.name
    
    def analyze_background_noise(self, audio_data: bytes, duration: float = 3.0) -> Optional[NoiseProfile]:
        """
        Analyze background noise from an audio sample.
        
        Args:
            audio_data: Binary audio data
            duration: Expected duration of the noise sample
            
        Returns:
            NoiseProfile object or None if analysis fails
        """
        try:
            # Convert audio bytes to in-memory file
            audio_io = io.BytesIO(audio_data)
            
            # Load audio with librosa
            y, sr = librosa.load(audio_io, sr=None, mono=True)
            
            # Check if the sample is long enough
            if len(y) / sr < 0.5:  # At least 0.5 seconds
                self.logger.warning("Noise sample too short for analysis")
                return None
                
            # Create noise profile
            profile = NoiseProfile(y, sr)
            self.logger.info("Analyzed background noise: RMS=%.6f, Max=%.6f", profile.rms, profile.max_amplitude)
            return profile
        
        except Exception as e:
            self.logger.error("Error analyzing background noise: %s", str(e))
            return None
    
    def segment_audio(self, audio_data: bytes, noise_profile: Optional[NoiseProfile] = None,
                     min_segment_length: float = 0.2, max_segment_length: float = 1.5, 
                     silence_threshold: Optional[float] = None) -> List[np.ndarray]:
        """
        Segment audio data into individual sound segments.
        
        Args:
            audio_data: Binary audio data
            noise_profile: Optional noise profile for adaptive thresholding
            min_segment_length: Minimum length of a segment in seconds
            max_segment_length: Maximum length of a segment in seconds
            silence_threshold: Threshold for silence detection (0-1)
            
        Returns:
            List of audio segments as numpy arrays
        """
        try:
            # Convert audio bytes to in-memory file
            audio_io = io.BytesIO(audio_data)
            
            # Load audio with librosa
            y, sr = librosa.load(audio_io, sr=None, mono=True)
            
            # Determine silence threshold
            if silence_threshold is None and noise_profile:
                # Use noise profile to set threshold
                silence_threshold = noise_profile.get_silence_threshold()
                self.logger.debug("Using adaptive silence threshold: %.6f", silence_threshold)
            
            # Configure segmenter
            segmentation_params = {
                "min_segment_length": min_segment_length,
                "max_segment_length": max_segment_length,
                "silence_threshold": silence_threshold or 0.03
            }
            
            # Use the ML component for segmentation
            self.segmenter = AudioSegmenter(segmentation_params)
            segments_with_metadata = self.segmenter.segment_audio(y, sr)
            
            # Extract just the audio data from the segments
            segments = [segment for segment, _ in segments_with_metadata]
            
            self.logger.info("Segmented audio into %d segments", len(segments))
            return segments
            
        except Exception as e:
            self.logger.error("Error segmenting audio: %s", str(e))
            return []
    
    def normalize_audio(self, audio: np.ndarray, target_db: float = -23.0) -> np.ndarray:
        """
        Normalize audio to a target LUFS level.
        
        Args:
            audio: Audio data as numpy array
            target_db: Target LUFS level for normalization (default: -23.0)
            
        Returns:
            Normalized audio as numpy array
        """
        try:
            # Use pyloudnorm for LUFS normalization
            import pyloudnorm as pyln
            
            # Default sample rate if not specified
            sr = 16000
            
            # Create BS.1770 meter
            meter = pyln.Meter(sr)
            
            # Measure integrated loudness
            loudness = meter.integrated_loudness(audio)
            
            if not np.isfinite(loudness):
                self.logger.warning(f"Could not measure loudness (got {loudness}). Falling back to peak normalization.")
                # Fall back to peak normalization
                normalization_params = {
                    "target_peak": 0.9,
                    "normalization_type": "peak",
                    "remove_dc_offset": True
                }
                normalizer = AudioNormalizer(normalization_params)
                return normalizer.normalize(audio)
                
            # Calculate gain required to reach target LUFS
            gain_db = target_db - loudness
            gain_linear = 10.0**(gain_db / 20.0)
            
            # Apply gain and clip to avoid distortion
            normalized_audio = audio.astype(np.float32) * gain_linear
            normalized_audio = np.clip(normalized_audio, -1.0, 1.0)
            
            self.logger.debug(f"Normalized audio from {loudness:.2f} LUFS to {target_db:.2f} LUFS (applied gain: {gain_db:.2f} dB)")
            return normalized_audio
            
        except ImportError:
            self.logger.warning("pyloudnorm not available, falling back to peak normalization")
            # Fall back to peak normalization
            normalization_params = {
                "target_peak": 0.9,
                "normalization_type": "peak",
                "remove_dc_offset": True
            }
            normalizer = AudioNormalizer(normalization_params)
            return normalizer.normalize(audio)
        except Exception as e:
            self.logger.error("Error normalizing audio: %s", str(e))
            return audio
    
    def process_audio(self, audio_data: bytes, sr: int = 16000, 
                     noise_profile: Optional[NoiseProfile] = None) -> Tuple[bool, Optional[bytes]]:
        """
        Apply full audio processing pipeline.
        
        Args:
            audio_data: Binary audio data
            sr: Target sample rate
            noise_profile: Optional noise profile for processing
            
        Returns:
            Tuple of (success, processed_audio_bytes)
        """
        try:
            # Convert audio bytes to in-memory file
            audio_io = io.BytesIO(audio_data)
            
            # Load audio with librosa and resample if necessary
            y, sr_orig = librosa.load(audio_io, sr=sr, mono=True)
            
            # Configure components with appropriate parameters
            filtering_params = {
                "use_bandpass": True,
                "bandpass_low": 80.0,
                "bandpass_high": 7800.0,
                "use_pre_emphasis": True
            }
            
            # Configure filter
            self.filter = AudioFilter(filtering_params)
            
            # Apply processing pipeline
            # 1. First filter using the ML component
            filtered_audio = self.filter.apply_filters(y, sr)
            
            # 2. Then normalize to -23 LUFS
            normalized_audio = self.normalize_audio(filtered_audio, target_db=-23.0)
            
            # 3. Apply silence padding - ensure 100ms at beginning and end
            padded_audio = pad_audio(normalized_audio, sr, target_length=1.25, start_silence_ms=100.0, end_silence_ms=100.0)
            
            # Check if padding returned None (segment discarded)
            if padded_audio is None:
                 self.logger.warning("Segment discarded during padding/trimming.")
                 return False, None # Indicate failure if segment was discarded

            # Convert back to bytes with careful normalization preservation
            output_io = io.BytesIO()
            audio_to_save = np.clip(padded_audio, -1.0, 1.0) * 32767
            audio_to_save = audio_to_save.astype(np.int16)
            sf.write(output_io, audio_to_save, sr, format='wav')
            output_io.seek(0)
            
            self.logger.info("Successfully processed audio")
            return True, output_io.read()
        except Exception as e:
            self.logger.error("Error in audio processing pipeline: %s", str(e))
            return False, None
    
    def process_sound(self, raw_sound_instance: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process raw sound, save PENDING segments using UserID and new filename.
        Populates detailed metadata for each segment.
        """
        # Extract identifiers from the raw instance metadata
        recording_id = raw_sound_instance.get('id') # Raw recording ID (e.g., rec_uuid)
        user_id = raw_sound_instance.get('user_id') # User's UUID
        class_id = raw_sound_instance.get('class_id')
        raw_audio_path_str = raw_sound_instance.get('path') 
        username = raw_sound_instance.get('username') # Original username
        class_name = raw_sound_instance.get('class_name') 
        
        # Validation
        if not all([recording_id, user_id, class_id, raw_audio_path_str, username, class_name]):
            self.logger.error(f"Missing critical info (incl. username/classname) for processing {recording_id}")
            return []
        
        try:
            # --- Load Raw Audio --- 
            self.logger.debug(f"[ProcessSound] Loading raw audio from: {raw_audio_path_str}")
            try:
                y, sr = load_audio_from_file(str(raw_audio_path_str))
                self.logger.debug(f"[ProcessSound] Raw audio loaded successfully (sr={sr}, shape={y.shape if isinstance(y, np.ndarray) else 'N/A'})")
            except FileNotFoundError:
                self.logger.error(f"[ProcessSound] Raw audio file NOT FOUND at path: {raw_audio_path_str}")
                return [] # Critical error if file not found
            except Exception as load_err:
                self.logger.error(f"[ProcessSound] Failed to load raw audio from file {raw_audio_path_str}: {load_err}", exc_info=True)
                return [] # Return empty list on load error
            
            # --- Segment Audio --- 
            self.logger.debug(f"[ProcessSound] Starting segmentation for {raw_audio_path_str}")
            segmentation_params = {
                "min_segment_length": 0.2,
                "max_segment_length": 2.0,
                "silence_threshold": 0.01,
                "min_silence_length": 0.1,
                "pad_silence": 0.0  # Segmenter adds 20ms margin internally
            }
            self.segmenter = AudioSegmenter(segmentation_params) 
            
            segmentation_result = None 
            try:
                # Explicitly call segmenter
                segmentation_result = self.segmenter.segment_audio(y, sr)
                self.logger.debug(f"[ProcessSound] Segmentation raw result type: {type(segmentation_result)}") # DEBUG Type
            except Exception as seg_err:
                self.logger.error(f"[ProcessSound] AudioSegmenter call failed: {seg_err}", exc_info=True)
                return [] 

            # Explicitly validate and assign to the variable used in the loop
            segments_with_info = [] # Default to empty list
            if segmentation_result is not None and isinstance(segmentation_result, list):
                segments_with_info = segmentation_result # Assign if valid
                self.logger.info(f"[ProcessSound] Found {len(segments_with_info)} segments after segmentation.")
            else:
                self.logger.warning(f"[ProcessSound] Segmentation did not return a valid list. Found type: {type(segmentation_result)}")
                # segments_with_info remains empty list
                 
            # Log right before loop
            self.logger.debug(f"[ProcessSound] BEFORE LOOP: segments_with_info type={type(segments_with_info)}, length={len(segments_with_info)}")
                 
            # Proceed only if segments were found (redundant check now, but safe)
            if not segments_with_info:
                self.logger.warning(f"[ProcessSound] No valid segments found for {raw_audio_path_str}. Returning empty list.")
                return []
                 
            # --- ADDED: Load Noise Profile (if exists) --- 
            noise_clip = None
            try:
                noise_profile_path = self.file_manager.get_user_noise_profile_path(user_id)
                if noise_profile_path.exists():
                    noise_clip, noise_sr = load_audio_from_file(str(noise_profile_path))
                    if noise_sr != self.target_sample_rate:
                        noise_clip = librosa.resample(noise_clip, orig_sr=noise_sr, target_sr=self.target_sample_rate)
                        self.logger.debug(f"Resampled noise profile to {self.target_sample_rate} Hz.")
                    self.logger.info(f"Loaded noise profile for user {user_id} from {noise_profile_path}")
                else:
                    self.logger.debug(f"No noise profile found for user {user_id} at {noise_profile_path}")
            except ImportError:
                self.logger.error("librosa library not installed. Cannot resample noise profile.")
                noise_clip = None # Cannot use profile if resampling fails
            except Exception as noise_err:
                self.logger.error(f"Error loading noise profile for user {user_id}: {noise_err}", exc_info=True)
                noise_clip = None
            # --- END Load Noise Profile ---
            
            # --- Process and Save Each Segment --- 
            created_segments_metadata: List[Dict[str, Any]] = [] 
 
            self.target_sample_rate = 16000 # Example: Set a default or get from config

            # --- ADDED: Initialize filter and normalizer (if needed) ---
            # These might be configured globally, but let's ensure they exist.
            if not hasattr(self, 'filter'): self.filter = AudioFilter()
            if not hasattr(self, 'normalizer'): self.normalizer = AudioNormalizer() # Ensure normalizer is initialized
            # --- END ADDED ---

            for i, (segment_audio, segment_meta) in enumerate(segments_with_info):
                pending_audio_path: Optional[Path] = None # Define outside try block
                segment_id = None # Define outside try block
                try:
                    # --- DEBUG: Stats immediately after segmentation ---
                    try:
                        seg_min, seg_max = np.min(segment_audio), np.max(segment_audio)
                        seg_mean, seg_rms = np.mean(segment_audio), np.sqrt(np.mean(segment_audio**2))
                        self.logger.debug(f"[Segment {i+1}] Initial Segment Stats: Min={seg_min:.4f}, Max={seg_max:.4f}, Mean={seg_mean:.4f}, RMS={seg_rms:.4f}, Shape={segment_audio.shape}")
                    except Exception as stat_err:
                        self.logger.error(f"[Segment {i+1}] Error calculating initial segment stats: {stat_err}")
                    # --- END DEBUG ---

                    # 1. Format Standardization (as before - includes 100ms padding from segmenter)
                    if not hasattr(self, 'target_sample_rate') or not self.target_sample_rate:
                        self.logger.error("[ProcessSound] target_sample_rate not configured.")
                        continue
                    # --- MODIFIED: Disable normalization in ensure_audio_format --- 
                    segment_data, processed_sr = ensure_audio_format(segment_audio, sr, target_sr=self.target_sample_rate, normalize=False)
                    
                    # --- DEBUG: Stats after ensure_audio_format ---
                    try:
                        fmt_min, fmt_max = np.min(segment_data), np.max(segment_data)
                        fmt_mean, fmt_rms = np.mean(segment_data), np.sqrt(np.mean(segment_data**2))
                        self.logger.debug(f"[Segment {i+1}] After Format Stats:    Min={fmt_min:.4f}, Max={fmt_max:.4f}, Mean={fmt_mean:.4f}, RMS={fmt_rms:.4f}, Shape={segment_data.shape}")
                    except Exception as stat_err:
                        self.logger.error(f"[Segment {i+1}] Error calculating stats after format: {stat_err}")
                    # --- END DEBUG ---

                    # --- ADDED: Filtering --- 
                    # --- TEMP DISABLED for debugging sound loss --- 
                    try:
                        filtered_segment = self.filter.apply_filters(segment_data, processed_sr)
                        self.logger.debug(f"[Segment {i+1}] After filtering: shape={filtered_segment.shape}")
                    except Exception as filter_e:
                        self.logger.error(f"[Segment {i+1}] Filtering failed: {filter_e}", exc_info=True)
                        continue # Skip segment if filtering fails
                    filtered_segment = segment_data # Pass segment_data directly since filtering is disabled
                    # self.logger.debug(f"[Segment {i+1}] Filtering bypassed for debugging.") # Commented out bypass log
                    # --- END Filtering (Disabled) ---

                    # --- DEBUG: Check amplitude after filtering (which is currently bypassed) ---
                    try:
                        filt_min, filt_max = np.min(filtered_segment), np.max(filtered_segment)
                        filt_mean, filt_rms = np.mean(filtered_segment), np.sqrt(np.mean(filtered_segment**2))
                        self.logger.debug(f"[Segment {i+1}] After Filtering Stats: Min={filt_min:.4f}, Max={filt_max:.4f}, Mean={filt_mean:.4f}, RMS={filt_rms:.4f}")
                    except Exception as stat_err:
                        self.logger.error(f"[Segment {i+1}] Error calculating stats after filtering: {stat_err}")
                    # --- END DEBUG ---

                    # --- ADDED: Noise Reduction (if profile loaded) ---
                    noise_reduced_segment = filtered_segment # Default to filtered data
                    if noise_clip is not None:
                        try:
                            # Ensure noisereduce is imported
                            import noisereduce as nr
                            # Perform noise reduction
                            noise_reduced_segment = nr.reduce_noise(y=filtered_segment, sr=processed_sr, y_noise=noise_clip, prop_decrease=1.0, stationary=True)
                            self.logger.debug(f"[Segment {i+1}] Applied noise reduction.")
                        except ImportError:
                            self.logger.warning("noisereduce library not installed. Skipping noise reduction. Run: pip install noisereduce")
                        except Exception as nr_err:
                            self.logger.error(f"[Segment {i+1}] Noise reduction failed: {nr_err}", exc_info=True)
                            # Continue with filtered_segment if reduction fails
                    else:
                        self.logger.debug("[Segment {i+1}] No noise profile loaded, skipping noise reduction.")
                    # --- END Noise Reduction ---

                    # --- Re-enabled: Fixed Length Padding/Trimming --- 
                    target_duration = 1.25 # seconds
                    padded_segment_data = None # Initialize before try block
                    try:
                        # Apply padding using the imported function
                        padded_segment_data = pad_audio(noise_reduced_segment, processed_sr, target_length=target_duration)
                        if padded_segment_data is None:
                            self.logger.warning(f"[Segment {i+1}] Discarded during padding/trimming (likely excessive length).")
                            continue # Skip to the next segment
                        self.logger.debug(f"[Segment {i+1}] Padded/trimmed to {target_duration}s: shape={padded_segment_data.shape}")
                    except Exception as pad_e:
                        self.logger.error(f"[Segment {i+1}] Padding/trimming failed: {pad_e}", exc_info=True)
                        continue # Skip if padding fails
                    # --- END Padding/Trimming ---

                    # --- MOVED HERE: LUFS Normalization (-23 LUFS) on Padded Audio ---
                    target_lufs = -23.0
                    final_segment_data = padded_segment_data # Use padded data if LUFS fails
                    lufs_normalization_successful = False # Flag to track success
                    try:
                        # Measure loudness on the PADDED data
                        meter = pyln.Meter(processed_sr) 
                        loudness = meter.integrated_loudness(padded_segment_data) 
                        self.logger.debug(f"[Segment {i+1}] Measured LUFS on padded audio: {loudness:.2f}")
                        
                        if not np.isfinite(loudness):
                            self.logger.warning(f"[Segment {i+1}] Could not measure loudness on padded audio (LUFS: {loudness}). Skipping LUFS normalization.")
                            lufs_normalization_successful = False
                            # Keep final_segment_data = padded_segment_data
                        else:
                            # Calculate gain and apply normalization
                            gain_db = target_lufs - loudness
                            gain_linear = 10.0**(gain_db / 20.0)
                            # Apply gain to the padded data
                            final_segment_data = (padded_segment_data.astype(np.float32) * gain_linear)
                            final_segment_data = np.clip(final_segment_data, -1.0, 1.0)
                            self.logger.debug(f"[Segment {i+1}] Normalized padded audio to {target_lufs} LUFS (applied gain: {gain_db:.2f} dB)")
                            lufs_normalization_successful = True

                    except ImportError:
                        self.logger.error("pyloudnorm not installed. Cannot perform LUFS normalization. Please run: pip install pyloudnorm")
                        lufs_normalization_successful = False
                        # Keep final_segment_data = padded_segment_data
                    except ValueError as ve: # Should not happen now with padding, but catch just in case
                        self.logger.error(f"[Segment {i+1}] LUFS normalization ValueError on padded audio: {ve}", exc_info=True)
                        lufs_normalization_successful = False
                        # Keep final_segment_data = padded_segment_data
                    except Exception as norm_e:
                        self.logger.error(f"[Segment {i+1}] LUFS normalization generic error on padded audio: {norm_e}", exc_info=True)
                        lufs_normalization_successful = False
                        # Keep final_segment_data = padded_segment_data
                    # --- END LUFS Normalization ---

                    # --- DEBUG: Stats before saving (Now after padding and LUFS attempt) ---
                    try:
                        final_min, final_max = np.min(final_segment_data), np.max(final_segment_data)
                        final_mean, final_rms = np.mean(final_segment_data), np.sqrt(np.mean(final_segment_data**2))
                        self.logger.debug(f"[Segment {i+1}] Before Save Stats:     Min={final_min:.4f}, Max={final_max:.4f}, Mean={final_mean:.4f}, RMS={final_rms:.4f}, Shape={final_segment_data.shape}")
                    except Exception as stat_err:
                        self.logger.error(f"[Segment {i+1}] Error calculating stats before save: {stat_err}")
                    # --- END DEBUG ---

                    # --- NEW: Save the processed segment audio FIRST ---
                    # pending_audio_path initialized before try block
                    # segment_id initialized before try block
                    try:
                        # Generate IDs (needed for filename)
                        # Extract timestamp from recording_id (e.g., raw_rec_oh_ronrubin_20250807_133025123)
                        # Segment ID format: seg_<class_name>_<username>_<timestamp>_<segment_number>
                        parts = recording_id.split('_')
                        if len(parts) >= 5:
                            # raw_rec_oh_ronrubin_20250807_133025123 -> extract timestamp
                            timestamp_part = f"{parts[-2]}_{parts[-1]}"  # 20250807_133025123
                        else:
                            # Fallback if ID format is unexpected
                            timestamp_part = datetime.now().strftime("%Y%m%d_%H%M%S%f")[:-3]
                        
                        segment_id = f"seg_{class_name.lower()}_{username}_{timestamp_part}_{i+1}"
                        segment_type = RecordingType.PENDING

                        # 1. Get the target path using FileManager
                        pending_audio_path = self.file_manager.get_sound_instance_path(
                            class_name=class_name,
                            user_id=user_id, # Pass user_id
                            recording_type=segment_type,
                            recording_id=segment_id, # Use segment ID for pending file
                            extension='wav'
                        )

                        # 2. Convert numpy array to WAV bytes in memory
                        wav_buffer = io.BytesIO()
                        # Assuming target bit depth is 16, adjust if necessary
                        # Clip data before converting to int16
                        clipped_data = np.clip(final_segment_data, -1.0, 1.0)
                        int16_data = (clipped_data * 32767).astype(np.int16)
                        sf.write(wav_buffer, int16_data, processed_sr, format='WAV', subtype='PCM_16')
                        wav_buffer.seek(0)
                        wav_bytes = wav_buffer.read()

                        # 3. Save the WAV bytes using FileManager's basic save
                        if not self.file_manager.save_file(wav_bytes, pending_audio_path):
                            raise IOError(f"FileManager failed to save pending audio bytes to {pending_audio_path}")

                        self.logger.info(f"[Segment {i+1}] Saved PENDING audio to {pending_audio_path}")

                    except Exception as save_e:
                        self.logger.error(f"[Segment {i+1}] Failed to save PENDING audio data: {save_e}", exc_info=True)
                        # Optional: Attempt cleanup if file was partially created? FileManager.save_file might handle this.
                        continue # Skip this segment if saving fails
                    # --- END Save Audio ---

                    # --- Define relative path AFTER successful save ---
                    # This should only be reached if pending_audio_path is not None
                    relative_pending_path = str(pending_audio_path.relative_to(self.file_manager.get_data_root()))

                    # Extract properties FROM FINAL PROCESSED DATA
                    segment_duration = len(final_segment_data) / processed_sr # Should be target_duration
                    hz = processed_sr
                    physical_type = "mono" # Assuming mono output
                    bit_depth = 16 # Should match saving bit depth

                    # Generate timestamp for metadata
                    segment_timestamp = datetime.now()

                    # --- FIX: Construct metadata dict separately ---
                    pending_metadata_dict_content = {
                        # Copy essential fields from raw instance, avoid overwriting crucial segment info
                        "source_dictionary_id": raw_sound_instance.get("source_dictionary_id"),
                        "source_dictionary_name": raw_sound_instance.get("source_dictionary_name"),
                        "class_name": class_name, # Use class_name derived earlier
                        "username": username,     # Use username derived earlier
                        "original_recording_id": recording_id, # Link to the raw recording
                        "original_file_path": raw_sound_instance.get("relative_wav_path"), # Path of the raw file
                        "processing_flags": {
                             "lufs_normalized": lufs_normalization_successful, # Track if LUFS norm was applied
                             # Add other flags as needed (e.g., filtering, noise reduction)
                        },
                        # Segment-specific info from the segmentation process
                        "segment_index": i + 1,
                        "segment_start_time": segment_meta.get("start_time"),
                        "segment_end_time": segment_meta.get("end_time"),
                        "original_start_time": segment_meta.get("original_start_time"),
                        "original_end_time": segment_meta.get("original_end_time"),
                        # Add other fields from raw_sound_instance.metadata if desired, carefully
                        **(raw_sound_instance.get("metadata", {})),
                        # Overwrite/ensure standard audio properties are for the *segment*
                        "bit_depth": bit_depth,
                        "physical_type": physical_type,
                        "sample_rate": hz,
                        "duration": round(segment_duration, 3) if segment_duration else None,
                        # --- ADDED: Explicitly set status for the metadata dict ---
                        "status": RecordingType.PENDING.value 
                    }
                    # Clean up potentially problematic keys copied from raw metadata
                    pending_metadata_dict_content.pop('path', None)
                    pending_metadata_dict_content.pop('id', None)
                    pending_metadata_dict_content.pop('relative_wav_path', None)
                    pending_metadata_dict_content.pop('recording_type', None)
                    pending_metadata_dict_content.pop('status', None)
                    pending_metadata_dict_content.pop('timestamp', None)
                    pending_metadata_dict_content.pop('updated_at', None)
                    # --- END FIX ---

                    # --- FIX: Create Recording object with explicit args ---
                    pending_metadata_obj = Recording(
                        id=segment_id, # Use the generated segment ID
                        user_id=user_id,
                        class_id=class_id,
                        timestamp=segment_timestamp,
                        updated_at=segment_timestamp,
                        recording_type=RecordingType.PENDING, # Explicitly set type
                        relative_wav_path=relative_pending_path, # Use path relative to data root
                        duration=round(segment_duration, 3) if segment_duration else None,
                        sample_rate=hz,
                        source_sound_id=recording_id, # Link pending segment to original raw recording
                        metadata=pending_metadata_dict_content # Pass the constructed dict
                        # No 'status' needed here - RecordingRepo handles it via recording_type implicitly on save? Check Repo.
                    )
                    # --- END FIX ---

                    # Save the metadata object using the repository
                    # --- MODIFIED: Pass user_id to save method ---
                    if self.recording_repo.save(pending_metadata_obj, user_id=user_id):
                        created_segments_metadata.append(pending_metadata_obj.to_dict())
                        self.logger.info(f"[Segment {i+1}] Saved PENDING metadata for {segment_id}")
                    else:
                        self.logger.error(f"[ProcessSound] Failed to save PENDING metadata for segment {segment_id}. Skipping.")
                        # Attempt to clean up the saved audio file if metadata save fails
                        if pending_audio_path and pending_audio_path.exists():
                            try:
                                self.file_manager.delete_file(pending_audio_path) # Use FileManager delete
                                self.logger.info(f"Cleaned up audio file {pending_audio_path} due to metadata save failure.")
                            except OSError as cleanup_err:
                                self.logger.warning(f"[ProcessSound] Could not cleanup audio {pending_audio_path}: {cleanup_err}")

                except Exception as e:
                    self.logger.error(f"[ProcessSound] Unexpected error processing segment {i+1} for raw recording {recording_id}: {e}", exc_info=True)
                    # Attempt cleanup if audio was saved but metadata failed later in the block
                    if pending_audio_path and pending_audio_path.exists():
                        try:
                            self.file_manager.delete_file(pending_audio_path) # Use FileManager delete
                            self.logger.info(f"Cleaned up audio file {pending_audio_path} due to unexpected error in segment processing.")
                        except OSError as cleanup_err:
                            self.logger.warning(f"[ProcessSound] Could not cleanup audio {pending_audio_path} after error: {cleanup_err}")
                    # Continue to next segment if one fails
                    continue

            self.logger.info(f"[ProcessSound] Finished processing. Successfully saved {len(created_segments_metadata)} out of {len(segments_with_info)} detected segments for raw recording {recording_id}.")
            
            # --- Clean up noise profile after successful segmentation ---
            if created_segments_metadata and noise_profile_path and noise_profile_path.exists():
                try:
                    self.file_manager.delete_file(noise_profile_path)
                    self.logger.info(f"[ProcessSound] Cleaned up noise profile for user {user_id} after successful segmentation")
                except Exception as cleanup_err:
                    self.logger.warning(f"[ProcessSound] Failed to clean up noise profile: {cleanup_err}")
            # --- End noise profile cleanup ---
            
            return created_segments_metadata
        except Exception as e:
            self.logger.error(f"[ProcessSound] Error processing sound instance {recording_id}: {e}", exc_info=True)
            return []
    
    def get_pending_segments(self, class_id: Optional[str] = None, 
                           user_id: Optional[str] = None) -> List[Recording]:
        """
        Get all pending segments for user verification.
        
        Args:
            class_id: Optional class ID to filter by
            user_id: Optional user ID to filter by
            
        Returns:
            List of pending segment recordings
        """
        try:
            # Use the repository to find pending segments
            return self.recording_repo.find(
                class_id=class_id,
                user_id=user_id,
                recording_type=RecordingType.PENDING,
                status=RecordingType.PENDING
            )
        except Exception as e:
            self.logger.error("Error getting pending segments: %s", str(e))
            return []
    
    def verify_segment(self, segment_id: str, approved: bool) -> bool:
        """
        Verify or reject a segment, moving the files properly.
        
        Args:
            segment_id: ID of the segment to verify
            approved: True to approve, False to reject
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get the segment
            segment = self.recording_repo.find_by_id(segment_id)
            
            if not segment:
                self.logger.warning("Segment %s not found", segment_id)
                return False
            
            # Ensure segment is pending
            if segment.type != RecordingType.PENDING or segment.status != RecordingType.PENDING:
                self.logger.warning("Segment %s is not a pending segment", segment_id)
                return False
            
            # Get paths for easier reference
            pending_wav_path = Path(segment.path)
            pending_json_path = pending_wav_path.with_suffix('.json')
            
            # Get class name for folder structure
            class_name = self._get_class_name(segment.class_id)
            if not class_name:
                self.logger.error("Failed to get class name for segment %s", segment_id)
                return False
            
            verification_timestamp = datetime.now()
            
            if approved:
                # 1. Update status to VERIFIED
                segment.update_status(RecordingType.VERIFIED)
                segment.metadata["date_verified"] = verification_timestamp.isoformat()
                
                # 2. Generate gold standard path and filename
                gold_filename = f"gold_{os.path.basename(segment.relative_wav_path).replace('pending', 'verified')}"
                gold_dir = pending_wav_path.parent.parent / "gold"
                gold_dir.mkdir(exist_ok=True, parents=True)
                gold_wav_path = gold_dir / gold_filename
                gold_json_path = gold_wav_path.with_suffix('.json')
                
                # 3. Create gold standard recording object
                gold_relative_path = str(gold_wav_path.relative_to(self.file_manager.get_data_root()))
                gold_recording = Recording(
                    class_id=segment.class_id,
                    user_id=segment.user_id,
                    relative_wav_path=gold_relative_path,
                    path=str(gold_wav_path),
                    status=RecordingType.VERIFIED,
                    type=RecordingType.GOLD,
                    duration=segment.duration,
                    sample_rate=segment.sample_rate,
                    source_sound_id=segment.source_sound_id,
                    metadata=segment.metadata.copy()  # Copy metadata from segment
                )
                
                # 4. Move (not copy) the pending WAV file to gold location
                try:
                    # Use file_manager's move_file if it exists
                    if hasattr(self.file_manager, 'move_file'):
                        success = self.file_manager.move_file(str(pending_wav_path), str(gold_wav_path))
                    else:
                        # Fallback to os operations
                        import shutil
                        shutil.move(str(pending_wav_path), str(gold_wav_path))
                        success = True
                    
                    if not success:
                        raise Exception(f"Failed to move pending WAV file to gold location")
                        
                    self.logger.info(f"Moved WAV from {pending_wav_path} to {gold_wav_path}")
                except Exception as move_err:
                    self.logger.error(f"Error moving WAV file: {move_err}")
                    return False
                
                # 5. Save gold recording metadata to the new JSON file
                if not self.recording_repo.save(gold_recording):
                    self.logger.error("Failed to save gold recording metadata")
                    # Try to move the WAV file back if metadata save fails
                    try:
                        if gold_wav_path.exists() and not pending_wav_path.exists():
                            shutil.move(str(gold_wav_path), str(pending_wav_path))
                    except:
                        pass
                    return False
                
                # 6. Delete the pending JSON file (since data is now in the gold JSON)
                try:
                    if pending_json_path.exists():
                        pending_json_path.unlink()
                        self.logger.info(f"Deleted pending JSON file: {pending_json_path}")
                except Exception as del_err:
                    self.logger.warning(f"Could not delete pending JSON: {del_err}")
                    # Non-critical error, continue
                
                self.logger.info(f"Approved segment {segment_id} as gold standard at {gold_wav_path}")
                return True
                
            else:
                # Reject the segment - move to discarded folder
                segment.update_status(RecordingType.REJECTED)
                segment.metadata["date_discarded"] = verification_timestamp.isoformat()
                
                # 1. Create discarded folder
                discarded_dir = pending_wav_path.parent.parent / "discarded"
                discarded_dir.mkdir(exist_ok=True, parents=True)
                
                # 2. Generate discarded filename
                discarded_filename = f"discarded_{os.path.basename(segment.relative_wav_path).replace('pending', 'rejected')}"
                discarded_wav_path = discarded_dir / discarded_filename
                discarded_json_path = discarded_wav_path.with_suffix('.json')
                
                # 3. Update segment path for the discarded location
                segment.relative_wav_path = str(discarded_wav_path.relative_to(self.file_manager.get_data_root()))
                segment.path = str(discarded_wav_path)
                
                # 4. Move the WAV file to discarded location
                try:
                    # Use file_manager's move_file if it exists
                    if hasattr(self.file_manager, 'move_file'):
                        success = self.file_manager.move_file(str(pending_wav_path), str(discarded_wav_path))
                    else:
                        # Fallback to os operations
                        import shutil
                        shutil.move(str(pending_wav_path), str(discarded_wav_path))
                        success = True
                    
                    if not success:
                        raise Exception(f"Failed to move pending WAV file to discarded location")
                        
                    self.logger.info(f"Moved WAV from {pending_wav_path} to {discarded_wav_path}")
                except Exception as move_err:
                    self.logger.error(f"Error moving WAV file to discarded: {move_err}")
                    return False
                
                # 5. Save updated segment metadata to the new JSON path
                if not self.recording_repo.save(segment):
                    self.logger.error("Failed to save discarded recording metadata")
                    # Try to move the WAV file back if metadata save fails
                    try:
                        if discarded_wav_path.exists() and not pending_wav_path.exists():
                            shutil.move(str(discarded_wav_path), str(pending_wav_path))
                    except:
                        pass
                    return False
                
                # 6. Delete the original pending JSON file
                try:
                    if pending_json_path.exists():
                        pending_json_path.unlink()
                        self.logger.info(f"Deleted pending JSON file: {pending_json_path}")
                except Exception as del_err:
                    self.logger.warning(f"Could not delete pending JSON: {del_err}")
                    # Non-critical error, continue
                
                self.logger.info(f"Rejected segment {segment_id}, moved to discarded: {discarded_wav_path}")
                return True
                
        except Exception as e:
            self.logger.error("Error verifying segment %s: %s", segment_id, str(e))
            return False
    
    def get_gold_recordings(self, class_id: Optional[str] = None, 
                          user_id: Optional[str] = None) -> List[Recording]:
        """
        Get all verified (gold) recordings for a class.
        
        Args:
            class_id: Optional class ID to filter by
            user_id: Optional user ID to filter by
            
        Returns:
            List of gold recordings
        """
        try:
            # Use the repository to find gold recordings
            return self.recording_repo.find(
                class_id=class_id,
                user_id=user_id,
                recording_type=RecordingType.GOLD,
                status=RecordingType.VERIFIED
            )
        except Exception as e:
            self.logger.error("Error getting gold recordings: %s", str(e))
            return []
    
    def segment_recording_file(self, audio_file_path: str) -> List[Tuple[np.ndarray, Dict[str, Any]]]:
        """
        Segment a recorded file into individual sound instances.
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            List of tuples containing (audio_segment, metadata)
        """
        try:
            # Load audio file
            audio_data, sample_rate = load_audio_from_file(audio_file_path)
            
            # Configure segmenter with appropriate parameters for silence detection
            segmentation_params = {
                "min_segment_length": 0.2,
                "max_segment_length": 2.0,
                "silence_threshold": 0.02,
                "min_silence_length": 0.5,  # 500ms as in original min_silence_len
                "pad_silence": 0.1  # 100ms as in original keep_silence
            }
            
            # Use AudioSegmenter class to segment the audio
            segmenter = AudioSegmenter(segmentation_params)
            segments = segmenter.segment_audio(audio_data, sample_rate)
            
            # Return the segments (audio data and metadata)
            return segments
        except Exception as e:
            self.logger.error("Error segmenting recording file: %s", str(e))
            return []
