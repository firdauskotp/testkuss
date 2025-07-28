from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, jsonify
from flask_admin import Admin, BaseView, expose
from flask_admin.base import MenuLink
from ..decorators import super_admin_required
from ..col import (
    login_collection, login_cust_collection, collection, 
    change_collection, refund_collection, remark_collection,
    profile_list_collection, device_list_collection, route_list_collection,
    eo_list_collection, logs_collection
)
from ..models import User
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import os

# Create a custom admin view that requires super admin authentication
class SuperAdminView(BaseView):
    def is_accessible(self):
        """Check if user is logged in and is a super admin"""
        from flask_security import current_user
        from flask import session
        
        current_app.logger.info(f"SuperAdminView.is_accessible() called - User authenticated: {current_user.is_authenticated}")
        
        # Must be authenticated with Flask-Security
        if not current_user.is_authenticated:
            current_app.logger.warning("Super admin access denied - user not authenticated")
            return False
        
        # Must have admin role
        if not current_user.has_role('admin'):
            current_app.logger.warning(f"Super admin access denied - user {current_user.email} doesn't have admin role")
            return False
        
        # Must be marked as super admin in session (set during login)
        if not session.get('is_super_admin', False):
            current_app.logger.warning(f"Super admin access denied - user {current_user.email} not marked as super admin in session")
            return False
        
        # Double-check in database that user is actually super admin
        from ..col import login_collection
        user_doc = login_collection.find_one({"email": current_user.email})
        if not user_doc or not user_doc.get('is_super_admin', False):
            current_app.logger.warning(f"Super admin access denied - user {current_user.email} not super admin in database")
            return False
        
        current_app.logger.info(f"Super admin access granted to {current_user.email}")
        return True
    
    def inaccessible_callback(self, name, **kwargs):
        """Redirect to login page if user doesn't have access"""
        from flask import flash, redirect, url_for
        from flask_security import current_user
        
        if not current_user.is_authenticated:
            flash("Please log in to access the super admin panel.", "warning")
        else:
            flash("Access denied. Only super administrators can access this page.", "danger")
        
        return redirect(url_for('new_auth.index'))
    
    @expose('/')
    def index(self):
        # Default view - just redirect to dashboard
        return redirect(url_for('admin_bp.SuperAdminDashboard:index'))

# Custom views for backward compatibility
class UserModelView(SuperAdminView):
    @expose('/')
    def index(self):
        # Get all admin users
        users = list(login_collection.find())
        return self.render('admin/list.html', users=users, title='Admin Users')
    
    @expose('/view/<id>')
    def view(self, id):
        user = login_collection.find_one({'_id': ObjectId(id)})
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('admin_bp.UserModelView:index'))
        return self.render('admin/view.html', user=user, title='View Admin User')
    
    @expose('/create', methods=['GET', 'POST'])
    def create(self):
        if request.method == 'POST':
            username = request.form.get('username', '').strip().lower()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            is_super_admin = request.form.get('is_super_admin') == 'on'
            
            # Validate inputs
            if not username or len(username) < 3:
                flash('Username must be at least 3 characters long.', 'danger')
                return self.render('admin/create_user.html', title='Create Admin User')
            
            if not email or '@' not in email:
                flash('Please enter a valid email address.', 'danger')
                return self.render('admin/create_user.html', title='Create Admin User')
            
            # Check for existing user
            if login_collection.find_one({'$or': [{'username': username}, {'email': email}]}):
                flash('Username or email already exists.', 'danger')
                return self.render('admin/create_user.html', title='Create Admin User')
            
            # Generate password if not provided
            if not password:
                password = self.generate_password()
                flash(f'User created with auto-generated password: {password}', 'info')
            
            # Create user
            login_collection.insert_one({
                'username': username,
                'email': email,
                'password': generate_password_hash(password, method='pbkdf2:sha256', salt_length=16),
                'is_super_admin': is_super_admin
            })
            
            flash('Admin user created successfully!', 'success')
            return redirect(url_for('admin_bp.UserModelView:index'))
        
        return self.render('admin/create_user.html', title='Create Admin User')
    
    @expose('/edit/<id>', methods=['GET', 'POST'])
    def edit(self, id):
        user = login_collection.find_one({'_id': ObjectId(id)})
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('admin_bp.UserModelView:index'))
        
        if request.method == 'POST':
            username = request.form.get('username', '').strip().lower()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            is_super_admin = request.form.get('is_super_admin') == 'on'
            
            # Validate inputs
            if not username or len(username) < 3:
                flash('Username must be at least 3 characters long.', 'danger')
                return self.render('admin/edit_user.html', user=user, title='Edit Admin User')
            
            # Check for existing user (excluding current user)
            if login_collection.find_one({'$and': [{'$or': [{'username': username}, {'email': email}]}, {'_id': {'$ne': ObjectId(id)}}]}):
                flash('Username or email already exists.', 'danger')
                return self.render('admin/edit_user.html', user=user, title='Edit Admin User')
            
            # Update user
            update_data = {
                'username': username,
                'email': email,
                'is_super_admin': is_super_admin
            }
            
            # Update password if provided
            if password:
                update_data['password'] = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
                flash('Password updated successfully!', 'success')
            elif request.form.get('generate_password') == 'on':
                new_password = self.generate_password()
                update_data['password'] = generate_password_hash(new_password, method='pbkdf2:sha256', salt_length=16)
                flash(f'Password auto-generated: {new_password}', 'info')
            
            login_collection.update_one({'_id': ObjectId(id)}, {'$set': update_data})
            flash('Admin user updated successfully!', 'success')
            return redirect(url_for('admin_bp.UserModelView:index'))
        
        return self.render('admin/edit_user.html', user=user, title='Edit Admin User')
    
    @expose('/delete/<id>')
    def delete(self, id):
        result = login_collection.delete_one({'_id': ObjectId(id)})
        if result.deleted_count:
            flash('User deleted successfully', 'success')
        else:
            flash('User not found', 'danger')
        return redirect(url_for('admin_bp.UserModelView:index'))
    
    def generate_password(self, length=12):
        import random
        import string
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(random.choice(characters) for _ in range(length))

