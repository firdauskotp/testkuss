#!/usr/bin/env python3
"""
Script to check user password in the database.
"""

import os
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv
from werkzeug.security import check_password_hash

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
    
    # Find the user
    user = login_collection.find_one({'username': 'ahmed'})
    if user:
        print(f"User found: {user['username']} ({user['email']})")
        print(f"Is super admin: {user.get('is_super_admin', False)}")
        print(f"Password hash: {user['password'][:50]}...")
        
        # Test some common passwords and the auto-generated one
        test_passwords = ['admin123', 'admin1234', 'password', 'admin', 'IQZEIY1KFn3j', 'sxzinV0qfg$Y']
        for pwd in test_passwords:
            if check_password_hash(user['password'], pwd):
                print(f"Password '{pwd}' matches!")
                break
        else:
            print("None of the test passwords matched.")
            print("The password was auto-generated during the setpassword command.")
    else:
        print("User 'ahmed' not found.")
else:
    print("Could not connect to database.")
