# backend/tests/test_global_settings_bp.py
import pytest
from flask import url_for, session, json # Import json for POST data
from bson import ObjectId # For comparing ObjectIds if necessary, though IDs often passed as strings

# Helper function to log in an admin user
def login_admin(client, mocker, app, admin_username="testglobaladmin", admin_id="testglobaladminid"):
    mock_user_data = { "_id": admin_id, "username": admin_username, "password": "hashed_password" }
    mocker.patch('backend.blueprints.auth_bp.login_collection.find_one', return_value=mock_user_data)
    mocker.patch('backend.blueprints.auth_bp.check_password_hash', return_value=True)
    mocker.patch('backend.blueprints.auth_bp.log_activity')
    with app.app_context():
        client.post(url_for('auth.admin_login'), data={'username': admin_username, 'password': 'password'})

# --- Tests for EO Global Settings ---
def test_eo_global_view_unauthenticated(client, app):
    with app.test_request_context():
        response = client.get(url_for('global_settings.eo_global_view'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

def test_eo_global_view_authenticated_empty(client, app, mocker):
    login_admin(client, mocker, app)
    mock_find_eo = mocker.patch('backend.blueprints.global_settings_bp.eo_pack_collection.find')
    mock_cursor = mocker.Mock()
    mock_cursor.sort.return_value = [] # find().sort() returns an empty list
    mock_find_eo.return_value = mock_cursor

    with app.test_request_context():
        response = client.get(url_for('global_settings.eo_global_view'))
    assert response.status_code == 200
    assert b"Manage Global Essential Oil List" in response.data
    assert b"Add New EO Entry" in response.data

def test_eo_global_view_with_data(client, app, mocker):
    login_admin(client, mocker, app)
    mock_eo_data = [
        {"_id": ObjectId("605c73a9759a2d2c58a9e001"), "eo_name": "Lavender", "order": 0},
        {"_id": ObjectId("605c73a9759a2d2c58a9e002"), "eo_name": "Citrus", "order": 1}
    ]
    mock_find_eo = mocker.patch('backend.blueprints.global_settings_bp.eo_pack_collection.find')
    mock_cursor = mocker.Mock()
    mock_cursor.sort.return_value = mock_eo_data
    mock_find_eo.return_value = mock_cursor

    with app.test_request_context():
        response = client.get(url_for('global_settings.eo_global_view'))
    assert response.status_code == 200
    assert b"Lavender" in response.data
    assert b"Citrus" in response.data

def test_save_eo_global_changes_success(client, app, mocker):
    login_admin(client, mocker, app)

    mock_eo_find_one = mocker.patch('backend.blueprints.global_settings_bp.eo_pack_collection.find_one')
    mock_eo_insert_one = mocker.patch('backend.blueprints.global_settings_bp.eo_pack_collection.insert_one')
    mock_eo_update_one = mocker.patch('backend.blueprints.global_settings_bp.eo_pack_collection.update_one')
    mock_eo_delete_one = mocker.patch('backend.blueprints.global_settings_bp.eo_pack_collection.delete_one')

    existing_eo_id_str = "605c73a9759a2d2c58a9e003"
    newly_added_peppermint_id = ObjectId()

    def find_one_side_effect(query_filter):
        # Call during ordering for newly added "Peppermint" (found by its actual new ObjectId AFTER insert)
        if query_filter.get("_id") == newly_added_peppermint_id:
            return {"_id": newly_added_peppermint_id, "eo_name": "Peppermint", "order": -1} # order is -1 as it was just inserted

        # Call during ordering for "Eucalyptus" (edited item, found by its existing ObjectId)
        if query_filter.get("_id") == ObjectId(existing_eo_id_str):
            return {"_id": ObjectId(existing_eo_id_str), "eo_name": "Eucalyptus", "order": 1} # current order before re-order

        # Call during initial check for "Peppermint" duplicate before adding (by name)
        if query_filter.get("eo_name") == "Peppermint" and "_id" not in query_filter and query_filter.get("order") is None:
            return None

        # Call during initial check for "Eucalyptus" duplicate when editing existing_eo_id_str (by name, excluding self)
        if query_filter.get("eo_name") == "Eucalyptus" and query_filter.get("_id", {}).get("$ne") == ObjectId(existing_eo_id_str):
            return None

        # Fallback for the case where the ordering loop looks for a new item by name and order: -1
        # This happens if the temp_id logic branch is false in the SUT's ordering loop.
        if query_filter.get("eo_name") == "Peppermint" and query_filter.get("order") == -1:
            return {"_id": newly_added_peppermint_id, "eo_name": "Peppermint", "order": -1}

        # print(f"Unhandled find_one query in test_save_eo_global_changes_success: {query_filter}") # For debugging
        return None

    mock_eo_find_one.side_effect = find_one_side_effect
    mock_eo_insert_one.return_value = mocker.Mock(inserted_id=newly_added_peppermint_id)

    post_data = {
        "added": [{"eo_name": "Peppermint", "temp_id": "client-temp-id-peppermint"}],
        "edited": [{"_id": existing_eo_id_str, "eo_name": "Eucalyptus"}],
        "deleted": ["605c73a9759a2d2c58a9e004"],
        "visual_order": [
            {"eo_name": "Peppermint", "temp_id": "client-temp-id-peppermint"},
            {"_id": existing_eo_id_str, "eo_name": "Eucalyptus"}
        ]
    }

    with app.test_request_context():
        response = client.post(url_for('global_settings.save_eo_global_changes'), json=post_data)

    assert response.status_code == 200
    assert response.json['status'] == 'success'

    mock_eo_insert_one.assert_called_once_with({"eo_name": "Peppermint", "order": -1})
    mock_eo_update_one.assert_any_call({'_id': ObjectId(existing_eo_id_str)}, {'$set': {'eo_name': 'Eucalyptus'}})
    mock_eo_delete_one.assert_called_once_with({'_id': ObjectId("605c73a9759a2d2c58a9e004")})

    mock_eo_update_one.assert_any_call({'_id': newly_added_peppermint_id}, {'$set': {'order': 0}})
    mock_eo_update_one.assert_any_call({'_id': ObjectId(existing_eo_id_str)}, {'$set': {'order': 1}})

# TODO: Add more tests for save_eo_global_changes (e.g., duplicate name on add/edit)

# --- Tests for Device Global Settings (similar structure to EO) ---
def test_device_global_view_unauthenticated(client, app):
    with app.test_request_context():
        response = client.get(url_for('global_settings.device_global_view'), follow_redirects=False)
    assert response.status_code == 302
    assert response.location == url_for('auth.admin_login')

# TODO: test_device_global_view_authenticated_empty
# TODO: test_device_global_view_with_data
# TODO: test_save_device_global_changes_success
# TODO: test_save_device_global_changes_duplicate_name
