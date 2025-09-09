import os
from datetime import datetime, timedelta
from flask_mail import Mail, Message
import calendar
from flask import flash, current_app, render_template_string, request, session, jsonify, redirect, url_for
import re
import functools
import traceback
from pymongo.errors import PyMongoError
from .col import collection
import json
import secrets
import string

# get current directory path 
current_dir = os.path.dirname(os.path.abspath(__file__))

def generate_random_password(length=12):
    """Generate a random password."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

def log_activity(name, action, database):
    """Log user activity with enhanced information"""
    try:
        log_entry = {
            "user": name,
            "action": action,
            "timestamp": datetime.now(),
            "ip_address": request.environ.get('REMOTE_ADDR', 'unknown'),
            "user_agent": request.environ.get('HTTP_USER_AGENT', 'unknown')[:200]  # Limit length
        }
        database.insert_one(log_entry)
    except Exception as e:
        current_app.logger.error(f"Failed to log activity: {e}")

def log_route_access(route_name, user_id=None, additional_info=None):
    """Log route access with detailed information"""
    try:
        log_data = {
            "route": route_name,
            "method": request.method,
            "url": request.url,
            "ip_address": request.environ.get('REMOTE_ADDR', 'unknown'),
            "user_agent": request.environ.get('HTTP_USER_AGENT', 'unknown')[:200],
            "timestamp": datetime.now(),
            "user_id": user_id or session.get('user_id', 'anonymous'),
            "session_id": session.get('session_id', 'no_session')
        }
        
        if additional_info:
            log_data.update(additional_info)
            
        current_app.logger.info(f"Route access: {log_data}")
    except Exception as e:
        current_app.logger.error(f"Failed to log route access: {e}")

def handle_route_error(func):
    """Decorator for comprehensive route error handling and logging"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        route_name = f"{func.__module__}.{func.__name__}"
        start_time = datetime.now()
        
        try:
            # Log route access
            user_id = session.get('user_id', 'anonymous')
            log_route_access(route_name, user_id)
            
            # Execute the route function
            result = func(*args, **kwargs)
            
            # Log successful completion
            duration = (datetime.now() - start_time).total_seconds()
            current_app.logger.info(f"Route {route_name} completed successfully in {duration:.3f}s")
            
            return result
            
        except PyMongoError as e:
            # Database-specific errors
            error_id = f"db_error_{int(datetime.now().timestamp())}"
            current_app.logger.error(f"Database error in {route_name} [{error_id}]: {str(e)}")
            current_app.logger.error(f"Database error traceback [{error_id}]: {traceback.format_exc()}")
            
            flash("Database service temporarily unavailable. Please try again later.", "danger")
            
            # Return appropriate response based on request type
            if request.is_json:
                return jsonify({
                    "error": "Database error",
                    "message": "Service temporarily unavailable",
                    "error_id": error_id
                }), 500
            else:
                return redirect(url_for('auth.index'))
                
        except ValueError as e:
            # Input validation errors
            error_id = f"validation_error_{int(datetime.now().timestamp())}"
            current_app.logger.warning(f"Validation error in {route_name} [{error_id}]: {str(e)}")
            
            flash("Invalid input provided. Please check your data and try again.", "warning")
            
            if request.is_json:
                return jsonify({
                    "error": "Validation error",
                    "message": str(e),
                    "error_id": error_id
                }), 400
            else:
                return redirect(request.referrer or url_for('auth.index'))
                
        except PermissionError as e:
            # Authorization errors
            error_id = f"auth_error_{int(datetime.now().timestamp())}"
            current_app.logger.warning(f"Authorization error in {route_name} [{error_id}]: {str(e)}")
            
            flash("You don't have permission to access this resource.", "danger")
            
            if request.is_json:
                return jsonify({
                    "error": "Authorization error",
                    "message": "Access denied",
                    "error_id": error_id
                }), 403
            else:
                return redirect(url_for('auth.admin_login'))
                
        except Exception as e:
            # Generic server errors
            error_id = f"server_error_{int(datetime.now().timestamp())}"
            current_app.logger.error(f"Unexpected error in {route_name} [{error_id}]: {str(e)}")
            current_app.logger.error(f"Unexpected error traceback [{error_id}]: {traceback.format_exc()}")
            
            flash("An unexpected error occurred. Please try again or contact support.", "danger")
            
            if request.is_json:
                return jsonify({
                    "error": "Server error",
                    "message": "An unexpected error occurred",
                    "error_id": error_id
                }), 500
            else:
                return redirect(url_for('auth.index'))
                
    return wrapper

