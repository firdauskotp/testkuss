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

# --- Tests for client_login ---
def test_client_login_get(client, app):
    """Test GET request to client_login page."""
    with app.app_context():
        response = client.get(url_for('auth.client_login'))
    assert response.status_code == 200
    # Should render the same template as index (client login form)
    assert b"Client Login" in response.data

def test_client_login_post_success(client, mocker, app):
    """Test successful client login POST request."""
    # Mock database find_one to return a valid client user
    mock_client_user = {
        "_id": "someclientid",
        "email": "testclient@example.com",
        "password": "pbkdf2:sha256:..." # A real hash of 'password'
    }
    mocker.patch('backend.blueprints.auth_bp.login_cust_collection.find_one', return_value=mock_client_user)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)

    with app.app_context():
        response = client.post(url_for('auth.client_login'), data={
            'email': 'testclient@example.com',
            'password': 'password'
        }, follow_redirects=False)

    assert response.status_code == 302
    assert response.location == url_for('customer.customer_form')

    with client.session_transaction() as sess:
        assert sess['user_id'] == "someclientid"
        assert sess['customer_email'] == "testclient@example.com"

def test_client_login_post_invalid_email(client, mocker, app):
    """Test client login POST with invalid email."""
    mocker.patch('backend.blueprints.auth_bp.login_cust_collection.find_one', return_value=None)

    with app.app_context():
        response = client.post(url_for('auth.client_login'), data={
            'email': 'wrong@example.com',
            'password': 'password'
        }, follow_redirects=False)

    assert response.status_code == 302
    assert response.location == url_for('auth.index')

    with client.session_transaction() as sess:
        assert 'user_id' not in sess
        assert 'customer_email' not in sess

def test_client_login_post_invalid_password(client, mocker, app):
    """Test client login POST with invalid password."""
    mock_client_user = {"email": "testclient@example.com", "password": "pbkdf2:sha256:..."}
    mocker.patch('backend.blueprints.auth_bp.login_cust_collection.find_one', return_value=mock_client_user)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=False)

    with app.app_context():
        response = client.post(url_for('auth.client_login'), data={
            'email': 'testclient@example.com',
            'password': 'wrongpassword'
        }, follow_redirects=False)

    assert response.status_code == 302
    assert response.location == url_for('auth.index')

    with client.session_transaction() as sess:
        assert 'user_id' not in sess
        assert 'customer_email' not in sess

# --- Tests for register (client user registration) ---
def test_register_get_unauthenticated(client, app):
    """Test GET request to register page without admin login."""
    with app.app_context():
        response = client.get(url_for('auth.register'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_register_get_authenticated(client, app, mocker):
    """Test GET request to register page with admin login."""
    # Login as admin first
    mock_admin_user = {"_id": "adminid", "username": "admin", "password": "hashed"}
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_admin_user)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)
    mocker.patch('backend.blueprints.auth_bp.log_activity')

    with app.app_context():
        # Login first
        client.post(url_for('auth.admin_login'), data={'username': 'admin', 'password': 'password'})
        # Then access register page
        response = client.get(url_for('auth.register'))

    assert response.status_code == 200
    assert b"Register Client User" in response.data

def test_register_post_success(client, app, mocker):
    """Test successful client user registration."""
    # Login as admin first
    mock_admin_user = {"_id": "adminid", "username": "admin", "password": "hashed"}
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_admin_user)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)
    mocker.patch('backend.blueprints.auth_bp.log_activity')

    # Mock customer collection operations
    mocker.patch('backend.blueprints.auth_bp.login_cust_collection.find_one', return_value=None)  # No existing user
    mock_insert = mocker.patch('backend.blueprints.auth_bp.login_cust_collection.insert_one')
    mock_log = mocker.patch('backend.blueprints.auth_bp.log_activity')

    with app.app_context():
        # Login first
        client.post(url_for('auth.admin_login'), data={'username': 'admin', 'password': 'password'})
        # Then register new client
        response = client.post(url_for('auth.register'), data={
            'email': 'newclient@example.com',
            'password': 'newpassword',
            'confirm_password': 'newpassword'
        }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Client user registered successfully!" in response.data

    mock_insert.assert_called_once()
    mock_log.assert_called_with("admin", "added client user: newclient@example.com", mocker.ANY)

def test_register_post_password_mismatch(client, app, mocker):
    """Test client registration with password mismatch."""
    # Login as admin first
    mock_admin_user = {"_id": "adminid", "username": "admin", "password": "hashed"}
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_admin_user)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)

    with app.app_context():
        # Login first
        client.post(url_for('auth.admin_login'), data={'username': 'admin', 'password': 'password'})
        # Then try to register with mismatched passwords
        response = client.post(url_for('auth.register'), data={
            'email': 'newclient@example.com',
            'password': 'newpassword',
            'confirm_password': 'differentpassword'
        }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Passwords do not match" in response.data

def test_register_post_duplicate_email(client, app, mocker):
    """Test client registration with duplicate email."""
    # Login as admin first
    mock_admin_user = {"_id": "adminid", "username": "admin", "password": "hashed"}
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_admin_user)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)

    # Mock existing user found
    mocker.patch('backend.blueprints.auth_bp.login_cust_collection.find_one', return_value={"email": "existing@example.com"})

    with app.app_context():
        # Login first
        client.post(url_for('auth.admin_login'), data={'username': 'admin', 'password': 'password'})
        # Then try to register with existing email
        response = client.post(url_for('auth.register'), data={
            'email': 'existing@example.com',
            'password': 'newpassword',
            'confirm_password': 'newpassword'
        }, follow_redirects=True)

    assert response.status_code == 200
    assert b"This email is already registered" in response.data

