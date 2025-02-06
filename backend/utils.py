from datetime import datetime, timedelta
from flask_mail import Mail, Message
import calendar

def log_activity(name, action, database):
    log_entry = {
        "user": name,
        "action": action,
        "timestamp": datetime.now(),
    }
    database.insert_one(log_entry)

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


def send_email_to_admin(case_no, from_email, mail):
    """Notify admin about a new case creation."""
    subject = f"New Case #{case_no} Created"
    body = f"A new case with case number #{case_no} has been created. Please check the system for details."
    send_email('medoroyalrma@gmail.com', from_email, subject, body, mail)


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
        print(body)
        print(to_email)
        print(from_email)
        print(subject)
        mail.send(msg)
    except Exception as e:
        print(f"Failed to send email: {e}")


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
        mongo.db.route_list_collection.insert_many(new_routes)
        mongo.db.route_list_collection.delete_many({"month": previous_month, "year": previous_year})

