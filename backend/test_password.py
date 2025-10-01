#!/usr/bin/env python3
"""
Test password verification
"""
from werkzeug.security import check_password_hash, generate_password_hash

# Test password
password = "admin123"

# The hash from the user file
stored_hash = "pbkdf2:sha256:600000$dgg6pyUZ0OKU1r0y$7e33d12859ca72be237588c8a999c7ebc8040e7c732c9ebc1cdcf8f3a92d2de2"

# Test if the password matches
matches = check_password_hash(stored_hash, password)
print(f"Password 'admin123' matches hash: {matches}")

# Let's also generate a new hash with a different method to ensure compatibility
new_hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
print(f"\nNew hash generated: {new_hash}")

# Test the new hash
new_matches = check_password_hash(new_hash, password)
print(f"Password 'admin123' matches new hash: {new_matches}")

# Let's also check what method the User model uses
import sys
sys.path.append('.')
from app.auth.models import User

# Create a test user object with the password
test_user = User(id="test", username="test", email="test@test.com")
test_user.password_hash = stored_hash

# Test using the User model's check_password method
user_check = test_user.check_password(password)
print(f"\nUser model check_password result: {user_check}")