# --- Tests for register_admin (admin user registration) ---
def test_register_admin_get_unauthenticated(client, app):
    """Test GET request to register_admin page without admin login."""
    with app.app_context():
        response = client.get(url_for('auth.register_admin'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_register_admin_get_authenticated(client, app, mocker):
    """Test GET request to register_admin page with admin login."""
    # Login as admin first
    mock_admin_user = {"_id": "adminid", "username": "admin", "password": "hashed"}
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_admin_user)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)
    mocker.patch('backend.blueprints.auth_bp.log_activity')

    with app.app_context():
        # Login first
        client.post(url_for('auth.admin_login'), data={'username': 'admin', 'password': 'password'})
        # Then access register_admin page
        response = client.get(url_for('auth.register_admin'))

    assert response.status_code == 200
    assert b"Register Admin User" in response.data

def test_register_admin_post_success(client, app, mocker):
    """Test successful admin user registration."""
    # Login as admin first
    mock_admin_user = {"_id": "adminid", "username": "admin", "password": "hashed"}
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_admin_user)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)
    mocker.patch('backend.blueprints.auth_bp.log_activity')

    # Mock admin collection operations
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', side_effect=[
        mock_admin_user,  # First call for login
        None  # Second call for new admin check (no existing user)
    ])
    mock_insert = mocker.patch('backend.blueprints.auth_bp.login_collection.insert_one')
    mock_log = mocker.patch('backend.blueprints.auth_bp.log_activity')

    with app.app_context():
        # Login first
        client.post(url_for('auth.admin_login'), data={'username': 'admin', 'password': 'password'})
        # Then register new admin
        response = client.post(url_for('auth.register_admin'), data={
            'username': 'newadmin',
            'password': 'newpassword',
            'confirm_password': 'newpassword'
        }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Admin user registered successfully!" in response.data

    mock_insert.assert_called_once()
    mock_log.assert_called_with("admin", "added admin user: newadmin", mocker.ANY)

def test_register_admin_post_password_mismatch(client, app, mocker):
    """Test admin registration with password mismatch."""
    # Login as admin first
    mock_admin_user = {"_id": "adminid", "username": "admin", "password": "hashed"}
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_admin_user)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)

    with app.app_context():
        # Login first
        client.post(url_for('auth.admin_login'), data={'username': 'admin', 'password': 'password'})
        # Then try to register with mismatched passwords
        response = client.post(url_for('auth.register_admin'), data={
            'username': 'newadmin',
            'password': 'newpassword',
            'confirm_password': 'differentpassword'
        }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Passwords do not match" in response.data

def test_register_admin_post_duplicate_username(client, app, mocker):
    """Test admin registration with duplicate username."""
    # Login as admin first
    mock_admin_user = {"_id": "adminid", "username": "admin", "password": "hashed"}
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_admin_user)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)

    # Mock existing admin found
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', side_effect=[
        mock_admin_user,  # First call for login
        {"username": "existingadmin"}  # Second call for new admin check (existing user)
    ])

    with app.app_context():
        # Login first
        client.post(url_for('auth.admin_login'), data={'username': 'admin', 'password': 'password'})
        # Then try to register with existing username
        response = client.post(url_for('auth.register_admin'), data={
            'username': 'existingadmin',
            'password': 'newpassword',
            'confirm_password': 'newpassword'
        }, follow_redirects=True)

    assert response.status_code == 200
    assert b"This username is already registered" in response.data
