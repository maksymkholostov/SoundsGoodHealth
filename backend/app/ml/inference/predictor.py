import os
import pickle
import logging
import numpy as np
from typing import Dict, List, Any, Optional
import tensorflow as tf

logger = logging.getLogger(__name__)

class ModelPredictor:
    """Base class for model predictors."""
    
    def predict(self, model: Any, features: np.ndarray) -> Dict[str, List[float]]:
        """
        Make predictions using a trained model.
        
        Args:
            model: Trained model
            features: Input features array of shape (n_samples, n_features)
            
        Returns:
            Dictionary with class probabilities
        """
        raise NotImplementedError("Subclasses must implement predict method")
    
    def load_model(self, path: str) -> Any:
        """
        Load a model from disk.
        
        Args:
            path: Path to the saved model
            
        Returns:
            Loaded model
        """
        with open(path, 'rb') as f:
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
            return pickle.load(f)


class SVMPredictor(ModelPredictor):
    """Predictor for SVM models."""
    
    def predict(self, model: Any, features: np.ndarray) -> Dict[str, float]:
        """Make predictions using an SVM model."""
        if features.ndim == 1:
            features = features.reshape(1, -1)
            
        # Get class probabilities
        probas = model.predict_proba(features)[0]
        
        # Get class labels
        classes = model.classes_
        
        # Return dictionary mapping class indices to probabilities
        return {str(c): float(p) for c, p in zip(classes, probas)}


class RandomForestPredictor(ModelPredictor):
    """Predictor for Random Forest models."""
    
    def predict(self, model: Any, features: np.ndarray) -> Dict[str, float]:
        """Make predictions using a Random Forest model."""
        if features.ndim == 1:
            features = features.reshape(1, -1)
            
        # Get class probabilities
        probas = model.predict_proba(features)[0]
        
        # Get class labels
        classes = model.classes_
        
        # Return dictionary mapping class indices to probabilities
        return {str(c): float(p) for c, p in zip(classes, probas)}


class CNNPredictor(ModelPredictor):
    """Predictor for CNN models."""
    
    # DB-OPERATION: read model
    def load_model(self, path: str) -> Any:
        """Load a TensorFlow model from SavedModel format or weights+architecture."""
        import json
        from pathlib import Path
        
        model_path = Path(path)
        
        # Check if it's a SavedModel format
        if (model_path / 'saved_model.pb').exists():
            # Standard SavedModel format
            return tf.keras.models.load_model(path)
        
        # Check if it's weights + architecture format
        elif (model_path / 'model.weights.h5').exists() and (model_path / 'architecture.json').exists():
            # Load architecture from JSON
            with open(model_path / 'architecture.json', 'r') as f:
                model_config = json.load(f)
            
            # Reconstruct model from config
            model = tf.keras.models.model_from_config(model_config)
            
            # Load weights
            model.load_weights(str(model_path / 'model.weights.h5'))
            
            # Compile the model (needed for predictions)
            model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
            
            logger.info(f"Loaded CNN model from weights+architecture at {path}")
            return model
        
        else:
            raise FileNotFoundError(f"No valid model format found at {path}")
    
    def predict(self, model: Any, features: np.ndarray) -> Dict[str, float]:
        """Make predictions using a CNN model."""
        # Reshape features appropriately
        input_shape = model.input_shape[1:]
        n_dims = len(input_shape)
        
        if n_dims == 3:  # (height, width, channels)
            if features.ndim == 2:
                features = features.reshape(1, features.shape[0], features.shape[1], 1)
            elif features.ndim == 3:
                features = features.reshape(1, features.shape[0], features.shape[1], features.shape[2])
        elif n_dims == 2:  # (height, width)
            if features.ndim == 1:
                features = features.reshape(1, features.shape[0], 1)
            elif features.ndim == 2:
                features = features.reshape(1, features.shape[0], features.shape[1])
        
        # Get class probabilities
        probas = model.predict(features)[0]
        
        # Return dictionary mapping class indices to probabilities
        return {str(i): float(p) for i, p in enumerate(probas)}
