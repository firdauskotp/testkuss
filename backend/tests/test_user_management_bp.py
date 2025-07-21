# backend/tests/test_user_management_bp.py
import pytest
from flask import url_for, session
# from flask import get_flashed_messages # If we want to assert flash messages

# Helper function to log in an admin user for protected routes
def login_admin(client, mocker, app, admin_username="testadmin", admin_id="605c72ef9c82f2001f00000a"): # Changed to valid hex
    # Mock database find_one to return a valid admin user
    mock_user_data = {
        "_id": admin_id, # This will be string version of ObjectId if find_one returns it like that
        "username": admin_username,
        "password": "hashed_password_for_testadmin"
    }
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_user_data)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)
    mocker.patch('backend.blueprints.auth_bp.log_activity') # Mock log_activity during login

    # Perform login
    # url_for needs an app context if called outside a request,
    # but client.post() will create one. For consistency if login_admin is called elsewhere:
    login_url = None
    with app.app_context():
        login_url = url_for('auth.admin_login')

    client.post(login_url, data={
        'username': admin_username,
        'password': 'password' # Actual password doesn't matter due to check_password_hash mock
    })
    # At this point, session should be set by auth_bp.admin_login


# --- Tests for view_users (client users) ---
def test_view_users_unauthenticated(client, app):
    with app.test_request_context(): # Context for url_for
        # The client.get will establish its own request context for the actual request
        response = client.get(url_for('user_mgnt.view_users'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_view_users_authenticated_empty(client, app, mocker):
    login_admin(client, mocker, app) # Log in as admin

    mocker.patch('backend.blueprints.user_management_bp.login_cust_collection.count_documents', return_value=0)
    mock_cursor_empty = mocker.Mock()
    mock_cursor_empty.skip.return_value.limit.return_value = []
    mocker.patch('backend.blueprints.user_management_bp.login_cust_collection.find', return_value=mock_cursor_empty)

    with app.test_request_context(): # Context for url_for
        response = client.get(url_for('user_mgnt.view_users'))

    assert response.status_code == 200
    assert b"Registered Customer Accounts" in response.data # Check page title from template
    assert b"No registered users found." in response.data # Match template message

def test_view_users_with_data(client, app, mocker):
    login_admin(client, mocker, app)

    mock_users_data = [
        {"_id": "605c72ef9c82f2001f0000c1", "email": "client1@example.com"},
        {"_id": "605c72ef9c82f2001f0000c2", "email": "client2@example.com"}
    ]
    mocker.patch('backend.blueprints.user_management_bp.login_cust_collection.count_documents', return_value=len(mock_users_data))
    mock_cursor_with_data = mocker.Mock()
    mock_cursor_with_data.skip.return_value.limit.return_value = mock_users_data
    mocker.patch('backend.blueprints.user_management_bp.login_cust_collection.find', return_value=mock_cursor_with_data)

    with app.test_request_context(): # Context for url_for
        response = client.get(url_for('user_mgnt.view_users'))

    assert response.status_code == 200
    assert b"client1@example.com" in response.data
    assert b"client2@example.com" in response.data

# --- Tests for delete_user (client user) ---
def test_delete_user_success(client, app, mocker):
    login_admin(client, mocker, app)

    client_user_id_to_delete = "605c72ef9c82f2001f0000c1" # Valid 24-char hex
    # Mock find_one to return the user being deleted (for logging or other checks)
    # The blueprint converts this string ID to ObjectId, so mock should reflect what DB returns after conversion if needed
    mocker.patch('backend.blueprints.user_management_bp.login_cust_collection.find_one',
                 return_value={"_id": client_user_id_to_delete, "email": "client1@example.com"}) # _id here is str
    # Mock delete_one
    mock_delete_one = mocker.patch('backend.blueprints.user_management_bp.login_cust_collection.delete_one', return_value=mocker.Mock(deleted_count=1))
    # Mock log_activity
    mock_log = mocker.patch('backend.blueprints.user_management_bp.log_activity')

    delete_user_url = None
    view_users_url = None
    with app.test_request_context(): # Context for url_for
        delete_user_url = url_for('user_mgnt.delete_user')
        view_users_url = url_for('user_mgnt.view_users')

    response = client.post(delete_user_url, data={'user_id': client_user_id_to_delete}, follow_redirects=False)

    assert response.status_code == 302
    assert response.location == view_users_url
    mock_delete_one.assert_called_once()
    mock_log.assert_called_once()

# TODO: Add test_delete_user_unauthenticated (should redirect to admin_login)

# --- Tests for view_admins ---
def test_view_admins_unauthenticated(client, app):
    with app.test_request_context(): # Context for url_for
        response = client.get(url_for('user_mgnt.view_admins'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_view_admins_authenticated_empty(client, app, mocker):
    login_admin(client, mocker, app)

    mocker.patch('backend.blueprints.user_management_bp.login_collection.count_documents', return_value=0)
    mock_cursor_admin_empty = mocker.Mock()
    mock_cursor_admin_empty.skip.return_value.limit.return_value = []
    mocker.patch('backend.blueprints.user_management_bp.login_collection.find', return_value=mock_cursor_admin_empty)

    with app.test_request_context(): # Context for url_for
        response = client.get(url_for('user_mgnt.view_admins'))
    assert response.status_code == 200
    assert b"Registered Admin Accounts" in response.data # Check page title from template
    assert b"No registered admins found." in response.data # Match template message

# TODO: Add test_view_admins_with_data

# --- Tests for delete_admin ---
def test_delete_admin_success(client, app, mocker):
    # Login as a different admin to delete another admin
    login_admin(client, mocker, app, admin_username="superadmin", admin_id="605c72ef9c82f2001f0000ab")

    admin_id_to_delete = "605c72ef9c82f2001f0000ad" # Valid 24-char hex
    mocker.patch('backend.blueprints.user_management_bp.login_collection.find_one',
                 return_value={"_id": admin_id_to_delete, "username": "admintodelete"}) # _id here is str
    mock_delete_one_admin = mocker.patch('backend.blueprints.user_management_bp.login_collection.delete_one', return_value=mocker.Mock(deleted_count=1))
    mocker.patch('backend.blueprints.user_management_bp.log_activity')

    delete_admin_url = None
    view_admins_url = None
    with app.test_request_context(): # Context for url_for
        delete_admin_url = url_for('user_mgnt.delete_admin')
        view_admins_url = url_for('user_mgnt.view_admins')

    response = client.post(delete_admin_url, data={'user_id': admin_id_to_delete}, follow_redirects=False)

    assert response.status_code == 302
    assert response.location == view_admins_url
    mock_delete_one_admin.assert_called_once()

def test_delete_admin_self(client, app, mocker):
    # Log in as the admin who we will attempt to delete
    admin_id_to_delete_and_login = "605c72ef9c82f2001f0000aa" # Valid hex, use for both login and delete attempt
    login_admin(client, mocker, app, admin_username="testadmin", admin_id=admin_id_to_delete_and_login)

    # This mock is for when the route tries to find_one before deleting. It's not strictly necessary for the self-delete logic test if that check happens first.
    # However, if find_one is called, it should return the user.
    mocker.patch('backend.blueprints.user_management_bp.login_collection.find_one',
                 return_value={"_id": admin_id_to_delete_and_login, "username": "testadmin"})
    mock_delete_one_admin = mocker.patch('backend.blueprints.user_management_bp.login_collection.delete_one')

    delete_admin_url = None
    view_admins_url = None
    with app.test_request_context(): # Context for url_for
        delete_admin_url = url_for('user_mgnt.delete_admin')
        view_admins_url = url_for('user_mgnt.view_admins')

    # Ensure session user_id matches the one we are trying to delete
    with client.session_transaction() as sess:
        # login_admin helper already sets session['user_id'] to admin_id_to_delete_and_login
        # and session['username'] to "testadmin"
        assert sess['user_id'] == admin_id_to_delete_and_login

    response = client.post(delete_admin_url, data={'user_id': admin_id_to_delete_and_login}, follow_redirects=False)

    assert response.status_code == 302 # Should redirect
    assert response.location == view_admins_url # Back to admin list
    mock_delete_one_admin.assert_not_called() # Should not have been called

    # To check flash messages, you'd typically do:
    # response_followed = client.post(url_for('user_mgnt.delete_admin'), data={'user_id': admin_id_to_delete}, follow_redirects=True)
    # with client.session_transaction() as sess:
    #     flashes = sess.get('_flashes', []) # Default category
    # assert any("You cannot delete your own admin account." in message for category, message in flashes)
    # For simplicity, this detailed flash check is omitted here.

# TODO: Add test_delete_admin_unauthenticated
