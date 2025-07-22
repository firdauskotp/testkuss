# backend/tests/test_api_helpers_bp.py
import pytest
from flask import url_for, session, json, current_app
import io
from bson import ObjectId # For mocking ObjectIds

# Helper function to log in an admin (assuming some API routes might be protected)
def login_admin(client, mocker, app, admin_username="testapiadmin", admin_id="testapiadminid"):
    mock_user_data = { "_id": admin_id, "username": admin_username, "password": "hashed_password" }
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_user_data)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)
    mocker.patch('backend.blueprints.auth_bp.log_activity')
    with app.app_context():
        client.post(url_for('auth.admin_login'), data={'username': admin_username, 'password': 'password'})

# --- Test for an image fetching route (e.g., get_image) ---
def test_get_image_success(client, app, mocker):
    # login_admin(client, mocker, app) # If endpoint requires admin login

    mock_file_id_str = "605c73a9759a2d2c58a9f001"
    mock_gridfs_file = mocker.Mock()
    mock_gridfs_file.read.return_value = b"fake image data"
    mock_gridfs_file.content_type = "image/jpeg"

    # Path for fs used in api_helpers_bp.py is from ..app import fs
    mock_fs_get = mocker.patch('backend.blueprints.api_helpers_bp.fs.get', return_value=mock_gridfs_file)

    with app.test_request_context():
        image_url = url_for('api_helpers.get_image', file_id=mock_file_id_str)

    response = client.get(image_url)

    assert response.status_code == 200
    assert response.mimetype == "image/jpeg"
    assert response.data == b"fake image data"
    mock_fs_get.assert_called_once_with(ObjectId(mock_file_id_str))

def test_get_image_not_found(client, app, mocker):
    # login_admin(client, mocker, app) # If endpoint requires admin login

    mock_file_id_str = "605c73a9759a2d2c58a9f002"
    # The get_image route in api_helpers_bp.py has a try-except returning jsonify, 404
    mocker.patch('backend.blueprints.api_helpers_bp.fs.get', side_effect=Exception("GridFS NoFile or other error"))

    with app.test_request_context():
        image_url = url_for('api_helpers.get_image', file_id=mock_file_id_str)

    response = client.get(image_url)
    assert response.status_code == 404
    assert response.json is not None
    assert "error" in response.json


# --- Test for a data fetching route (e.g., get_premises) ---
def test_get_premises_success(client, app, mocker):
    # login_admin(client, mocker, app) # If endpoint requires admin login

    company_name = "TestCompany"
    mock_premises_data = ["Premise A", "Premise B"]
    # Path for services_collection used in api_helpers_bp.py
    mocker.patch('backend.blueprints.api_helpers_bp.services_collection.distinct', return_value=mock_premises_data)

    with app.test_request_context():
        # Ensure endpoint name is correct
        premises_url = url_for('api_helpers.get_premises', company=company_name)

    response = client.get(premises_url)

    assert response.status_code == 200
    # The route renders a template 'partials/premise_checkboxes.html'.
    # So we should check for HTML content, not JSON.
    assert response.mimetype == "text/html"
    assert b"Premise A" in response.data # Check if premise names are in the rendered HTML
    assert b"Premise B" in response.data
    # Example assertion for checkbox structure if known:
    assert b'<input type="checkbox" class="form-check-input premise-checkbox" value="Premise A"' in response.data

def test_get_premises_empty(client, app, mocker):
    # login_admin(client, mocker, app) # If endpoint requires admin login
    company_name = "EmptyCo"
    mocker.patch('backend.blueprints.api_helpers_bp.services_collection.distinct', return_value=[])

    with app.test_request_context():
        premises_url = url_for('api_helpers.get_premises', company=company_name)
    response = client.get(premises_url)
    assert response.status_code == 200
    # Check if the template correctly handles empty list (e.g., no checkboxes rendered or a specific message)
    # Assuming if empty, no checkboxes with value will be present
    assert b'value="Premise A"' not in response.data
    # The partial might not have a specific "No premises found" message, it might just render nothing.

# --- Test for an update route (e.g., update_data) ---
def test_update_data_success(client, app, mocker):
    # login_admin(client, mocker, app) # Assuming this route is protected

    mock_update_result = mocker.Mock()
    mock_update_result.modified_count = 1
    # Path for services_collection used in api_helpers_bp.py
    mock_update = mocker.patch('backend.blueprints.api_helpers_bp.services_collection.update_one', return_value=mock_update_result)

    post_data = {'sn': '123', 'field_to_update': 'new_value'}

    with app.test_request_context():
        update_url = url_for('api_helpers.update_data')
    response = client.post(update_url, json=post_data)

    assert response.status_code == 200
    assert response.json == {'success': True}
    mock_update.assert_called_once_with({'S/N': 123}, {'$set': {'field_to_update': 'new_value'}})

def test_update_data_no_modification(client, app, mocker):
    # login_admin(client, mocker, app) # Assuming this route is protected
    mock_update_result = mocker.Mock()
    mock_update_result.modified_count = 0
    mocker.patch('backend.blueprints.api_helpers_bp.services_collection.update_one', return_value=mock_update_result)

    post_data = {'sn': '456', 'field_to_update': 'same_value'}
    with app.test_request_context():
        update_url = url_for('api_helpers.update_data')
    response = client.post(update_url, json=post_data)

    assert response.status_code == 200
    assert response.json['success'] is False
    assert response.json['message'] == 'Record not found or no changes made'

def test_update_data_invalid_sn_format(client, app, mocker):
    # login_admin(client, mocker, app) # Assuming this route is protected

    # No need to mock update_one as it should fail before that
    post_data = {'sn': 'invalid_sn_str', 'field_to_update': 'new_value'}

    with app.test_request_context():
        update_url = url_for('api_helpers.update_data')
    response = client.post(update_url, json=post_data)

    assert response.status_code == 400 # Bad request due to invalid S/N format
    assert response.json['success'] is False
    assert "Invalid S/N format" in response.json['message']

# TODO: Add tests for more API helpers, e.g., one that returns JSON list, one for POST with different data.
# TODO: Add authentication checks for API routes if they are meant to be protected.
#       The login_admin helper is provided but not used in all tests yet.
