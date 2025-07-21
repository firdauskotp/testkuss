# backend/blueprints/auth_bp.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
import os
import re
from datetime import datetime

# Assuming col.py and utils.py are in the parent directory (backend/)
from ..col import login_collection, login_cust_collection, logs_collection
from ..utils import log_activity, handle_route_error, require_auth, sanitize_input, is_valid_email

auth_bp = Blueprint('auth', __name__, template_folder='../templates', static_folder='../static')

def validate_input(value, max_length=100):
    """Basic input validation to prevent injection attacks"""
    if not value or len(value) > max_length:
        return False
    return True

@auth_bp.route("/")
@handle_route_error
def index():
    """Main index page - client login form"""
    current_app.logger.info("Index page accessed")
    return render_template("index.html")

@auth_bp.route("/admin-login", methods=["GET", "POST"])
@handle_route_error
def admin_login():
    """Admin login with enhanced error handling and logging"""
    from .. import limiter
    
    if request.method == "GET":
        current_app.logger.info("Admin login page accessed")
        return render_template("login.html")
    
    # Apply rate limiting to POST requests
    @limiter.limit("5 per minute")
    def _admin_login_post():
        current_app.logger.info("Admin login attempt started")
        
        # Input validation
        username = sanitize_input(request.form.get("username", "").strip(), 50)
        password = request.form.get("password", "")
        
        # Validate inputs
        if not username or not password:
            current_app.logger.warning(f"Admin login failed: Missing credentials - IP: {request.environ.get('REMOTE_ADDR')}")
            flash("Username and password are required.", "danger")
            return redirect(url_for(".admin_login"))
        
        if not validate_input(username, 50) or not validate_input(password, 100):
            current_app.logger.warning(f"Admin login failed: Invalid input format - IP: {request.environ.get('REMOTE_ADDR')}")
            flash("Invalid username or password format.", "danger")
            return redirect(url_for(".admin_login"))
        
        try:
            # Database query with error handling
            user = login_collection.find_one({"username": username})
            
            # Constant-time comparison to prevent timing attacks
            if user and check_password_hash(user["password"], password):
                # Successful login
                session.permanent = True
                session["user_id"] = str(user["_id"])
                session["username"] = user["username"]
                session["login_time"] = datetime.now().isoformat()
                session["user_type"] = "admin"
                
                flash("Login successful!", "success")
                log_activity(session["username"], "admin_login_success", logs_collection)
                current_app.logger.info(f"Admin login successful: {username}")
                return redirect(url_for("dashboard"))
            else:
                # Failed login - log attempt
                log_activity(username, "admin_login_failed", logs_collection)
                current_app.logger.warning(f"Admin login failed: Invalid credentials for {username}")
                flash("Invalid username or password.", "danger")
                return redirect(url_for(".admin_login"))
                
        except Exception as e:
            current_app.logger.error(f"Admin login error: {str(e)} - Username: {username}")
            flash("Login system temporarily unavailable.", "danger")
            return redirect(url_for(".admin_login"))
    
    return _admin_login_post()

@auth_bp.route("/client-login", methods=["GET", "POST"])
@handle_route_error
def client_login():
    """Client login with enhanced error handling and logging"""
    from .. import limiter
    
    if request.method == "GET":
        current_app.logger.info("Client login page accessed")
        return render_template("index.html")
    
    # Apply rate limiting to POST requests
    @limiter.limit("5 per minute")
    def _client_login_post():
        current_app.logger.info("Client login attempt started")
        
        # Input validation
        email = sanitize_input(request.form.get("email", "").strip().lower(), 254)
        password = request.form.get("password", "")
        
        # Email validation
        if not email or not is_valid_email(email):
            current_app.logger.warning(f"Client login failed: Invalid email format - IP: {request.environ.get('REMOTE_ADDR')}")
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for(".index"))
        
        if not validate_input(password, 100) or not password:
            current_app.logger.warning(f"Client login failed: Invalid password - Email: {email}")
            flash("Password is required.", "danger")
            return redirect(url_for(".index"))
        
        try:
            # Database query with error handling
            user = login_cust_collection.find_one({"email": email})
            
            if user and check_password_hash(user["password"], password):
                # Successful login
                session.permanent = True
                session["user_id"] = str(user["_id"])
                session["customer_email"] = user["email"]
                session["login_time"] = datetime.now().isoformat()
                session["user_type"] = "customer"
                
                flash("Login successful!", "success")
                log_activity(email, "customer_login_success", logs_collection)
                current_app.logger.info(f"Customer login successful: {email}")
                return redirect(url_for("customer.customer_form"))
            else:
                # Failed login - log attempt
                log_activity(email, "customer_login_failed", logs_collection)
                current_app.logger.warning(f"Customer login failed: Invalid credentials for {email}")
                flash("Invalid email or password.", "danger")
                return redirect(url_for(".index"))
                
        except Exception as e:
            current_app.logger.error(f"Customer login error: {str(e)} - Email: {email}")
            flash("Login system temporarily unavailable.", "danger")
            return redirect(url_for(".index"))
    
    return _client_login_post()