def require_auth(user_type='admin'):
    """Decorator to require authentication for routes"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                if user_type == 'admin':
                    if 'username' not in session:
                        current_app.logger.warning(f"Unauthorized admin access attempt to {func.__name__}")
                        flash("Please log in to access this page.", "warning")
                        return redirect(url_for('auth.admin_login'))
                elif user_type == 'customer':
                    if 'customer_email' not in session:
                        current_app.logger.warning(f"Unauthorized customer access attempt to {func.__name__}")
                        flash("Please log in to access this page.", "warning")
                        return redirect(url_for('auth.index'))
                        
                # Validate session
                if not validate_session():
                    current_app.logger.warning(f"Invalid session for {user_type} accessing {func.__name__}")
                    flash("Your session has expired. Please log in again.", "warning")
                    if user_type == 'admin':
                        return redirect(url_for('auth.admin_login'))
                    else:
                        return redirect(url_for('auth.index'))
                        
                return func(*args, **kwargs)
            except Exception as e:
                current_app.logger.error(f"Auth decorator error in {func.__name__}: {e}")
                raise
                
        return wrapper
    return decorator

def validate_session():
    """Validate session integrity and expiration"""
    if 'login_time' in session:
        try:
            login_time = datetime.fromisoformat(session['login_time'])
            # Session expires after 2 hours
            if datetime.now() - login_time > timedelta(hours=2):
                session.clear()
                return False
        except (ValueError, TypeError):
            session.clear()
            return False
    return True

def format_devices_for_email(devices_data):
    """
    Format multiple devices data for email templates.
    
    Args:
        devices_data (list): List of device dictionaries
        
    Returns:
        tuple: (devices_summary, images_note) - Both as Markup objects for safe HTML rendering
    """
    from markupsafe import Markup
    
    if not devices_data:
        return Markup("No devices listed."), Markup("No images attached.")
    
    devices_summary = "<strong>Device Details:</strong><br>"
    has_images = False
    
    for i, device in enumerate(devices_data, 1):
        devices_summary += f"<br><strong>Device {i}:</strong><br>"
        devices_summary += f"<ul>"
        devices_summary += f"<li><strong>Location:</strong> {device.get('location', 'Not specified')}</li>"
        devices_summary += f"<li><strong>Model:</strong> {device.get('model', 'Not specified')}</li>"
        
        # Format issues
        issues = device.get('issues', [])
        if issues:
            issues_str = ', '.join(issues)
            devices_summary += f"<li><strong>Issues:</strong> {issues_str}</li>"
        else:
            devices_summary += f"<li><strong>Issues:</strong> None specified</li>"
        
        # Add remarks if present
        remarks = device.get('remarks', '').strip()
        if remarks:
            devices_summary += f"<li><strong>Remarks:</strong> {remarks}</li>"
        
        devices_summary += f"</ul>"
        
        # Check if device has image
        if device.get('image_id'):
            has_images = True
    
    # Generate images note
    if has_images:
        if len(devices_data) == 1:
            images_note = "Device image is attached to this email."
        else:
            images_note = "Device images are attached to this email where available."
    else:
        images_note = "No device images were provided."
    
    # Return as Markup objects so they render as HTML instead of escaped text
    return Markup(devices_summary), Markup(images_note)


def sanitize_input(input_string, max_length=100):
    """Basic input sanitization"""
    if not input_string:
        return ""
    
    # Remove potential XSS patterns
    input_string = str(input_string).strip()
    
    # Limit length
    if len(input_string) > max_length:
        return input_string[:max_length]
    
    return input_string

def is_valid_email(email):
    """Validate email format with comprehensive regex"""
    if not email or len(email) > 254:
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def safe_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return value
    
def send_email_to_customer(case_no, user_email, from_email, mail):
    """Send a confirmation email to the customer with HTML formatting."""
    subject = f"Case #{case_no} Created Successfully - KUSS Support"
    
    # Create a professional HTML email
    body_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #007bff; border-bottom: 2px solid #007bff; padding-bottom: 10px;">
                📧 Case Confirmation - KUSS Support
            </h2>
            
            <p>Dear Valued Customer,</p>
            
            <p>Thank you for submitting your support request. Your case has been successfully created and logged in our system.</p>
            
            <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin: 20px 0;">
                <h3 style="margin-top: 0; color: #007bff;">Case Details:</h3>
                <p><strong>Case Number:</strong> #{case_no}</p>
                <p><strong>Created:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Status:</strong> Under Review</p>
            </div>
            
            <p><strong>What's Next?</strong></p>
            <ul>
                <li>Our technical staff will review your case within 24 hours</li>
                <li>You will receive updates via email as progress is made</li>
                <li>Our team may contact you for additional information if needed</li>
            </ul>
            
            <p>Please keep your case number <strong>#{case_no}</strong> for future reference.</p>
            
            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            
            <p style="font-size: 12px; color: #666;">
                Best regards,<br>
                KUSS Technical Support Team<br>
                <em>This is an automated message. Please do not reply directly to this email.</em>
            </p>
        </div>
    </body>
    </html>
    """
    
    try:
        send_email(
            to_email=user_email,
            from_email=from_email,
            subject=subject,
            body_html=body_html,
            mail=mail
        )
        current_app.logger.info(f"Customer notification email sent successfully for case #{case_no}")
    except Exception as e:
        current_app.logger.error(f"Failed to send customer notification for case #{case_no}: {e}")
        raise


