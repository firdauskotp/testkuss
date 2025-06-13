# backend/tests/test_staff_actions_bp.py
import pytest
from flask import url_for, session, current_app
import io # For mocking file uploads
from bson import ObjectId # For mocking database _id fields

# Helper function to log in an admin user
def login_admin(client, mocker, app, admin_username="teststaff", admin_id="605c72ef9c82f2001f0000aa"): # Valid hex
    mock_user_data = { "_id": admin_id, "username": admin_username, "password": "hashed_password" }
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_user_data)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)
    mocker.patch('backend.blueprints.auth_bp.log_activity')

    admin_login_url = None
    with app.app_context():
        admin_login_url = url_for('auth.admin_login')
    client.post(admin_login_url, data={'username': admin_username, 'password': 'password'})

# --- Tests for get_case_details API endpoint ---
def test_get_case_details_unauthenticated(client, app):
    with app.test_request_context():
        response = client.get(url_for('staff.get_case_details', case_no=1), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_get_case_details_found(client, app, mocker):
    login_admin(client, mocker, app)
    mock_case = {"case_no": 1, "premise_name": "Test Premise", "details": "Some details"}
    mocker.patch('backend.blueprints.staff_actions_bp.collection.find_one', return_value=mock_case)

    with app.test_request_context():
        response = client.get(url_for('staff.get_case_details', case_no=1))

    assert response.status_code == 200
    assert response.json['case_no'] == 1
    assert response.json['premise_name'] == "Test Premise"

def test_get_case_details_not_found(client, app, mocker):
    login_admin(client, mocker, app)
    mocker.patch('backend.blueprints.staff_actions_bp.collection.find_one', return_value=None)

    with app.test_request_context():
        response = client.get(url_for('staff.get_case_details', case_no=2))

    assert response.status_code == 404
    assert response.json['error'] == "Case not found"

# --- Tests for staff_form ---
def test_staff_form_get_unauthenticated(client, app):
    with app.test_request_context():
        response = client.get(url_for('staff.staff_form', case_no=1), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_staff_form_get_case_not_found(client, app, mocker):
    login_admin(client, mocker, app)
    mocker.patch('backend.blueprints.staff_actions_bp.collection.find_one', return_value=None)

    redirect_target_url = None
    with app.app_context(): # Use app.app_context for current_app access
        if 'data_reports.view_complaints_list' in current_app.view_functions:
            redirect_target_url = url_for('data_reports.view_complaints_list', _external=True)
        else:
            redirect_target_url = url_for('dashboard', _external=True)

    response = client.get(url_for('staff.staff_form', case_no=1), follow_redirects=False)

    assert response.status_code == 302
    assert response.location == redirect_target_url

def test_staff_form_get_case_found(client, app, mocker):
    login_admin(client, mocker, app)
    mock_case_id_str = "605c73a9759a2d2c58a9aaaa"
    mock_case = {"_id": ObjectId(mock_case_id_str), "case_no": 1, "premise_name": "Found Premise", "issues": []}
    mocker.patch('backend.blueprints.staff_actions_bp.collection.find_one', return_value=mock_case)

    with app.test_request_context():
        response = client.get(url_for('staff.staff_form', case_no=1))

    assert response.status_code == 200
    assert b"Update Case #1" in response.data
    assert b"Found Premise" in response.data

def test_staff_form_post_update_case(client, app, mocker):
    login_admin(client, mocker, app)
    mock_case_id_str = "605c73a9759a2d2c58a9bbbb"
    initial_case_data = {"_id": ObjectId(mock_case_id_str), "case_no": 2, "premise_name": "Updateable Premise", "image_id": None, "issues": []}

    mocker.patch('backend.blueprints.staff_actions_bp.collection.find_one', return_value=initial_case_data)
    mock_update_one = mocker.patch('backend.blueprints.staff_actions_bp.collection.update_one')
    mock_fs_put = mocker.patch('backend.blueprints.staff_actions_bp.main_fs_instance.put', return_value="new_image_id")

    form_data = {
        'actions': ['Action A', 'Action B'],
        'remarks': 'Case updated remarks.',
        'case_closed': 'No',
        'appointment_date': '2024-12-31',
        'appointment_time': '14:00',
        'staff_name': 'Staff Member Test',
        'signature': 'base64encodedsignaturedata',
        'image': (io.BytesIO(b"new image data"), 'new_image.jpg')
    }

    staff_form_url = None
    with app.test_request_context():
        staff_form_url = url_for('staff.staff_form', case_no=2)

    response = client.post(staff_form_url, data=form_data,
                               content_type='multipart/form-data', follow_redirects=False)

    assert response.status_code == 302
    assert response.location == staff_form_url

    mock_update_one.assert_called_once()
    update_args = mock_update_one.call_args[0][1]['$set']
    assert update_args['remarks'] == 'Case updated remarks.'
    assert update_args['image_id'] == 'new_image_id'
    mock_fs_put.assert_called_once()

def test_staff_form_post_close_case(client, app, mocker):
    login_admin(client, mocker, app)
    mock_case_id_str = "605c73a9759a2d2c58a9cccc"
    initial_case_data = {"_id": ObjectId(mock_case_id_str), "case_no": 3, "premise_name": "Closable Premise", "issues": []}

    mocker.patch('backend.blueprints.staff_actions_bp.collection.find_one', return_value=initial_case_data)
    mock_delete_one = mocker.patch('backend.blueprints.staff_actions_bp.collection.delete_one')

    form_data = { 'case_closed': 'Yes', 'staff_name': 'Closer Staff' }

    staff_form_url = None
    expected_redirect_url = None
    with app.app_context(): # Use app.app_context for current_app access
        staff_form_url = url_for('staff.staff_form', case_no=3)
        # The route redirects without _external=True, so match that
        if 'data_reports.view_complaints_list' in current_app.view_functions:
            expected_redirect_url = url_for('data_reports.view_complaints_list')
        else:
            expected_redirect_url = url_for('dashboard')

    response = client.post(staff_form_url, data=form_data, follow_redirects=False)

    assert response.status_code == 302
    assert response.location == expected_redirect_url
    mock_delete_one.assert_called_once()
