from flask_security import UserMixin, RoleMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import re

class Role(RoleMixin):
    def __init__(self, name, description=None):
        self.name = name
        self.description = description

class User(UserMixin):
    def __init__(self, email, password=None, username=None, active=True, roles=None, fs_uniquifier=None):
        self.email = email.lower().strip()
        self.username = username.lower().strip() if username else email.split('@')[0]
        self.active = active
        self.roles = roles or []
        self.fs_uniquifier = fs_uniquifier or self._generate_uniquifier()
        self.created_at = datetime.utcnow()
        
        if password:
            self.password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        else:
            self.password = None
    
    def _generate_uniquifier(self):
        """Generate a unique identifier for Flask-Security"""
        import uuid
        return str(uuid.uuid4())
    
    def set_password(self, password):
        """Set user password with hashing"""
        self.password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
    
    def check_password(self, password):
        """Check if provided password matches the hashed password"""
        return check_password_hash(self.password, password)
    
    def has_role(self, role_name):
        """Check if user has a specific role"""
        return any(role.name == role_name for role in self.roles)
    
    def add_role(self, role):
        """Add a role to the user"""
        if role not in self.roles:
            self.roles.append(role)
    
    def remove_role(self, role):
        """Remove a role from the user"""
        if role in self.roles:
            self.roles.remove(role)
    
    def get_id(self):
        """Return user ID for Flask-Login. Use MongoDB _id instead of fs_uniquifier"""
        return getattr(self, 'id', None) or self.fs_uniquifier
    
    @staticmethod
    def validate_email(email):
        """Validate email format"""
        if not email or len(email) > 254:
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_password(password):
        """Validate password strength"""
        if not password or len(password) < 8:
            return False
        return len(password) <= 100

# MongoDB collections for storing users and roles
# These would be imported from col.py or defined here
# For now, we'll define the structure but they'll be connected in the app initialization

# User data structure that matches our existing collections
class UserDataModel:
    """Model for existing user data structure"""
    
    @staticmethod
    def from_admin_document(doc):
        """Convert existing admin document to User model"""
        # Create user without password to avoid double hashing
        user = User(
            email=doc.get('email', ''),
            username=doc.get('username', ''),
            active=True
        )
        user.id = str(doc.get('_id'))
        # Set the already hashed password directly
        user.password = doc.get('password', '')
        # Add admin role
        admin_role = Role('admin', 'Administrator role')
        user.add_role(admin_role)
        return user
    
    @staticmethod
    def from_customer_document(doc):
        """Convert existing customer document to User model"""
        # Create user without password to avoid double hashing
        user = User(
            email=doc.get('email', ''),
            active=True
        )
        user.id = str(doc.get('_id'))
        # Set the already hashed password directly
        user.password = doc.get('password', '')
        # Add customer role
        customer_role = Role('customer', 'Customer role')
        user.add_role(customer_role)
        return user
