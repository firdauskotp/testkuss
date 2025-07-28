from flask_security import UserDatastore
from .models import User, Role
from .col import login_collection, login_cust_collection
from bson import ObjectId
from werkzeug.security import check_password_hash

class MongoUserDatastore(UserDatastore):
    """MongoDB-based user datastore for Flask-Security"""
    
    def __init__(self):
        self.admin_collection = login_collection
        self.customer_collection = login_cust_collection
    
    def get_user(self, identifier):
        """Get user by ID, email, or fs_uniquifier"""
        try:
            # Try to find by ObjectId first
            if isinstance(identifier, str) and len(identifier) == 24:
                try:
                    obj_id = ObjectId(identifier)
                    # Check admin collection
                    user_doc = self.admin_collection.find_one({"_id": obj_id})
                    if user_doc:
                        return self._create_user_from_doc(user_doc, 'admin')
                    
                    # Check customer collection
                    user_doc = self.customer_collection.find_one({"_id": obj_id})
                    if user_doc:
                        return self._create_user_from_doc(user_doc, 'customer')
                except:
                    pass
            
            # Try to find by fs_uniquifier (Flask-Security unique identifier)
            user_doc = self.admin_collection.find_one({"fs_uniquifier": identifier})
            if user_doc:
                return self._create_user_from_doc(user_doc, 'admin')
            
            user_doc = self.customer_collection.find_one({"fs_uniquifier": identifier})
            if user_doc:
                return self._create_user_from_doc(user_doc, 'customer')
            
            # Try to find by email
            user_doc = self.admin_collection.find_one({"email": identifier})
            if user_doc:
                return self._create_user_from_doc(user_doc, 'admin')
            
            user_doc = self.customer_collection.find_one({"email": identifier})
            if user_doc:
                return self._create_user_from_doc(user_doc, 'customer')
            
            # Try to find by username (admin only)
            user_doc = self.admin_collection.find_one({"username": identifier})
            if user_doc:
                return self._create_user_from_doc(user_doc, 'admin')
                
        except Exception as e:
            print(f"Error getting user: {e}")
        
        return None
    
    def _create_user_from_doc(self, user_doc, user_type):
        """Create User object from database document"""
        roles = []
        if user_type == 'admin':
            roles.append(Role('admin', 'Administrator role'))
            if user_doc.get('is_super_admin', False):
                roles.append(Role('super_admin', 'Super Administrator role'))
        else:
            roles.append(Role('customer', 'Customer role'))
        
        # Create user without password to avoid double hashing
        user = User(
            email=user_doc['email'],
            username=user_doc.get('username'),
            active=True,
            roles=roles,
            fs_uniquifier=user_doc.get('fs_uniquifier')  # Use existing or generate new
        )
        user.id = str(user_doc['_id'])
        # Set the already hashed password directly
        user.password = user_doc['password']
        
        # Ensure fs_uniquifier is set (Flask-Security requirement)
        if not user.fs_uniquifier:
            user.fs_uniquifier = user._generate_uniquifier()
        
        return user
    
    def find_user(self, **kwargs):
        """Find user by email, username, etc."""
        email = kwargs.get('email')
        username = kwargs.get('username')
        
        if email:
            return self.get_user(email)
        elif username:
            return self.get_user(username)
        
        return None
    
    def verify_password(self, user, password):
        """Verify user password"""
        if user and user.password:
            return check_password_hash(user.password, password)
        return False
    
    # Required methods for Flask-Security UserDatastore
    def put(self, obj):
        """Save user object (not implemented for this simple setup)"""
        pass
    
    def delete(self, obj):
        """Delete user object (not implemented for this simple setup)"""
        pass
    
    def commit(self):
        """Commit changes (not needed for MongoDB)"""
        pass
    
    def create_role(self, **kwargs):
        """Create a new role"""
        return Role(**kwargs)
    
    def find_role(self, role):
        """Find role by name"""
        if isinstance(role, str):
            return Role(role)
        return role
    
    def create_user(self, **kwargs):
        """Create a new user"""
        return User(**kwargs)
    
    def delete_user(self, user):
        """Delete a user (not implemented)"""
        pass
    
    def activate_user(self, user):
        """Activate a user"""
        user.active = True
    
    def deactivate_user(self, user):
        """Deactivate a user"""
        user.active = False
    
    def add_role_to_user(self, user, role):
        """Add role to user"""
        if isinstance(role, str):
            role = Role(role)
        user.add_role(role)
    
    def remove_role_from_user(self, user, role):
        """Remove role from user"""
        if isinstance(role, str):
            role = Role(role)
        user.remove_role(role)
