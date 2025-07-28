from flask_security import Security
from flask_security.core import AnonymousUser
from flask import current_app, redirect, url_for, flash
from .models import User, Role
from .user_datastore import MongoUserDatastore
import os

# Custom anonymous user class
class CustomAnonymousUser(AnonymousUser):
    def has_role(self, role):
        return False

def configure_security(app):
    """Configure Flask-Security for the application"""
    
    # Create datastore (no parameters needed - it manages collections internally)
    datastore = MongoUserDatastore()
    
    # Initialize Flask-Security
    security = Security(app, datastore)
    
    # Configure Flask-Login login view (this overrides Flask-Security's default)
    from flask_login import LoginManager
    login_manager = app.login_manager
    login_manager.login_view = 'new_auth.index'  # Point to your custom login route
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'
    
    # Set up user loader callback - CRITICAL for session management
    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login session management"""
        return datastore.get_user(user_id)
    
    # Set custom anonymous user
    security.anonymous_user = CustomAnonymousUser
    
    # Configure Flask-Security settings
    app.config['SECURITY_PASSWORD_SALT'] = os.getenv('SECURITY_PASSWORD_SALT', 'default-salt-change-in-production')
    app.config['SECURITY_REGISTERABLE'] = False  # Disable default registration
    app.config['SECURITY_SEND_REGISTER_EMAIL'] = False  # Disable email for now
    app.config['SECURITY_POST_LOGIN_VIEW'] = '/dashboard'
    app.config['SECURITY_POST_LOGOUT_VIEW'] = '/'
    app.config['SECURITY_POST_REGISTER_VIEW'] = '/'
    app.config['SECURITY_UNAUTHORIZED_VIEW'] = '/'  # Redirect unauthorized to your login page
    app.config['SECURITY_LOGIN_URL'] = '/'  # Set login URL to your index route
    app.config['SECURITY_LOGOUT_URL'] = '/logout'  # Set logout URL
    app.config['SECURITY_LOGIN_USER_TEMPLATE'] = None  # Disable default login template
    app.config['SECURITY_REGISTER_USER_TEMPLATE'] = None  # Disable default register template
    
    # Disable Flask-Security views completely to avoid conflicts
    app.config['SECURITY_LOGIN_WITHOUT_VIEWS'] = True
    app.config['SECURITY_REGISTER_WITHOUT_VIEWS'] = True
    
    # Configure password hashing
    app.config['SECURITY_PASSWORD_HASH'] = 'pbkdf2_sha256'
    app.config['SECURITY_PASSWORD_LENGTH_MIN'] = 8
    
    # Configure session
    app.config['SECURITY_TRACKABLE'] = True
    
    # Enable CSRF protection
    app.config['SECURITY_CSRF_PROTECT_MECHANISMS'] = ['session', 'basic']
    app.config['SECURITY_CSRF_IGNORE_UNAUTH_ENDPOINTS'] = False
    app.config['WTF_CSRF_TIME_LIMIT'] = None  # Disable time limit for CSRF tokens
    
    return security

def check_user_role(user, required_role):
    """Check if user has the required role"""
    if not user or not user.is_authenticated:
        return False
    
    # For our custom implementation, check roles directly
    if hasattr(user, 'has_role'):
        return user.has_role(required_role)
    
    # Fallback for custom user objects
    if hasattr(user, 'roles'):
        return any(role.name == required_role for role in user.roles)
    
    return False
