# backend/tests/test_auth_bp.py
import pytest
from flask import url_for, session # Removed get_flashed_messages for now, can add if testing flash
# No need to import app or client, they come from conftest.py as fixtures

# Mocked database collections (can be refined in conftest.py later if shared across test files)
# For now, define simple mock data structures here or use mocker for each test.

def test_index_route(client, app): # Add app fixture
    """Test the index route (client login page)."""
    with app.app_context():
        response = client.get(url_for('auth.index'))
    assert response.status_code == 200
    # Check for some unique text on the client login page
    assert b"Client Login" in response.data # Assuming 'Client Login' is in the rendered template's body or title

def test_admin_login_get(client, app): # Add app fixture
    """Test GET request to admin_login page."""
    with app.app_context():
        response = client.get(url_for('auth.admin_login'))
    assert response.status_code == 200
    # Check for some unique text on the admin login page
    assert b"Admin Login" in response.data # Assuming 'Admin Login' is in the rendered template

def test_admin_login_post_success(client, mocker, app): # Add app fixture
    """Test successful admin login POST request."""
    # Mock database find_one to return a valid admin user
    mock_admin_user = {
        "_id": "someadminid", # Corrected from testadminid to match previous successful test if any dependency
        "username": "testadmin",
        "password": "pbkdf2:sha256:..." # A real hash of 'password'
    }
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_admin_user)

    # Mock check_password_hash to return True
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)

    # Mock log_activity
    mock_log = mocker.patch('backend.blueprints.auth_bp.log_activity')

    admin_login_url = None
    dashboard_url = None
    with app.test_request_context('/admin-login'): # Context for url_for calls
        admin_login_url = url_for('auth.admin_login')
        dashboard_url = url_for('dashboard')

    # Test the POST request and the redirect
    response_no_redirect = client.post(admin_login_url, data={
        'username': 'testadmin',
        'password': 'password'
    }, follow_redirects=False)

    assert response_no_redirect.status_code == 302
    assert response_no_redirect.location == dashboard_url

    # Check that session variables are set correctly
    with client.session_transaction() as sess:
        assert sess['user_id'] == "someadminid" # Ensure this matches mock_admin_user["_id"]
        assert sess['username'] == "testadmin"

    mock_log.assert_called_once_with("testadmin", "login", mocker.ANY)

    # Now, test if the dashboard is accessible after login
    # This uses the same client, which now has the session cookie from the login

    # Mock database calls made by the dashboard route
    # Collections are imported into app.py from col.py, so patch their original location.
    mocker.patch('backend.col.collection.count_documents', return_value=0)
    mocker.patch('backend.col.change_collection.count_documents', return_value=0)
    mocker.patch('backend.col.refund_collection.count_documents', return_value=0)
    mocker.patch('backend.col.remark_collection.count_documents', side_effect=[0, 0]) # For normal and urgent

    with app.test_request_context(dashboard_url): # Context for rendering dashboard
        dashboard_response = client.get(dashboard_url)
    assert dashboard_response.status_code == 200
    assert b"Dashboard Overview" in dashboard_response.data # Check for unique dashboard content

def test_admin_login_post_invalid_username(client, mocker, app): # Add app fixture
    """Test admin login POST with invalid username."""
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=None) # No user found

    with app.app_context(): # Wrap the call that might render a template via redirect
        response = client.post(url_for('auth.admin_login'), data={
            'username': 'wrongadmin',
            'password': 'password'
        }, follow_redirects=False) # Still check the redirect first

    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login') # Redirects back to admin_login

    # Test for flash message (requires app config SECRET_KEY and test client handling)
    # For simplicity, this part can be added later or tested by checking HTML content if flash appears there.
    # Example with follow_redirects=True and checking content:
    # response_followed = client.post(url_for('auth.admin_login'), data={'username': 'wrongadmin', 'password': 'password'}, follow_redirects=True)
    # assert b"Invalid username or password." in response_followed.data

    with client.session_transaction() as sess: # Check session is not set
        assert 'user_id' not in sess

def test_admin_login_post_invalid_password(client, mocker):
    """Test admin login POST with invalid password."""
    mock_admin_user = {"username": "testadmin", "password": "pbkdf2:sha256:..."}
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_admin_user)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=False) # Password check fails

    response = client.post(url_for('auth.admin_login'), data={
        'username': 'testadmin',
        'password': 'wrongpassword'
    }, follow_redirects=False)

    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')
    with client.session_transaction() as sess:
        assert 'user_id' not in sess

def test_logout(client, mocker):
    """Test logout functionality."""
    mock_log = mocker.patch('backend.blueprints.auth_bp.log_activity')

    # Simulate an admin login to set the session
    with client.session_transaction() as sess:
        sess['user_id'] = "testadminid"
        sess['username'] = "testadmin"

    response = client.get(url_for('auth.logout'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.index')

    with client.session_transaction() as sess: # Check session is cleared
        assert 'user_id' not in sess
        assert 'username' not in sess

    mock_log.assert_called_once_with("testadmin", "logout", mocker.ANY)

# TODO: Add tests for client_login (GET, POST success/failure)
# TODO: Add tests for register (GET access control, POST success, duplicate email, password mismatch)
# TODO: Add tests for register_admin (GET access control, POST success, duplicate username, password mismatch)
