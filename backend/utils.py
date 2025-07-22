import os
from datetime import datetime, timedelta
from flask_mail import Mail, Message
import calendar
from flask import flash, current_app, render_template_string, request, session, jsonify, redirect, url_for
import re
import functools
import traceback
from pymongo.errors import PyMongoError
from col import collection
import json

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
    """Send a confirmation email to the customer."""
    subject = f"Case #{case_no} Created Successfully"
    body = f"Thank you for submitting your case. Your case number is #{case_no}. Our staff will get in touch with you shortly."
    send_email(user_email, from_email, subject, body, mail)


def send_email_to_admin(case_no, user_email, from_email, mail):
    """Notify admin about a new case creation."""
    subject = f"New Case #{case_no} Created"
    body = f"A new case with case number #{case_no} has been created. Please check the system for details."
    send_email(os.getenv('ADMIN_EMAIL_ADDRESS'), from_email, subject, body, mail)


# def send_email(to_email, subject, body):
#     """Generic function to send an email."""
#     try:
#         msg = MIMEMultipart()
#         msg["From"] = app.config['MAIL_USERNAME']
#         msg["To"] = to_email
#         msg["Subject"] = subject

#         msg.attach(MIMEText(body, "plain"))

#         with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
#             server.starttls()
#             server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
#             server.send_message(msg)
#     except Exception as e:
#         print(f"Failed to send email: {e}")

# def send_email(to_email, from_email, subject, body, mail):
#     """Generic function to send an email using Flask-Mail."""
#     try:
#         msg = Message(subject, sender= from_email, recipients=[to_email])
#         msg.body = body
#         # Log email details for debugging (without exposing sensitive content)
#         from flask import current_app
#         current_app.logger.info(f"Sending email to: {to_email[:3]}...@{to_email.split('@')[1] if '@' in to_email else 'unknown'}")
#         current_app.logger.info(f"Email subject: {subject}")
#         mail.send(msg)
#     except Exception as e:
#         from flask import current_app
#         current_app.logger.error(f"Failed to send email: {e}")

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

def generate_file_for(template_key, variables):
    if template_key == "case_completed_notification":
        return generate_case_pdf(variables["case_id"])  # returns bytes
    else:
        return b""
    
def send_dynamic_email(template_key, variables, mail):
    """
    1) loads email_templates.json  
    2) renders subject & HTML body (Jinja in JSON)  
    3) attaches any attachment_template (filename rendered by Jinja, file bytes from your generator)  
    4) calls send_email()  
    """
    # 1) load + look up
    with open('email_templates.json') as f:
        templates = json.load(f)
    tpl = templates.get(template_key)
    if not tpl:
        raise KeyError(f"No such template: {template_key}")

    # 2) render subject & body
    subject = render_template_string(tpl['subject'], **variables)
    body_html = render_template_string(tpl['email_content'], **variables)

    # 3) prepare attachments list
    attachments = []
    if tpl.get('attachment_template'):
        # render the filename
        filename = render_template_string(tpl['attachment_template'], **variables)
        # generate or load the file bytes (you supply this)
        file_bytes = generate_file_for(template_key, variables)
        # e.g. PDF
        attachments.append((filename, 'application/pdf', file_bytes))

    # 4) finally send
    send_email(
        to_email   = render_template_string(tpl['receiver_email'], **variables),
        from_email = tpl['sender_email'],
        subject    = subject,
        body_html  = body_html,
        mail       = mail,
        attachments=attachments
    )


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