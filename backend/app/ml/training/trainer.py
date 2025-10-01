import os
import pickle
import logging
import numpy as np
from typing import Dict, Tuple, Any, Optional
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)

class ModelTrainer(ABC):
    """Base abstract class for model trainers."""
    
    @abstractmethod
    def train(self, X: np.ndarray, y: np.ndarray, params: Optional[Dict[str, Any]] = None) -> Tuple[Any, Dict[str, float]]:
        """
        Train a model and return the model and metrics.
        
        Args:
            X: Features array of shape (n_samples, n_features)
            y: Labels array of shape (n_samples,)
            params: Optional model-specific parameters
            
        Returns:
            Tuple of (trained_model, metrics_dict)
        """
        pass
    
    def save_model(self, model: Any, path: str) -> None:
        """
        Save a trained model to disk.
        
        Args:
            model: The trained model object
            path: Path to save the model
        """
        with open(path, 'wb') as f:
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
            pickle.dump(model, f)
    
    def load_model(self, path: str) -> Any:
        """
        Load a trained model from disk.
        
        Args:
            path: Path to the saved model
            
        Returns:
            The loaded model object
        """
        with open(path, 'rb') as f:
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
            return pickle.load(f)


class SVM_Trainer(ModelTrainer):
    """Trainer for Support Vector Machine models."""
    
    def train(self, X: np.ndarray, y: np.ndarray, params: Optional[Dict[str, Any]] = None) -> Tuple[Any, Dict[str, float]]:
        """Train an SVM model on the provided data."""
        from sklearn.svm import SVC
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        
        # Default parameters
        default_params = {
            'C': 1.0,
            'kernel': 'rbf',
            'gamma': 'scale',
            'probability': True,
            'random_state': 42
        }
        
        # Update with user-provided parameters
        if params:
            default_params.update(params)
        
        # Remove our internal parameters before passing to sklearn
        default_params.pop('_model_id_for_log', None)
        default_params.pop('num_classes', None)  # Not needed for SVM 

        # --- Reshape Input for scikit-learn --- 
        # Input X is (n_samples, height, width), flatten features for SVM
        n_samples = X.shape[0]
        if X.ndim == 3:
             X_flat = X.reshape(n_samples, -1) # Flatten height*width
             logger.info(f"Flattened input features from {X.shape} to {X_flat.shape} for SVM.")
        elif X.ndim == 2:
             X_flat = X # Already suitable
             logger.info(f"Input features already 2D (shape: {X.shape}). Using directly for SVM.")
        else:
             raise ValueError(f"SVM expects 2D or 3D input, got {X.ndim}D (shape: {X.shape})")
        # --- End Reshape --- 

        # Split data into training and validation sets using flattened data
        X_train, X_val, y_train, y_val = train_test_split(
            X_flat, y, test_size=0.2, random_state=default_params['random_state']
        )
        
        # Train the model
        model = SVC(**default_params)
        model.fit(X_train, y_train)
        
        # Evaluate the model
        y_pred = model.predict(X_val)
        
        # Calculate metrics
        metrics = {
            'accuracy': float(accuracy_score(y_val, y_pred)),
            'precision': float(precision_score(y_val, y_pred, average='weighted')),
            'recall': float(recall_score(y_val, y_pred, average='weighted')),
            'f1': float(f1_score(y_val, y_pred, average='weighted')),
            'num_train_samples': len(X_train),
            'num_val_samples': len(X_val)
        }
        
        logger.info(f"SVM training completed with accuracy: {metrics['accuracy']:.4f}")
        
        return model, metrics


