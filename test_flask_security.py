#!/usr/bin/env python3
"""
Test script to verify Flask-Security configuration.
"""

import os
import sys
from werkzeug.security import check_password_hash

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Set up Flask app
from backend import app
from backend.security import configure_security
from backend.models import UserDataModel
from backend.col import login_collection

def test_flask_security_config():
    """Test Flask-Security configuration."""
    print("Testing Flask-Security configuration...")
    
    with app.app_context():
        # Test that we can find the user
        user_doc = login_collection.find_one({'username': 'ahmed'})
        if not user_doc:
            print("ERROR: User 'ahmed' not found in database")
            return False
        
        print(f"User found: {user_doc['username']} ({user_doc['email']})")
        
        # Test creating user object through Flask-Security datastore
        from backend.security import MongoUserDatastore
        datastore = MongoUserDatastore(login_collection)
        
        # Test find_user by username
        user = datastore.find_user(username='ahmed')
        if not user:
            print("ERROR: Could not find user through datastore")
            return False
        
        print(f"User object created: {user.username} ({user.email})")
        print(f"User password hash: {user.password[:50]}...")
        print(f"User has admin role: {user.has_role('admin')}")
        
        # Test password verification
        from flask_security.utils import verify_password
        password = "IQZEIY1KFn3j"
        
        # Print some debug info
        print(f"Testing password: {password}")
        print(f"User password hash: {user.password}")
        
        # Test with werkzeug's check_password_hash first
        from werkzeug.security import check_password_hash
        if check_password_hash(user.password, password):
            print("SUCCESS: Werkzeug password verification passed")
        else:
            print("ERROR: Werkzeug password verification failed")
        
        # Test with Flask-Security's verify_password
        try:
            if verify_password(password, user.password):
                print("SUCCESS: Flask-Security password verification passed")
                return True
            else:
                print("ERROR: Flask-Security password verification failed")
                return False
        except Exception as e:
            print(f"ERROR: Flask-Security password verification failed with exception: {e}")
            return False

if __name__ == '__main__':
    print("Running Flask-Security tests...")
    
    try:
        success = test_flask_security_config()
        if success:
            print("\nFlask-Security test passed!")
            sys.exit(0)
        else:
            print("\nFlask-Security test failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\nFlask-Security test failed with exception: {e}")
        sys.exit(1)
