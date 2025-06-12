import pytest
import unittest
from unittest.mock import patch, MagicMock, ANY
from flask import Flask, jsonify, render_template_string
from datetime import datetime, timedelta

# Assuming your Flask app instance is named 'app' in 'backend.app'
# and collections are in 'backend.col'
# We will need to adjust these imports if the actual structure is different.
# For now, let's assume we can import app and collections directly or they are set up in a fixture.

# Placeholder for app and db collections - these would typically be imported or set up via fixtures
# from backend.app import app as flask_app # Assuming your app is named flask_app
# from backend.col import services_collection, changed_models_collection, discontinue_collection

class TestApp:

    @pytest.fixture(autouse=True)
    def client(self, monkeypatch):
        # Create a new Flask app for testing or use the existing one
        # This setup is basic and might need adjustment based on your app's structure
        self.app = Flask(__name__) # Or import your actual app instance
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test_secret_key' # Needed for session if used by tested routes

        # Mock collections that will be used by the app.
        # We are creating MagicMock instances for each collection.
        self.mock_services_collection = MagicMock()
        self.mock_changed_models_collection = MagicMock()
        self.mock_discontinue_collection = MagicMock()
        self.mock_logs_collection = MagicMock() # for log_activity

        # Patch the collections in the application context.
        # The actual module path for collections ('backend.app.services_collection', etc.)
        # needs to match where they are accessed by your Flask app's routes.
        # This assumes collections are imported directly into backend.app or backend.col
        # and then used by functions in backend.app

        # If collections are in backend.col and imported into backend.app:
        monkeypatch.setattr("backend.app.services_collection", self.mock_services_collection)
        monkeypatch.setattr("backend.app.changed_models_collection", self.mock_changed_models_collection)
        monkeypatch.setattr("backend.app.discontinue_collection", self.mock_discontinue_collection)
        monkeypatch.setattr("backend.app.logs_collection", self.mock_logs_collection) # for log_activity

        # If collections are directly in backend.app (less likely based on col.py):
        # monkeypatch.setattr("backend.app.services_collection", self.mock_services_collection)

        # If your app uses 'db' object from which collections are accessed, mock that instead.
        # e.g., mock_db = MagicMock()
        # mock_db.services_collection = self.mock_services_collection
        # monkeypatch.setattr("backend.app.db", mock_db)

        # Import the app and its functions after patching
        from backend.app import app as flask_app
        from backend.app import get_premises, get_devices, change_form, clear_discontinued_items, log_activity

        # Configure routes for testing (if not already done by importing flask_app)
        # This is a simplified way to ensure routes are available for the test client.
        # In a real scenario, your app factory or app instance would handle this.
        if not hasattr(flask_app, '_got_first_request') or not flask_app._got_first_request:
            @self.app.route('/get-premises/<company>')
            def _get_premises_route(company):
                return get_premises(company)

            @self.app.route('/get-devices/<premise>')
            def _get_devices_route(premise):
                return get_devices(premise)

            @self.app.route('/change-form', methods=['POST', 'GET'])
            def _change_form_route():
                 # Mock session for change_form if it relies on session['username']
                with patch('backend.app.session', {'username': 'testuser'}):
                    return change_form()

            # For clear_discontinued_items, we'll test its logic directly, not as a route.
            # However, if it uses app context (like app.logger), that needs to be handled.
            self.clear_discontinued_items_func = clear_discontinued_items
            self.log_activity_func = log_activity


        self.test_client = self.app.test_client()
        # yield self.test_client # if we need to return it for pytest tests

    def setup_method(self, method):
        """Reset mocks before each test method."""
        self.mock_services_collection.reset_mock()
        self.mock_changed_models_collection.reset_mock()
        self.mock_discontinue_collection.reset_mock()
        self.mock_logs_collection.reset_mock()


    def test_get_premises(self):
        """Test the /get-premises/<company> endpoint."""
        # Mock the database call
        self.mock_services_collection.distinct.return_value = ['Premise1', 'Premise2']

        # Mock render_template_string which is used if render_template is not fully setup
        # Or ensure your app's template loader is configured for tests
        with patch('backend.app.render_template', return_value="<input type='checkbox' value='Premise1'>Premise1</input>") as mock_render:
            response = self.test_client.get('/get-premises/TestCompany')

        assert response.status_code == 200
        assert b"Premise1" in response.data # Check for premise name in HTML
        self.mock_services_collection.distinct.assert_called_once_with('Premise Name', {'company': 'TestCompany'})
        mock_render.assert_called_once_with('partials/premise_checkboxes.html', premises=['Premise1', 'Premise2'])

    def test_get_devices(self):
        """Test the /get-devices/<premise> endpoint."""
        self.mock_services_collection.find.return_value = [
            {'Model': 'ModelX'},
            {'Model': 'ModelY'},
            {'Model': 'ModelX'} # Duplicate to test uniqueness
        ]
        response = self.test_client.get('/get-devices/TestPremise')
        assert response.status_code == 200
        json_data = response.get_json()
        assert 'models' in json_data
        assert sorted(json_data['models']) == sorted(['ModelX', 'ModelY'])
        self.mock_services_collection.find.assert_called_once_with({'Premise Name': 'TestPremise'})

    def test_change_form_post_no_collect_back(self):
        """Test POST to /change-form without collectBack."""
        form_data = {
            'companyName': 'TestCompany',
            'premises': ['Premise1'],
            'devices': ['DeviceA'],
            'month': 'JAN',
            'year': '2024',
            'remark': 'Test remark'
            # No 'collectBack' means it's not "on"
        }
        # Mock the log_activity function if it's called
        with patch('backend.app.log_activity', MagicMock()) as mock_log:
            with patch('backend.app.flash', MagicMock()) as mock_flash: # Mock flash
                response = self.test_client.post('/change-form', data=form_data)

        assert response.status_code == 302 # Expecting a redirect
        self.mock_changed_models_collection.insert_one.assert_called_once()
        inserted_data = self.mock_changed_models_collection.insert_one.call_args[0][0]
        assert inserted_data['company'] == 'TestCompany'
        assert inserted_data['collect_back'] is False
        assert 'collect_back_date_dt' not in inserted_data
        mock_log.assert_called_once() # Check if log_activity was called

    def test_change_form_post_with_collect_back(self):
        """Test POST to /change-form with collectBack."""
        form_data = {
            'companyName': 'TestCompany',
            'premises': ['Premise1'],
            'devices': ['DeviceA'],
            'collectBack': 'on', # Checkbox is checked
            'month': 'MAR',
            'year': '2025',
            'remark': 'Collect back test'
        }
        with patch('backend.app.log_activity', MagicMock()) as mock_log:
            with patch('backend.app.flash', MagicMock()) as mock_flash: # Mock flash
                response = self.test_client.post('/change-form', data=form_data)

        assert response.status_code == 302 # Expecting a redirect
        self.mock_discontinue_collection.insert_one.assert_called_once()
        inserted_data = self.mock_discontinue_collection.insert_one.call_args[0][0]
        assert inserted_data['company'] == 'TestCompany'
        assert inserted_data['collect_back'] is True
        assert 'collect_back_date_dt' in inserted_data
        assert inserted_data['collect_back_date_dt'] == datetime(2025, 3, 1)
        mock_log.assert_called_once()

    def test_clear_discontinued_items_logic(self):
        """Test the core logic of clear_discontinued_items."""
        fixed_now = datetime(2024, 7, 15, 10, 0, 0)

        past_item_id = "past_item_id_obj" # In real ObjectId, but string for mock matching
        future_item_id = "future_item_id_obj"

        # Mock items in the collection
        # Note: direct use of self.mock_discontinue_collection refers to the one patched into backend.app
        # If clear_discontinued_items uses a direct import from backend.col, that needs specific patching or a different approach.
        # For this test, we assume clear_discontinued_items uses the (mocked) discontinue_collection available in its module (backend.app)

        # This test needs to call the *function* clear_discontinued_items directly,
        # not via scheduler.
        # The function clear_discontinued_items is imported and available as self.clear_discontinued_items_func

        with patch('backend.app.datetime') as mock_datetime:
            mock_datetime.now.return_value = fixed_now

            # No need to mock .find() then .delete_many(), just mock .delete_many directly for this unit test
            self.mock_discontinue_collection.delete_many.return_value = MagicMock(deleted_count=1)

            # Call the function that contains the logic
            # Ensure that discontinue_collection used by clear_discontinued_items is our mock
            self.clear_discontinued_items_func()

            self.mock_discontinue_collection.delete_many.assert_called_once_with({
                "collect_back_date_dt": {"$lte": fixed_now}
            })
            # To assert which items remain, you'd typically mock `find` to return specific items
            # and then check `delete_many` arguments, or check the contents of a test DB.
            # With full mocking of delete_many, we only check it was called correctly.

    def test_clear_discontinued_items_no_items_to_delete(self):
        """Test clear_discontinued_items when no items are old enough."""
        fixed_now = datetime(2024, 1, 15, 10, 0, 0)

        with patch('backend.app.datetime') as mock_datetime:
            mock_datetime.now.return_value = fixed_now
            self.mock_discontinue_collection.delete_many.return_value = MagicMock(deleted_count=0)

            self.clear_discontinued_items_func()

            self.mock_discontinue_collection.delete_many.assert_called_once_with({
                "collect_back_date_dt": {"$lte": fixed_now}
            })

