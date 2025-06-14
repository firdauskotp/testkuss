# backend/blueprints/customer_actions_bp.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.utils import secure_filename # For file uploads
from datetime import datetime

# Assuming database collections, mail functions, fs are accessible
from ..col import collection # 'collection' for customer cases
from ..utils import send_email_to_customer, send_email_to_admin # Email utilities
# Changed to import directly from .app to avoid circular import with backend/__init__.py
from backend import fs # GridFS instance from main app (__init__.py or app.py)
from backend import mail as main_mail_instance # Mail instance from main app (__init__.py or app.py)

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
    if request.endpoint and request.endpoint.endswith('customer_form'): 
        if not is_customer_logged_in():
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('auth.client_login'))
            return redirect(url_for('auth.client_login'))

@customer_actions_bp.route("/help", methods=["GET", "POST"])
@customer_actions_bp.route("/help", methods=["GET", "POST"])
def customer_form():
    if not is_customer_logged_in(): 
        flash("Please log in to submit a help request.", "warning")
        return redirect(url_for('auth.client_login'))

    if request.method == "POST":
        case_no_count = collection.count_documents({}) 
        case_no = case_no_count + 1 
        user_email = session["customer_email"]
        premise_name = request.form.get("premise_name")
        
        devices_data = []
        device_index = 0
        while True:
            # Check for a required field for each device to see if it exists (e.g., model)
            model_field_name = f"devices[{device_index}][model]"
            if model_field_name not in request.form or not request.form.get(model_field_name): # Also check if model is empty
                break # No more devices or current device model is empty

            location = request.form.get(f"devices[{device_index}][location]", "")
            model = request.form.get(model_field_name, "") # Already checked it exists
            issues = request.form.getlist(f"devices[{device_index}][issues]")
            remarks = request.form.get(f"devices[{device_index}][remarks]", "")
            
            image_file_name = f"devices[{device_index}][image]"
            image_id = None
            if image_file_name in request.files:
                image_file = request.files[image_file_name]
                if image_file and image_file.filename: 
                    filename = secure_filename(image_file.filename)
                    image_data = image_file.read()
                    # Ensure content_type is passed if available and appropriate for fs.put
                    image_id = fs.put(image_data, filename=filename, content_type=image_file.content_type) 
            
            devices_data.append({
                "location": location,
                "model": model,
                "issues": issues,
                "remarks": remarks,
                "image_id": image_id # This will be None if no image was uploaded
            })
            device_index += 1

        if not devices_data and device_index == 0 : # Check if no devices were processed at all
            flash("Please add details for at least one device.", "danger")
            # Rerender form, potentially passing back premise_name if desired
            return render_template("customer-complaint-form.html", premise_name=premise_name) 

        case_document = {
            "case_no": case_no,
            "user_email": user_email, 
            "premise_name": premise_name,
            "devices": devices_data, # List of device dictionaries
            "created_at": datetime.now(),
        }
        collection.insert_one(case_document)
        
        mail_sender_address = current_app.config.get('MAIL_SENDER_ADDRESS')
        if not mail_sender_address: # Fallback or error if not configured
        if not mail_sender_address: # Fallback or error if not configured
            flash("Email configuration error. Case submitted but notifications might fail.", "warning")
            # Log this for admin attention
        
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
    return render_template("case-success.html", case_no=case_no)
