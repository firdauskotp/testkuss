# backend/blueprints/customer_actions_bp.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.utils import secure_filename # For file uploads
from datetime import datetime

# Assuming database collections, mail functions, fs are accessible
from ..col import collection # 'collection' for customer cases
from ..utils import send_email_to_customer, send_email_to_admin, handle_route_error, require_auth, sanitize_input # Email utilities and error handling
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

@customer_actions_bp.route("/help", methods=["GET", "POST"])
@handle_route_error
def customer_form():
    """Enhanced customer complaint form with comprehensive validation and error handling"""
    current_app.logger.info(f"Customer form accessed by: {session.get('customer_email', 'unknown')}")
    
    if not is_customer_logged_in(): 
        current_app.logger.warning("Unauthorized access attempt to customer form")
        flash("Please log in to submit a help request.", "warning")
        return redirect(url_for('auth.client_login'))

    if request.method == "GET":
        return render_template("customer-complaint-form.html")

    customer_email = session.get('customer_email', 'unknown')
    current_app.logger.info(f"Customer complaint submission by: {customer_email}")

    try:
        case_no_count = collection.count_documents({}) 
        case_no = case_no_count + 1 
        user_email = customer_email
        premise_name = sanitize_input(request.form.get("premise_name", ""), 200)
        
        if not premise_name:
            current_app.logger.warning(f"Customer form submission missing premise name by: {customer_email}")
            flash("Premise name is required.", "danger")
            return render_template("customer-complaint-form.html")
        
        devices_data = []
        device_index = 0
        while True:
            # Check for a required field for each device to see if it exists (e.g., model)
            model_field_name = f"devices[{device_index}][model]"
            if model_field_name not in request.form or not request.form.get(model_field_name): # Also check if model is empty
                break # No more devices or current device model is empty

            location = sanitize_input(request.form.get(f"devices[{device_index}][location]", ""), 100)
            model = sanitize_input(request.form.get(model_field_name, ""), 100) # Already checked it exists
            issues = request.form.getlist(f"devices[{device_index}][issues]")
            remarks = sanitize_input(request.form.get(f"devices[{device_index}][remarks]", ""), 500)
            
            # Validate device data
            if not model:
                current_app.logger.warning(f"Device {device_index} missing model by: {customer_email}")
                flash(f"Device {device_index + 1} model is required.", "danger")
                return render_template("customer-complaint-form.html", premise_name=premise_name)
            
            image_file_name = f"devices[{device_index}][image]"
            image_id = None
            if image_file_name in request.files:
                image_file = request.files[image_file_name]
                if image_file and image_file.filename: 
                    # Validate file type and size
                    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
                    filename = secure_filename(image_file.filename)
                    if '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions:
                        # Check file size (5MB limit)
                        image_file.seek(0, 2)  # Seek to end
                        file_size = image_file.tell()
                        image_file.seek(0)  # Reset to beginning
                        
                        if file_size > 5 * 1024 * 1024:  # 5MB
                            current_app.logger.warning(f"File too large for device {device_index} by: {customer_email}")
                            flash(f"Image for device {device_index + 1} is too large. Maximum size is 5MB.", "danger")
                            return render_template("customer-complaint-form.html", premise_name=premise_name)
                        
                        image_data = image_file.read()
                        # Ensure content_type is passed if available and appropriate for fs.put
                        image_id = fs.put(image_data, filename=filename, content_type=image_file.content_type)
                        current_app.logger.info(f"Image uploaded for device {device_index} by: {customer_email}")
                    else:
                        current_app.logger.warning(f"Invalid file type for device {device_index} by: {customer_email}")
                        flash(f"Invalid file type for device {device_index + 1}. Please use PNG, JPG, JPEG, or GIF.", "danger")
                        return render_template("customer-complaint-form.html", premise_name=premise_name)
            
            devices_data.append({
                "location": location,
                "model": model,
                "issues": issues,
                "remarks": remarks,
                "image_id": image_id # This will be None if no image was uploaded
            })
            device_index += 1

        if not devices_data and device_index == 0 : # Check if no devices were processed at all
            current_app.logger.warning(f"No devices added to complaint by: {customer_email}")
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
        current_app.logger.info(f"Case #{case_no} created by: {customer_email}")
        
        mail_sender_address = current_app.config.get('MAIL_SENDER_ADDRESS')
        if not mail_sender_address: # Fallback or error if not configured
            current_app.logger.error("Email configuration missing - MAIL_SENDER_ADDRESS not set")
            flash("Email configuration error. Case submitted but notifications might fail.", "warning")
            # Log this for admin attention
        
        try:
            send_email_to_customer(case_no, user_email, mail_sender_address, main_mail_instance)
            send_email_to_admin(case_no, user_email, mail_sender_address, main_mail_instance)
            current_app.logger.info(f"Email notifications sent for case #{case_no}")
        except Exception as e:
            current_app.logger.error(f"Email notification failed for case #{case_no}: {str(e)}")
            flash(f"Case submitted, but email notifications failed: {e}", "warning")
            # Log the exception e
            
        return redirect(url_for(".case_success", case_no=case_no))
    
    except Exception as e:
        current_app.logger.error(f"Customer form submission error by {customer_email}: {str(e)}")
        flash("An error occurred while submitting your request. Please try again.", "danger")
        return render_template("customer-complaint-form.html")

@customer_actions_bp.route("/case-success/<int:case_no>", methods=["GET", "POST"])
@handle_route_error
def case_success(case_no):
    """Enhanced case success page with validation and logging"""
    customer_email = session.get('customer_email', 'unknown')
    current_app.logger.info(f"Case success page accessed for case #{case_no} by: {customer_email}")
    
    if not is_customer_logged_in():
        current_app.logger.warning(f"Unauthorized access to case success page for case #{case_no}")
        flash("Please log in to view your case.", "warning")
        return redirect(url_for('auth.client_login'))
    
    # Validate case number
    if case_no <= 0:
        current_app.logger.warning(f"Invalid case number accessed: {case_no} by: {customer_email}")
        flash("Invalid case number.", "danger")
        return redirect(url_for('.customer_form'))
    
    # Verify the case belongs to the logged-in customer
    try:
        case = collection.find_one({"case_no": case_no, "user_email": customer_email})
        if not case:
            current_app.logger.warning(f"Unauthorized case access attempt: case #{case_no} by: {customer_email}")
            flash("Case not found or access denied.", "danger")
            return redirect(url_for('.customer_form'))
        
        current_app.logger.info(f"Valid case success page view: case #{case_no} by: {customer_email}")
        return render_template("case-success.html", case_no=case_no)
    
    except Exception as e:
        current_app.logger.error(f"Error verifying case #{case_no} access by {customer_email}: {str(e)}")
        flash("An error occurred while loading your case information.", "danger")
        return redirect(url_for('.customer_form'))
