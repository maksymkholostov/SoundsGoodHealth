from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class FeatureSet:
    """
    Represents a version of feature extraction algorithms.
    
    Feature sets are versioned (e.g., 'v0.1') and contain metadata about
    the specific features extracted and the algorithms used.
    """
    id: str  # Unique identifier (usually a version string like 'v0.1')
    name: str  # Human-readable name
    description: str  # Description of the feature set
    features: List[str]  # List of feature names included in this set
    parameters: Dict[str, Any]  # Parameters used for extraction
    created_at: datetime = field(default_factory=datetime.now)
    
    @classmethod
    def create(cls, id: str, name: str, description: str, 
              features: List[str], parameters: Dict[str, Any]) -> 'FeatureSet':
        """
        Create a new feature set.
        
        Args:
            id: Version identifier for the feature set
            name: Human-readable name
            description: Description of the feature set
            features: List of feature names included in this set
            parameters: Parameters used for extraction
            
        Returns:
            FeatureSet instance
        """
        return cls(
            id=id,
            name=name,
            description=description,
            features=features,
            parameters=parameters
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'features': self.features,
            'parameters': self.parameters,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureSet':
        """Create from dictionary"""
        # Handle date parsing
        created_at = datetime.fromisoformat(data['created_at']) if isinstance(data['created_at'], str) else data['created_at']
        
        return cls(
            id=data['id'],
            name=data['name'],
            description=data['description'],
            features=data['features'],
            parameters=data['parameters'],
            created_at=created_at
        )


@dataclass
class FeatureExtraction:
    """
    Represents metadata for an extracted feature file.
    
    The actual feature data is stored in the file system, and this class
    stores metadata about those features.
    """
    id: str  # Unique identifier for the feature extraction
    recording_id: str  # ID of the recording these features were extracted from
    feature_set_id: str  # ID of the feature set used
    filename: str  # Filename in the storage system
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata
    created_at: datetime = field(default_factory=datetime.now)
    
    @classmethod
    def create(cls, recording_id: str, feature_set_id: str, 
              filename: str, metadata: Optional[Dict[str, Any]] = None) -> 'FeatureExtraction':
        """
        Create a new feature extraction record.
        
        Args:
            recording_id: ID of the recording
            feature_set_id: ID of the feature set used
            filename: Filename in the storage system
            metadata: Additional metadata
            
        Returns:
            FeatureExtraction instance
        """
        # Extract class name from metadata if available
        meta = metadata or {}
        class_name = meta.get('class_name', 'unknown')
        
        # Extract user_id from recording_id (e.g., gold_eh_ronrubin_... -> ronrubin)
        try:
            parts = recording_id.split('_')
            if len(parts) >= 3:
                user_id = parts[2]
            else:
                user_id = 'unknown'
        except:
            user_id = 'unknown'
        
        # Generate timestamp-based ID: feat_{class}_{user}_{timestamp}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")[:-3]  # Remove last 3 digits of microseconds
        feature_id = f"feat_{class_name.lower()}_{user_id}_{timestamp}"
        
        return cls(
            id=feature_id,
            recording_id=recording_id,
            feature_set_id=feature_set_id,
            filename=filename,
            metadata=meta
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'recording_id': self.recording_id,
            'feature_set_id': self.feature_set_id,
            'filename': self.filename,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureExtraction':
        """Create from dictionary"""
        # Handle date parsing
        created_at = datetime.fromisoformat(data['created_at']) if isinstance(data['created_at'], str) else data['created_at']
        
        return cls(
            id=data['id'],
            recording_id=data['recording_id'],
            feature_set_id=data['feature_set_id'],
            filename=data['filename'],
            metadata=data.get('metadata', {}),
            created_at=created_at
        )