class CustomerModelView(SuperAdminView):
    @expose('/')
    def index(self):
        # Get all customer users
        customers = list(login_cust_collection.find())
        return self.render('admin/list.html', customers=customers, title='Customer Users')
    
    @expose('/view/<id>')
    def view(self, id):
        customer = login_cust_collection.find_one({'_id': ObjectId(id)})
        if not customer:
            flash('Customer not found', 'danger')
            return redirect(url_for('admin_bp.CustomerModelView:index'))
        return self.render('admin/view.html', customer=customer, title='View Customer User')
    
    @expose('/delete/<id>')
    def delete(self, id):
        result = login_cust_collection.delete_one({'_id': ObjectId(id)})
        if result.deleted_count:
            flash('Customer deleted successfully', 'success')
        else:
            flash('Customer not found', 'danger')
        return redirect(url_for('admin_bp.CustomerModelView:index'))

# Create the blueprint (moved to different URL to avoid conflict with Flask-Admin)
admin_bp = Blueprint('admin_bp', __name__, url_prefix='/admin-panel', 
                     template_folder='../templates')

# Initialize Flask-Admin
admin = Admin(
    name='KUSS Super Admin Panel',
    template_mode='bootstrap4',
    url='/super-admin',
    endpoint='super_admin'
)

# Add custom views for different collections
admin.add_view(UserModelView(name='Admin Users', endpoint='admin_users'))
admin.add_view(CustomerModelView(name='Customer Users', endpoint='customer_users'))
# For other collections, we'll add them as simple list views
admin.add_view(SuperAdminView(name='Help Requests', endpoint='help_requests'))
admin.add_view(SuperAdminView(name='Device Changes', endpoint='device_changes'))
admin.add_view(SuperAdminView(name='Discontinued Clients', endpoint='discontinued_clients'))
admin.add_view(SuperAdminView(name='Remarks', endpoint='remarks'))
admin.add_view(SuperAdminView(name='Profiles', endpoint='profiles'))
admin.add_view(SuperAdminView(name='Devices', endpoint='devices'))
admin.add_view(SuperAdminView(name='Routes', endpoint='routes'))
admin.add_view(SuperAdminView(name='EO Lists', endpoint='eo_lists'))
admin.add_view(SuperAdminView(name='Activity Logs', endpoint='activity_logs'))

# Add a custom view for super admin dashboard
class SuperAdminDashboard(SuperAdminView):
    @expose('/')
    def index(self):
        current_app.logger.warning("SuperAdminDashboard.index() called - this should not happen without authentication!")
        
        # Get counts for different collections
        admin_count = login_collection.count_documents({})
        customer_count = login_cust_collection.count_documents({})
        help_request_count = collection.count_documents({})
        change_count = change_collection.count_documents({})
        refund_count = refund_collection.count_documents({})
        remark_count = remark_collection.count_documents({})
        
        # Get recent activity (last 5 logs)
        recent_logs = list(logs_collection.find().sort('timestamp', -1).limit(5))
        
        # Get top customers by help request count
        from collections import Counter
        help_requests = list(collection.find({}, {'customer_email': 1}))
        customer_request_counts = Counter(req['customer_email'] for req in help_requests if 'customer_email' in req)
        top_customers = customer_request_counts.most_common(5)
        
        return self.render(
            'admin/master.html',
            admin_count=admin_count,
            customer_count=customer_count,
            help_request_count=help_request_count,
            change_count=change_count,
            refund_count=refund_count,
            remark_count=remark_count,
            recent_logs=recent_logs,
            top_customers=top_customers
        )

# Add the custom dashboard view
admin.add_view(SuperAdminDashboard(name='Dashboard', endpoint='super_admin_dashboard'))

# Add logout link
admin.add_link(MenuLink(name='Logout', url='/logout'))

# Route to initialize Flask-Admin with the app
def init_admin(app):
    """Initialize Flask-Admin with the Flask app"""
    admin.init_app(app)

# Test route to debug Flask-Security integration
@admin_bp.route('/test-auth')
def test_auth():
    """Test route to check Flask-Security current_user"""
    from flask_security import current_user
    from flask import session
    
    info = {
        'is_authenticated': current_user.is_authenticated if hasattr(current_user, 'is_authenticated') else False,
        'has_admin_role': current_user.has_role('admin') if hasattr(current_user, 'has_role') else False,
        'session_super_admin': session.get('is_super_admin', False),
        'current_user_email': getattr(current_user, 'email', 'No email') if hasattr(current_user, 'email') else 'No email attribute',
        'current_user_type': str(type(current_user))
    }
    
    return jsonify(info)

# Export the necessary components
__all__ = ['admin_bp', 'admin', 'init_admin']
