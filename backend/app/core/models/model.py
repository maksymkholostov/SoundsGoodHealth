from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime
from enum import Enum


class ModelType(Enum):
    """Type of machine learning model"""
    CNN = "cnn"
    CNN1D = "cnn1d"  # Lightweight 1D CNN for small datasets
    LSTM = "lstm"
    SVM = "svm"
    RF = "rf"  # Random Forest
    KNN = "knn"
    CUSTOM = "custom"


class ModelStatus(Enum):
    """Status of a model in its lifecycle"""
    CREATED = "created"
    TRAINING = "training"
    TRAINED = "trained"
    FAILED = "failed"
    ARCHIVED = "archived"


@dataclass
class ModelVersion:
    """
    Represents metadata for a trained machine learning model.
    
    The actual model is stored in the file system, and this class
    stores metadata about that model.
    """
    id: str  # Unique identifier for the model version
    dictionary_id: str  # ID of the dictionary this model is for
    feature_set_id: str  # ID of the feature set used for training
    user_id: str  # ID of the user who created this model
    name: str  # User-friendly name for this model version
    type: ModelType  # Type of model architecture
    version: str  # Version string (e.g., 'v01')
    parameters: Dict[str, Any]  # Parameters used for training
    metrics: Dict[str, Any]  # Performance metrics
    filename: str  # Filename in the storage system
    status: ModelStatus  # Current status
    classes: List[str]  # IDs of classes this model can identify
    training_ids: List[str] = field(default_factory=list)  # IDs of recordings used for training
    validation_ids: List[str] = field(default_factory=list)  # IDs of recordings used for validation
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    @classmethod
    def create(cls, dictionary_id: str, feature_set_id: str, user_id: str,
              name: str, model_type: ModelType, version: str, parameters: Dict[str, Any],
              classes: List[str], filename: str) -> 'ModelVersion':
        """
        Create a new model version.
        
        Args:
            dictionary_id: ID of the dictionary this model is for
            feature_set_id: ID of the feature set used for training
            user_id: ID of the user who created this model
            name: User-friendly name for this model version
            model_type: Type of model architecture
            version: Version string
            parameters: Parameters used for training
            classes: IDs of classes this model can identify
            filename: Filename in the storage system
            
        Returns:
            ModelVersion instance
        """
        # Generate timestamp-based ID: {model}_{dict}_{user}_{timedate}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")[:-3]  # Remove last 3 digits of microseconds
        model_id = f"{model_type.value}_{dictionary_id}_{user_id}_{timestamp}"
        
        return cls(
            id=model_id,
            dictionary_id=dictionary_id,
            feature_set_id=feature_set_id,
            user_id=user_id,
            name=name,
            type=model_type,
            version=version,
            parameters=parameters,
            metrics={},
            filename=filename,
            status=ModelStatus.CREATED,
            classes=classes
        )
    
    def mark_training(self) -> None:
        """Mark this model as currently training"""
        self.status = ModelStatus.TRAINING
        self.updated_at = datetime.now()
    
    def mark_trained(self, metrics: Dict[str, Any]) -> None:
        """
        Mark this model as successfully trained.
        
        Args:
            metrics: Performance metrics for the model
        """
        self.status = ModelStatus.TRAINED
        self.metrics = metrics
        self.updated_at = datetime.now()
    
    def mark_failed(self, error: str) -> None:
        """
        Mark this model as failed.
        
        Args:
            error: Error message explaining the failure
        """
        self.status = ModelStatus.FAILED
        self.metadata['error'] = error
        self.updated_at = datetime.now()
    
    def archive(self) -> None:
        """Mark this model as archived (no longer active)"""
        self.status = ModelStatus.ARCHIVED
        self.updated_at = datetime.now()
    
    def add_training_data(self, recording_ids: List[str], is_validation: bool = False) -> None:
        """
        Add recording IDs used for training or validation.
        
        Args:
            recording_ids: IDs of recordings used
            is_validation: If True, add to validation set, else to training set
        """
        if is_validation:
            self.validation_ids.extend(recording_ids)
        else:
            self.training_ids.extend(recording_ids)
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        # Sanitize parameters and metrics to remove non-serializable objects
        def sanitize_value(v):
            """Recursively remove non-JSON-serializable objects"""
            if callable(v):
                return None  # Skip functions
            elif isinstance(v, dict):
                return {k: sanitize_value(val) for k, val in v.items() if not callable(val) and k not in ['progress_callback', '_model_id_for_log']}
            elif isinstance(v, (list, tuple)):
                return [sanitize_value(item) for item in v if not callable(item)]
            else:
                try:
                    # Test if value is JSON serializable
                    import json
                    json.dumps(v)
                    return v
                except (TypeError, ValueError):
                    return None  # Skip non-serializable objects
        
        def sanitize_dict(d):
            """Remove functions and other non-JSON-serializable objects from dict"""
            if not isinstance(d, dict):
                return d
            # Explicitly exclude known non-serializable keys
            return {k: sanitize_value(v) for k, v in d.items() 
                    if not callable(v) and k not in ['progress_callback', '_model_id_for_log']}
        
        return {
            'id': self.id,
            'dictionary_id': self.dictionary_id,
            'feature_set_id': self.feature_set_id,
            'user_id': self.user_id,
            'name': self.name,
            'type': self.type.value,
            'version': self.version,
            'parameters': sanitize_dict(self.parameters),
            'metrics': sanitize_dict(self.metrics),
            'filename': self.filename,
            'status': self.status.value,
            'classes': self.classes,
            'training_ids': self.training_ids,
            'validation_ids': self.validation_ids,
            'metadata': sanitize_dict(self.metadata),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelVersion':
        """Create from dictionary"""
        # Handle date parsing
        created_at = datetime.fromisoformat(data['created_at']) if isinstance(data['created_at'], str) else data['created_at']
        updated_at = datetime.fromisoformat(data['updated_at']) if isinstance(data['updated_at'], str) else data['updated_at']
        
        return cls(
            id=data['id'],
            dictionary_id=data['dictionary_id'],
            feature_set_id=data['feature_set_id'],
            user_id=data['user_id'],
            name=data['name'],
            type=ModelType(data['type']),
            version=data['version'],
            parameters=data['parameters'],
            metrics=data['metrics'],
            filename=data['filename'],
            status=ModelStatus(data['status']),
            classes=data['classes'],
            training_ids=data.get('training_ids', []),
            validation_ids=data.get('validation_ids', []),
            metadata=data.get('metadata', {}),
            created_at=created_at,
            updated_at=updated_at
        )
