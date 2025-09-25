# backend/tests/test_forms_bp.py
import pytest
from flask import url_for, session, current_app # Added current_app for config access
from datetime import datetime
# from ..col import relevant_collections... # Will be mocked

# Helper function to log in an admin user (can be imported or defined)
def login_admin(client, mocker, app, admin_username="testformadmin", admin_id="testformadminid"): # Added app
    mock_user_data = { "_id": admin_id, "username": admin_username, "password": "hashed_password" }
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_user_data)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)
    mocker.patch('backend.blueprints.auth_bp.log_activity')

    admin_login_url = None
    with app.app_context(): # Context for url_for
        admin_login_url = url_for('auth.admin_login')
    client.post(admin_login_url, data={'username': admin_username, 'password': 'password'})

# --- Tests for new_customer form ---
def test_new_customer_get_unauthenticated(client, app):
    with app.test_request_context():
        response = client.get(url_for('forms.new_customer'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_new_customer_get_authenticated(client, app, mocker):
    login_admin(client, mocker, app)
    # Mock collections needed for rendering the new_customer form (e.g., for dropdowns)
    mock_model_cursor = mocker.Mock()
    mock_model_cursor.sort.return_value = [] # find().sort() returns an empty list
    mocker.patch('backend.blueprints.forms_bp.model_list_collection.find', return_value=mock_model_cursor)

    mock_eo_cursor = mocker.Mock()
    mock_eo_cursor.sort.return_value = [] # find().sort() returns an empty list
    mocker.patch('backend.blueprints.forms_bp.eo_pack_collection.find', return_value=mock_eo_cursor)

    with app.test_request_context():
        response = client.get(url_for('forms.new_customer'))
    assert response.status_code == 200
    assert b"New Customer Registration" in response.data # Check for page title

def test_new_customer_post_success(client, app, mocker):
    login_admin(client, mocker, app)

    # Mock collections for POST logic
    mock_profile_insert = mocker.patch('backend.blueprints.forms_bp.profile_list_collection.insert_many')
    mock_device_insert = mocker.patch('backend.blueprints.forms_bp.device_list_collection.insert_many')

    # Mock based on app.config['MODE']
    # For this test, we'll explicitly set MODE to 'TEST' to direct to test_collection
    with app.app_context():
        original_mode = current_app.config.get('MODE')
        current_app.config['MODE'] = 'TEST'

    mock_master_list_insert = mocker.patch('backend.blueprints.forms_bp.test_collection.insert_many')
    mock_services_insert = mocker.patch('backend.blueprints.forms_bp.services_collection.insert_many') # Also mock services just in case

    mock_log_activity = mocker.patch('backend.blueprints.forms_bp.log_activity')

    # Mock collections for rendering the form again after redirect (if any data is re-fetched)
    # These also need to return mock cursors that support .sort()
    mock_model_cursor_redirect = mocker.Mock()
    mock_model_cursor_redirect.sort.return_value = []
    mocker.patch('backend.blueprints.forms_bp.model_list_collection.find', return_value=mock_model_cursor_redirect)

    mock_eo_cursor_redirect = mocker.Mock()
    mock_eo_cursor_redirect.sort.return_value = []
    mocker.patch('backend.blueprints.forms_bp.eo_pack_collection.find', return_value=mock_eo_cursor_redirect)

    form_data = {
        'dateCreated': datetime.now().strftime("%Y-%m-%d"),
        'companyName': 'Test New Company',
        'industry': 'Tech',
        'premiseName1': 'Main Office',
        'premiseArea1': 'HQ',
        'premiseAddress1': '123 Main St',
        'picName1': 'John Doe',
        'picDesignation1': 'Manager',
        'picContact1': '555-1234',
        'picEmail1': 'john.doe@testcompany.com',
        'contactPremise1': 'Main Office',
        'deviceLocation1': 'Lobby',
        'deviceSN1': 'SN001',
        'deviceModel1': 'ModelX',
        'deviceColour1': 'Black',
        'deviceVolume1': '100',
        'deviceScent1': 'Citrus',
        'devicePremise1': 'Main Office',
        'E1Days1': 'Mon-Fri', 'E1StartTime1': '09:00', 'E1EndTime1': '17:00', 'E1Pause1': '60', 'E1Work1': '30',
        'E2Days1': '', 'E2StartTime1': '', 'E2EndTime1': '', 'E2Pause1': '', 'E2Work1': '',
        'E3Days1': '', 'E3StartTime1': '', 'E3EndTime1': '', 'E3Pause1': '', 'E3Work1': '',
        'E4Days1': '', 'E4StartTime1': '', 'E4EndTime1': '', 'E4Pause1': '', 'E4Work1': '',
    }

    with app.test_request_context():
        response = client.post(url_for('forms.new_customer'), data=form_data, follow_redirects=True)

    assert response.status_code == 200
    assert b"Company Test New Company added successfully!" in response.data

    mock_profile_insert.assert_called()
    mock_device_insert.assert_called_once()

    if current_app.config.get('MODE') == 'PROD':
        mock_services_insert.assert_called_once()
        mock_master_list_insert.assert_not_called()
    else:
        mock_master_list_insert.assert_called_once()
        mock_services_insert.assert_not_called()

    mock_log_activity.assert_called_once()

    # Restore original MODE
    with app.app_context():
        if original_mode is not None:
            current_app.config['MODE'] = original_mode
        else:
            current_app.config.pop('MODE', None)

# --- Tests for change_form ---
def test_change_form_get_unauthenticated(client, app):
    with app.test_request_context():
        response = client.get(url_for('forms.change_form'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_change_form_get_authenticated(client, app, mocker):
    login_admin(client, mocker, app)
    
    # Mock collections for rendering the form
    mocker.patch('backend.blueprints.forms_bp.services_collection.distinct', return_value=['Company A', 'Company B'])
    
    with app.test_request_context():
        response = client.get(url_for('forms.change_form'))
    assert response.status_code == 200
    assert b"Change Request Form" in response.data

def test_change_form_post_settings_update(client, app, mocker):
    login_admin(client, mocker, app)
    
    # Mock collections
    mock_change_insert = mocker.patch('backend.blueprints.forms_bp.change_form_collection.insert_one')
    mock_log = mocker.patch('backend.blueprints.forms_bp.log_activity')
    
    form_data = {
        'companyName': 'Test Company',
        'date': '2024-01-15',
        'month': 'January',
        'year': '2024',
        'premises': ['Premise 1', 'Premise 2'],
        'devices': ['Device 1', 'Device 2'],
        'changeScent': 'on',
        'changeScentText': 'New Scent',
        'redoSettings': 'on',
        'reduceIntensity': 'off',
        'increaseIntensity': 'off',
        'moveDevice': 'off',
        'moveDeviceText': '',
        'relocateDevice': 'off',
        'relocateDeviceDropdown': '',
        'collectBack': 'off',
        'remark': 'Test remark'
    }
    
    with app.test_request_context():
        response = client.post(url_for('forms.change_form'), data=form_data, follow_redirects=False)
    
    assert response.status_code == 302
    assert response.location == url_for('dashboard')
    
    mock_change_insert.assert_called_once()
    mock_log.assert_called_with("testformadmin", "updated settings : ['Premise 1', 'Premise 2']['Device 1', 'Device 2']", mocker.ANY)

def test_change_form_post_collect_back(client, app, mocker):
    login_admin(client, mocker, app)
    
    # Mock collections
    mock_refund_insert = mocker.patch('backend.blueprints.forms_bp.refund_collection.insert_one')
    mock_log = mocker.patch('backend.blueprints.forms_bp.log_activity')
    
    form_data = {
        'companyName': 'Test Company',
        'date': '2024-01-15',
        'month': 'January',
        'year': '2024',
        'premises': ['Premise 1'],
        'devices': ['Device 1'],
        'changeScent': 'off',
        'changeScentText': '',
        'redoSettings': 'off',
        'reduceIntensity': 'off',
        'increaseIntensity': 'off',
        'moveDevice': 'off',
        'moveDeviceText': '',
        'relocateDevice': 'off',
        'relocateDeviceDropdown': '',
        'collectBack': 'on',
        'remark': 'Collecting back device'
    }
    
    with app.test_request_context():
        response = client.post(url_for('forms.change_form'), data=form_data, follow_redirects=False)
    
    assert response.status_code == 302
    assert response.location == url_for('dashboard')
    
    mock_refund_insert.assert_called_once()
    mock_log.assert_called_with("testformadmin", "collected back : ['Premise 1']['Device 1']", mocker.ANY)

# --- Tests for pre_service ---
def test_pre_service_get_unauthenticated(client, app):
    with app.test_request_context():
        response = client.get(url_for('forms.pre_service'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_pre_service_get_authenticated(client, app, mocker):
    login_admin(client, mocker, app)
    
    # Mock collections
    mocker.patch('backend.blueprints.forms_bp.services_collection.distinct', return_value=['Company A', 'Company B'])
    
    with app.test_request_context():
        response = client.get(url_for('forms.pre_service'))
    assert response.status_code == 200
    assert b"Pre-Service Route Planning" in response.data

def test_pre_service_post_success(client, app, mocker):
    login_admin(client, mocker, app)
    
    # Mock collections
    mock_route_insert = mocker.patch('backend.blueprints.forms_bp.route_list_collection.insert_one')
    mock_log = mocker.patch('backend.blueprints.forms_bp.log_activity')
    
    form_data = {
        'date': '2024-01-15T10:00:00Z',
        'company': 'Test Company',
        'premise': 'Test Premise',
        'model': 'Model X',
        'color': 'Black',
        'eo': 'Citrus'
    }
    
    with app.test_request_context():
        response = client.post(url_for('forms.pre_service'), data=form_data, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Route for Company: Test Company, Premise: Test Premise added successfully!" in response.data
    
    mock_route_insert.assert_called_once()
    mock_log.assert_called_with("testformadmin", "pre-service route added for: Test Company : Test Premise", mocker.ANY)

# --- Tests for service ---
def test_service_get_unauthenticated(client, app):
    with app.test_request_context():
        response = client.get(url_for('forms.service'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_service_get_authenticated(client, app, mocker):
    login_admin(client, mocker, app)
    
    # Mock collections
    mocker.patch('backend.blueprints.forms_bp.services_collection.distinct', return_value=['Company A', 'Company B'])
    mocker.patch('backend.blueprints.forms_bp.profile_list_collection.find', return_value=[])
    
    with app.test_request_context():
        response = client.get(url_for('forms.service'))
    assert response.status_code == 200
    assert b"Field Service Report" in response.data

def test_service_post_success(client, app, mocker):
    login_admin(client, mocker, app)
    
    # Mock collections
    mock_premise = {"premise_name": "Test Premise", "company": "Test Company"}
    mocker.patch('backend.blueprints.forms_bp.profile_list_collection.find_one', return_value=mock_premise)
    
    mock_devices = [
        {
            "location": "Lobby",
            "S/N": 12345,
            "Model": "Model X",
            "Current EO": "Citrus",
            "Volume": 100,
            "E1 - DAYS": "Mon-Fri",
            "E1 - START": "09:00",
            "E1 - END": "17:00",
            "E1 - WORK": 30,
            "E1 - PAUSE": 60,
            "E2 - DAYS": "",
            "E2 - START": "",
            "E2 - END": "",
            "E2 - WORK": "",
            "E2 - PAUSE": "",
            "E3 - DAYS": "",
            "E3 - START": "",
            "E3 - END": "",
            "E3 - WORK": "",
            "E3 - PAUSE": "",
            "E4 - DAYS": "",
            "E4 - START": "",
            "E4 - END": "",
            "E4 - WORK": "",
            "E4 - PAUSE": ""
        }
    ]
    mocker.patch('backend.blueprints.forms_bp.device_list_collection.find', return_value=mock_devices)
    
    mock_pics = [{"name": "John Doe", "email": "john@example.com"}]
    mocker.patch('backend.blueprints.forms_bp.profile_list_collection.find', side_effect=[mock_pics, mock_pics])
    
    mock_change_insert = mocker.patch('backend.blueprints.forms_bp.change_form_collection.insert_one')
    
    form_data = {
        'premiseName': 'Test Premise',
        'actions': ['Action 1', 'Action 2'],
        'remarks': 'Service completed successfully',
        'staffName': 'John Doe',
        'signature': 'John Doe',
        'balance1': '80'  # For the first device
    }
    
    with app.test_request_context():
        response = client.post(url_for('forms.service'), data=form_data, follow_redirects=False)
    
    assert response.status_code == 302
    # Note: The redirect URL might need adjustment based on actual implementation
    # assert response.location == url_for('forms.service')
    
    mock_change_insert.assert_called_once()

def test_service_post_invalid_premise(client, app, mocker):
    login_admin(client, mocker, app)
    
    # Mock collections - no premise found
    mocker.patch('backend.blueprints.forms_bp.profile_list_collection.find_one', return_value=None)
    
    form_data = {
        'premiseName': 'Invalid Premise',
        'actions': ['Action 1'],
        'remarks': 'Test',
        'staffName': 'John Doe',
        'signature': 'John Doe'
    }
    
    with app.test_request_context():
        response = client.post(url_for('forms.service'), data=form_data, follow_redirects=False)
    
    assert response.status_code == 302
    # Should redirect to field_service or show error

# --- Tests for service2 ---
def test_service2_get_unauthenticated(client, app):
    with app.test_request_context():
        response = client.get(url_for('forms.service2'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_service2_get_authenticated(client, app, mocker):
    login_admin(client, mocker, app)
    
    # Mock collections
    mocker.patch('backend.blueprints.forms_bp.services_collection.distinct', return_value=['Company A', 'Company B'])
    
    with app.test_request_context():
        response = client.get(url_for('forms.service2'))
    assert response.status_code == 200
    assert b"Service Form 2" in response.data

# --- Tests for post_service ---
def test_post_service_get_unauthenticated(client, app):
    with app.test_request_context():
        response = client.get(url_for('forms.post_service'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_post_service_get_authenticated(client, app, mocker):
    login_admin(client, mocker, app)
    
    with app.test_request_context():
        response = client.get(url_for('forms.post_service'))
    assert response.status_code == 200
    assert b"Post-Service Report" in response.data

def test_post_service_post_success(client, app, mocker):
    login_admin(client, mocker, app)
    
    # Mock collections
    mock_update = mocker.patch('backend.blueprints.forms_bp.eo_pack_collection.update_one')
    mock_log = mocker.patch('backend.blueprints.forms_bp.log_activity')
    
    form_data = {
        'essential_oil': 'Citrus',
        'oil_balance': '50',
        'balance_brought_back': '20',
        'balance_brought_back_percent': '40%',
        'refill_amount': '30',
        'refill_amount_percent': '60%'
    }
    
    with app.test_request_context():
        response = client.post(url_for('forms.post_service'), data=form_data, follow_redirects=False)
    
    assert response.status_code == 302
    assert response.location == url_for('dashboard')
    
    mock_update.assert_called_once()
    mock_log.assert_called_with("testformadmin", "Updated/added post-service record for EO: Citrus", mocker.ANY)

# --- Tests for remark form ---
def test_remark_get_unauthenticated(client, app):
    with app.test_request_context():
        response = client.get(url_for('forms.remark'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_remark_get_authenticated(client, app, mocker):
    login_admin(client, mocker, app)
    with app.test_request_context():
        response = client.get(url_for('forms.remark'))
    assert response.status_code == 200
    assert b"Submit a New Remark" in response.data

def test_remark_post_success(client, app, mocker):
    login_admin(client, mocker, app, admin_username="remarkposter")

    mock_remark_insert = mocker.patch('backend.blueprints.forms_bp.remark_collection.insert_one')
    mock_log = mocker.patch('backend.blueprints.forms_bp.log_activity')

    form_data = {
        'remark': 'This is a test remark.',
        'urgent': 'on' # For checkbox
    }

    remark_url = None
    dashboard_url = None
    with app.test_request_context():
        remark_url = url_for('forms.remark')
        dashboard_url = url_for('dashboard')

    response = client.post(remark_url, data=form_data, follow_redirects=False)

    assert response.status_code == 302
    assert response.location == dashboard_url

    mock_remark_insert.assert_called_once()
    inserted_remark = mock_remark_insert.call_args[0][0]
    assert inserted_remark['username'] == "remarkposter"
    assert inserted_remark['remark'] == 'This is a test remark.'
    assert inserted_remark['urgent'] is True

    mock_log.assert_called_once()

# --- Tests for discontinue functionality ---
def test_change_form_post_collect_back_sends_email(client, app, mocker):
    """Test that collect_back sends discontinue email to PIC"""
    login_admin(client, mocker, app)

    # Mock collections
    mock_customer = {
        "_id": "customer_id",
        "company": "Test Company",
        "email": "pic@testcompany.com"
    }
    mocker.patch('backend.blueprints.forms_bp.profile_list_collection.find_one', return_value=mock_customer)
    mock_refund_insert = mocker.patch('backend.blueprints.forms_bp.refund_collection.insert_one')
    mock_log = mocker.patch('backend.blueprints.forms_bp.log_activity')
    mock_email = mocker.patch('backend.blueprints.forms_bp.send_dynamic_email')

    form_data = {
        'companyName': 'Test Company',
        'date': '2025-09-26',
        'month': '09',
        'year': '2025',
        'premises': ['Premise 1'],
        'devices': ['Device 1'],
        'collectBack': 'on',
        'remark': 'Test discontinue remark'
    }

    with app.test_request_context():
        response = client.post(url_for('forms.change_form'), data=form_data, follow_redirects=False)

    assert response.status_code == 302
    assert response.location == url_for('dashboard')

    # Verify refund collection was used (not change_form_collection)
    mock_refund_insert.assert_called_once()
    inserted_data = mock_refund_insert.call_args[0][0]
    assert inserted_data['collect_back'] is True
    assert inserted_data['company'] == 'Test Company'

    # Verify email was sent
    mock_email.assert_called_once_with(
        "discontinue_notification",
        mocker.ANY,  # The data dict with customer_email added
        mocker.ANY   # mail object
    )

    mock_log.assert_called()

def test_change_form_post_device_replacement(client, app, mocker):
    """Test that non-collect-back changes go to device_replacements collection"""
    login_admin(client, mocker, app)

    # Mock collections
    mock_customer = {
        "_id": "customer_id",
        "company": "Test Company",
        "email": "pic@testcompany.com"
    }
    mocker.patch('backend.blueprints.forms_bp.profile_list_collection.find_one', return_value=mock_customer)
    mock_replacement_insert = mocker.patch('backend.blueprints.forms_bp.device_replacements_collection.insert_one')
    mock_log = mocker.patch('backend.blueprints.forms_bp.log_activity')

    form_data = {
        'companyName': 'Test Company',
        'date': '2025-09-26',
        'month': '09',
        'year': '2025',
        'premises': ['Premise 1'],
        'devices': ['Device 1'],
        'changeScent': 'on',
        'changeScentText': 'Lavender',
        'remark': 'Test change remark'
    }

    with app.test_request_context():
        response = client.post(url_for('forms.change_form'), data=form_data, follow_redirects=False)

    assert response.status_code == 302
    assert response.location == url_for('dashboard')

    # Verify device_replacements collection was used
    mock_replacement_insert.assert_called_once()
    inserted_data = mock_replacement_insert.call_args[0][0]
    assert inserted_data['status'] == 'pending'
    assert inserted_data['change_scent'] is True
    assert inserted_data['change_scent_to'] == 'Lavender'
    assert 'submitted_at' in inserted_data

    mock_log.assert_called()

# --- Tests for device replacements workflow ---
def test_device_replacements_get_unauthenticated(client, app):
    """Test that device replacements page requires authentication"""
    with app.test_request_context():
        response = client.get(url_for('forms.device_replacements'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_device_replacements_get_authenticated(client, app, mocker):
    """Test device replacements page loads for authenticated users"""
    login_admin(client, mocker, app)

    # Mock device replacements collection
    mock_replacements = [
        {
            "_id": "replacement_id_1",
            "company": "Test Company",
            "status": "pending",
            "submitted_at": datetime.now(),
            "devices": ["Device 1"],
            "premises": ["Premise 1"]
        }
    ]
    mocker.patch('backend.blueprints.forms_bp.device_replacements_collection.find', return_value=mock_replacements)

    with app.test_request_context():
        response = client.get(url_for('forms.device_replacements'))

    assert response.status_code == 200
    assert b"Pending Device Replacements" in response.data

def test_confirm_replacement_success(client, app, mocker):
    """Test successful replacement confirmation"""
    login_admin(client, mocker, app)

    # Mock replacement data
    mock_replacement = {
        "_id": "replacement_id",
        "company": "Test Company",
        "devices": ["Device 1"],
        "premises": ["Premise 1"],
        "status": "pending"
    }
    mocker.patch('backend.blueprints.forms_bp.device_replacements_collection.find_one', return_value=mock_replacement)
    mocker.patch('backend.blueprints.forms_bp.device_replacements_collection.update_one')
    mocker.patch('backend.blueprints.forms_bp.profile_list_collection.find_one', return_value={"email": "pic@test.com"})
    mock_log = mocker.patch('backend.blueprints.forms_bp.log_activity')
    mock_email = mocker.patch('backend.blueprints.forms_bp.send_dynamic_email')

    form_data = {
        'client_signature': 'signature_data',
        'technician_notes': 'Changes completed successfully'
    }

    with app.test_request_context():
        response = client.post(url_for('forms.confirm_replacement', replacement_id='replacement_id'),
                              data=form_data, follow_redirects=False)

    assert response.status_code == 302
    assert response.location == url_for('forms.device_replacements')

    # Verify update was called
    from backend.blueprints.forms_bp import device_replacements_collection
    update_mock = mocker.patch.object(device_replacements_collection, 'update_one')
    update_mock.assert_called_once()

    # Verify email was sent
    mock_email.assert_called_once_with(
        "change_completed_notification",
        mocker.ANY,
        mocker.ANY
    )

    mock_log.assert_called()

def test_confirm_replacement_not_found(client, app, mocker):
    """Test confirmation with non-existent replacement ID"""
    login_admin(client, mocker, app)

    mocker.patch('backend.blueprints.forms_bp.device_replacements_collection.find_one', return_value=None)

    with app.test_request_context():
        response = client.get(url_for('forms.confirm_replacement', replacement_id='nonexistent_id'))

    assert response.status_code == 302
    assert response.location == url_for('forms.device_replacements')

# --- Tests for discontinued clients management ---
def test_discontinued_clients_get_unauthenticated(client, app):
    """Test that discontinued clients page requires admin authentication"""
    with app.test_request_context():
        response = client.get(url_for('forms.discontinued_clients'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_discontinued_clients_get_non_admin(client, app, mocker):
    """Test that discontinued clients page requires admin user type"""
    # Login as technician (non-admin)
    mock_user_data = {"_id": "tech_id", "username": "technician", "password": "hashed_password"}
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_user_data)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)
    mocker.patch('backend.blueprints.auth_bp.log_activity')

    with app.app_context():
        admin_login_url = url_for('auth.admin_login')
    client.post(admin_login_url, data={'username': 'technician', 'password': 'password'})

    # Mock session to be technician
    with app.test_request_context():
        with client.session_transaction() as sess:
            sess['user_type'] = 'technician'

        response = client.get(url_for('forms.discontinued_clients'), follow_redirects=False)

    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_discontinued_clients_get_admin(client, app, mocker):
    """Test discontinued clients page loads for admin users"""
    login_admin(client, mocker, app)

    # Mock discontinued clients
    mock_discontinued = [
        {
            "_id": "discontinued_id_1",
            "company": "Test Company",
            "submitted_at": datetime.now(),
            "devices": ["Device 1"],
            "premises": ["Premise 1"]
        }
    ]
    mocker.patch('backend.blueprints.forms_bp.refund_collection.find', return_value=mock_discontinued)

    with app.test_request_context():
        response = client.get(url_for('forms.discontinued_clients'))

    assert response.status_code == 200
    assert b"Discontinued Clients" in response.data

def test_reactivate_client_success(client, app, mocker):
    """Test successful client reactivation"""
    login_admin(client, mocker, app)

    # Mock discontinued client
    mock_client = {
        "_id": "client_id",
        "company": "Test Company",
        "premises": ["Premise 1"],
        "devices": ["Device 1"]
    }
    mocker.patch('backend.blueprints.forms_bp.refund_collection.find_one', return_value=mock_client)
    mock_log = mocker.patch('backend.blueprints.forms_bp.log_activity')

    with app.test_request_context():
        response = client.post(url_for('forms.reactivate_client', client_id='client_id'), follow_redirects=False)

    assert response.status_code == 302
    assert response.location == url_for('forms.discontinued_clients')

    mock_log.assert_called_once()

def test_reactivate_client_not_found(client, app, mocker):
    """Test reactivation with non-existent client ID"""
    login_admin(client, mocker, app)

    mocker.patch('backend.blueprints.forms_bp.refund_collection.find_one', return_value=None)

    with app.test_request_context():
        response = client.post(url_for('forms.reactivate_client', client_id='nonexistent_id'), follow_redirects=False)

    assert response.status_code == 302
    assert response.location == url_for('forms.discontinued_clients')

# --- Tests for PDF generation ---
def test_generate_discontinue_pdf(app, mocker):
    """Test discontinue PDF generation"""
    from backend.utils import generate_discontinue_pdf

    test_data = {
        "company": "Test Company",
        "date": "2025-09-26",
        "user": "testuser",
        "premises": ["Premise 1", "Premise 2"],
        "devices": ["Device 1", "Device 2"],
        "remark": "Test discontinue remark"
    }

    pdf_bytes = generate_discontinue_pdf(test_data)

    # Verify PDF was generated (basic check)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    # PDF files start with %PDF-
    assert pdf_bytes.startswith(b'%PDF-')

def test_generate_change_completed_pdf(app, mocker):
    """Test change completion PDF generation"""
    from backend.utils import generate_change_completed_pdf

    test_data = {
        "company": "Test Company",
        "confirmed_by": "technician1",
        "confirmation_date": "2025-09-26",
        "date": "2025-09-20",
        "premises": ["Premise 1"],
        "devices": ["Device 1"],
        "change_scent": True,
        "change_scent_to": "Lavender",
        "technician_notes": "Changes completed successfully"
    }

    pdf_bytes = generate_change_completed_pdf(test_data)

    # Verify PDF was generated
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b'%PDF-')

# --- Tests for email template handling ---
def test_generate_file_for_discontinue_notification(app, mocker):
    """Test that generate_file_for handles discontinue notification"""
    from backend.utils import generate_file_for

    test_variables = {
        "company": "Test Company",
        "customer_email": "pic@test.com"
    }

    pdf_bytes = generate_file_for("discontinue_notification", test_variables)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0

def test_generate_file_for_change_completed_notification(app, mocker):
    """Test that generate_file_for handles change completed notification"""
    from backend.utils import generate_file_for

    test_variables = {
        "company": "Test Company",
        "customer_email": "pic@test.com"
    }

    pdf_bytes = generate_file_for("change_completed_notification", test_variables)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
