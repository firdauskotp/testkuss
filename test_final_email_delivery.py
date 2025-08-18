#!/usr/bin/env python3
"""
Final Email Delivery Test
Tests both customer and admin email delivery to ensure the complete workflow works.
"""

import sys
import os
from datetime import datetime

# Add the current directory to Python path to import backend modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_complete_email_workflow():
    """Test both customer and admin email delivery"""
    from backend import app  # Import the app directly
    from backend.utils import send_customer_email, send_team_email
    from flask_mail import Mail
    
    print("=" * 60)
    print("FINAL EMAIL DELIVERY TEST")
    print("=" * 60)
    
    # Use the existing Flask app
    mail = Mail(app)
    
    with app.app_context():
        # Debug environment variables
        import os
        print("Environment variables check:")
        print(f"  MAIL_SENDER_ADDRESS: {os.getenv('MAIL_SENDER_ADDRESS')}")
        print(f"  ADMIN_EMAIL_ADDRESS: {os.getenv('ADMIN_EMAIL_ADDRESS')}")
        print(f"  MAIL_USERNAME: {os.getenv('MAIL_USERNAME')}")
        print()
        
        print(f"Test started at: {datetime.now()}")
        print(f"Mail server: {app.config.get('MAIL_SERVER')}")
        print(f"Mail port: {app.config.get('MAIL_PORT')}")
        print(f"Mail sender: {app.config.get('MAIL_SENDER_ADDRESS')}")
        print(f"Admin email: {app.config.get('ADMIN_EMAIL_ADDRESS')}")
        print()
        
        # Test variables
        test_customer_email = "customer.test@gmail.com"
        test_variables = {
            'customer_name': 'John Test Customer',
            'customer_email': test_customer_email,
            'case_number': 'TEST-2024-001',
            'complaint_type': 'Product Quality',
            'complaint_description': 'Test complaint for email delivery verification',
            'resolution_description': 'This is a test resolution.',
            'case_id': 'TEST-001',
            'submission_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'team_email': app.config.get('ADMIN_EMAIL_ADDRESS')  # Explicitly set team email
        }
        
        print("Test Variables:")
        for key, value in test_variables.items():
            print(f"  {key}: {value}")
        print()
        
        # Test 1: Customer Email
        print("📧 TEST 1: Customer Email Delivery")
        print("-" * 40)
        try:
            result1 = send_customer_email(
                template_key='help_request_new_case_created',
                variables=test_variables,
                mail=mail
            )
            print(f"✅ Customer email result: {result1}")
            if result1:
                print(f"✅ Customer email sent successfully to: {test_customer_email}")
            else:
                print(f"❌ Customer email failed")
        except Exception as e:
            print(f"❌ Customer email error: {e}")
        
        print()
        
        # Test 2: Admin/Team Email
        print("📧 TEST 2: Admin/Team Email Delivery")
        print("-" * 40)
        try:
            result2 = send_team_email(
                template_key='team_help_request_new_case_received',
                variables=test_variables,
                mail=mail
            )
            print(f"✅ Admin email result: {result2}")
            if result2:
                print(f"✅ Admin email sent successfully to: {app.config.get('ADMIN_EMAIL_ADDRESS')}")
            else:
                print(f"❌ Admin email failed")
        except Exception as e:
            print(f"❌ Admin email error: {e}")
        
        print()
        print("=" * 60)
        
        # Summary
        print("SUMMARY:")
        if 'result1' in locals() and result1:
            print("✅ Customer notification: WORKING")
        else:
            print("❌ Customer notification: FAILED")
        
        if 'result2' in locals() and result2:
            print("✅ Admin notification: WORKING")
        else:
            print("❌ Admin notification: FAILED")
        
        print()
        print("Check your email inboxes to verify delivery!")
        print("=" * 60)

if __name__ == '__main__':
    test_complete_email_workflow()
