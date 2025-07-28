#!/usr/bin/env python3
"""
Test script to verify email functionality
"""
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_mail import Mail, Message
from dotenv import load_dotenv
import os

def test_email_configuration():
    """Test email configuration and sending"""
    print("Testing email configuration...")
    
    # Load environment variables
    load_dotenv()
    
    # Create a test Flask app
    app = Flask(__name__)
    
    # Configure email settings
    app.config['MAIL_SERVER'] = os.getenv('SMTP_GOOGLE_SERVER')
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False
    app.config['MAIL_USERNAME'] = os.getenv('SMTP_TEST_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('SMTP_TEST_APP_PASSWORD')
    
    print(f"MAIL_SERVER: {app.config['MAIL_SERVER']}")
    print(f"MAIL_USERNAME: {app.config['MAIL_USERNAME']}")
    print(f"MAIL_PORT: {app.config['MAIL_PORT']}")
    
    # Check if configuration is complete
    if not app.config['MAIL_SERVER'] or not app.config['MAIL_USERNAME']:
        print("❌ Email configuration is incomplete!")
        return False
    
    try:
        # Initialize mail
        mail = Mail(app)
        
        # Create a test message
        msg = Message(
            subject="Test Email from KUSS System",
            sender=app.config['MAIL_USERNAME'],
            recipients=[app.config['MAIL_USERNAME']],  # Send to self for testing
            body="This is a test email to verify email functionality."
        )
        
        print("Attempting to send test email...")
        
        # Send the message
        with app.app_context():
            mail.send(msg)
        
        print("✅ Email sent successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False

if __name__ == "__main__":
    print("Email Configuration Test")
    print("=" * 30)
    
    success = test_email_configuration()
    
    if success:
        print("\n🎉 Email configuration is working correctly!")
    else:
        print("\n💥 Email configuration has issues. Please check your settings.")
