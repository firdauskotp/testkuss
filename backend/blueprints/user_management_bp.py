# backend/blueprints/user_management_bp.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from bson import ObjectId # For delete operations
import os
from werkzeug.security import generate_password_hash
from flask_mail import Message
from .. import mail

from ..col import login_collection, login_cust_collection, logs_collection # Relative imports
from ..utils import log_activity, generate_random_password # Relative import

user_management_bp = Blueprint(
    'user_mgnt',
    __name__,
    template_folder='../templates', # Points to backend/templates
    static_folder='../static', # Points to backend/static
    url_prefix='/admin/users' # Prefix for all routes in this blueprint
)

# Helper to check admin session
def is_admin_logged_in():
    return 'username' in session

@user_management_bp.before_request
def require_admin_login():
    # Protect all routes in this blueprint
    if not is_admin_logged_in():
        flash("You must be logged in as an admin to access this page.", "warning")
        return redirect(url_for('auth.admin_login')) # Redirect to auth blueprint's admin_login

@user_management_bp.route('/view-clients')
def view_users(): # Was original view_users, now for client users
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    # In the template, the filter for 'username' was actually for client's email.
    # The filter for 'email' was also for client's email. We can combine these or clarify.
    # For now, let's assume 'email_filter' is the primary one used in the template search box.
    email_filter = request.args.get('email') # From original template's filter name for email
    username_as_email_filter = request.args.get('username') # From original template's filter name for username (used as email)

    query = {}
    if email_filter:
        query["email"] = {"$regex": email_filter, "$options": "i"}
    elif username_as_email_filter: # If email_filter is not provided, check username_as_email_filter
         query["email"] = {"$regex": username_as_email_filter, "$options": "i"}

    total_list = login_cust_collection.count_documents(query)
    users_list = list(
        login_cust_collection.find(query, {'email': 1, '_id': 1}) # Only fetch email and _id
        .skip((page - 1) * limit)
        .limit(limit)
    )
    for u_item in users_list: # Renamed loop variable
        u_item['_id'] = str(u_item['_id'])

    total_pages = (total_list + limit - 1) // limit
    # base_url = request.path # This would be /admin/users/view-clients
    pagination_base_url = url_for('.view_users') # Generates /admin/users/view-clients

    # query_params should only contain relevant filters for this page
    active_query_params = {}
    if email_filter: active_query_params['email'] = email_filter
    if username_as_email_filter: active_query_params['username'] = username_as_email_filter
    # Limit is part of pagination_vars in template, not needed in query_params for url_for again

    return render_template('view-users.html', users=users_list,
                           page=page, total_pages=total_pages, limit=limit,
                           pagination_base_url=pagination_base_url,
                           query_params=active_query_params) # Pass only active filters

@user_management_bp.route('/delete-client', methods=['POST'])
def delete_user(): # Was original delete_user, now for client users
    user_id = request.form['user_id']
    user_obj = login_cust_collection.find_one({'_id': ObjectId(user_id)}) # Renamed variable
    email = user_obj.get('email', 'Unknown') if user_obj else 'Unknown'

    if user_obj:
        login_cust_collection.delete_one({'_id': ObjectId(user_id)})
        flash("Client user deleted successfully!", "success")
        log_activity(session["username"], f"deleted client user with email: {email}", logs_collection)
    else:
        flash("User not found.", "danger")
    return redirect(url_for('.view_users'))

@user_management_bp.route('/view-admins')
def view_admins():
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    username_filter = request.args.get('username')
    query = {}
    if username_filter:
        query["username"] = {"$regex": username_filter, "$options": "i"}

    total_list = login_collection.count_documents(query)
    admins_list = list(
        login_collection.find(query, {'username': 1, '_id': 1}) # Only fetch username and _id
        .skip((page - 1) * limit)
        .limit(limit)
    )
    for admin_item in admins_list: # Renamed loop variable
        admin_item['_id'] = str(admin_item['_id'])

    total_pages = (total_list + limit - 1) // limit
    pagination_base_url = url_for('.view_admins')

    active_query_params = {}
    if username_filter: active_query_params['username'] = username_filter

    return render_template('view-admins.html', admins=admins_list,
                           page=page, total_pages=total_pages, limit=limit,
                           pagination_base_url=pagination_base_url, query_params=active_query_params)

@user_management_bp.route('/delete-admin', methods=['POST'])
def delete_admin():
    user_id_to_delete = request.form['user_id'] # Renamed variable

    # Prevent admin from deleting themselves
    if 'user_id' in session and session['user_id'] == user_id_to_delete:
        flash("You cannot delete your own admin account.", "danger")
        return redirect(url_for('.view_admins'))

    user_to_delete = login_collection.find_one({'_id': ObjectId(user_id_to_delete)})
    if user_to_delete:
        username_deleted = user_to_delete.get('username', 'Unknown')
        login_collection.delete_one({'_id': ObjectId(user_id_to_delete)})
        flash(f"Admin user '{username_deleted}' deleted successfully!", "success")
        log_activity(session["username"], f"deleted admin user: {username_deleted}", logs_collection)
    else:
        flash("Admin user not found.", "danger")
    return redirect(url_for('.view_admins'))