@auth_bp.route("/logout")
@handle_route_error
def logout():
    """Enhanced logout with comprehensive logging"""
    user_logged_out = None
    user_type = session.get("user_type", "unknown")
    
    current_app.logger.info(f"Logout initiated for user type: {user_type}")
    
    if "username" in session: # Admin user
        user_logged_out = session["username"]
        log_activity(user_logged_out, "admin_logout", logs_collection)
        current_app.logger.info(f"Admin logout: {user_logged_out}")
    elif "customer_email" in session: # Customer user
        user_logged_out = session["customer_email"]
        log_activity(user_logged_out, "customer_logout", logs_collection)
        current_app.logger.info(f"Customer logout: {user_logged_out}")

    # Clear session completely
    session.clear()
    
    if user_logged_out:
        flash("You have been logged out successfully.", "success")
        current_app.logger.info(f"Logout completed for: {user_logged_out}")
    else:
        flash("No active session to log out from.", "info")
        current_app.logger.warning("Logout attempted with no active session")
    
    return redirect(url_for(".index")) # Redirect to the main page (client login)

@auth_bp.route('/register', methods=['GET', 'POST'])
@require_auth('admin')
@handle_route_error
def register(): # Client user registration
    """Enhanced client user registration with comprehensive validation and logging"""
    current_app.logger.info(f"Client registration page accessed by admin: {session.get('username')}")
    
    if request.method == 'GET':
        return render_template('register.html')
    
    admin_username = session.get('username', 'unknown')
    current_app.logger.info(f"Client registration attempt by admin: {admin_username}")
    
    # Input validation
    email = sanitize_input(request.form.get('email', '').strip().lower(), 254)
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    # Comprehensive validation
    if not email or not is_valid_email(email):
        current_app.logger.warning(f"Client registration failed: Invalid email by {admin_username}")
        flash("Please enter a valid email address.", "danger")
        return redirect(url_for('.register'))

    if not password or len(password) < 8:
        current_app.logger.warning(f"Client registration failed: Weak password by {admin_username}")
        flash("Password must be at least 8 characters long.", "danger")
        return redirect(url_for('.register'))
    
    if len(password) > 100:
        current_app.logger.warning(f"Client registration failed: Password too long by {admin_username}")
        flash("Password too long.", "danger")
        return redirect(url_for('.register'))

    if password != confirm_password:
        current_app.logger.warning(f"Client registration failed: Password mismatch by {admin_username}")
        flash("Passwords do not match. Please try again.", "danger")
        return redirect(url_for('.register'))

    try:
        existing_user = login_cust_collection.find_one({'email': email})
        if existing_user:
            current_app.logger.warning(f"Client registration failed: Duplicate email {email} by {admin_username}")
            flash("This email is already registered. Please use a different email.", "danger")
            return redirect(url_for('.register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        login_cust_collection.insert_one({'email': email, 'password': hashed_password})

        flash("Client user registered successfully!", "success")
        log_activity(admin_username, f"added client user: {email}", logs_collection)
        current_app.logger.info(f"Client user registered by {admin_username}: {email}")
        return redirect(url_for('.register'))
    
    except Exception as e:
        current_app.logger.error(f"Client registration error by {admin_username}: {str(e)}")
        flash("Registration failed. Please try again.", "danger")
        return redirect(url_for('.register'))

@auth_bp.route('/register-admin', methods=['GET', 'POST'])
@require_auth('admin')
@handle_route_error
def register_admin(): # Admin registration
    """Enhanced admin registration with comprehensive validation and logging"""
    current_app.logger.info(f"Admin registration page accessed by admin: {session.get('username')}")
    
    if request.method == 'GET':
        return render_template('register-admin.html')
    
    admin_username = session.get('username', 'unknown')
    current_app.logger.info(f"Admin registration attempt by admin: {admin_username}")
    
    # Input validation
    username = sanitize_input(request.form.get('username', '').strip().lower(), 100)
    email = sanitize_input(request.form.get('email', '').strip().lower(), 254)
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    # Comprehensive validation
    if not username or len(username) < 3:
        current_app.logger.warning(f"Admin registration failed: Invalid username by {admin_username}")
        flash("Username must be at least 3 characters long.", "danger")
        return redirect(url_for('.register_admin'))

    if not email or not is_valid_email(email):
        current_app.logger.warning(f"Admin registration failed: Invalid email by {admin_username}")
        flash("Please enter a valid email address.", "danger")
        return redirect(url_for('.register_admin'))

    if not password or len(password) < 8:
        current_app.logger.warning(f"Admin registration failed: Weak password by {admin_username}")
        flash("Password must be at least 8 characters long.", "danger")
        return redirect(url_for('.register_admin'))
    
    if len(password) > 100:
        current_app.logger.warning(f"Admin registration failed: Password too long by {admin_username}")
        flash("Password too long.", "danger")
        return redirect(url_for('.register_admin'))

    if password != confirm_password:
        current_app.logger.warning(f"Admin registration failed: Password mismatch by {admin_username}")
        flash("Passwords do not match. Please try again.", "danger")
        return redirect(url_for('.register_admin'))

    try:
        # Check for existing username or email
        existing_user = login_collection.find_one({'$or': [{'username': username}, {'email': email}]})
        if existing_user:
            current_app.logger.warning(f"Admin registration failed: Duplicate credentials by {admin_username}")
            flash("Username or email already exists. Please use different credentials.", "danger")
            return redirect(url_for('.register_admin'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        login_collection.insert_one({
            'username': username,
            'email': email,
            'password': hashed_password
        })

        flash("Admin registered successfully!", "success")
        log_activity(admin_username, f"added admin user: {username} ({email})", logs_collection)
        current_app.logger.info(f"Admin user registered by {admin_username}: {username} ({email})")
        return redirect(url_for('.register_admin'))
    
    except Exception as e:
        current_app.logger.error(f"Admin registration error by {admin_username}: {str(e)}")
        flash("Registration failed. Please try again.", "danger")
        return redirect(url_for('.register_admin'))
