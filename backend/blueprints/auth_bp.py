# backend/blueprints/auth_bp.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os

# Assuming col.py and utils.py are in the parent directory (backend/)
from ..col import login_collection, login_cust_collection, logs_collection
from ..utils import log_activity

auth_bp = Blueprint('auth', __name__, template_folder='../templates', static_folder='../static')

@auth_bp.route("/")
def index():
    # This was rendering client_login form, which is now index.html
    return render_template("index.html")

@auth_bp.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = login_collection.find_one({"username": username})
        if user and check_password_hash(user["password"], password):
            session["user_id"] = str(user["_id"])
            session["username"] = user["username"]
            flash("Login successful!", "success")
            log_activity(session["username"], "login", logs_collection)
            # Assuming 'dashboard.dashboard_home' if dashboard is also a blueprint, or just 'dashboard' if it's an app route
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "danger")
            return redirect(url_for(".admin_login"))
    return render_template("login.html")

@auth_bp.route("/client-login", methods=["GET", "POST"])
def client_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = login_cust_collection.find_one({"email": email})
        if user and check_password_hash(user["password"], password):
            session["user_id"] = str(user["_id"])
            session["customer_email"] = user["email"]
            flash("Login successful!", "success")
            # log_activity for client login could be added here
            return redirect(url_for("customer.customer_form"))
        else:
            flash("Invalid email or password.", "danger")
            return redirect(url_for(".index"))
    # GET request to /client-login should also render the client login form (index.html)
    return render_template("index.html")


@auth_bp.route("/logout")
def logout():
    user_logged_out = None
    if "username" in session: # Admin user
        user_logged_out = session["username"]
        log_activity(user_logged_out, "logout", logs_collection)
    elif "customer_email" in session: # Customer user
        user_logged_out = session["customer_email"]
        # Add log_activity for customer logout if desired
        # log_activity(user_logged_out, "customer_logout", logs_collection)

    session.clear()
    if user_logged_out:
        flash("You have been logged out.", "success")
    else:
        flash("No active session to log out from.", "info")
    return redirect(url_for(".index")) # Redirect to the main page (client login)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register(): # Client user registration
    if 'username' not in session:
        flash("Admin access required to register new client users.", "warning")
        return redirect(url_for('.admin_login')) # Redirect to admin login within the same blueprint

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('.register'))

        existing_user = login_cust_collection.find_one({'email': email})
        if existing_user:
            flash("This email is already registered. Please use a different email.", "danger")
            return redirect(url_for('.register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        login_cust_collection.insert_one({'email': email, 'password': hashed_password})

        flash("Client user registered successfully!", "success")
        log_activity(session["username"], "added client user: " + str(email), logs_collection)
        return redirect(url_for('.register'))
    return render_template('register.html')

@auth_bp.route('/register-admin', methods=['GET', 'POST'])
def register_admin(): # Admin user registration
    if 'username' not in session:
        flash("Admin access required to register new admin users.", "warning")
        return redirect(url_for('.admin_login'))

    if request.method == 'POST':
        username_form = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('.register_admin'))

        existing_user = login_collection.find_one({'username': username_form})
        if existing_user:
            flash("This username is already registered. Please use a different username.", "danger")
            return redirect(url_for('.register_admin'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        login_collection.insert_one({'username': username_form, 'password': hashed_password})

        flash("Admin user registered successfully!", "success")
        log_activity(session["username"], "added admin user: " + str(username_form), logs_collection)
        return redirect(url_for('.register_admin'))
    return render_template('register-admin.html')
