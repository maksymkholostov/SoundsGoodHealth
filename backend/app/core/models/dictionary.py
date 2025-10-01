from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid


@dataclass
class SoundClass:
    """
    Represents a globally unique sound class definition.
    Stored in the central class registry.
    """
    name: str  # User-friendly name for the sound class (should be unique, enforced by service)
    id: str = field(default="")  # Will be set to cls_<name> format in __post_init__
    description: Optional[str] = None  # Optional description
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Generate human-readable ID from name if not provided"""
        if not self.id and self.name:
            # Create ID in format cls_<name> with lowercase name
            # Ensure the name is valid for use in filenames
            safe_name = self.name.strip().lower()
            if not safe_name:
                raise ValueError("Sound class name cannot be empty")
            self.id = f"cls_{safe_name}"
    
    # Removed the create classmethod as default_factory handles ID generation
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        # Ensure updated_at is current on serialization if needed? Or handle in service?
        # For now, just serialize current state.
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SoundClass':
        """Create from dictionary"""
        # Handle date parsing gracefully
        created_at_input = data.get('created_at')
        updated_at_input = data.get('updated_at')
        
        created_at = None
        if isinstance(created_at_input, str):
            try:
                created_at = datetime.fromisoformat(created_at_input)
            except ValueError:
                 created_at = datetime.now() # Fallback if format is wrong
        elif isinstance(created_at_input, datetime):
            created_at = created_at_input
        else:
             created_at = datetime.now() # Fallback if missing or wrong type

        updated_at = None
        if isinstance(updated_at_input, str):
            try:
                updated_at = datetime.fromisoformat(updated_at_input)
            except ValueError:
                 updated_at = datetime.now()
        elif isinstance(updated_at_input, datetime):
            updated_at = updated_at_input
        else:
             updated_at = datetime.now()
        
        return cls(
            name=data['name'],
            id=data['id'], # ID comes from data, no default factory used here
            description=data.get('description'),
            created_at=created_at,
            updated_at=updated_at
        )


@dataclass
class Dictionary:
    """
    Represents a collection of sound classes, identified by their global IDs.
    Stored in the central system dictionaries file.
    """
    name: str  # User-friendly name for the dictionary (should be unique, enforced by service)
    creator_user_id: str # User ID of the original creator (as a label)
    id: str = field(default="")  # Will be set to dict_<name> format in __post_init__ # Add default factory for ID
    description: Optional[str] = None  # Optional description
    class_ids: List[str] = field(default_factory=list)  # List of SoundClass IDs from the global registry
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Generate human-readable ID from name if not provided"""
        if not self.id and self.name:
            # Create ID in format dict_<name> with lowercase name and underscores for spaces
            safe_name = self.name.strip().lower().replace(' ', '_')
            if not safe_name:
                raise ValueError("Dictionary name cannot be empty")
            self.id = f"dict_{safe_name}"
    
    # Removed the old create classmethod, default factory handles ID
    
    def add_class(self, class_id: str) -> bool:
        """
        Add a sound class ID to this dictionary if not already present.
        
        Args:
            class_id: ID of the class (from global registry) to add.
            
        Returns:
            True if the class ID was added, False if it was already present.
        """
        if class_id not in self.class_ids:
            self.class_ids.append(class_id)
            self.updated_at = datetime.now()
            return True
        return False
    
    def remove_class(self, class_id: str) -> bool:
        """
        Remove a sound class ID from this dictionary.
        
        Args:
            class_id: ID of the class to remove.
            
        Returns:
            True if the class ID was removed, False if not found.
        """
        if class_id in self.class_ids:
            self.class_ids.remove(class_id)
            self.updated_at = datetime.now()
            return True
        return False
    
    # Removed get_class method - responsibility moved to service layer
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'creator_user_id': self.creator_user_id, # Added creator
            'description': self.description,
            'class_ids': self.class_ids, # Use class_ids now
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Dictionary':
        """Create from dictionary"""
        # Handle date parsing gracefully (similar to SoundClass)
        created_at_input = data.get('created_at')
        updated_at_input = data.get('updated_at')
        created_at = datetime.now() # Default
        updated_at = datetime.now() # Default
        if isinstance(created_at_input, str):
            try: created_at = datetime.fromisoformat(created_at_input)
            except ValueError: pass # Keep default
        elif isinstance(created_at_input, datetime): created_at = created_at_input
        if isinstance(updated_at_input, str):
            try: updated_at = datetime.fromisoformat(updated_at_input)
            except ValueError: pass # Keep default
        elif isinstance(updated_at_input, datetime): updated_at = updated_at_input

        # Ensure class_ids is a list, default to empty list if missing or wrong type
        class_ids = data.get('class_ids', [])
        if not isinstance(class_ids, list):
             class_ids = []

        return cls(
            name=data['name'],
            creator_user_id=data.get('creator_user_id', 'unknown'), # Added creator, provide default
            id=data['id'],
            description=data.get('description'),
            class_ids=class_ids, # Use class_ids now
            created_at=created_at,
            updated_at=updated_at
        )
