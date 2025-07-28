#!/usr/bin/env python3
"""
Test script to verify the complete login process.
"""

import os
import sys
from werkzeug.security import generate_password_hash, check_password_hash

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.col import login_collection

def test_user_in_database():
    """Test that the user exists in the database with correct password."""
    print("Testing user in database...")
    
    # Find the user
    user_doc = login_collection.find_one({'username': 'ahmed'})
    if not user_doc:
        print("ERROR: User 'ahmed' not found in database")
        return False
    
    print(f"User found: {user_doc['username']} ({user_doc['email']})")
    print(f"Is super admin: {user_doc.get('is_super_admin', False)}")
    
    # Test password
    password = "IQZEIY1KFn3j"
    if check_password_hash(user_doc['password'], password):
        print("SUCCESS: Password verification passed")
        return True
    else:
        print("ERROR: Password verification failed")
        return False

def test_user_creation():
    """Test creating a new user with the same method used in manage.py."""
    print("\nTesting user creation...")
    
    # Check if user already exists
    existing_user = login_collection.find_one({'username': 'testuser'})
    if existing_user:
        # Delete existing test user
        login_collection.delete_one({'username': 'testuser'})
        print("Deleted existing test user")
    
    # Create a new test user
    password = "testpassword123"
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
    
    result = login_collection.insert_one({
        'username': 'testuser',
        'email': 'test@example.com',
        'password': hashed_password,
        'is_super_admin': False
    })
    
    if result.inserted_id:
        print("SUCCESS: Test user created")
        
        # Verify the user
        user_doc = login_collection.find_one({'username': 'testuser'})
        if user_doc and check_password_hash(user_doc['password'], password):
            print("SUCCESS: Test user password verification passed")
            # Clean up
            login_collection.delete_one({'username': 'testuser'})
            print("Cleaned up test user")
            return True
        else:
            print("ERROR: Test user password verification failed")
            return False
    else:
        print("ERROR: Failed to create test user")
        return False

if __name__ == '__main__':
    print("Running login tests...")
    
    success1 = test_user_in_database()
    success2 = test_user_creation()
    
    if success1 and success2:
        print("\nAll tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed!")
        sys.exit(1)
