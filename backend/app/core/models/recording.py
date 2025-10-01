from dataclasses import dataclass, field
from datetime import datetime
import uuid
from enum import Enum
from typing import Optional, Dict, Any
import logging

# UPDATED Enum: Combines Type and initial Status/Origin
class RecordingType(Enum):
    RAW_RECORDED = "raw_recorded" # Recorded via UI, unprocessed (except format)
    RAW_UPLOADED = "raw_uploaded" # Uploaded file, unprocessed (except format)
    PENDING = "pending"          # Processed segment awaiting verification
    GOLD = "gold"                # Verified/Approved segment
    AUGMENTED = "augmented"      # Artificial variation of a GOLD segment
    REJECTED = "rejected"        # Segment discarded during verification

# REMOVED RecordingStatus Enum
# class RecordingStatus(Enum): ...

@dataclass
class Recording:
    """Represents metadata for a single sound instance file (wav)."""
    # --- Non-Default Fields FIRST ---
    user_id: str # User's UUID
    class_id: str # Class UUID
    recording_type: RecordingType # Use the single combined enum
    relative_wav_path: str # Path relative to data_root (e.g., sounds/ClassName/userID/raw/...) - Type determines last dir

    # --- Fields with Defaults LAST ---
    # ID should be generated externally with proper format, not here
    id: str = field(default_factory=lambda: f"temp_{uuid.uuid4()}") 
    timestamp: datetime = field(default_factory=datetime.now) # Use this as primary timestamp (created_at)
    updated_at: datetime = field(default_factory=datetime.now) 

    # Optional fields (default to None)
    duration: Optional[float] = None # In seconds
    sample_rate: Optional[int] = None # e.g., hz
    source_sound_id: Optional[str] = None # Link for PENDING/GOLD/AUGMENTED
    augmentation_params: Optional[Dict[str, Any]] = None # Specific to AUGMENTED
    metadata: Dict[str, Any] = field(default_factory=dict) # For username, class_name, source, file_type, audio props etc.

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the object to a dictionary suitable for JSON."""
        # Ensure required fields from metadata are included at top level if needed
        base_metadata = self.metadata or {}
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "class_id": self.class_id,
            # Store essential info also directly if convenient, otherwise rely on metadata dict
            "username": base_metadata.get('username'), 
            "class_name": base_metadata.get('class_name'), 
            "recording_type": self.recording_type.value,
            # "recording_status": self.status.value, # REMOVED status
            "created_at": self.timestamp.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "relative_wav_path": self.relative_wav_path,
            "file_type": base_metadata.get('file_type', '.wav'), 
            "source": base_metadata.get('source'), 
            "duration_seconds": self.duration, 
            "hz": self.sample_rate, 
            "bit_depth": base_metadata.get('bit_depth'),
            "physical_type": base_metadata.get('physical_type'),
            "file_size_bytes": base_metadata.get('file_size_bytes'),
            "source_sound_id": self.source_sound_id,
            "augmentation_params": self.augmentation_params,
            "metadata": base_metadata, # Include the full metadata dict as well
        }
        # Filter out None values for cleaner JSON
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional['Recording']:
        """Deserializes from a dictionary."""
        # Essential fields needed to construct the object
        rec_id = data.get('id')
        user_id = data.get('user_id')
        class_id = data.get('class_id')
        type_val = data.get('recording_type', data.get('type')) # Use new key first
        rel_path = data.get('relative_wav_path')
        ts_str = data.get('created_at', data.get('timestamp'))

        if not all([rec_id, user_id, class_id, type_val, rel_path, ts_str]):
            logging.warning(f"Skipping record {rec_id or 'NO_ID'}: Missing essential field(s) (id, user_id, class_id, type, rel_path, timestamp/created_at). Data: {data}")
            return None
        
        try: # Convert type string to Enum
            rec_type = RecordingType(str(type_val).lower())
        except ValueError:
            logging.warning(f"Skipping record {rec_id}: Invalid recording_type value '{type_val}'")
            return None
            
        try: # Convert timestamp string to datetime
            timestamp = datetime.fromisoformat(ts_str)
        except (ValueError, TypeError):
            logging.warning(f"Skipping record {rec_id}: Invalid created_at/timestamp format '{ts_str}'")
            return None
            
        # Handle updated_at (optional, defaults to created_at)
        updated_at_str = data.get('updated_at', ts_str)
        try: updated_at = datetime.fromisoformat(updated_at_str)
        except: updated_at = timestamp
            
        # --- Create the object --- 
        try:
            # Extract known top-level fields
            obj_data = {
                "id": rec_id,
                "user_id": user_id,
                "class_id": class_id,
                "recording_type": rec_type,
                "relative_wav_path": rel_path,
                "timestamp": timestamp,
                "updated_at": updated_at, 
                "duration": data.get('duration_seconds', data.get('duration')), # Allow float/None
                "sample_rate": data.get('hz', data.get('sample_rate')), # Allow int/None
                "source_sound_id": data.get('source_sound_id'),
                "augmentation_params": data.get('augmentation_params'),
                "metadata": data.get('metadata', {}) # Ensure metadata dict exists
            }
            # Filter out None values before passing to constructor?
            # No, dataclass handles Optional fields
            
            return cls(**obj_data)
            
        except Exception as e:
            logging.error(f"Error creating Recording object for {rec_id} from dict: {e}", exc_info=True)
            return None

    # REMOVED update_status method
    # def update_status(self, new_status: RecordingStatus): ...

    def __post_init__(self):
        # Ensure type is enum
        if isinstance(self.recording_type, str):
            try: self.recording_type = RecordingType(self.recording_type)
            except ValueError: logging.error(f"Invalid type string '{self.recording_type}' passed to Recording init for {self.id}")
        # Ensure timestamps are datetime
        if isinstance(self.timestamp, str): self.timestamp = datetime.fromisoformat(self.timestamp)
        if isinstance(self.updated_at, str): self.updated_at = datetime.fromisoformat(self.updated_at)

        # Basic validation
        if self.recording_type in [RecordingType.PENDING, RecordingType.GOLD, RecordingType.AUGMENTED] and not self.source_sound_id:
             logging.warning(f"Recording {self.id} of type {self.recording_type.value} is missing source_sound_id.")
        if self.recording_type == RecordingType.AUGMENTED and not self.augmentation_params:
             logging.warning(f"Augmented recording {self.id} is missing augmentation_params.")
