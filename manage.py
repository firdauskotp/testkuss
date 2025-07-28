#!/usr/bin/env python3
"""
Management CLI for the KUSS application.
Provides commands for user management and system administration.
"""

import os
import sys
import getpass
from werkzeug.security import generate_password_hash
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv

def get_db_connection():
    """Get database connection without loading Flask app."""
    try:
        # Load environment variables
        load_dotenv()
        
        # MongoDB Configuration
        MONGO_URI = os.getenv('MONGO_URL')
        if MONGO_URI:
            # Remove quotes if present
            MONGO_URI = MONGO_URI.strip("'\"")
            
            # Try to connect without SSL first since local MongoDB typically doesn't use SSL
            try:
                mongo = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tls=False)
                # Test the connection
                mongo.admin.command('ping')
                print("Connected to MongoDB successfully")
                return mongo
            except Exception as error:
                print(f"Connection failed: {error}")
                # Try with SSL as fallback
                try:
                    mongo = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
                    mongo.admin.command('ping')
                    print("Connected to MongoDB with SSL")
                    return mongo
                except Exception as ssl_error:
                    print(f"SSL connection also failed: {ssl_error}")
                    raise Exception("Could not connect to MongoDB")
        else:
            raise Exception("MONGO_URL not found in environment variables")
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

# Get database connection
mongo = get_db_connection()
if mongo:
    login_db = mongo['login_admin']
    login_collection = login_db['log']
else:
    # Create a mock collection for testing
    class MockCollection:
        def find_one(self, query):
            return None
        def find(self, query=None, projection=None):
            return []
        def insert_one(self, doc):
            class MockResult:
                inserted_id = "mock_id"
            return MockResult()
        def delete_one(self, query):
            class MockResult:
                deleted_count = 1
            return MockResult()
        def count_documents(self, query):
            return 0
    login_collection = MockCollection()

def create_super_user():
    """Create a super admin user via CLI."""
    print("Create Super Admin User")
    print("=" * 30)
    
    # Get user input
    username = input("Username: ").strip().lower()
    if not username or len(username) < 3:
        print("Error: Username must be at least 3 characters long.")
        return False
    
    email = input("Email: ").strip().lower()
    if not email or '@' not in email:
        print("Error: Please enter a valid email address.")
        return False
    
    # Check if user already exists
    if login_collection.find_one({'$or': [{'username': username}, {'email': email}]}):
        print("Error: Username or email already exists.")
        return False
    
    # Get password
    password = getpass.getpass("Password (leave blank to auto-generate): ")
    if not password:
        # Generate a secure password
        import random
        import string
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(random.choice(characters) for _ in range(12))
        print(f"Generated password: {password}")
    
    if len(password) < 8:
        print("Error: Password must be at least 8 characters long.")
        return False
    
    # Confirm password
    confirm_password = getpass.getpass("Confirm Password: ")
    if password != confirm_password:
        print("Error: Passwords do not match.")
        return False
    
    # Create user
    try:
        login_collection.insert_one({
            'username': username,
            'email': email,
            'password': generate_password_hash(password, method='pbkdf2:sha256', salt_length=16),
            'is_super_admin': True
        })
        print("Success: Super admin user created successfully!")
        return True
    except Exception as e:
        print(f"Error: Failed to create user - {str(e)}")
        return False

def list_admin_users():
    """List all admin users."""
    print("Admin Users")
    print("=" * 30)
    
    try:
        users = list(login_collection.find({}, {'username': 1, 'email': 1, 'is_super_admin': 1}))
        if not users:
            print("No admin users found.")
            return
        
        print(f"{'Username':<20} {'Email':<30} {'Super Admin'}")
        print("-" * 60)
        for user in users:
            username = user.get('username', 'N/A')
            email = user.get('email', 'N/A')
            is_super = 'Yes' if user.get('is_super_admin', False) else 'No'
            print(f"{username:<20} {email:<30} {is_super}")
    except Exception as e:
        print(f"Error: Failed to list users - {str(e)}")

def delete_user():
    """Delete a user by username or email."""
    print("Delete User")
    print("=" * 30)
    
    identifier = input("Enter username or email to delete: ").strip()
    if not identifier:
        print("Error: Please provide a username or email.")
        return False
    
    try:
        # Find user
        user = login_collection.find_one({'$or': [{'username': identifier}, {'email': identifier}]})
        if not user:
            print("Error: User not found.")
            return False
        
        # Confirm deletion
        username = user.get('username', 'N/A')
        email = user.get('email', 'N/A')
        print(f"User found: {username} ({email})")
        confirm = input("Are you sure you want to delete this user? (y/N): ").strip().lower()
        
        if confirm != 'y':
            print("Deletion cancelled.")
            return False
        
        # Delete user
        result = login_collection.delete_one({'_id': user['_id']})
        if result.deleted_count:
            print("Success: User deleted successfully.")
            return True
        else:
            print("Error: Failed to delete user.")
            return False
    except Exception as e:
        print(f"Error: Failed to delete user - {str(e)}")
        return False

def set_user_password():
    """Set password for a user."""
    print("Set User Password")
    print("=" * 30)
    
    identifier = input("Enter username or email: ").strip()
    if not identifier:
        print("Error: Please provide a username or email.")
        return False
    
    try:
        # Find user
        user = login_collection.find_one({'$or': [{'username': identifier}, {'email': identifier}]})
        if not user:
            print("Error: User not found.")
            return False
        
        # Get new password
        password = getpass.getpass("New Password (leave blank to auto-generate): ")
        if not password:
            # Generate a secure password
            import random
            import string
            characters = string.ascii_letters + string.digits + "!@#$%^&*"
            password = ''.join(random.choice(characters) for _ in range(12))
            print(f"Generated password: {password}")
        
        if len(password) < 8:
            print("Error: Password must be at least 8 characters long.")
            return False
        
        # Confirm password
        confirm_password = getpass.getpass("Confirm New Password: ")
        if password != confirm_password:
            print("Error: Passwords do not match.")
            return False
        
        # Update password
        result = login_collection.update_one(
            {'_id': user['_id']},
            {'$set': {'password': generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)}}
        )
        
        if result.modified_count:
            print("Success: Password updated successfully.")
            return True
        else:
            print("Error: Failed to update password.")
            return False
    except Exception as e:
        print(f"Error: Failed to set password - {str(e)}")
        return False

def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("KUSS Management CLI")
        print("=" * 30)
        print("Available commands:")
        print("  createsuperuser - Create a super admin user")
        print("  listusers       - List all admin users")
        print("  deleteuser      - Delete a user")
        print("  setpassword     - Set password for a user")
        print("\nUsage: python manage.py <command>")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'createsuperuser':
        create_super_user()
    elif command == 'listusers':
        list_admin_users()
    elif command == 'deleteuser':
        delete_user()
    elif command == 'setpassword':
        set_user_password()
    else:
        print(f"Error: Unknown command '{command}'")
        print("Available commands: createsuperuser, listusers, deleteuser, setpassword")

if __name__ == '__main__':
    main()