# To run these tests, you would use pytest in your terminal:
# pytest backend/tests/test_app.py

# Notes on improvements/adjustments:
# 1. App Factory Pattern: If your Flask app uses an app factory (create_app()),
#    it's better to create a test app instance from that factory in the fixture.
# 2. Database Fixtures: For more complex tests, you might use database fixtures
#    (e.g., with pytest-mongodb) to manage test data in a real test database
#    or use more sophisticated mocking libraries for MongoDB.
# 3. Configuration: Ensure all necessary Flask configurations (like SECRET_KEY for sessions)
#    are set correctly for the test environment.
# 4. Patching accuracy: The paths used in monkeypatch.setattr and @patch
#    (e.g., "backend.app.services_collection") must exactly match the path
#    to the object as it's seen by the module being tested. If `backend.app` imports
#    `services_collection` from `backend.col` as `from backend.col import services_collection`,
#    then when testing routes in `backend.app`, you patch `backend.app.services_collection`.
# 5. Direct function testing: For `clear_discontinued_items_logic`, ensure the function is called
#    in a way that it uses the mocked `discontinue_collection`. The current setup assumes
#    `clear_discontinued_items` (when imported into the test) will use the patched collections.

# The current fixture setup attempts to patch collections within the 'backend.app' namespace.
# If your routes/functions in 'backend.app' import collections from 'backend.col' like:
# `from backend.col import services_collection`
# then patching `backend.app.services_collection` should work for tests of those routes/functions.
# If `clear_discontinued_items` itself directly imports `discontinue_collection` from `backend.col`,
# the patch for that specific function call might need to be `patch('backend.app.discontinue_collection', self.mock_discontinue_collection)`
# or ensuring the fixture patches it correctly before the function is imported/used by the test.
# The `autouse=True` fixture with monkeypatching at the start should generally cover this,
# as long as `from backend.app import clear_discontinued_items` happens *after* the patch is applied.
# The current structure of the fixture where functions are imported after patching should be okay.
```
