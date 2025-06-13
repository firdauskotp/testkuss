# backend/tests/conftest.py
import pytest
from backend.app import app as flask_app # Import your Flask app instance

@pytest.fixture(scope='function') # Changed from 'module' to 'function'
def app():
    """Instance of Flask app for testing."""
    # Configure your app for testing
    # Reconfiguring the globally imported flask_app instance for each test.
    # A true app factory pattern (def create_app()) would be better for full isolation.
    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "pytest_secret_key",
        "SERVER_NAME": "localhost.test",
        # "WTF_CSRF_ENABLED": False, # Example: disable CSRF for testing forms
    })

    # The test client obtained from this app will create its own app context
    # for each request. Pushing a context here is mainly for operations
    # directly within the test function that might need `url_for` or app config
    # outside of a client request, or to ensure URL map is built.
    with flask_app.app_context():
        print("\n--- URL MAP IN CONftest.py APP FIXTURE (BEGIN) ---")
        if hasattr(flask_app, 'url_map'):
            for rule in flask_app.url_map.iter_rules():
                print(f"Endpoint: {rule.endpoint}, Methods: {','.join(rule.methods)}, Path: {str(rule)}")
        else:
            print("URL map not available on flask_app object.")
        print("--- URL MAP IN CONftest.py APP FIXTURE (END) ---\n")
        pass

    yield flask_app

    # Teardown code can go here if needed
    # with flask_app.app_context():
    #     # drop_db() or other cleanup

@pytest.fixture(scope='function') # Changed from 'module' to 'function'
def client(app):
    """A test client for the app."""
    return app.test_client()

# You could also add a 'runner' fixture if you use Flask CLI commands
# @pytest.fixture(scope='module')
# def runner(app):
#     return app.test_cli_runner()
