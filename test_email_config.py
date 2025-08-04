#!/usr/bin/env python3
"""
Test Flask-Mail configuration directly
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.config import get_config, validate_environment

def test_flask_mail_config():
    """Test Flask-Mail configuration without starting the full Flask app"""
    
    print("🔧 Testing Flask-Mail Configuration...")
    print("=" * 50)
    
    try:
        # Validate environment
        validate_environment()
        print("✅ Environment validation passed")
        
        # Get configuration
        config_class = get_config()
        print(f"✅ Configuration loaded: {config_class.__name__}")
        
        # Test email configuration
        print(f"📧 Mail Server: {config_class.MAIL_SERVER}")
        print(f"📧 Mail Port: {config_class.MAIL_PORT}")
        print(f"📧 Mail SSL: {config_class.MAIL_USE_SSL}")
        print(f"📧 Mail TLS: {config_class.MAIL_USE_TLS}")
        print(f"📧 Mail Username: {config_class.MAIL_USERNAME}")
        print(f"📧 Mail Password Set: {bool(config_class.MAIL_PASSWORD)}")
        print(f"📧 Default Sender: {config_class.MAIL_DEFAULT_SENDER}")
        print(f"📧 Suppress Send: {config_class.MAIL_SUPPRESS_SEND}")
        
        # Check for missing variables
        missing_vars = config_class.get_missing_email_vars()
        if missing_vars:
            print(f"⚠️ Missing email vars: {missing_vars}")
        else:
            print("✅ All email configuration variables present")
        
        # Test direct SMTP connection
        print("\n🔍 Testing Direct SMTP Connection...")
        import smtplib
        import ssl
        
        try:
            server = smtplib.SMTP_SSL(config_class.MAIL_SERVER, config_class.MAIL_PORT)
            server.login(config_class.MAIL_USERNAME, config_class.MAIL_PASSWORD)
            print("✅ Direct SMTP connection successful")
            server.quit()
        except Exception as e:
            print(f"❌ Direct SMTP connection failed: {e}")
            return False
        
        # Test Flask-Mail compatibility
        print("\n🔍 Testing Flask-Mail Compatibility...")
        from flask import Flask
        from flask_mail import Mail
        
        # Create minimal Flask app for testing
        test_app = Flask(__name__)
        test_app.config.from_object(config_class)
        
        with test_app.app_context():
            mail = Mail(test_app)
            
            try:
                # Test connection
                with mail.connect() as conn:
                    print("✅ Flask-Mail connection successful")
                    return True
            except Exception as e:
                print(f"❌ Flask-Mail connection failed: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_flask_mail_config()
    if success:
        print("\n🎉 All email tests passed! Flask-Mail should be working correctly.")
    else:
        print("\n⚠️ Email configuration has issues that need to be resolved.")
    sys.exit(0 if success else 1)