class RandomForest_Trainer(ModelTrainer):
    """Trainer for Random Forest models."""
    
    def train(self, X: np.ndarray, y: np.ndarray, params: Optional[Dict[str, Any]] = None) -> Tuple[Any, Dict[str, float]]:
        """Train a Random Forest model on the provided data."""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        
        # Default parameters
        default_params = {
            'n_estimators': 100,
            'max_depth': None,
            'min_samples_split': 2,
            'random_state': 42
        }
        
        # Update with user-provided parameters
        if params:
            default_params.update(params)
        
        # Remove our internal parameters before passing to sklearn
        default_params.pop('_model_id_for_log', None)
        default_params.pop('num_classes', None)  # Not needed for SVM 

        # --- Reshape Input for scikit-learn --- 
        # Input X is (n_samples, height, width), flatten features for RF
        n_samples = X.shape[0]
        if X.ndim == 3:
             X_flat = X.reshape(n_samples, -1) # Flatten height*width
             logger.info(f"Flattened input features from {X.shape} to {X_flat.shape} for RandomForest.")
        elif X.ndim == 2:
             X_flat = X # Already suitable
             logger.info(f"Input features already 2D (shape: {X.shape}). Using directly for RandomForest.")
        else:
             raise ValueError(f"RandomForest expects 2D or 3D input, got {X.ndim}D (shape: {X.shape})")
        # --- End Reshape --- 

        # Split data into training and validation sets using flattened data
        X_train, X_val, y_train, y_val = train_test_split(
            X_flat, y, test_size=0.2, random_state=default_params['random_state']
        )
        
        # Train the model
        model = RandomForestClassifier(**default_params)
        model.fit(X_train, y_train)
        
        # Evaluate the model
        y_pred = model.predict(X_val)
        
        # Calculate metrics
        metrics = {
            'accuracy': float(accuracy_score(y_val, y_pred)),
            'precision': float(precision_score(y_val, y_pred, average='weighted')),
            'recall': float(recall_score(y_val, y_pred, average='weighted')),
            'f1': float(f1_score(y_val, y_pred, average='weighted')),
            'num_train_samples': len(X_train),
            'num_val_samples': len(X_val)
        }
        
        logger.info(f"Random Forest training completed with accuracy: {metrics['accuracy']:.4f}")
        
        return model, metrics


