# backend/blueprints/auth_bp.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
import os
import re
from datetime import datetime

# Assuming col.py and utils.py are in the parent directory (backend/)
from ..col import login_collection, login_cust_collection, logs_collection
from ..utils import log_activity

auth_bp = Blueprint('auth', __name__, template_folder='../templates', static_folder='../static')

def validate_input(value, max_length=100):
    """Basic input validation to prevent injection attacks"""
    if not value or len(value) > max_length:
        return False
    return True

def is_valid_email(email):
    """Validate email format"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, email) is not None

@auth_bp.route("/")
def index():
    # This was rendering client_login form, which is now index.html
    return render_template("index.html")

@auth_bp.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    # Import limiter here to avoid circular imports
    from .. import limiter
    
    # Apply rate limiting to this specific route
    @limiter.limit("5 per minute")
    def _admin_login_post():
        # Input validation
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        # Basic validation
        if not validate_input(username, 50) or not validate_input(password, 100):
            flash("Invalid username or password format.", "danger")
            return redirect(url_for(".admin_login"))
        
        if not username or not password:
            flash("Username and password are required.", "danger")
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
                current_app.logger.warning(f"Admin login failed: {username}")
                flash("Invalid username or password.", "danger")
                return redirect(url_for(".admin_login"))
                
        except Exception as e:
            current_app.logger.error(f"Admin login error: {str(e)}")
            flash("Login system temporarily unavailable.", "danger")
            return redirect(url_for(".admin_login"))
    
    if request.method == "POST":
        return _admin_login_post()
    
    return render_template("login.html")

@auth_bp.route("/client-login", methods=["GET", "POST"])
def client_login():
    # Import limiter here to avoid circular imports
    from .. import limiter
    
    # Apply rate limiting to this specific route
    @limiter.limit("5 per minute")
    def _client_login_post():
        # Input validation
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        
        # Email validation
        if not email or not is_valid_email(email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for(".index"))
        
        if not validate_input(password, 100) or not password:
            flash("Password is required.", "danger")
            return redirect(url_for(".index"))
        
        # Additional email length check
        if len(email) > 254:  # RFC 5321 limit
            flash("Email address too long.", "danger")
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
                current_app.logger.warning(f"Customer login failed: {email}")
                flash("Invalid email or password.", "danger")
                return redirect(url_for(".index"))
                
        except Exception as e:
            current_app.logger.error(f"Customer login error: {str(e)}")
            flash("Login system temporarily unavailable.", "danger")
            return redirect(url_for(".index"))
    
    if request.method == "POST":
        return _client_login_post()
    
    # GET request to /client-login should also render the client login form (index.html)
    return render_template("index.html")


@auth_bp.route("/logout")
def logout():
    user_logged_out = None
    user_type = session.get("user_type", "unknown")
    
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
    else:
        flash("No active session to log out from.", "info")
    
    return redirect(url_for(".index")) # Redirect to the main page (client login)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register(): # Client user registration
    if 'username' not in session:
        flash("Admin access required to register new client users.", "warning")
        return redirect(url_for('.admin_login')) # Redirect to admin login within the same blueprint

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Input validation
        if not email or not is_valid_email(email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for('.register'))
        
        if len(email) > 254:  # RFC 5321 limit
            flash("Email address too long.", "danger")
            return redirect(url_for('.register'))

        if not password or len(password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return redirect(url_for('.register'))
        
        if len(password) > 100:
            flash("Password too long.", "danger")
            return redirect(url_for('.register'))

        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('.register'))

        try:
            existing_user = login_cust_collection.find_one({'email': email})
            if existing_user:
                flash("This email is already registered. Please use a different email.", "danger")
                return redirect(url_for('.register'))

            hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
            login_cust_collection.insert_one({'email': email, 'password': hashed_password})

            flash("Client user registered successfully!", "success")
            log_activity(session["username"], f"added client user: {email}", logs_collection)
            current_app.logger.info(f"Client user registered by {session['username']}: {email}")
            return redirect(url_for('.register'))
        
        except Exception as e:
            current_app.logger.error(f"Client registration error: {str(e)}")
            flash("Registration failed. Please try again.", "danger")
            return redirect(url_for('.register'))
    
    return render_template('register.html')

@auth_bp.route('/register-admin', methods=['GET', 'POST'])
def register_admin(): # Admin user registration
    if 'username' not in session:
        flash("Admin access required to register new admin users.", "warning")
        return redirect(url_for('.admin_login'))

    if request.method == 'POST':
        username_form = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Input validation
        if not validate_input(username_form, 50) or not username_form:
            flash("Please enter a valid username (1-50 characters).", "danger")
            return redirect(url_for('.register_admin'))
        
        # Username format validation (alphanumeric and underscore only)
        if not re.match("^[a-zA-Z0-9_]+$", username_form):
            flash("Username can only contain letters, numbers, and underscores.", "danger")
            return redirect(url_for('.register_admin'))

        if not password or len(password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return redirect(url_for('.register_admin'))
        
        if len(password) > 100:
            flash("Password too long.", "danger")
            return redirect(url_for('.register_admin'))

        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('.register_admin'))

        try:
            existing_user = login_collection.find_one({'username': username_form})
            if existing_user:
                flash("This username is already registered. Please use a different username.", "danger")
                return redirect(url_for('.register_admin'))

            hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
            login_collection.insert_one({'username': username_form, 'password': hashed_password})

            flash("Admin user registered successfully!", "success")
            log_activity(session["username"], f"added admin user: {username_form}", logs_collection)
            current_app.logger.info(f"Admin user registered by {session['username']}: {username_form}")
            return redirect(url_for('.register_admin'))
        
        except Exception as e:
            current_app.logger.error(f"Admin registration error: {str(e)}")
            flash("Registration failed. Please try again.", "danger")
            return redirect(url_for('.register_admin'))
    
    return render_template('register-admin.html')
