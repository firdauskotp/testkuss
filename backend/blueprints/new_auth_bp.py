# backend/blueprints/new_auth_bp.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from flask_security import login_user, logout_user, current_user
from ..models import User, Role
from ..col import login_collection, login_cust_collection, logs_collection
from ..utils import log_activity, handle_route_error, sanitize_input, is_valid_email
from werkzeug.security import generate_password_hash, check_password_hash
import os
import re
from datetime import datetime

new_auth_bp = Blueprint('new_auth', __name__, template_folder='../templates', static_folder='../static')

@new_auth_bp.route("/", methods=["GET", "POST"])
@handle_route_error
def index():
    """Main index page - unified login form"""
    from .. import limiter
    from .. import security  # Import security instance to access datastore
    
    if request.method == "GET":
        current_app.logger.info("Index page accessed")
        if current_user.is_authenticated:
            if current_user.has_role('admin'):
                return redirect(url_for('dashboard'))
            elif current_user.has_role('customer'):
                return redirect(url_for('customer.customer_form'))
            else:
                return redirect(url_for('dashboard'))
        return render_template("index.html")
    
    # Handle POST request (login attempt)
    # Apply rate limiting to POST requests
    @limiter.limit("5 per minute")
    def _login_post():
        current_app.logger.info("Login attempt started via index route")
        
        # Input validation
        login_input = sanitize_input(request.form.get("login_input", "").strip().lower(), 254)
        password = request.form.get("password", "")
        
        # Validate inputs
        if not login_input or not password:
            current_app.logger.warning(f"Login failed: Missing credentials - IP: {request.environ.get('REMOTE_ADDR')}")
            flash("Login credentials and password are required.", "danger")
            return render_template("index.html")
        
        try:
            # Use Flask-Security's datastore to find and authenticate user
            user = security.datastore.get_user(login_input)
            
            if user and security.datastore.verify_password(user, password):
                # Login user with Flask-Security
                login_user(user, remember=True)
                
                # Store super admin status in session for admin users
                if user.has_role('admin'):
                    # Check if user is super admin in database
                    user_doc = login_collection.find_one({"email": user.email})
                    if user_doc and user_doc.get('is_super_admin', False):
                        session['is_super_admin'] = True
                
                flash("Login successful!", "success")
                
                # Determine user type for logging
                user_type = "admin" if user.has_role('admin') else "customer"
                log_activity(login_input, f"{user_type}_login_success", logs_collection)
                current_app.logger.info(f"{user_type.capitalize()} login successful: {login_input}")
                
                # Redirect based on role
                if user.has_role('admin'):
                    return redirect(url_for('dashboard'))
                elif user.has_role('customer'):
                    return redirect(url_for('customer.customer_form'))
                else:
                    return redirect(url_for('dashboard'))
            else:
                # Failed login - log attempt
                log_activity(login_input, "login_failed", logs_collection)
                current_app.logger.warning(f"Login failed: Invalid credentials for {login_input}")
                if is_valid_email(login_input):
                    flash("Invalid email or password.", "danger")
                else:
                    flash("Invalid username or password.", "danger")
                return render_template("index.html")
                
        except Exception as e:
            current_app.logger.error(f"Login error: {str(e)} - Login input: {login_input}")
            flash("Login system temporarily unavailable.", "danger")
            return render_template("index.html")
    
    return _login_post()

# Redirect old routes to new unified routes
@new_auth_bp.route("/register-admin")
def register_admin_redirect():
    """Redirect old register-admin route to new unified register"""
    return redirect(url_for('new_auth.register'))

# @new_auth_bp.route("/login")
# def login_redirect():
#     """Redirect old login route to new unified login"""
#     return redirect(url_for('new_auth.index'))

# @new_auth_bp.route("/client-login")
# def client_login_redirect():
#     """Redirect old client-login route to new unified login"""
#     return redirect(url_for('new_auth.index'))

