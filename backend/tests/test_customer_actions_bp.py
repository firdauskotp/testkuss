# backend/tests/test_customer_actions_bp.py
import pytest
from flask import url_for, session, current_app
import io # For mocking file uploads

# Helper function to log in a customer
def login_customer(client, app, customer_email="testcust@example.com", customer_id="testcustid"):
    # No direct password check, just set the session variable as client_login would
    # Using app.test_client() to ensure session transaction happens on the correct app instance
    with client.session_transaction() as sess:
        sess['customer_email'] = customer_email
        sess['user_id'] = customer_id # Assuming 'user_id' is also set for customers for consistency

# --- Tests for customer_form ---
def test_customer_form_get_unauthenticated(client, app):
    with app.test_request_context(): # Context for url_for
        response = client.get(url_for('customer.customer_form'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.client_login')

def test_customer_form_get_authenticated(client, app):
    login_customer(client, app)
    with app.test_request_context(): # Context for url_for
        response = client.get(url_for('customer.customer_form'))
    assert response.status_code == 200
    # Assuming "Create a New Support Case" is the page_title for customer-complaint-form.html
    assert b"Create a New Support Case" in response.data

def test_customer_form_post_success(client, app, mocker):
    login_customer(client, app, customer_email="submitter@example.com")

    # Mock database calls
    mocker.patch('backend.blueprints.customer_actions_bp.collection.count_documents', return_value=0) # For case_no generation
    mock_insert_one = mocker.patch('backend.blueprints.customer_actions_bp.collection.insert_one')

    # Mock GridFS 'put'
    mock_fs_put = mocker.patch('backend.blueprints.customer_actions_bp.fs.put', return_value="mock_image_id")

    # Mock email sending functions
    mock_send_to_customer = mocker.patch('backend.blueprints.customer_actions_bp.send_email_to_customer')
    mock_send_to_admin = mocker.patch('backend.blueprints.customer_actions_bp.send_email_to_admin')

    # Ensure MAIL_SENDER_ADDRESS is set in the test app config
    with app.app_context():
        original_sender = current_app.config.get('MAIL_SENDER_ADDRESS')
        current_app.config['MAIL_SENDER_ADDRESS'] = 'test_sender@example.com'

    form_data = {
        'premise_name': 'Test Premise',
        'location': 'Test Location',
        'model': 'Test Model',
        'issues': ['Issue 1', 'Issue 2'], # Example for getlist
        'remarks': 'Test remarks here.',
        'image': (io.BytesIO(b"fake image data"), 'test.jpg') # Mock file upload
    }

    customer_form_url = None
    case_success_url = None
    with app.test_request_context(): # For url_for calls
        customer_form_url = url_for('customer.customer_form')
        case_success_url = url_for('customer.case_success', case_no=1) # case_no will be 0+1=1

    response = client.post(customer_form_url, data=form_data,
                           content_type='multipart/form-data', follow_redirects=False)

    assert response.status_code == 302
    assert response.location == case_success_url

    mock_insert_one.assert_called_once()
    inserted_data = mock_insert_one.call_args[0][0]
    assert inserted_data['email'] == "submitter@example.com"
    assert inserted_data['premise_name'] == "Test Premise"
    assert inserted_data['image_id'] == "mock_image_id"

    mock_fs_put.assert_called_once()
    mock_send_to_customer.assert_called_once()
    mock_send_to_admin.assert_called_once()

    args_customer, _ = mock_send_to_customer.call_args
    assert args_customer[0] == 1 # case_no
    assert args_customer[1] == "submitter@example.com" # user_email
    assert args_customer[2] == 'test_sender@example.com' # from_email

    # Restore original config if it was changed
    if original_sender is not None:
        with app.app_context():
            current_app.config['MAIL_SENDER_ADDRESS'] = original_sender
    else: # If it wasn't set, remove it to leave app state clean
        with app.app_context():
            current_app.config.pop('MAIL_SENDER_ADDRESS', None)


def test_customer_form_post_no_image(client, app, mocker):
    login_customer(client, app, customer_email="noimage@example.com")

    mocker.patch('backend.blueprints.customer_actions_bp.collection.count_documents', return_value=5)
    mock_insert_one = mocker.patch('backend.blueprints.customer_actions_bp.collection.insert_one')
    mock_fs_put = mocker.patch('backend.blueprints.customer_actions_bp.fs.put')
    mocker.patch('backend.blueprints.customer_actions_bp.send_email_to_customer')
    mocker.patch('backend.blueprints.customer_actions_bp.send_email_to_admin')

    # Ensure MAIL_SENDER_ADDRESS for this test too
    with app.app_context():
        original_sender = current_app.config.get('MAIL_SENDER_ADDRESS')
        current_app.config['MAIL_SENDER_ADDRESS'] = 'test_sender@example.com'


    form_data = {
        'premise_name': 'No Image Premise',
        'location': 'Location X',
        'model': 'Model Y',
        'issues': 'Issue A', # Note: getlist would make this ['Issue A']
        'remarks': 'No image submitted.'
    }
    customer_form_url = None
    case_success_url = None
    with app.test_request_context():
        customer_form_url = url_for('customer.customer_form')
        case_success_url = url_for('customer.case_success', case_no=6) # 5+1 = 6

    response = client.post(customer_form_url, data=form_data, follow_redirects=False)

    assert response.status_code == 302
    assert response.location == case_success_url
    mock_insert_one.assert_called_once()
    inserted_data = mock_insert_one.call_args[0][0]
    assert inserted_data['image_id'] is None
    mock_fs_put.assert_not_called()

    if original_sender is not None:
        with app.app_context():
            current_app.config['MAIL_SENDER_ADDRESS'] = original_sender
    else:
        with app.app_context():
            current_app.config.pop('MAIL_SENDER_ADDRESS', None)


# --- Tests for case_success ---
def test_case_success_get(client, app): # Adjusted: case_success is public
    login_customer(client, app) # Login still needed if template expects session data
    test_case_no = 999
    with app.test_request_context(): # Context for url_for
        response = client.get(url_for('customer.case_success', case_no=test_case_no))
    assert response.status_code == 200
    # Assuming "Case Submission Successful" is the page_title for case-success.html
    assert b"Case Submission Successful" in response.data
    assert bytes(str(test_case_no), 'utf-8') in response.data
# Note: The prompt had a closing ``` which is removed here.
# The actual SyntaxError was at line 149 because of the trailing ```.
# The content above is the Python code without any markdown fences.
