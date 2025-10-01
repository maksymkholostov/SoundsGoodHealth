"""Lightweight 1D CNN trainer for small datasets."""

import logging
import numpy as np
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class CNN1D_Trainer:
    """Trainer for lightweight 1D Convolutional Neural Network models."""
    
    def train(self, X: np.ndarray, y: np.ndarray, params: Optional[Dict[str, Any]] = None) -> Tuple[Any, Dict[str, float], list]:
        """
        Train a lightweight 1D CNN model on MFCC features.
        
        Args:
            X: Input features - expects MFCCs of shape (samples, time_steps, n_mfcc)
               If 3D mel_spectrogram provided, will extract MFCCs
            y: Labels as class indices
            params: Optional training parameters
            
        Returns:
            Tuple of (model, metrics, history)
        """
        import tensorflow as tf
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import (Conv1D, MaxPooling1D, GlobalMaxPooling1D, 
                                             Dense, Dropout, BatchNormalization)
        from tensorflow.keras.utils import to_categorical
        from tensorflow.keras.regularizers import l2
        from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
        from sklearn.model_selection import train_test_split
        
        logger.info("🎯 Starting lightweight 1D CNN training")
        
        # Default parameters
        default_params = {
            'epochs': 100,  # Increased default to allow more time for convergence
            'batch_size': 4,  # Small batch for small dataset
            'learning_rate': 0.0001,  # Reduced from 0.001 to prevent overshooting
            'dropout_rate': 0.6,  # Increased from 0.5 for better regularization
            'l2_reg': 0.02,  # Increased from 0.01 for stronger regularization
            'random_state': 42,
            'use_mfcc': True,  # Use MFCCs instead of full mel spectrogram
            'n_mfcc': 20  # Reduced from 40 for even fewer parameters
        }
        
        if params:
            default_params.update(params)
        
        # Prepare features - extract MFCCs if needed
        if len(X.shape) == 3 and X.shape[1] == 128:  # Likely mel_spectrogram (samples, 128, time)
            logger.info(f"Converting mel spectrograms to MFCCs. Input shape: {X.shape}")
            # Extract MFCCs from mel spectrograms
            import librosa
            n_mfcc = default_params['n_mfcc']
            X_mfcc = []
            for mel_spec in X:
                # Convert to log scale and extract MFCCs
                log_mel = librosa.power_to_db(mel_spec, ref=np.max)
                mfccs = librosa.feature.mfcc(S=log_mel, n_mfcc=n_mfcc)
                # Transpose to (time, features) format
                X_mfcc.append(mfccs.T)
            X = np.array(X_mfcc)
            logger.info(f"Converted to MFCCs. New shape: {X.shape}")
        
        # Ensure correct shape (samples, time_steps, features)
        if len(X.shape) == 2:
            # If 2D, assume it's (samples, features) and add time dimension
            X = np.expand_dims(X, axis=1)
            logger.warning(f"Input was 2D, expanded to: {X.shape}")
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=default_params['random_state'],
            stratify=y  # Ensure both classes in validation
        )
        
        logger.info(f"Data split - Train: {X_train.shape}, Val: {X_val.shape}")
        logger.info(f"Train class distribution: {np.bincount(y_train)}")
        logger.info(f"Val class distribution: {np.bincount(y_val)}")
        
        # Get dimensions
        time_steps = X_train.shape[1]
        n_features = X_train.shape[2]
        # Use num_classes from params if provided (to handle missing classes in training data)
        # Otherwise use max label + 1 (since labels are 0-indexed)
        if 'num_classes' in default_params:
            num_classes = default_params['num_classes']
        else:
            # For 0-indexed labels, num_classes = max_label + 1
            # E.g., labels [0, 2] need 3 classes (0, 1, 2)
            num_classes = int(np.max(y)) + 1
        
        logger.info(f"Using {num_classes} output classes (from params: {default_params.get('num_classes')}, max label: {np.max(y)}, unique labels: {np.unique(y).tolist()})")
        
        # Build lightweight 1D CNN
        model = Sequential([
            # First conv block - very few filters
            Conv1D(8, kernel_size=5, activation='relu', 
                   kernel_regularizer=l2(default_params['l2_reg']),
                   input_shape=(time_steps, n_features)),
            BatchNormalization(),
            MaxPooling1D(pool_size=2),
            Dropout(0.3),
            
            # Second conv block
            Conv1D(16, kernel_size=3, activation='relu',
                   kernel_regularizer=l2(default_params['l2_reg'])),
            BatchNormalization(),
            
            # Global pooling instead of flatten - huge parameter reduction
            GlobalMaxPooling1D(),
            
            # Small dense layer
            Dense(16, activation='relu', 
                  kernel_regularizer=l2(default_params['l2_reg'])),
            Dropout(default_params['dropout_rate']),
            
            # Output layer
            Dense(num_classes, activation='softmax')
        ])
        
        # Compile model
        optimizer = tf.keras.optimizers.Adam(learning_rate=default_params['learning_rate'])
        model.compile(
            optimizer=optimizer,
            loss='sparse_categorical_crossentropy',  # Use sparse since we have integer labels
            metrics=['accuracy']
        )
        
        # Print model summary
        model.summary()
        total_params = model.count_params()
        logger.info(f"📊 Total parameters: {total_params:,} (vs 8.2M in original CNN)")
        
        # Callbacks for better training
        callbacks = [
            EarlyStopping(monitor='val_loss', patience=20, restore_best_weights=True),  # Patience of 20 epochs for convergence
            ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=10, min_lr=1e-7, verbose=1)  # Increased patience proportionally
        ]
        
        # Add history tracking callback if model_id provided
        history_data = []
        progress_callback = params.get('progress_callback') if params else None
        total_epochs = default_params['epochs']
        
        if params and '_model_id_for_log' in params:
            class SimpleHistoryCallback(tf.keras.callbacks.Callback):
                def on_epoch_end(self, epoch, logs=None):
                    logs = logs or {}
                    epoch_metrics = {
                        'epoch': epoch + 1,
                        'loss': float(logs.get('loss', 0)),
                        'accuracy': float(logs.get('accuracy', 0)),
                        'val_loss': float(logs.get('val_loss', 0)),
                        'val_accuracy': float(logs.get('val_accuracy', 0))
                    }
                    history_data.append(epoch_metrics)
                    
                    # Report progress if callback provided
                    if progress_callback:
                        logger.info(f"Calling progress_callback for epoch {epoch + 1}")
                        progress_callback(epoch + 1, total_epochs, epoch_metrics)
                    
                    # Log every epoch (not just every 10)
                    logger.info(f"Epoch {epoch+1}: train_acc={epoch_metrics['accuracy']:.3f}, "
                              f"val_acc={epoch_metrics['val_accuracy']:.3f}")
            
            callbacks.append(SimpleHistoryCallback())
        
        # Train model with data augmentation for small dataset
        logger.info("🚀 Starting training...")
        
        # Simple data augmentation - add noise to training data
        noise_level = 0.005
        X_train_aug = X_train + np.random.normal(0, noise_level, X_train.shape)
        
        history = model.fit(
            X_train_aug, y_train,
            validation_data=(X_val, y_val),
            epochs=default_params['epochs'],
            batch_size=default_params['batch_size'],
            callbacks=callbacks,
            verbose=1
        )
        
        # Evaluate final model
        y_pred = np.argmax(model.predict(X_val), axis=1)
        val_accuracy = np.mean(y_pred == y_val)
        
        # Calculate metrics
        from sklearn.metrics import precision_score, recall_score, f1_score
        metrics = {
            'accuracy': float(val_accuracy),
            'precision': float(precision_score(y_val, y_pred, average='weighted', zero_division=0)),
            'recall': float(recall_score(y_val, y_pred, average='weighted', zero_division=0)),
            'f1': float(f1_score(y_val, y_pred, average='weighted', zero_division=0)),
            'val_loss': float(history.history['val_loss'][-1]),
            'num_train_samples': len(X_train),
            'num_val_samples': len(X_val),
            'total_parameters': int(total_params)
        }
        
        logger.info(f"✅ Training complete - Accuracy: {metrics['accuracy']:.3f}, "
                   f"Parameters: {total_params:,}")
        
        return model, metrics, history_data
    
    def save_model(self, model: Any, path: str) -> None:
        """Save the model in TensorFlow SavedModel format or weights+architecture."""
        import tensorflow as tf
        from pathlib import Path
        import json
        
        model_path = Path(path)
        
        # For 1D CNN, save as weights + architecture (more reliable)
        model_path.mkdir(parents=True, exist_ok=True)
        
        # Save architecture as JSON
        model_json = model.to_json()
        with open(model_path / 'architecture.json', 'w') as f:
            json.dump(json.loads(model_json), f, indent=2)
        
        # Save weights
        model.save_weights(str(model_path / 'model.weights.h5'))
        
        # Also save model config for reference
        config = {
            'model_type': 'cnn1d',
            'input_shape': model.input_shape[1:],
            'output_shape': model.output_shape[1:],
            'total_params': model.count_params()
        }
        with open(model_path / 'model_config.json', 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Model saved to {model_path} (weights + architecture format)")
    
    def load_model(self, path: str) -> Any:
        """Load a saved 1D CNN model."""
        import tensorflow as tf
        from pathlib import Path
        import json
        
        model_path = Path(path)
        
        # Load architecture
        with open(model_path / 'architecture.json', 'r') as f:
            model_config = json.load(f)
        
        # Reconstruct model
        model = tf.keras.models.model_from_config(model_config)
        
        # Load weights
        model.load_weights(str(model_path / 'model.weights.h5'))
        
        # Compile (needed for predictions)
        model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
        
        logger.info(f"Loaded 1D CNN model from {path}")
        return model