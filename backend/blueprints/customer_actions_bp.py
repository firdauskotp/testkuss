# backend/blueprints/customer_actions_bp.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.utils import secure_filename # For file uploads
from datetime import datetime

# Assuming database collections, mail functions, fs are accessible
from ..col import collection # 'collection' for customer cases
from ..utils import send_email_to_customer, send_email_to_admin # Email utilities
# For fs and mail, it's better if they are registered with the app and accessed via current_app
# For now, we will try to import them directly, assuming they are initialized in __init__.py of backend or similar
# If this fails, current_app.extensions['gridfs_instance'] or similar would be better.
from backend.extentions import fs # GridFS instance from main app (__init__.py or app.py)
from backend.extentions import mail as main_mail_instance # Mail instance from main app (__init__.py or app.py)

customer_actions_bp = Blueprint(
    'customer',
    __name__,
    template_folder='../templates', # Points to backend/templates
    static_folder='../static',     # Points to backend/static
    url_prefix='/customer'
)

# Helper to check customer session
def is_customer_logged_in():
    return 'customer_email' in session

@customer_actions_bp.before_request
def require_customer_login():
    # Protect all routes in this blueprint that are not explicitly public
    # For example, case_success might be reachable without login if someone has the URL
    # but customer_form should definitely be protected.
    if request.endpoint and request.endpoint.endswith('customer_form'): # Protect only specific routes if needed
        if not is_customer_logged_in():
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('auth.client_login')) # Redirect to client_login in auth blueprint

@customer_actions_bp.route("/help", methods=["GET", "POST"]) # Was /customer-help
def customer_form():
    # This check is now more specific due to before_request potentially being too broad
    if not is_customer_logged_in():
        flash("Please log in to submit a help request.", "warning")
        return redirect(url_for('auth.client_login'))

    if request.method == "POST":
        # Ensure config is loaded if not already
        if not current_app.config.get('MAIL_SENDER_ADDRESS'):
             # This indicates an issue with app context or config loading, but try to proceed
             print("Warning: MAIL_SENDER_ADDRESS not found in current_app.config during POST")


        case_no_count = collection.count_documents({}) # Renamed to avoid conflict
        case_no = case_no_count + 1

        user_email = session["customer_email"]
        premise_name = request.form.get("premise_name")
        location = request.form.get("location")
        model = request.form.get("model")
        issues = request.form.getlist("issues")
        remarks = request.form.get("remarks", "")
        image = request.files.get('image')
        image_id = None

        if image and image.filename: # Check if filename is not empty
            filename = secure_filename(image.filename)
            image_data = image.read()
            image_id = fs.put(image_data, filename=filename)
        elif image and not image.filename: # Handle case where file input is present but no file selected
            pass # image_id remains None

        collection.insert_one({
            "case_no": case_no, "premise_name": premise_name, "location": location,
            "image_id": image_id, "model": model, "issues": issues,
            "remarks": remarks, "email": user_email, "created_at": datetime.now(),
        })

        mail_sender_address = current_app.config.get('MAIL_SENDER_ADDRESS')
        if not mail_sender_address:
            flash("Email configuration error. Case submitted but notifications might fail.", "warning")
            # Potentially log this error for admin

        try:
            send_email_to_customer(case_no, user_email, mail_sender_address, main_mail_instance)
            send_email_to_admin(case_no, user_email, mail_sender_address, main_mail_instance)
        except Exception as e:
            flash(f"Case submitted, but email notifications failed: {e}", "warning")
            # Log the exception e

        return redirect(url_for(".case_success", case_no=case_no))

    return render_template("customer-complaint-form.html")

@customer_actions_bp.route("/case-success/<int:case_no>", methods=["GET", "POST"])
def case_success(case_no):
    # This page might not need login, as it's a confirmation.
    # If it does, the @customer_actions_bp.before_request would handle it if not specific.
    return render_template("case-success.html", case_no=case_no)