@user_management_bp.route('/view-technicians')
def view_technicians():
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    username_filter = request.args.get('username')
    query = {"role": "technician"}
    if username_filter:
        query["username"] = {"$regex": username_filter, "$options": "i"}

    total_list = login_collection.count_documents(query)
    technicians_list = list(
        login_collection.find(query, {'username': 1, '_id': 1})
        .skip((page - 1) * limit)
        .limit(limit)
    )
    for tech_item in technicians_list:
        tech_item['_id'] = str(tech_item['_id'])

    total_pages = (total_list + limit - 1) // limit
    pagination_base_url = url_for('.view_technicians')

    active_query_params = {}
    if username_filter: active_query_params['username'] = username_filter

    return render_template('view-technicians.html', technicians=technicians_list,
                           page=page, total_pages=total_pages, limit=limit,
                           pagination_base_url=pagination_base_url, query_params=active_query_params)

@user_management_bp.route('/add-technician', methods=['GET', 'POST'])
def add_technician():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('.add_technician'))

        if login_collection.find_one({'username': username}):
            flash("Username already exists.", "danger")
            return redirect(url_for('.add_technician'))

        hashed_password = generate_password_hash(password)
        login_collection.insert_one({
            'username': username,
            'password': hashed_password,
            'role': 'technician'
        })
        flash("Technician account created successfully!", "success")
        log_activity(session["username"], f"created technician account: {username}", logs_collection)
        return redirect(url_for('.view_technicians'))

    return render_template('add-technician.html')

@user_management_bp.route('/delete-technician', methods=['POST'])
def delete_technician():
    user_id_to_delete = request.form['user_id']

    user_to_delete = login_collection.find_one({'_id': ObjectId(user_id_to_delete), 'role': 'technician'})
    if user_to_delete:
        username_deleted = user_to_delete.get('username', 'Unknown')
        login_collection.delete_one({'_id': ObjectId(user_id_to_delete)})
        flash(f"Technician user '{username_deleted}' deleted successfully!", "success")
        log_activity(session["username"], f"deleted technician user: {username_deleted}", logs_collection)
    else:
        flash("Technician user not found.", "danger")
    return redirect(url_for('.view_technicians'))

@user_management_bp.route('/change-password', methods=['POST'])
def change_password():
    user_id = request.form.get('user_id')
    user_type = request.form.get('user_type')  # 'admin', 'user', or 'technician'

    if not user_id or not user_type:
        flash("Invalid request. User ID and type are required.", "danger")
        return redirect(request.referrer or url_for('.view_users'))

    if user_type in ['admin', 'technician']:
        collection = login_collection
    else:
        collection = login_cust_collection

    user = collection.find_one({'_id': ObjectId(user_id)})

    if not user:
        flash("User not found.", "danger")
        if user_type == 'admin':
            return redirect(request.referrer or url_for('.view_admins'))
        elif user_type == 'technician':
            return redirect(request.referrer or url_for('.view_technicians'))
        else:
            return redirect(request.referrer or url_for('.view_users'))

    new_password = generate_random_password()
    hashed_password = generate_password_hash(new_password)

    collection.update_one({'_id': ObjectId(user_id)}, {'$set': {'password': hashed_password}})

    user_email = user.get('email')
    if not user_email and user_type != 'admin' and user_type != 'technician':
        flash("User does not have an email address.", "danger")
        return redirect(url_for('.view_users'))

    # Send email to the user if they have an email
    if user_email:
        try:
            msg_user = Message("Your Password Has Been Changed",
                               sender=os.getenv('MAIL_SENDER_ADDRESS'),
                               recipients=[user_email])
            msg_user.body = f"Your password has been changed by an administrator. Your new password is: {new_password}"
            mail.send(msg_user)
            flash(f"Password for {user_email} has been changed and an email has been sent.", "success")
        except Exception as e:
            flash(f"Password was changed, but failed to send email to the user. Error: {e}", "warning")
    else:
        # For admins/technicians without email, just confirm the change without sending email
        flash(f"Password for {user.get('username')} has been changed.", "success")


    # Send notification to the logged-in admin
    admin_email = os.getenv('ADMIN_EMAIL_ADDRESS')
    if admin_email and admin_email != user_email:
        try:
            target_identifier = user_email if user_type == 'user' else user.get('username', 'N/A')
            msg_admin = Message("Password Change Notification",
                                sender=os.getenv('MAIL_SENDER_ADDRESS'),
                                recipients=[admin_email])
            msg_admin.body = f"The password for {user_type} '{target_identifier}' was changed by admin '{session['username']}'."
            mail.send(msg_admin)
        except Exception as e:
            flash(f"Failed to send notification email to admin. Error: {e}", "warning")

    log_activity(session["username"], f"changed password for {user_type} with ID: {user_id}", logs_collection)

    if user_type == 'admin':
        return redirect(request.referrer or url_for('.view_admins'))
    elif user_type == 'technician':
        return redirect(request.referrer or url_for('.view_technicians'))
    else:
        return redirect(request.referrer or url_for('.view_users'))
