"""
CSRF Token utilities for manual CSRF protection.
"""
import os
import hmac
import hashlib
import time
from flask import session, request, current_app

def generate_csrf_token():
    """Generate a CSRF token for the current session."""
    if 'csrf_token' not in session:
        # Generate a new CSRF token
        token = os.urandom(32).hex()
        session['csrf_token'] = token
        session['csrf_timestamp'] = time.time()
    return session['csrf_token']

def validate_csrf_token(token):
    """Validate a CSRF token."""
    if not token:
        return False
    
    session_token = session.get('csrf_token')
    if not session_token:
        return False
    
    # Check if token matches
    if not hmac.compare_digest(token, session_token):
        return False
    
    # Check if token is not too old (1 hour)
    timestamp = session.get('csrf_timestamp', 0)
    if time.time() - timestamp > 3600:  # 1 hour
        return False
    
    return True

def get_csrf_token():
    """Get the current CSRF token, generating one if needed."""
    return generate_csrf_token()
