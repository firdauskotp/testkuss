# backend/tests/test_data_reports_bp.py
import pytest
from flask import url_for, session
from datetime import datetime

# Helper function to log in an admin user
def login_admin(client, mocker, app, admin_username="testreportadmin", admin_id="testreportadminid"):
    mock_user_data = { "_id": admin_id, "username": admin_username, "password": "hashed_password" }
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_user_data)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)
    mocker.patch('backend.blueprints.auth_bp.log_activity')
    with app.app_context(): # Ensure url_for works within helper
        client.post(url_for('auth.admin_login'), data={'username': admin_username, 'password': 'password'})

# --- Tests for 'reports' (all-list) endpoint ---
def test_reports_all_list_get_unauthenticated(client, app):
    with app.test_request_context():
        response = client.get(url_for('data_reports.reports'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_reports_all_list_get_authenticated_empty(client, app, mocker):
    login_admin(client, mocker, app)

    mocker.patch('backend.blueprints.data_reports_bp.services_collection.count_documents', return_value=0)
    mock_find_services = mocker.patch('backend.blueprints.data_reports_bp.services_collection.find')
    mock_cursor = mocker.Mock()
    mock_cursor.skip.return_value.limit.return_value = []
    mock_find_services.return_value = mock_cursor

    with app.test_request_context():
        response = client.get(url_for('data_reports.reports'))

    assert response.status_code == 200
    assert b"Comprehensive Data Report" in response.data # Check page_title block
    # Assuming the template has a specific message or structure for no data
    # For example, if it shows a table with "No data available" in a row:
    assert b"No data available for the current filters." in response.data

def test_reports_all_list_get_with_data_and_filters(client, app, mocker):
    login_admin(client, mocker, app)

    mock_service_data = [
        {'S/N': 1, 'company': 'Company A', 'month_year': datetime(2023, 1, 15), 'Model': 'ModelX', 'industry': 'Tech', 'Premise Name': 'HQ', 'premise_area': 'Area1', 'premise_address': 'Addr1', 'pics': [], 'Color':'Blue', 'Volume':100, 'Current EO':'Citrus', 'Balance':50,'Consumption':50,'New EO':'', 'Refilled':0, 'E1 - DAYS':'Mon-Fri','E1 - START':'09:00','E1 - END':'17:00','E1 - WORK':60,'E1 - PAUSE':120, 'E2 - DAYS':'','E2 - START':'','E2 - END':'','E2 - WORK':'','E2 - PAUSE':'', 'E3 - DAYS':'','E3 - START':'','E3 - END':'','E3 - WORK':'','E3 - PAUSE':'', 'E4 - DAYS':'','E4 - START':'','E4 - END':'','E4 - WORK':'','E4 - PAUSE':'', '#1 Scent Effectiveness':'Good', '#1 Common encounters':'None', '#1 Other remarks':'All good'},
        {'S/N': 2, 'company': 'Company B', 'month_year': datetime(2023, 2, 10), 'Model': 'ModelY', 'industry': 'Retail', 'Premise Name': 'Store', 'premise_area': 'Area2', 'premise_address': 'Addr2', 'pics': [], 'Color':'Red', 'Volume':200, 'Current EO':'Floral', 'Balance':100,'Consumption':100,'New EO':'', 'Refilled':0, 'E1 - DAYS':'Sat-Sun','E1 - START':'10:00','E1 - END':'18:00','E1 - WORK':30,'E1 - PAUSE':90, 'E2 - DAYS':'','E2 - START':'','E2 - END':'','E2 - WORK':'','E2 - PAUSE':'', 'E3 - DAYS':'','E3 - START':'','E3 - END':'','E3 - WORK':'','E3 - PAUSE':'', 'E4 - DAYS':'','E4 - START':'','E4 - END':'','E4 - WORK':'','E4 - PAUSE':'', '#1 Scent Effectiveness':'Okay', '#1 Common encounters':'Dusty', '#1 Other remarks':'Needs check'}
    ]

    mocker.patch('backend.blueprints.data_reports_bp.services_collection.count_documents', return_value=len(mock_service_data))
    mock_find_services = mocker.patch('backend.blueprints.data_reports_bp.services_collection.find')
    mock_cursor = mocker.Mock()

    filtered_mock_data = [d for d in mock_service_data if d['company'] == 'Company A']

    def side_effect_find(query, projection):
        if query.get('company', {}).get('$regex') == 'Company A':
            mock_cursor.skip.return_value.limit.return_value = filtered_mock_data
        else:
            mock_cursor.skip.return_value.limit.return_value = mock_service_data
        return mock_cursor

    mock_find_services.side_effect = side_effect_find


    with app.test_request_context():
        response = client.get(url_for('data_reports.reports', Company='Company A', page='1', limit='10'))

    assert response.status_code == 200
    assert b"Company A" in response.data
    assert b"ModelX" in response.data
    assert b"Company B" not in response.data
    assert b"ModelY" not in response.data

    mock_find_services.assert_called()
    args, kwargs = mock_find_services.call_args
    assert 'company' in args[0]
    assert args[0]['company'] == {'$regex': 'Company A', '$options': 'i'}


# --- Tests for 'activity_logs_view' (logs) endpoint ---
def test_activity_logs_get_unauthenticated(client, app):
    with app.test_request_context():
        response = client.get(url_for('data_reports.activity_logs_view'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_activity_logs_get_authenticated_empty(client, app, mocker):
    login_admin(client, mocker, app)

    mocker.patch('backend.blueprints.data_reports_bp.logs_collection.count_documents', return_value=0)
    mock_find_logs = mocker.patch('backend.blueprints.data_reports_bp.logs_collection.find')
    mock_cursor = mocker.Mock()
    mock_cursor.sort.return_value.skip.return_value.limit.return_value = []
    mock_find_logs.return_value = mock_cursor

    with app.test_request_context():
        response = client.get(url_for('data_reports.activity_logs_view'))

    assert response.status_code == 200
    assert b"System Activity Log" in response.data
    assert b"No activity logs found." in response.data

def test_activity_logs_get_with_data(client, app, mocker):
    login_admin(client, mocker, app)

    mock_log_data = [
        {'user': 'admin1', 'action': 'Logged in', 'timestamp': datetime(2023, 3, 1, 10, 0, 0)},
        {'user': 'admin2', 'action': 'Deleted user X', 'timestamp': datetime(2023, 3, 1, 11, 0, 0)}
    ]
    mocker.patch('backend.blueprints.data_reports_bp.logs_collection.count_documents', return_value=len(mock_log_data))
    mock_find_logs = mocker.patch('backend.blueprints.data_reports_bp.logs_collection.find')
    mock_cursor = mocker.Mock()
    mock_cursor.sort.return_value.skip.return_value.limit.return_value = mock_log_data
    mock_find_logs.return_value = mock_cursor

    with app.test_request_context():
        response = client.get(url_for('data_reports.activity_logs_view'))

    assert response.status_code == 200
    assert b"admin1" in response.data
    assert b"Logged in" in response.data
    assert b"Deleted user X" in response.data
    assert b"2023-03-01" in response.data # Check for formatted date
