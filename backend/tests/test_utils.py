import pytest
import os
from unittest.mock import patch, MagicMock
from flask_mail import Message
# Assuming your utils.py is in the parent directory of 'tests' and is named utils.py
# Adjust the import path if your project structure is different.
# For example, if utils.py is directly under 'backend':
from backend import utils # Or specific functions: from backend.utils import send_email, send_email_to_customer, send_email_to_admin

# Mock Flask-Mail's Mail instance. This mock will be used by the send_email function.
# It needs to have a 'send' method.
mock_mail_app = MagicMock()

def test_send_email():
    # Test the generic send_email function
    # The following patch is removed as 'mail' is passed as an argument:
    # with patch.object(utils.mail, 'send') as mock_send:
    to_email = "recipient@example.com"
    from_email = "sender@example.com"
    subject = "Test Subject"
    body = "Test Body"

    # The 'mail' object in utils.py is what needs to be mocked, or its 'send' method.
    # For this test, we assume 'utils.mail' is the Mail instance used by send_email.
    # If 'send_email' creates its own Mail instance or gets it from Flask app context,
    # the mocking strategy will need to be adjusted.

    # Let's assume 'utils.py' has 'mail = Mail()' at the global level or passed around
    # and 'send_email' uses this 'mail' object.
    # If 'mail' is an attribute of an app object, it might be like 'app.mail.send'

    # Re-evaluating based on the provided utils.py structure:
    # The 'mail' object is passed as an argument to the send_email function.
    # So we need to pass a MagicMock for 'mail' when calling send_email.

    passed_mock_mail = MagicMock()
    utils.send_email(to_email, from_email, subject, body, passed_mock_mail)

    passed_mock_mail.send.assert_called_once()
    args, _ = passed_mock_mail.send.call_args
    sent_msg = args[0]

    assert isinstance(sent_msg, Message)
    assert sent_msg.subject == subject
    assert sent_msg.recipients == [to_email]
    assert sent_msg.sender == from_email
    assert sent_msg.body == body

def test_send_email_to_customer():
    # Test sending email to customer
    with patch.object(utils, 'send_email') as mock_generic_send_email:
        case_no = "12345"
        user_email = "customer@example.com"
        from_email = "support@example.com"

        # The 'mail' object is also passed to send_email_to_customer
        passed_mock_mail_for_customer = MagicMock()

        utils.send_email_to_customer(case_no, user_email, from_email, passed_mock_mail_for_customer)

        expected_subject = f"Case #{case_no} Created Successfully"
        expected_body = f"Thank you for submitting your case. Your case number is #{case_no}. Our staff will get in touch with you shortly."

        mock_generic_send_email.assert_called_once_with(
            user_email,
            from_email,
            expected_subject,
            expected_body,
            passed_mock_mail_for_customer
        )

@patch('os.getenv')
def test_send_email_to_admin(mock_getenv):
    # Test sending email to admin
    # Mock os.getenv to return a fake admin email
    mock_getenv.return_value = "admin@example.com"

    with patch.object(utils, 'send_email') as mock_generic_send_email:
        case_no = "67890"
        # user_email is the customer's email, from_email is the sender
        customer_email = "anothercustomer@example.com"
        from_email = "noreply@example.com"

        # The 'mail' object is also passed to send_email_to_admin
        passed_mock_mail_for_admin = MagicMock()

        utils.send_email_to_admin(case_no, customer_email, from_email, passed_mock_mail_for_admin)

        admin_email_address = "admin@example.com" # As returned by mocked os.getenv
        expected_subject = f"New Case #{case_no} Created"
        expected_body = f"A new case with case number #{case_no} has been created. Please check the system for details."

        mock_generic_send_email.assert_called_once_with(
            admin_email_address, # This should be the admin's email
            from_email,
            expected_subject,
            expected_body,
            passed_mock_mail_for_admin
        )
        # Verify that os.getenv was called to get the admin email
        mock_getenv.assert_called_with('ADMIN_EMAIL_ADDRESS')

def test_send_email_failure():
    # Test the generic send_email function's failure case
    with patch('builtins.print') as mock_print: # Mock print to check error message
        to_email = "recipient@example.com"
        from_email = "sender@example.com"
        subject = "Test Subject"
        body = "Test Body"

        # Create a mock mail object that will raise an exception when 'send' is called
        mock_mail_raiser = MagicMock()
        mock_mail_raiser.send.side_effect = Exception("SMTP Connection Error")

        utils.send_email(to_email, from_email, subject, body, mock_mail_raiser)

        mock_mail_raiser.send.assert_called_once() # Ensure send was attempted
        # Check that an error message was printed
        mock_print.assert_any_call(f"Failed to send email: SMTP Connection Error")
