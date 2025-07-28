#!/usr/bin/env python3
"""
Test script to verify authentication functionality.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from werkzeug.security import generate_password_hash, check_password_hash
from flask_security.utils import verify_password

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from models import User, UserDataModel, Role

class TestAuthentication(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a test user document (simulating database document)
        self.test_password = "IQZEIY1KFn3j"
        self.hashed_password = generate_password_hash(self.test_password, method='pbkdf2:sha256', salt_length=16)
        
        self.user_doc = {
            '_id': 'test_id',
            'username': 'ahmed',
            'email': 'medoroyalrma@gmail.com',
            'password': self.hashed_password,
            'is_super_admin': True
        }
    
    def test_password_hashing(self):
        """Test that password hashing and verification works correctly."""
        # Test that the password hash is valid
        self.assertTrue(check_password_hash(self.hashed_password, self.test_password))
    
    def test_user_creation_from_document(self):
        """Test creating User object from database document."""
        # Create user from document
        user = UserDataModel.from_admin_document(self.user_doc)
        
        # Verify user properties
        self.assertEqual(user.username, 'ahmed')
        self.assertEqual(user.email, 'medoroyalrma@gmail.com')
        self.assertEqual(user.id, 'test_id')
        self.assertEqual(user.password, self.hashed_password)
        
        # Verify user has admin role
        self.assertTrue(user.has_role('admin'))
    
    def test_user_password_verification(self):
        """Test that User object can verify passwords correctly."""
        # Create user from document
        user = UserDataModel.from_admin_document(self.user_doc)
        
        # Test password verification using check_password_hash
        self.assertTrue(check_password_hash(user.password, self.test_password))
        
        # Test with wrong password
        self.assertFalse(check_password_hash(user.password, "wrongpassword"))

if __name__ == '__main__':
    unittest.main()
