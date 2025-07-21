import os
from datetime import datetime, timedelta
from flask_mail import Mail, Message
import calendar
from flask import flash, current_app, request, session, jsonify, redirect, url_for
import re
import functools
import traceback
from pymongo.errors import PyMongoError

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

def send_email(to_email, from_email, subject, body, mail):
    """Generic function to send an email using Flask-Mail."""
    try:
        msg = Message(subject, sender= from_email, recipients=[to_email])
        msg.body = body
        # Log email details for debugging (without exposing sensitive content)
        from flask import current_app
        current_app.logger.info(f"Sending email to: {to_email[:3]}...@{to_email.split('@')[1] if '@' in to_email else 'unknown'}")
        current_app.logger.info(f"Email subject: {subject}")
        mail.send(msg)
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Failed to send email: {e}")


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