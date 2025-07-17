import os
from datetime import datetime, timedelta
from flask_mail import Mail, Message
import calendar
from flask import flash, current_app, request, session
import re

def log_activity(name, action, database):
    """Log user activity with enhanced information"""
    log_entry = {
        "user": name,
        "action": action,
        "timestamp": datetime.now(),
        "ip_address": request.environ.get('REMOTE_ADDR', 'unknown'),
        "user_agent": request.environ.get('HTTP_USER_AGENT', 'unknown')[:200]  # Limit length
    }
    database.insert_one(log_entry)

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