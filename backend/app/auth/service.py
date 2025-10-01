import logging
from typing import Dict, List, Optional, Any, Tuple
import re
from datetime import datetime

from ..auth.models import User
from ..core.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)

class AuthService:
    """Service for authentication and user management."""
    
    def __init__(self, user_repo: UserRepository):
        """
        Initialize the auth service.
        
        Args:
            user_repo: UserRepository instance
        """
        self.user_repo = user_repo
    
    def register_user(
        self, 
        username: str, 
        email: str, 
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> Tuple[Optional[User], Optional[str]]:
        """
        Register a new user.
        
        Args:
            username: Username
            email: Email address
            password: Password
            first_name: First name (optional)
            last_name: Last name (optional)
            
        Returns:
            Tuple of (User, None) if successful, (None, error_message) otherwise
        """
        # Input validation
        if not username or not email or not password:
            return None, "Username, email, and password are required"
        
        # Username validation - no underscores allowed, only letters and numbers
        if not re.match(r'^[a-zA-Z0-9]{3,30}$', username):
            return None, "Username must be 3-30 characters and contain only letters and numbers"
        
        # Email validation
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return None, "Invalid email format"
        
        # Password validation
        if len(password) < 8:
            return None, "Password must be at least 8 characters"
        
        # Check if username or email already exists
        if self.user_repo.username_exists(username):
            return None, "Username already exists"
        
        if self.user_repo.email_exists(email.lower()):
            return None, "Email already exists"
        
        # Create and save the user
        user = User.create(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_admin=True  # All users are admins for now (one for all, all for one)
        )
        
        if self.user_repo.save(user):
            logger.info(f"User registered: {username}")
            return user, None
        else:
            logger.error(f"Failed to save user: {username}")
            return None, "Error creating user"
    
    def authenticate(self, username_or_email: str, password: str) -> Tuple[Optional[User], Optional[str]]:
        """
        Authenticate a user.
        
        Args:
            username_or_email: Username or email address
            password: Password
            
        Returns:
            Tuple of (User, None) if successful, (None, error_message) otherwise
        """
        # Check if input is email or username
        is_email = '@' in username_or_email
        
        # Get user by username or email
        if is_email:
            user = self.user_repo.get_by_email(username_or_email.lower())
            login_type = "email"
        else:
            user = self.user_repo.get_by_username(username_or_email)
            login_type = "username"
        
        if not user:
            return None, f"User not found with this {login_type}"
        
        # Check if account is active
        if not user.is_active:
            return None, "Account is deactivated"
        
        # Check password
        if not user.check_password(password):
            return None, "Invalid password"
        
        # Record login
        user.record_login()
        self.user_repo.save(user)
        
        return user, None
    
    # DB-OPERATION: read user
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        Get a user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            User if found, None otherwise
        """
        return self.user_repo.get_by_id(user_id)
    
    # DB-OPERATION: read user
    def get_user_by_token(self, token: str) -> Optional[User]:
        """
        Get a user by API token.
        
        Args:
            token: API token
            
        Returns:
            User if found, None otherwise
        """
        return self.user_repo.get_by_token(token)
    
    # DB-OPERATION: read user
    def list_users(self) -> List[Dict[str, Any]]:
        """
        List all users.
        
        Returns:
            List of user dictionaries (without private fields)
        """
        users = self.user_repo.list_users()
        return [user.to_dict() for user in users]
    
    # DB-OPERATION: update user
    def update_user(
        self,
        user_id: str,
        username: Optional[str] = None,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_admin: Optional[bool] = None,
        preferences: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[User], Optional[str]]:
        """
        Update a user.
        
        Args:
            user_id: User ID
            username: New username (optional)
            email: New email (optional)
            first_name: New first name (optional)
            last_name: New last name (optional)
            is_active: New active status (optional)
            is_admin: New admin status (optional)
            preferences: New preferences (optional)
            
        Returns:
            Tuple of (User, None) if successful, (None, error_message) otherwise
        """
        # Get the user
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return None, "User not found"
        
        # Check username uniqueness if changing
        if username and username != user.username:
            if not re.match(r'^[a-zA-Z0-9]{3,30}$', username):
                return None, "Username must be 3-30 characters and contain only letters and numbers"
            
            if self.user_repo.username_exists(username):
                return None, "Username already exists"
            
            user.username = username
        
        # Check email uniqueness if changing
        if email and email != user.email:
            email_lower = email.lower()
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                return None, "Invalid email format"
                
            if self.user_repo.email_exists(email_lower):
                return None, "Email already exists"
            
            user.email = email
        
        # Update other fields if provided
        if first_name is not None:
            user.first_name = first_name
        
        if last_name is not None:
            user.last_name = last_name
        
        if is_active is not None:
            user.is_active = is_active
        
        if is_admin is not None:
            user.is_admin = is_admin
        
        if preferences is not None:
            user.preferences = preferences
        
        # Update timestamp
        user.updated_at = datetime.now()
        
        # Save the updated user
        if self.user_repo.save(user):
            return user, None
        else:
            return None, "Error updating user"
    
    def change_password(self, user_id: str, current_password: str, new_password: str) -> Tuple[bool, Optional[str]]:
        """
        Change a user's password.
        
        Args:
            user_id: User ID
            current_password: Current password
            new_password: New password
            
        Returns:
            Tuple of (success, error_message)
        """
        # Get the user
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return False, "User not found"
        
        # Verify current password
        if not user.check_password(current_password):
            return False, "Current password is incorrect"
        
        # Validate new password
        if len(new_password) < 8:
            return False, "New password must be at least 8 characters"
        
        # Update password
        user.update_password(new_password)
        
        # Save the updated user
        if self.user_repo.save(user):
            return True, None
        else:
            return False, "Error updating password"
    
    def generate_new_token(self, user_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate a new API token for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Tuple of (token, None) if successful, (None, error_message) otherwise
        """
        # Get the user
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return None, "User not found"
        
        # Generate new token
        token = user.generate_new_token()
        
        # Save the updated user
        if self.user_repo.save(user):
            return token, None
        else:
            return None, "Error generating token"
    
    # DB-OPERATION: delete user
    def delete_user(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Delete a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Tuple of (success, error_message)
        """
        if self.user_repo.delete(user_id):
            return True, None
        else:
            return False, "Error deleting user"

    def verify_password_reset_token(self, token: str) -> Optional[str]:
        """
        Verify a password reset token.
        
        Args:
            token: Password reset token
            
        Returns:
            User ID if valid, None otherwise
        """
        try:
            user_id = self.user_repo.verify_password_reset_token(token)
            return user_id
        except Exception as e:
            logger.error(f"Error verifying reset token: {str(e)}")
            return None
    
    def generate_password_reset_token(self, user_id: str) -> str:
        """
        Generate a password reset token for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Password reset token
        """
        import secrets
        import time
        
        # Generate a secure random token
        token = secrets.token_urlsafe(32)
        
        # Get the user
        user = self.user_repo.get_by_id(user_id)
        if not user:
            logger.error(f"Cannot generate token for non-existent user: {user_id}")
            return ""
        
        # Store token in user preferences with expiration time (24 hours)
        expiration = int(time.time()) + 24 * 60 * 60
        
        if 'reset_tokens' not in user.preferences:
            user.preferences['reset_tokens'] = {}
        
        # Add token to user preferences
        user.preferences['reset_tokens'][token] = expiration
        
        # Remove expired tokens
        now = int(time.time())
        expired_tokens = [t for t, exp in user.preferences['reset_tokens'].items() if exp < now]
        for expired in expired_tokens:
            del user.preferences['reset_tokens'][expired]
        
        # Save user
        if not self.user_repo.save(user):
            logger.error(f"Failed to save reset token for user: {user_id}")
            return ""
        
        return token
