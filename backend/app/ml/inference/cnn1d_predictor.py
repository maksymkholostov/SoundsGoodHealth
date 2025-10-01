"""Predictor for lightweight 1D CNN models."""

import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class CNN1DPredictor:
    """Predictor for 1D CNN models."""
    
    def load_model(self, path: str) -> Any:
        """Load a 1D CNN model from saved files."""
        import tensorflow as tf
        import json
        from pathlib import Path
        
        model_path = Path(path)
        
        # Check for weights + architecture format (what we save)
        if (model_path / 'model.weights.h5').exists() and (model_path / 'architecture.json').exists():
            # Load architecture from JSON
            with open(model_path / 'architecture.json', 'r') as f:
                model_config = json.load(f)
            
            # Reconstruct model from config
            model = tf.keras.models.model_from_config(model_config)
            
            # Load weights
            model.load_weights(str(model_path / 'model.weights.h5'))
            
            # Compile the model (needed for predictions)
            model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
            
            logger.info(f"Loaded 1D CNN model from {path}")
            return model
        else:
            raise FileNotFoundError(f"No valid 1D CNN model format found at {path}")
    
    def predict(self, model: Any, features: np.ndarray) -> Dict[str, float]:
        """
        Make predictions using a 1D CNN model.
        
        Args:
            model: Trained 1D CNN model
            features: Input features - expects shape (batch, time_steps, features)
                     For inference, this should be MFCCs not mel_spectrogram
        
        Returns:
            Dictionary mapping class indices to probabilities
        """
        # Ensure features are 3D (batch, time, features)
        if features.ndim == 2:
            # If 2D, assume it's (time, features) and add batch dimension
            features = np.expand_dims(features, axis=0)
        elif features.ndim == 1:
            # If 1D, reshape to (1, 1, features)
            features = features.reshape(1, 1, -1)
        
        # Check if we need to extract MFCCs from mel_spectrogram
        if features.shape[-1] > 100:  # Likely flattened mel_spectrogram
            # This is a flattened mel_spectrogram, need to reshape and extract MFCCs
            logger.warning(f"Received flattened features of shape {features.shape}, extracting MFCCs")
            
            # Assuming it's flattened from (128, 251) mel_spectrogram
            if features.shape[-1] == 32128:  # 128 * 251
                # Reshape back to mel_spectrogram
                mel_spec = features[0].reshape(128, 251)
                
                # Extract MFCCs
                import librosa
                log_mel = librosa.power_to_db(mel_spec, ref=np.max)
                mfccs = librosa.feature.mfcc(S=log_mel, n_mfcc=20)
                
                # Transpose to (time, features) and add batch dim
                features = np.expand_dims(mfccs.T, axis=0)
                logger.info(f"Extracted MFCCs, new shape: {features.shape}")
        
        # Get predictions
        predictions = model.predict(features, verbose=0)[0]
        
        # Return dictionary mapping class indices to probabilities
        return {str(i): float(p) for i, p in enumerate(predictions)}