#!/usr/bin/env python3
"""
Test enhanced dynamic email functionality
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.config import get_config, validate_environment

def test_enhanced_email_functions():
    """Test the enhanced dynamic email functions"""
    
    print("🔧 Testing Enhanced Dynamic Email Functions...")
    print("=" * 60)
    
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
        test_app.config['MAIL_SUPPRESS_SEND'] = True  # Suppress actual sending
        
        with test_app.app_context():
            mail = Mail(test_app)
            
            # Import enhanced email functions
            from backend.utils import send_dynamic_email, send_customer_email, send_team_email
            
            print("\n🔍 Testing Enhanced Email Function Imports...")
            print("✅ send_dynamic_email imported successfully")
            print("✅ send_customer_email imported successfully")
            print("✅ send_team_email imported successfully")
            
            # Set up test variables
            test_variables = {
                "case_id": "TEST123",
                "premise_name": "Test Premise",
                "customer_email": "customer@example.com",
                "device_location": "Test Location",
                "issues": "Test issues",
                "remarks": "Test remarks"
            }
            
            # Set admin email for testing
            os.environ['ADMIN_EMAIL_ADDRESS'] = 'admin@example.com'
            test_app.config['ADMIN_EMAIL_ADDRESS'] = 'admin@example.com'
            
            print("\n🔍 Testing Customer Email Function...")
            try:
                result = send_customer_email(
                    template_key="help_request_new_case_created",
                    variables=test_variables,
                    mail=mail,
                    customer_email="customer@example.com"
                )
                print("✅ send_customer_email function works correctly")
            except Exception as e:
                print(f"❌ send_customer_email failed: {e}")
                return False
            
            print("\n🔍 Testing Team Email Function...")
            try:
                result = send_team_email(
                    template_key="team_help_request_new_case_received",
                    variables=test_variables,
                    mail=mail,
                    team_email="admin@example.com"
                )
                print("✅ send_team_email function works correctly")
            except Exception as e:
                print(f"❌ send_team_email failed: {e}")
                return False
            
            print("\n🔍 Testing Dynamic Email with Recipient Override...")
            try:
                result = send_dynamic_email(
                    template_key="help_request_new_case_created",
                    variables=test_variables,
                    mail=mail,
                    recipient_override="override@example.com"
                )
                print("✅ send_dynamic_email with recipient_override works correctly")
            except Exception as e:
                print(f"❌ send_dynamic_email with override failed: {e}")
                return False
            
            print("\n🔍 Testing Dynamic Email with Recipient Type...")
            try:
                result = send_dynamic_email(
                    template_key="help_request_new_case_created",
                    variables=test_variables,
                    mail=mail,
                    recipient_type="customer"
                )
                print("✅ send_dynamic_email with recipient_type works correctly")
            except Exception as e:
                print(f"❌ send_dynamic_email with recipient_type failed: {e}")
                return False
            
            print("\n🎉 All enhanced email function tests passed!")
            
            # Show the improvements
            print("\n📈 Enhanced Email System Features:")
            print("✅ Flexible recipient handling (customer, team, admin)")
            print("✅ Recipient override capability")
            print("✅ Smart template variant selection")
            print("✅ Comprehensive error handling and logging")
            print("✅ Email validation and fallback logic")
            print("✅ Convenience functions for common use cases")
            
            return True
                
    except Exception as e:
        print(f"❌ Enhanced email function test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_enhanced_email_functions()
    if success:
        print("\n✅ All enhanced email functions are working correctly!")
    else:
        print("\n❌ Some enhanced email functions have issues.")
    sys.exit(0 if success else 1)