@new_auth_bp.route("/logout")
@handle_route_error
def logout():
    """Logout user"""
    user_email = None
    user_type = "unknown"
    
    if current_user.is_authenticated:
        user_email = current_user.email
        if current_user.has_role('admin'):
            user_type = "admin"
        elif current_user.has_role('customer'):
            user_type = "customer"
    
    current_app.logger.info(f"Logout initiated for {user_type}: {user_email}")
    
    # Logout with Flask-Security
    logout_user()
    
    # Clear super admin session variable if it exists
    if 'is_super_admin' in session:
        session.pop('is_super_admin', None)
    
    if user_email:
        flash("You have been logged out successfully.", "success")
        log_activity(user_email, f"{user_type}_logout", logs_collection)
        current_app.logger.info(f"Logout completed for {user_type}: {user_email}")
    else:
        flash("No active session to log out from.", "info")
        current_app.logger.warning("Logout attempted with no active session")
    
    return redirect(url_for(".index"))

@new_auth_bp.route('/register', methods=['GET', 'POST'])
@handle_route_error
def register():
    """Unified registration for customers and admins"""
    # Only allow registration if not logged in
    if current_user.is_authenticated:
        if current_user.has_role('admin'):
            return redirect(url_for('dashboard'))
        elif current_user.has_role('customer'):
            return redirect(url_for('customer.customer_form'))
    
    if request.method == 'GET':
        return render_template('register.html')
    
    # Determine registration type from form
    registration_type = request.form.get('registration_type', 'customer')
    
    # Input validation
    email = sanitize_input(request.form.get('email', '').strip().lower(), 254)
    username = sanitize_input(request.form.get('username', '').strip().lower(), 100) if registration_type == 'admin' else None
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    # Comprehensive validation
    if not email or not is_valid_email(email):
        current_app.logger.warning(f"Registration failed: Invalid email")
        flash("Please enter a valid email address.", "danger")
        return redirect(url_for('.register'))

    if not password or len(password) < 8:
        current_app.logger.warning(f"Registration failed: Weak password")
        flash("Password must be at least 8 characters long.", "danger")
        return redirect(url_for('.register'))
    
    if len(password) > 100:
        current_app.logger.warning(f"Registration failed: Password too long")
        flash("Password too long.", "danger")
        return redirect(url_for('.register'))

    if password != confirm_password:
        current_app.logger.warning(f"Registration failed: Password mismatch")
        flash("Passwords do not match. Please try again.", "danger")
        return redirect(url_for('.register'))

    try:
        # Check for existing user in both collections
        existing_admin = login_collection.find_one({'email': email})
        existing_customer = login_cust_collection.find_one({'email': email})
        
        if existing_admin or existing_customer:
            current_app.logger.warning(f"Registration failed: Duplicate email {email}")
            flash("This email is already registered. Please use a different email.", "danger")
            return redirect(url_for('.register'))

        # Register user based on type
        if registration_type == 'admin':
            if not username or len(username) < 3:
                current_app.logger.warning(f"Admin registration failed: Invalid username")
                flash("Username must be at least 3 characters long.", "danger")
                return redirect(url_for('.register'))
            
            # Check for existing username
            existing_username = login_collection.find_one({'username': username})
            if existing_username:
                current_app.logger.warning(f"Admin registration failed: Duplicate username {username}")
                flash("Username already exists. Please use a different username.", "danger")
                return redirect(url_for('.register'))
            
            # Check if this is the first admin user (super admin)
            admin_count = login_collection.count_documents({})
            is_super_admin = (admin_count == 0)  # First admin is super admin
            
            # Create admin user
            login_collection.insert_one({
                'username': username,
                'email': email,
                'password': generate_password_hash(password, method='pbkdf2:sha256', salt_length=16),
                'is_super_admin': is_super_admin
            })
            
            if is_super_admin:
                flash("Super Admin user registered successfully! Please log in.", "success")
                log_activity("system", f"added SUPER admin user: {username} ({email})", logs_collection)
                current_app.logger.info(f"SUPER Admin user registered: {username} ({email})")
            else:
                flash("Admin user registered successfully! Please log in.", "success")
                log_activity("system", f"added admin user: {username} ({email})", logs_collection)
                current_app.logger.info(f"Admin user registered: {username} ({email})")
        else:
            # Create customer user
            login_cust_collection.insert_one({
                'email': email,
                'password': generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
            })
            
            flash("Customer user registered successfully! Please log in.", "success")
            log_activity("system", f"added customer user: {email}", logs_collection)
            current_app.logger.info(f"Customer user registered: {email}")
        
        return redirect(url_for('.index'))
    
    except Exception as e:
        current_app.logger.error(f"Registration error: {str(e)}")
        flash("Registration failed. Please try again.", "danger")
        return redirect(url_for('.register'))
