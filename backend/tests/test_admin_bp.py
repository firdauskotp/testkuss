import pytest
from flask import session
from bson import ObjectId
from ..blueprints.admin_bp import UserModelView, CustomerModelView
from ..col import login_collection, login_cust_collection

# Import the new auth blueprint for testing
import pytest
from flask import session, url_for
from bson import ObjectId
from ..blueprints.admin_bp import UserModelView, CustomerModelView
from ..col import login_collection, login_cust_collection

# Helper function to log in an admin user
def login_admin(client, mocker, app, admin_username="testadmin", admin_id="testadminid", is_super_admin=True):
    mock_user_data = { 
        "_id": admin_id, 
        "username": admin_username, 
        "email": f"{admin_username}@example.com",
        "password": "hashed_password",
        "is_super_admin": is_super_admin
    }
    mocker.patch('backend.blueprints.new_auth_bp.login_collection.find_one', return_value=mock_user_data)
    mocker.patch('backend.blueprints.new_auth_bp.check_password_hash', return_value=True)
    mocker.patch('backend.blueprints.new_auth_bp.log_activity')
    with app.app_context(): # Ensure url_for works within helper
        client.post(url_for('new_auth.index'), data={'login_input': admin_username, 'password': 'password'})

def test_super_admin_view_access(client, app, mocker):
    """Test that super admin view is accessible to super admins"""
    # Login as super admin
    login_admin(client, mocker, app, is_super_admin=True)
    
    with app.test_request_context():
        response = client.get('/super-admin/')
    # Should redirect to dashboard
    assert response.status_code == 302

def test_super_admin_view_no_access(client, app, mocker):
    """Test that super admin view is not accessible to non-super admins"""
    # Login as regular admin
    login_admin(client, mocker, app, is_super_admin=False)
    
    with app.test_request_context():
        response = client.get('/super-admin/')
    # Should redirect to dashboard with flash message
    assert response.status_code == 302

def test_user_model_view_index(client, app, mocker):
    """Test user model view index page"""
    # Login as super admin
    login_admin(client, mocker, app, is_super_admin=True)
    
    with app.test_request_context():
        response = client.get('/super-admin/admin_users/')
    assert response.status_code == 200

def test_customer_model_view_index(client, app, mocker):
    """Test customer model view index page"""
    # Login as super admin
    login_admin(client, mocker, app, is_super_admin=True)
    
    with app.test_request_context():
        response = client.get('/super-admin/customer_users/')
    assert response.status_code == 200

def test_admin_user_create_get(client, app, mocker):
    """Test admin user creation form"""
    # Login as super admin
    login_admin(client, mocker, app, is_super_admin=True)
    
    with app.test_request_context():
        response = client.get('/super-admin/admin_users/create')
    assert response.status_code == 200

def test_admin_user_create_post(client, app, mocker):
    """Test admin user creation"""
    # Login as super admin
    login_admin(client, mocker, app, is_super_admin=True)
    
    data = {
        'username': 'testadmin',
        'email': 'testadmin@example.com',
        'password': 'testpassword123',
        'is_super_admin': 'on'
    }
    
    with app.test_request_context():
        response = client.post('/super-admin/admin_users/create', data=data, follow_redirects=True)
    assert response.status_code == 200
    
    # Check if user was created
    user = login_collection.find_one({'username': 'testadmin'})
    assert user is not None
    assert user['email'] == 'testadmin@example.com'

def test_admin_user_edit_get(client, app, mocker):
    """Test admin user edit form"""
    # Login as super admin
    login_admin(client, mocker, app, is_super_admin=True)
    
    # Create a test user
    user_id = login_collection.insert_one({
        'username': 'edituser',
        'email': 'edituser@example.com',
        'password': 'testpassword123',
        'is_super_admin': False
    }).inserted_id
    
    with app.test_request_context():
        response = client.get(f'/super-admin/admin_users/edit/{user_id}')
    assert response.status_code == 200

def test_admin_user_delete(client, app, mocker):
    """Test admin user deletion"""
    # Login as super admin
    login_admin(client, mocker, app, is_super_admin=True)
    
    # Create a test user
    user_id = login_collection.insert_one({
        'username': 'deleteuser',
        'email': 'deleteuser@example.com',
        'password': 'testpassword123',
        'is_super_admin': False
    }).inserted_id
    
    with app.test_request_context():
        response = client.get(f'/super-admin/admin_users/delete/{user_id}', follow_redirects=True)
    assert response.status_code == 200
    
    # Check if user was deleted
    user = login_collection.find_one({'_id': user_id})
    assert user is None

def test_customer_user_delete(client, app, mocker):
    """Test customer user deletion"""
    # Login as super admin
    login_admin(client, mocker, app, is_super_admin=True)
    
    # Create a test customer
    customer_id = login_cust_collection.insert_one({
        'email': 'deletecustomer@example.com',
        'password': 'testpassword123'
    }).inserted_id
    
    with app.test_request_context():
        response = client.get(f'/super-admin/customer_users/delete/{customer_id}', follow_redirects=True)
    assert response.status_code == 200
    
    # Check if customer was deleted
    customer = login_cust_collection.find_one({'_id': customer_id})
    assert customer is None
