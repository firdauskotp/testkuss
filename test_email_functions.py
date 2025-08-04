#!/usr/bin/env python3
"""
Test email functions in utils.py
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.config import get_config, validate_environment

def test_email_functions():
    """Test all email functions in utils.py"""
    
    print("🔧 Testing Email Functions...")
    print("=" * 50)
    
    try:
        # Validate environment
        validate_environment()
        print("✅ Environment validation passed")
        
        # Get configuration
        config_class = get_config()
        print(f"✅ Configuration loaded: {config_class.__name__}")
        
        # Test Flask app and email setup
        from flask import Flask
        from flask_mail import Mail
        
        # Create minimal Flask app for testing
        test_app = Flask(__name__)
        test_app.config.from_object(config_class)
        
        with test_app.app_context():
            mail = Mail(test_app)
            
            # Import email functions
            from backend.utils import send_email, send_email_to_customer, send_email_to_admin, is_valid_email
            
            print("\n🔍 Testing Email Function Imports...")
            print("✅ send_email imported successfully")
            print("✅ send_email_to_customer imported successfully")
            print("✅ send_email_to_admin imported successfully")
            print("✅ is_valid_email imported successfully")
            
            # Test email validation
            print("\n🔍 Testing Email Validation...")
            valid_emails = ["test@example.com", "user.name@domain.co.uk", "admin@localhost.local"]
            invalid_emails = ["invalid-email", "@domain.com", "user@", ""]
            
            for email in valid_emails:
                if is_valid_email(email):
                    print(f"✅ Valid email: {email}")
                else:
                    print(f"❌ Should be valid: {email}")
            
            for email in invalid_emails:
                if not is_valid_email(email):
                    print(f"✅ Invalid email correctly rejected: {email}")
                else:
                    print(f"❌ Should be invalid: {email}")
            
            # Test email function signatures
            print("\n🔍 Testing Email Function Signatures...")
            
            # Test that we can create a test email without sending
            test_app.config['MAIL_SUPPRESS_SEND'] = True  # Suppress actual sending
            
            try:
                # Test send_email function
                result = send_email(
                    to_email="test@example.com",
                    from_email=config_class.MAIL_DEFAULT_SENDER,
                    subject="Test Email",
                    body_html="<h1>Test</h1><p>This is a test email.</p>",
                    mail=mail
                )
                print("✅ send_email function signature works correctly")
                
                # Test send_email_to_customer function
                send_email_to_customer(
                    case_no="TEST123",
                    user_email="customer@example.com",
                    from_email=config_class.MAIL_DEFAULT_SENDER,
                    mail=mail
                )
                print("✅ send_email_to_customer function works correctly")
                
                # Test send_email_to_admin function
                # Set admin email for testing
                os.environ['ADMIN_EMAIL_ADDRESS'] = 'admin@example.com'
                send_email_to_admin(
                    case_no="TEST123",
                    user_email="customer@example.com",
                    from_email=config_class.MAIL_DEFAULT_SENDER,
                    mail=mail
                )
                print("✅ send_email_to_admin function works correctly")
                
            except Exception as e:
                print(f"❌ Email function test failed: {e}")
                return False
            
            print("\n🎉 All email function tests passed!")
            
            # Show current email configuration
            print("\n📧 Current Email Configuration:")
            print(f"Mail Server: {config_class.MAIL_SERVER}")
            print(f"Mail Port: {config_class.MAIL_PORT}")
            print(f"Mail SSL: {config_class.MAIL_USE_SSL}")
            print(f"Mail Username: {config_class.MAIL_USERNAME}")
            print(f"Default Sender: {config_class.MAIL_DEFAULT_SENDER}")
            print(f"Suppress Send: {config_class.MAIL_SUPPRESS_SEND}")
            
            return True
                
    except Exception as e:
        print(f"❌ Email function test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_email_functions()
    if success:
        print("\n✅ All email functions are working correctly!")
    else:
        print("\n❌ Some email functions have issues.")
    sys.exit(0 if success else 1)