def send_email_to_admin(case_no, user_email, from_email, mail):
    """Notify admin about a new case creation with detailed HTML formatting."""
    admin_email = os.getenv('ADMIN_EMAIL_ADDRESS')
    
    if not admin_email:
        current_app.logger.warning("ADMIN_EMAIL_ADDRESS not configured - skipping admin notification")
        return
    
    subject = f"🚨 New Support Case #{case_no} - Action Required"
    
    # Create a detailed HTML email for admin
    body_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #dc3545; border-bottom: 2px solid #dc3545; padding-bottom: 10px;">
                🚨 New Support Case - Action Required
            </h2>
            
            <div style="background-color: #fff3cd; padding: 15px; border: 1px solid #ffeaa7; border-radius: 5px; margin: 20px 0;">
                <h3 style="margin-top: 0; color: #856404;">Case Summary:</h3>
                <p><strong>Case Number:</strong> #{case_no}</p>
                <p><strong>Customer Email:</strong> {user_email}</p>
                <p><strong>Created:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Status:</strong> Pending Review</p>
            </div>
            
            <div style="background-color: #d1ecf1; padding: 15px; border: 1px solid #bee5eb; border-radius: 5px; margin: 20px 0;">
                <h3 style="margin-top: 0; color: #0c5460;">Required Actions:</h3>
                <ul>
                    <li>Review the case details in the admin dashboard</li>
                    <li>Assign to appropriate technical staff</li>
                    <li>Contact customer if additional information is needed</li>
                    <li>Update case status as work progresses</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="http://localhost:5000/dashboard" 
                   style="background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    📋 View Case in Dashboard
                </a>
            </div>
            
            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            
            <p style="font-size: 12px; color: #666;">
                KUSS Admin Notification System<br>
                <em>This is an automated notification. Please log into the admin dashboard for full case details.</em>
            </p>
        </div>
    </body>
    </html>
    """
    
    try:
        send_email(
            to_email=admin_email,
            from_email=from_email,
            subject=subject,
            body_html=body_html,
            mail=mail
        )
        current_app.logger.info(f"Admin notification email sent successfully for case #{case_no}")
    except Exception as e:
        current_app.logger.error(f"Failed to send admin notification for case #{case_no}: {e}")
        raise


from fpdf import FPDF
import io
from datetime import datetime

def generate_case_pdf(case_id):
    """Generate PDF summary for completed help request case."""


    # Step 1: Get case data
    case = collection.find_one({"case_no": case_id})
    if not case:
        raise ValueError(f"No case found with ID {case_id}")

    # Step 2: Prepare PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Help Request Case Summary - #{case_id}", ln=1, align="C")
    pdf.ln(5)

    def add_field(label, value):
        pdf.set_font("Arial", "B", size=10)
        pdf.cell(50, 7, txt=label)
        pdf.set_font("Arial", size=10)
        if isinstance(value, bool):
            pdf.multi_cell(0, 7, txt="Yes" if value else "No", ln=1)
        elif isinstance(value, list):
            if not value:
                pdf.multi_cell(0, 7, txt="N/A", ln=1)
            else:
                for item in value:
                    pdf.cell(5)
                    pdf.multi_cell(0, 7, txt=f"- {item}", ln=1)
        else:
            pdf.multi_cell(0, 7, txt=str(value) if value else "N/A", ln=1)

    # Step 3: Add content
    add_field("Premise Name:", case.get("premise_name"))
    add_field("Customer Email:", case.get("user_email"))
    add_field("Created At:", case.get("created_at").strftime("%Y-%m-%d %H:%M") if case.get("created_at") else "N/A")

    pdf.ln(5)
    pdf.set_font("Arial", "B", size=11)
    pdf.cell(200, 10, txt="Device Issues:", ln=1)
    pdf.set_font("Arial", size=10)

    for i, device in enumerate(case.get("devices", []), start=1):
        pdf.set_font("Arial", "B", size=10)
        pdf.cell(0, 7, txt=f"Device {i}", ln=1)
        add_field("  Model:", device.get("model"))
        add_field("  Location:", device.get("location"))
        add_field("  Issues:", device.get("issues"))
        add_field("  Remarks:", device.get("remarks"))
        pdf.ln(3)

    # Add staff-side updates if present
    pdf.ln(3)
    if case.get("staff_name"):
        pdf.set_font("Arial", "B", size=11)
        pdf.cell(200, 10, txt="Staff Response", ln=1)
        pdf.set_font("Arial", size=10)
        add_field("Staff Name:", case.get("staff_name"))
        add_field("Actions Done:", case.get("actions_done"))
        add_field("Remarks:", case.get("remarks"))
        add_field("Revisit Date:", case.get("revisit_date"))
        add_field("Revisit Time:", case.get("revisit_time"))
        add_field("Updated By:", case.get("updated_by"))
        add_field("Updated At:", case.get("updated_at").strftime("%Y-%m-%d %H:%M") if case.get("updated_at") else "N/A")

    # Step 4: Return bytes
    return pdf.output(dest="S").encode('latin-1')

def generate_change_form_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt="Change Request Details", ln=True, align="C")

    for key, value in data.items():
        if key == "e_settings":
            pdf.cell(200, 10, txt="E-Settings:", ln=True)
            for device, settings in value.items():
                pdf.cell(200, 10, txt=f"  Device: {device}", ln=True)
                for e_key, e_value in settings.items():
                    pdf.cell(200, 10, txt=f"    {e_key}: {e_value}", ln=True)
        else:
            pdf.cell(200, 10, txt=f"{key.replace('_', ' ').title()}: {value}", ln=True)

    return pdf.output(dest="S").encode('latin-1')

def generate_file_for(template_key, variables):
    if template_key == "case_completed_notification":
        return generate_case_pdf(variables["case_id"])  # returns bytes
    if template_key == "change_form_confirmation":
        return generate_change_form_pdf(variables)
    else:
        return b""
    
def send_dynamic_email(template_key, variables, mail, recipient_override=None, recipient_type=None):
    """
    Enhanced dynamic email sender with flexible recipient handling.
    
    Args:
        template_key (str): Key to look up in email_templates.json
        variables (dict): Variables to render in the template
        mail (Mail): Flask-Mail instance
        recipient_override (str, optional): Override the template's default recipient
        recipient_type (str, optional): 'customer', 'team', 'staff' - helps select appropriate template variant
    
    1) loads email_templates.json  
    2) renders subject & HTML body (Jinja in JSON)  
    3) handles flexible recipient selection
    4) attaches any attachment_template (filename rendered by Jinja, file bytes from your generator)  
    5) calls send_email()
    """
    try:
        # 1) Load templates
        current_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(current_dir, 'email_templates.json')) as f:
            templates = json.load(f)
        
        # 2) Smart template selection with recipient type
        if recipient_type and template_key not in templates:
            # Try to find a variant with recipient type prefix
            variant_key = f"{recipient_type}_{template_key}"
            if variant_key in templates:
                template_key = variant_key
                current_app.logger.info(f"Using template variant: {template_key}")
        
        tpl = templates.get(template_key)
        if not tpl:
            available_templates = list(templates.keys())
            error_msg = f"Template '{template_key}' not found. Available templates: {available_templates}"
            current_app.logger.error(error_msg)
            raise KeyError(error_msg)

        # 3) Enhanced recipient handling
        recipient_email = None
        
        if recipient_override:
            # Explicit override takes precedence
            recipient_email = recipient_override
            current_app.logger.info(f"Using recipient override: {recipient_email}")
        else:
            # Use template's default recipient with variable rendering
            template_recipient = tpl.get('receiver_email', '')
            
            # Handle different recipient types intelligently
            if recipient_type == 'team' or recipient_type == 'admin':
                # For team/admin emails, prefer team_email variable or fallback to admin config
                if 'team_email' in variables:
                    recipient_email = variables['team_email']
                    current_app.logger.info(f"Using team_email from variables: {recipient_email}")
                elif 'admin_email' in variables:
                    recipient_email = variables['admin_email']
                    current_app.logger.info(f"Using admin_email from variables: {recipient_email}")
                else:
                    # Fallback to application config
                    recipient_email = current_app.config.get('ADMIN_EMAIL_ADDRESS')
                    current_app.logger.info(f"Using ADMIN_EMAIL_ADDRESS from config: {recipient_email}")
                    if recipient_email:
                        variables['team_email'] = recipient_email  # Add to variables for template rendering
                        variables['admin_email'] = recipient_email
            elif recipient_type == 'customer':
                # For customer emails, prefer customer_email variable
                if 'customer_email' in variables:
                    recipient_email = variables['customer_email']
                    current_app.logger.info(f"Using customer_email from variables: {recipient_email}")
                elif 'user_email' in variables:
                    recipient_email = variables['user_email']
                    current_app.logger.info(f"Using user_email from variables: {recipient_email}")
            
            # If still no recipient, render the template's receiver_email
            if not recipient_email and template_recipient:
                try:
                    recipient_email = render_template_string(template_recipient, **variables)
                    current_app.logger.info(f"Rendered recipient from template '{template_recipient}': {recipient_email}")
                except Exception as render_error:
                    current_app.logger.error(f"Failed to render recipient email template '{template_recipient}': {render_error}")
                    # Fallback logic
                    if recipient_type == 'team':
                        recipient_email = current_app.config.get('ADMIN_EMAIL_ADDRESS')
                        current_app.logger.info(f"Fallback to ADMIN_EMAIL_ADDRESS: {recipient_email}")
                    elif recipient_type == 'customer' and 'customer_email' in variables:
                        recipient_email = variables['customer_email']
                        current_app.logger.info(f"Fallback to customer_email: {recipient_email}")
        
        # Validate recipient
        if not recipient_email:
            error_msg = f"No recipient email found for template '{template_key}' with recipient_type '{recipient_type}'"
            current_app.logger.error(error_msg)
            raise ValueError(error_msg)
        
        current_app.logger.info(f"Final recipient email: {recipient_email}")
        current_app.logger.info(f"Email sender: {current_app.config.get('MAIL_SENDER_ADDRESS')}")
        
        # Check if sender and recipient are the same
        sender_email = current_app.config.get('MAIL_SENDER_ADDRESS')
        if sender_email == recipient_email:
            current_app.logger.warning(f"Sender and recipient are the same ({sender_email}). This might cause delivery issues.")
        
        # Validate email format
        if not is_valid_email(recipient_email):
            error_msg = f"Invalid recipient email format: {recipient_email}"
            current_app.logger.error(error_msg)
            raise ValueError(error_msg)

        # 4) Render subject & body
        subject = render_template_string(tpl['subject'], **variables)
        body_html = render_template_string(tpl['email_content'], **variables)

        # 5) Prepare attachments list
        attachments = []
        if tpl.get('attachment_template'):
            try:
                # Render the filename
                filename = render_template_string(tpl['attachment_template'], **variables)
                # Generate or load the file bytes
                file_bytes = generate_file_for(template_key, variables)
                if file_bytes:
                    attachments.append((filename, 'application/pdf', file_bytes))
                    current_app.logger.info(f"Attachment prepared: {filename}")
            except Exception as att_error:
                current_app.logger.warning(f"Failed to prepare attachment for template '{template_key}': {att_error}")
                # Continue without attachment rather than failing

        # 6) Send email
        sender_email = tpl.get('sender_email', current_app.config.get('MAIL_DEFAULT_SENDER'))
        
        current_app.logger.info(f"Sending dynamic email - Template: {template_key}, Recipient: {recipient_email[:3]}...@{recipient_email.split('@')[1] if '@' in recipient_email else 'unknown'}")
        
        send_email(
            to_email=recipient_email,
            from_email=sender_email,
            subject=subject,
            body_html=body_html,
            mail=mail,
            attachments=attachments
        )
        
        current_app.logger.info(f"Dynamic email sent successfully - Template: {template_key}")
        return True
        
    except Exception as e:
        error_msg = f"Failed to send dynamic email with template '{template_key}': {str(e)}"
        current_app.logger.error(error_msg)
        raise Exception(error_msg) from e


def send_customer_email(template_key, variables, mail, customer_email=None):
    """Convenience function for sending emails to customers."""
    if customer_email:
        variables['customer_email'] = customer_email
    return send_dynamic_email(template_key, variables, mail, recipient_type='customer')


def send_team_email(template_key, variables, mail, team_email=None):
    """Convenience function for sending emails to team/admin."""
    if team_email:
        variables['team_email'] = team_email
    return send_dynamic_email(template_key, variables, mail, recipient_type='team')


def send_email(to_email, from_email, subject, body_html, mail, attachments=None):
    """
    Generic wrapper on Flask-Mail’s Message.
    Accepts:
     - body_html (string, assumed safe HTML)
     - attachments: list of (filename, mimetype, bytes) or file-paths
    """
    msg = Message(subject, sender=from_email, recipients=[to_email])
    msg.html = body_html

    # attach any files
    for att in attachments or []:
        if isinstance(att, str) and os.path.exists(att):
            with open(att, 'rb') as f:
                data = f.read()
            msg.attach(os.path.basename(att), 
                       'application/octet-stream', 
                       data)
        else:
            # tuple (filename, mime, bytes)
            name, mime, data = att
            msg.attach(name, mime, data)

    # logs
    current_app.logger.info(f"Sending email to: {to_email}")
    current_app.logger.info(f"Subject: {subject}")
    try:
        mail.send(msg)
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {e}")
        raise


def replicate_monthly_routes(database):
    current_date = datetime.now()
    previous_month = (current_date.month - 1) if current_date.month > 1 else 12
    previous_year = current_date.year if current_date.month > 1 else current_date.year - 1

    routes_to_copy = list(database.find({"month": previous_month, "year": previous_year}))

    new_routes = []
    for route in routes_to_copy:
        new_month = current_date.month
        new_year = current_date.year

        # Adjust day to fit within the month's days (e.g., 31st March → 30th April)
        max_days = calendar.monthrange(new_year, new_month)[1]
        new_day = min(route.get("day", 1), max_days)

        # Create new entry
        new_route = {
            "company": route["company"],
            "premise_name": route["premise_name"],
            "premise_area": route["premise_area"],
            "premise_address": route["premise_address"],
            "pics": route["pics"],
            "model": route["model"],
            "color": route["color"],
            "eo": route["eo"],
            "day": new_day,
            "month": new_month,
            "year": new_year
        }
        new_routes.append(new_route)

    if new_routes:
        database.insert_many(new_routes)
        database.delete_many({"month": previous_month, "year": previous_year})

def flash_message(message, category="info"):
    flash(message, category)