class CNN_Trainer(ModelTrainer):
    """Trainer for Convolutional Neural Network models."""
    
    def train(self, X: np.ndarray, y: np.ndarray, params: Optional[Dict[str, Any]] = None) -> Tuple[Any, Dict[str, float]]:
        """Train a CNN model on the provided data."""
        import tensorflow as tf
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import Conv2D, MaxPooling2D, Flatten, Dense, Dropout
        from tensorflow.keras.utils import to_categorical
        from sklearn.model_selection import train_test_split
        
        # OBVIOUS TEST MESSAGE TO CONFIRM THIS FILE IS BEING USED
        logger.error("🚨🚨🚨 CNN_TRAINER.TRAIN() IS BEING CALLED FROM TRAINER.PY 🚨🚨🚨")
        
        # Default parameters
        default_params = {
            'epochs': 30,
            'batch_size': 32,
            'learning_rate': 0.001,
            'dropout_rate': 0.5,
            'random_state': 42
        }
        
        # Update with user-provided parameters
        if params:
            default_params.update(params)
        
        # Split data into training and validation sets
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=default_params['random_state']
        )
        
        # Get number of classes
        num_classes = len(np.unique(y))
        
        # Assuming X contains spectrograms or MFCCs of shape (time_steps, features)
        if len(X_train.shape) == 2:
            # Reshape to (samples, height, width, channels)
            # This case might be less likely now, assuming Mel Spectrograms are loaded
            logger.warning("Input features have 2 dimensions, reshaping to (H, 1, 1) for CNN.")
            X_train = X_train.reshape(X_train.shape[0], X_train.shape[1], 1, 1)
            X_val = X_val.reshape(X_val.shape[0], X_val.shape[1], 1, 1)
        elif len(X_train.shape) == 3:
            # Input shape is (samples, height, width) - Add channel dimension
            logger.info(f"Input features have 3 dimensions (shape: {X_train.shape}). Adding channel dimension.")
            X_train = np.expand_dims(X_train, axis=-1) # Add channel axis at the end
            X_val = np.expand_dims(X_val, axis=-1)
        elif len(X_train.shape) == 4:
             # Assume input is already in correct shape (samples, height, width, channels)
             logger.info(f"Input features have 4 dimensions (shape: {X_train.shape}). Assuming correct format.")
             pass # No reshape needed
        else:
             raise ValueError(f"Unsupported input shape for CNN: {X_train.shape}")
        
        logger.info(f"CNN input shape after reshape: {X_train.shape}")

        # Convert labels to one-hot encoded vectors
        y_train_cat = to_categorical(y_train, num_classes)
        y_val_cat = to_categorical(y_val, num_classes)
        
        # --- Custom Callback for History & Status File --- 
        class TrainingLogCallback(tf.keras.callbacks.Callback):
            def __init__(self, status_log_path: str):
                super().__init__()
                self.status_log_path = status_log_path
                self.epoch_data = []
                self.best_val_loss = float('inf')
                # Clear log file at the beginning of training
                try:
                     with open(self.status_log_path, 'w') as f:
                         f.write("epoch,loss,accuracy,val_loss,val_accuracy,improved\n") # Header
                except Exception as e:
                     logger.error(f"Failed to clear/initialize status log {self.status_log_path}: {e}")

            def on_epoch_end(self, epoch, logs=None):
                logs = logs or {}
                current_val_loss = logs.get('val_loss')
                improved = False
                if current_val_loss is not None and current_val_loss < self.best_val_loss:
                    self.best_val_loss = current_val_loss
                    improved = True
                
                # COUNT WEIGHTS IN MODEL
                total_weights = 0
                trainable_weights = 0
                layer_info = []
                
                for i, layer in enumerate(self.model.layers):
                    if hasattr(layer, 'weights') and layer.weights:
                        layer_weights = sum([w.numpy().size for w in layer.weights])
                        layer_trainable = sum([w.numpy().size for w in layer.trainable_weights])
                        total_weights += layer_weights
                        trainable_weights += layer_trainable
                        layer_info.append(f"Layer{i}({layer.name}): {layer_weights} weights")
                
                # Log weight information every 5 epochs or on first/last epoch
                if epoch == 0 or epoch % 5 == 0 or epoch == 29:
                    logger.info(f"EPOCH {epoch+1} WEIGHTS: Total={total_weights:,}, Trainable={trainable_weights:,}")
                    for info in layer_info:
                        logger.info(f"  {info}")
                
                # Prepare metrics for logging and internal storage
                epoch_metrics = {
                    'epoch': epoch + 1,
                    'loss': logs.get('loss'),
                    'accuracy': logs.get('accuracy'),
                    'val_loss': current_val_loss,
                    'val_accuracy': logs.get('val_accuracy'),
                    'improved': improved,
                    'total_weights': total_weights,
                    'trainable_weights': trainable_weights
                }
                self.epoch_data.append(epoch_metrics)

                # Write current epoch metrics to the status log file
                try:
                     with open(self.status_log_path, 'a') as f:
                         # Use standard CSV format that can be parsed properly
                         f.write(f"{epoch_metrics['epoch']},{epoch_metrics['loss']:.4f},{epoch_metrics['accuracy']:.4f},"
                                 f"{epoch_metrics['val_loss']:.4f},{epoch_metrics['val_accuracy']:.4f},{epoch_metrics['improved']}\n")
                except Exception as e:
                    logger.error(f"Failed to write to status log {self.status_log_path} for epoch {epoch+1}: {e}")
        # --- End Custom Callback ---

        # Build the CNN model
        input_shape = X_train.shape[1:]
        
        model = Sequential([
            Conv2D(32, kernel_size=(3, 3), activation='relu', padding='same', input_shape=input_shape),
            MaxPooling2D(pool_size=(2, 2)),
            Conv2D(64, kernel_size=(3, 3), activation='relu', padding='same'),
            MaxPooling2D(pool_size=(2, 2)),
            Conv2D(128, kernel_size=(3, 3), activation='relu', padding='same'),
            MaxPooling2D(pool_size=(2, 2)),
            Flatten(),
            Dense(128, activation='relu'),
            Dropout(default_params['dropout_rate']),
            Dense(num_classes, activation='softmax')
        ])
        
        # Compile the model
        optimizer = tf.keras.optimizers.Adam(learning_rate=default_params['learning_rate'])
        model.compile(
            optimizer=optimizer,
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        # Determine path for the status log file within the model's directory
        # model_save_dir is determined later, so we might need to pass it to the callback
        # OR determine the path structure consistently beforehand.
        # Let's assume model_id is available via params or context?
        # For now, using a placeholder path - THIS NEEDS TO BE FIXED.
        model_id_for_log = params.get('_model_id_for_log', 'unknown_model') # Temp: Need a way to get model_id here
        log_dir = Path("backend/data/logs/training") # Central log directory
        log_dir.mkdir(parents=True, exist_ok=True)
        status_log_path = str(log_dir / f"{model_id_for_log}.log")
        logger.info(f"Status log path for callback: {status_log_path}")

        # Create instance of the callback
        history_callback = TrainingLogCallback(status_log_path)

        # Train the model
        # Use callbacks=[history_callback] instead of assigning history directly
        model.fit(
            X_train, y_train_cat,
            epochs=default_params['epochs'],
            batch_size=default_params['batch_size'],
            validation_data=(X_val, y_val_cat),
            verbose=0,
            callbacks=[history_callback] # Pass callback here
        )
        
        # Evaluate the model
        _, accuracy = model.evaluate(X_val, y_val_cat, verbose=0)
        
        # Calculate additional metrics
        y_pred_prob = model.predict(X_val)
        y_pred = np.argmax(y_pred_prob, axis=1)
        
        # Calculate metrics
        from sklearn.metrics import precision_score, recall_score, f1_score
        
        metrics = {
            'accuracy': float(accuracy),
            'precision': float(precision_score(y_val, y_pred, average='weighted')),
            'recall': float(recall_score(y_val, y_pred, average='weighted')),
            'f1': float(f1_score(y_val, y_pred, average='weighted')),
            'val_loss': float(history_callback.epoch_data[-1]['val_loss']),
            'num_train_samples': len(X_train),
            'num_val_samples': len(X_val)
        }
        
        logger.info(f"CNN training completed with accuracy: {metrics['accuracy']:.4f}")
        
        # Return model, final metrics, AND the detailed epoch history
        return model, metrics, history_callback.epoch_data
        
    # DB-OPERATION: create model
    def save_model(self, model: Any, path: str) -> None:
        """TEMPORARILY SKIP SAVING TO TEST IF THIS IS THE SOURCE OF BROKEN PIPE ERROR."""
        from pathlib import Path
        
        logger.error("🚨🚨🚨 CNN_TRAINER.SAVE_MODEL() IS BEING CALLED FROM TRAINER.PY 🚨🚨🚨")
        
        # SAVE WEIGHTS ONLY - BYPASS TENSORFLOW SAVEDMODEL COMPLETELY
        model_dir = Path(path)
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Count weights for debugging
        total_weights = sum([w.numpy().size for layer in model.layers for w in layer.weights])
        logger.info(f"📊 Model has {total_weights:,} total weights - SAVING WEIGHTS ONLY")
        
        try:
            # Save model weights as HDF5 (TensorFlow requires .weights.h5 extension)
            weights_path = model_dir / "model.weights.h5"
            model.save_weights(str(weights_path))
            logger.info(f"✅ SAVED WEIGHTS: {weights_path}")
            
            # Save model architecture 
            arch_path = model_dir / "architecture.json"
            with open(arch_path, 'w') as f:
                f.write(model.to_json())
            logger.info(f"✅ SAVED ARCHITECTURE: {arch_path}")
            
            # Success marker
            success_path = model_dir / "WEIGHTS_SAVED_SUCCESS"
            with open(success_path, 'w') as f:
                f.write(f"CNN weights saved successfully - {total_weights:,} parameters")
            
            logger.info(f"🎉 MODEL SAVED VIA WEIGHTS METHOD!")
            
        except Exception as e:
            logger.error(f"❌ WEIGHTS SAVE FAILED: {e}")
            raise
        
    # DB-OPERATION: read model
    def load_model(self, path: str) -> Any:
        """Load a TensorFlow model using multiple methods."""
        import tensorflow as tf
        import pickle
        import os
        from pathlib import Path
        
        model_dir = Path(path)
        
        # Method 1: Try to load from weights + architecture (our new format)
        architecture_path = model_dir / "architecture.json"
        weights_path = model_dir / "model.weights.h5"
        success_marker = model_dir / "WEIGHTS_SAVED_SUCCESS"
        
        if success_marker.exists() and architecture_path.exists() and weights_path.exists():
            try:
                logger.info(f"Loading CNN model from weights + architecture format: {path}")
                
                # Load architecture
                with open(architecture_path, 'r') as f:
                    model_json = f.read()
                model = tf.keras.models.model_from_json(model_json)
                
                # Load weights
                model.load_weights(str(weights_path))
                
                # Load and apply config if available
                config_path = model_dir / "config.pkl"
                if config_path.exists():
                    with open(config_path, 'rb') as f:
                        model_config = pickle.load(f)
                    # Recompile model with saved configuration
                    model.compile(
                        optimizer=tf.keras.optimizers.Adam.from_config(model_config['optimizer_config']),
                        loss=model_config['loss'],
                        metrics=model_config['metrics']
                    )
                
                logger.info("Successfully loaded CNN model from weights + architecture")
                return model
                
            except Exception as e:
                logger.error(f"Failed to load from weights + architecture: {e}")
        
        # Method 2: Try standard SavedModel format
        try:
            if os.path.isdir(path):
                logger.info(f"Loading CNN model from SavedModel format: {path}")
                return tf.keras.models.load_model(path)
        except Exception as e:
            logger.error(f"Failed to load from SavedModel format: {e}")
        
        # Method 3: Try .keras format
        try:
            keras_path = f"{path}.keras" if not path.endswith('.keras') else path
            if os.path.exists(keras_path):
                logger.info(f"Loading CNN model from .keras format: {keras_path}")
                return tf.keras.models.load_model(keras_path)
        except Exception as e:
            logger.error(f"Failed to load from .keras format: {e}")
            
        raise RuntimeError(f"Could not load CNN model from any format at path: {path}")
