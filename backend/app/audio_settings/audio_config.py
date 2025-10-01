"""
Centralized configuration for audio processing parameters.
"""

# Segmentation parameters
SEGMENTATION_MIN_SILENCE_LEN = 500  # milliseconds
SEGMENTATION_SILENCE_THRESH = -40  # dB
SEGMENTATION_KEEP_SILENCE = 100  # milliseconds

# Normalization parameters
NORMALIZATION_TARGET_DB = -20  # dB
NORMALIZATION_PADDING_MS = 50  # milliseconds

# Filtering parameters 
FILTER_LOW_CUTOFF = 100  # Hz
FILTER_HIGH_CUTOFF = 8000  # Hz
FILTER_NOTCH_FREQ = 60  # Hz (power line frequency)
FILTER_NOTCH_Q = 30  # Q-factor

# Feature extraction parameters
FEATURE_N_MFCC = 13
FEATURE_N_FFT = 2048
FEATURE_HOP_LENGTH = 512
FEATURE_N_MELS = 128
