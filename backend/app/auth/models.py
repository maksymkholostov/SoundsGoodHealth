from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

@dataclass
class User(UserMixin):
    """User model for authentication and authorization."""
    
    id: str
    username: str
    email: str
    password_hash: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    api_token: Optional[str] = None
    last_login: Optional[datetime] = None
    last_active: Optional[datetime] = None  # Track when user was last active
    preferences: Dict[str, Any] = field(default_factory=dict)
    
    # DB-OPERATION: read unknown
    def get_id(self):
        """Required by Flask-Login."""
        return self.id
    
    @classmethod
    def create(cls, username: str, email: str, password: str, first_name: Optional[str] = None, 
               last_name: Optional[str] = None, is_admin: bool = False) -> 'User':
        """
        Create a new user with hashed password.
        
        Args:
            username: Username
            email: Email address
            password: Plain text password (will be hashed)
            first_name: Optional first name
            last_name: Optional last name
            is_admin: Whether user has admin privileges
            
        Returns:
            New User instance
        """
        # Use username as the user ID for better readability and organization
        return cls(
            id=username,  # Username becomes the permanent user ID
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            is_admin=is_admin,
            api_token=str(uuid.uuid4())
        )
    
    def check_password(self, password: str) -> bool:
        """
        Check if password matches user's password hash.
        
        Args:
            password: Plain text password to check
            
        Returns:
            True if password matches, False otherwise
        """
        return check_password_hash(self.password_hash, password)
    
    # DB-OPERATION: update unknown
    def update_password(self, password: str) -> None:
        """
        Update user's password.
        
        Args:
            password: New plain text password
        """
        self.password_hash = generate_password_hash(password)
        self.updated_at = datetime.now()
    
    def generate_new_token(self) -> str:
        """
        Generate a new API token for the user.
        
        Returns:
            New API token
        """
        self.api_token = str(uuid.uuid4())
        self.updated_at = datetime.now()
        return self.api_token
    
    def record_login(self) -> None:
        """Record user login time."""
        now = datetime.now()
        self.last_login = now
        self.last_active = now  # Also update last active on login
        self.updated_at = now
    
    def update_activity(self) -> None:
        """Update user's last activity time."""
        self.last_active = datetime.now()
    
    def to_dict(self, include_private: bool = False) -> Dict[str, Any]:
        """
        Convert user to dictionary.
        
        Args:
            include_private: Whether to include private fields (password_hash, api_token)
            
        Returns:
            Dictionary representation of user
        """
        user_dict = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'last_active': self.last_active.isoformat() if self.last_active else None,
            'preferences': self.preferences
        }
        
        if include_private:
            user_dict.update({
                'password_hash': self.password_hash,
                'api_token': self.api_token
            })
        
        return user_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """
        Create a User instance from a dictionary.
        Handles datetime string conversion correctly.
        """
        from datetime import datetime # Local import
        
        parsed_dates = {}
        # Use correct field names from JSON/dict vs User class attribute
        date_fields_in_dict = {
            'created_at': 'created_at', 
            'updated_at': 'updated_at', 
            'last_active': 'last_active', 
            'last_login': 'last_login' # Key in dict maps to 'last_login' attribute
        }
        
        for dict_key, attr_name in date_fields_in_dict.items():
            if dict_key in data and isinstance(data[dict_key], str):
                try:
                    parsed_dates[attr_name] = datetime.fromisoformat(data[dict_key])
                except (ValueError, TypeError):
                    # Log warning or handle error, set to None
                    parsed_dates[attr_name] = None
            elif dict_key in data: # Handle if already a datetime (less likely from JSON)
                parsed_dates[attr_name] = data[dict_key]
            else:
                parsed_dates[attr_name] = None

        # Create instance with arguments accepted by __init__
        instance = cls(
            id=data.get('id'),
            username=data.get('username'),
            email=data.get('email'),
            password_hash=data.get('password_hash'),
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            is_active=data.get('is_active', True),
            is_admin=data.get('is_admin', False),
            api_token=data.get('api_token'),
            preferences=data.get('preferences', {})
        )
        
        # Set date fields after initialization
        instance.created_at = parsed_dates.get('created_at') or instance.created_at # Keep default if parsing failed
        instance.updated_at = parsed_dates.get('updated_at') or instance.updated_at # Keep default if parsing failed
        instance.last_login = parsed_dates.get('last_login')
        instance.last_active = parsed_dates.get('last_active')
        
        return instance
