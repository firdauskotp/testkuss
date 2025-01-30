import smtplib
from urllib.parse import urlencode
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify, Response
from flask_pymongo import MongoClient
from werkzeug.security import check_password_hash
from flask_mail import Mail, Message
from datetime import datetime
import certifi  # Only needed for Mac
from werkzeug.utils import secure_filename
import os, json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.security import generate_password_hash
import gridfs
from dotenv import load_dotenv
from bson import ObjectId, json_util
from utils import log_activity
from flask_cors import CORS


app = Flask(__name__)

CORS(app)

load_dotenv()

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# MongoDB Configuration
MONGO_URI = os.getenv('MONGO_URL')
mongo = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = mongo['customer']
collection = db['case_issue']

login_db=mongo['login_admin']
login_collection=login_db['log']

login_cust_db=mongo['login_cust']
login_cust_collection=login_cust_db['logg']

remark_db=mongo['remark']
remark_collection=remark_db['cases']

dashboard_db = mongo['dashboard_db']
services_collection = dashboard_db['services']
eo_list_collection = dashboard_db['eo_list']
eo_pack_collection = dashboard_db['eo_pack']
model_list_collection = dashboard_db['model_list']
others_list_collection = dashboard_db['others_devices_pack']
empty_bottles_list_collection = dashboard_db['others_empty_bottle_pack']
straw_list_collection = dashboard_db['straw_mist_heads_pack']
profile_list_collection = dashboard_db['profile']
device_list_collection = dashboard_db['device']

# customer_collection = dashboard_db['customer']
# device_collection = dashboard_db['device']
change_collection = dashboard_db['change']
refund_collection = dashboard_db['refund']

logs_db=mongo['logs']
logs_collection=logs_db['logs']

test_db=mongo['test']
test_collection=test_db['test']

fs = gridfs.GridFS(db)



app.config['MAIL_SERVER'] = os.getenv('SMTP_GOOGLE_SERVER')
app.config['MAIL_PORT'] = 587
# app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('SMTP_TEST_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('SMTP_TEST_APP_PASSWORD')

mail = Mail(app)

@app.route('/update-data', methods=['POST'])
def update_data():
    data = request.get_json()
    record_id = data.pop('sn')
    print("Record:", record_id)
    print("Object ID :", ObjectId)
    result = services_collection.update_one({'S/N': record_id}, {'$set': data})
    if result.modified_count > 0:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False})

@app.context_processor
def inject_builtin_functions():
    # Inject Python built-in functions into the Jinja2 environment
    return dict(max=max, min=min)

@app.template_filter('to_querystring')
def to_querystring(query_params):
    """Converts a dictionary into a query string."""
    return urlencode(query_params)

@app.template_filter('update_querystring')
def update_querystring(querystring, key, value):
    """Updates or adds a key-value pair in the query string."""
    query_dict = dict([kv.split('=') for kv in querystring.split('&') if '=' in kv])
    query_dict[key] = value
    return urlencode(query_dict)


# Routes
@app.route("/customer-help", methods=["GET", "POST"])
def customer_form():
    # """Form for customers to create new cases."""
    # if "customer_email" not in session:
    #     return redirect(url_for("client_login"))  # Redirect to login if not logged in

    # user_email = session["customer_email"] 
    if request.method == "POST":
        # Auto-increment case number
        case_no = collection.count_documents({}) + 1

        # Extract customer form data
        user_email = request.form.get("email")
        premise_name = request.form.get("premise_name")
        location = request.form.get("location")
        model = request.form.get("model")
        issues = request.form.getlist("issues")
        remarks = request.form.get("remarks", "")

        # Handle image upload
        image = request.files.get('image')  # Get the image file from the form
        image_id = None
        if image:
            filename = secure_filename(image.filename)
            image_data = image.read()  # Read the file data
            image_id = fs.put(image_data, filename=filename)  # Store the image in GridFS


        # Insert new case into MongoDB
        collection.insert_one({
            "case_no": case_no,
            "premise_name": premise_name,
            "location": location,
            "image_id": image_id,
            "model": model,
            "issues": issues,
            "remarks": remarks,
            "email": user_email,
            "created_at": datetime.now(),
        })

        # Send emails to the customer and admin
        send_email_to_customer(case_no, user_email)
        send_email_to_admin(case_no)
        

        # Redirect to success page
        return redirect(url_for("case_success", case_no=case_no))

    return render_template("customer-complaint-form.html")


@app.route("/staff-help/<int:case_no>", methods=["GET", "POST"])
def staff_form(case_no):
    """Form for staff to update and manage cases."""
    #case_details = db.case_issue.find_one({"case_no": case_no})
   # if not case_details:
    #    flash(f"Case #{case_no} not found!", "danger")
    #    return redirect(url_for("customer_form"))

    if request.method == "POST":
        # Extract form data
        actions_done = request.form.getlist("actions")
        remarks = request.form.get("remarks", "")
        case_closed = request.form.get("case_closed")
        revisit_date = request.form.get("appointment_date")
        revisit_time = request.form.get("appointment_time")
        staff_name = request.form.get("staff_name")
        
        # Handle signature file upload
        signature = None
        if "signature" in request.files:
            file = request.files["signature"]
            if file and file.filename:
                filename = secure_filename(f"case_{case_no}_{file.filename}")
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                signature = os.path.join(app.config["UPLOAD_FOLDER"], filename)

        # Update case in MongoDB
        collection.update_one(
            {"case_no": case_no},
            {"$set": {
                "actions_done": actions_done,
                "remarks": remarks,
                "case_closed": case_closed,
                "revisit_date": revisit_date,
                "revisit_time": revisit_time,
                "staff_name": staff_name,
                "signature": signature,
                "updated_at": datetime.now(),
            }}
        )


        # Send Email Notification
        msg = Message("Case Updated", sender=app.config['MAIL_USERNAME'], recipients=["team-email@example.com"])
        msg.body = f"""
        Case No: {case_no}
        Actions: {', '.join(actions)}
        Remarks: {remarks}
        Staff Name: {staff_name}
        Revisit Date: {revisit_date}
        """
        mail.send(msg)

        flash(f"Case #{case_no} updated successfully!", "success")
        return redirect(url_for("staff_form", case_no=case_no))

    case_data = collection.find_one({"case_no": case_no})
    return render_template("staff-complaint-form.html", case_no=case_no, case_data=case_data)

@app.route("/")
def index():
    return render_template("index.html")



@app.route("/case-success/<int:case_no>",methods=["GET","POST"])
def case_success(case_no):
    """Success page after creating a case."""
    return render_template("case-success.html", case_no=case_no)


def send_email_to_customer(case_no, user_email):
    """Send a confirmation email to the customer."""
    subject = f"Case #{case_no} Created Successfully"
    body = f"Thank you for submitting your case. Your case number is #{case_no}. Our staff will get in touch with you shortly."
    send_email(user_email, app.config['MAIL_USERNAME'], subject, body)


def send_email_to_admin(case_no):
    """Notify admin about a new case creation."""
    subject = f"New Case #{case_no} Created"
    body = f"A new case with case number #{case_no} has been created. Please check the system for details."
    send_email('medoroyalrma@gmail.com', app.config['MAIL_USERNAME'], subject, body)


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

def send_email(to_email, from_email, subject, body):
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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' not in session:
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

        login_cust_collection.insert_one({
            'email': email,
            'password': hashed_password
        })
        
        flash("User registered successfully!", "success")
        log_activity(session["username"],"added user : " +str(email),logs_collection)
        return redirect(url_for('dashboard'))


    return render_template('register.html')

@app.route('/register-admin', methods=['GET', 'POST'])
def register_admin():
    if 'username' not in session:
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

        login_collection.insert_one({
            'username': username,
            'password': hashed_password
        })
        
        flash("User registered successfully!", "success")
        log_activity(session["username"],"added user : " +str(username),logs_collection)
        return redirect(url_for('dashboard'))

    return render_template('register-admin.html')



@app.route('/delete_user', methods=['POST'])
def delete_user():
    if 'username' not in session:
        return redirect(url_for('admin_login'))
    
    user_id = request.form['user_id']
    user = login_cust_collection.find_one({'_id': ObjectId(user_id)})
    email = user.get('email', 'Unknown')  # Get the username or default to 'Unknown'

    login_cust_collection.delete_one({'_id': ObjectId(user_id)})
        
    flash("User deleted successfully!", "success")
    log_activity(session["username"], f"deleted user with email: {email}", logs_collection)
    return redirect(url_for('view_users'))

@app.route('/delete_admin', methods=['POST'])
def delete_admin():
    if 'username' not in session:
        return redirect(url_for('admin_login'))
    
    user_id = request.form['user_id']

    user = login_cust_collection.find_one({'_id': ObjectId(user_id)})
    username = user.get('username', 'Unknown')  # Get the username or default to 'Unknown'
    login_cust_collection.delete_one({'_id': ObjectId(user_id)})
    flash("User deleted successfully!", "success")
    log_activity(session["username"], f"deleted user with username: {username}", logs_collection)
    return redirect(url_for('view_admins'))

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Query MongoDB for the user
        user = login_collection.find_one({"username": username})

        if user and check_password_hash(user["password"], password):  # Assuming passwords are hashed
            # Set session for the logged-in user
            session["user_id"] = str(user["_id"])
            session["username"] = user["username"]
            flash("Login successful!", "success")
            log_activity(session["username"],"login",logs_collection)

            return redirect(url_for("dashboard"))  # Redirect to the dashboard
        else:
            flash("Invalid username or password.", "danger")
            return redirect(url_for("admin_login"))

    return render_template("login.html")

@app.route('/all-list',methods=['GET'])
def reports():
    if 'username' in session:
        # Pagination parameters
        page = int(request.args.get('page', 1))  # Current page (default: 1)
        limit = int(request.args.get('limit', 10))  # Entries per page (default: 10)


        # Get filter parameters
        month = request.args.get('month','').strip()
        year = request.args.get('year','').strip()
        EO = request.args.get("EO")
        Company = request.args.get("Company")
        Model = request.args.get("Model")
        Volume = request.args.get("Volume")
        SN = request.args.get("SN")
        Balance = request.args.get("Balance")
        Consumption = request.args.get("Consumption")
        Refilled = request.args.get("Refilled")
        E1_Work = request.args.get("E1_Work")
        E1_Pause = request.args.get("E1_Pause")
        E1_Days = request.args.get("E1_Days")
        E1_Start = request.args.get("E1_Start")
        E1_End = request.args.get("E1_End")
        E2_Work = request.args.get("E2_Work")
        E2_Pause = request.args.get("E2_Pause")
        E2_Days = request.args.get("E2_Days")
        E2_Start = request.args.get("E2_Start")
        E2_End = request.args.get("E2_End")
        E3_Work = request.args.get("E3_Work")
        E3_Pause = request.args.get("E3_Pause")
        E3_Days = request.args.get("E3_Days")
        E3_Start = request.args.get("E3_Start")
        E3_End = request.args.get("E3_End")
        E4_Work = request.args.get("E4_Work")
        E4_Pause = request.args.get("E4_Pause")
        E4_Days = request.args.get("E4_Days")
        E4_Start = request.args.get("E4_Start")
        E4_End = request.args.get("E4_End")
        Model = request.args.get("Model")
        Colour = request.args.get("Colour")
        Current_EO = request.args.get("Current_EO")
        New_EO = request.args.get("New_EO")
        Scent_Effectiveness = request.args.get("Scent_Effectiveness")
        Common_Encounters = request.args.get("Common_Encounters")
        Other_Remarks = request.args.get("Other_Remarks")


        query = {}
        if month and year:
            months = [int(m) for m in month.split(',')]
            month_list = [int(m.strip()) for m in month.split(',') if m.strip().isdigit()]
    
            query['$expr'] = {
                '$and': [
                    {'$in': [{'$month': '$month_year'}, month_list]},
                    {'$eq': [{'$year': '$month_year'}, int(year)]}
                ]
            }
        
       
        
        # Filter by EO (string partial match)

        if EO:
            query['Current EO'] = {'$regex': EO, '$options': 'i'}  # Case-insensitive partial match

        if Model:
            query['Model'] = {'$regex': Model, '$options': 'i'}  # Case-insensitive partial match

        if Company:
            query['company'] = {'$regex': Company, '$options': 'i'}  # Case-insensitive partial match


        # Filter by Volume (integer exact match)
        if Volume:
            query['Volume'] = int(Volume)
        
        # Filter by SN (string partial match)
        if SN:
            query['S/N'] = int(SN)  # Case-insensitive partial match

        # Filter by Balance (integer exact match)
        if Balance:
            query['Balance'] = int(Balance)

        # Filter by Consumption (integer exact match)
        if Consumption:
            query['Consumption'] = int(Consumption)

        # Filter by Refilled (integer exact match)
        if Refilled:
            query['Refilled'] = int(Refilled)

        # Filter for E1 Work (integer exact match)
        if E1_Work:
            query['E1 - WORK'] = int(E1_Work)

        # Filter for E1 Pause (integer exact match)
        if E1_Pause:
            query['E1 - PAUSE'] = int(E1_Pause)

        # Filter for E1 Days (integer exact match)
        if E1_Days:
            query['E1 - DAYS'] = {'$regex': E1_Days, '$options': 'i'}

        # Filter for E1 Start (integer exact match)
        if E1_Start:
            query['E1 - START'] = {'$regex': E1_Start, '$options': 'i'}

        # Filter for E1 End (integer exact match)
        if E1_End:
            query['E1 - END'] = {'$regex': E1_End, '$options': 'i'}

        # Filter for E2 Work (integer exact match)
        if E2_Work:
            query['E2 - WORK'] = int(E2_Work)

        # Filter for E2 Pause (integer exact match)
        if E2_Pause:
            query['E2 - PAUSE'] = int(E2_Pause)

        if E2_Days:
            query['E2 - DAYS'] = {'$regex': E2_Days, '$options': 'i'}

        # Filter for E1 Start (integer exact match)
        if E2_Start:
            query['E2 - START'] = {'$regex': E2_Start, '$options': 'i'}

        # Filter for E1 End (integer exact match)
        if E2_End:
            query['E2 - END'] = {'$regex': E2_End, '$options': 'i'}

        # Filter for E3 Work (integer exact match)
        if E3_Work:
            query['E3 - WORK'] = int(E3_Work)

        # Filter for E3 Pause (integer exact match)
        if E3_Pause:
            query['E3 - PAUSE'] = int(E3_Pause)

        # Filter for E3 Days (integer exact match)
        if E3_Days:
            query['E3 - DAYS'] = {'$regex': E3_Days, '$options': 'i'}

        # Filter for E1 Start (integer exact match)
        if E3_Start:
            query['E3 - START'] = {'$regex': E3_Start, '$options': 'i'}

        # Filter for E1 End (integer exact match)
        if E3_End:
            query['E3 - END'] = {'$regex': E3_End, '$options': 'i'}

        # Filter for E4 Work (integer exact match)
        if E4_Work:
            query['E4 - WORK'] = int(E4_Work)

        # Filter for E4 Pause (integer exact match)
        if E4_Pause:
            query['E4 - PAUSE'] = int(E4_Pause)

        # Filter for E4 Days (integer exact match)
        if E4_Days:
            query['E4 - DAYS'] = {'$regex': E4_Days, '$options': 'i'}

        # Filter for E1 Start (integer exact match)
        if E4_Start:
            query['E4 - START'] = {'$regex': E4_Start, '$options': 'i'}

        # Filter for E1 End (integer exact match)
        if E4_End:
            query['E4 - END'] = {'$regex': E4_End, '$options': 'i'}

        # Filter by Model (string partial match)
        if Model:
            query['Model'] = {'$regex': Model, '$options': 'i'}  # Case-insensitive partial match

        # Filter by Colour (string partial match)
        if Colour:
            query['Color'] = {'$regex': Colour, '$options': 'i'}  # Case-insensitive partial match

        # Filter by Current EO (string partial match)
        if Current_EO:
            query['Current EO'] = {'$regex': Current_EO, '$options': 'i'}  # Case-insensitive partial match

        # Filter by New EO (string partial match)
        if New_EO:
            query['New EO'] = {'$regex': New_EO, '$options': 'i'}  # Case-insensitive partial match

        # Filter by Scent Effectiveness (string partial match)
        if Scent_Effectiveness:
            query['#1 Scent Effectiveness'] = {'$regex': Scent_Effectiveness, '$options': 'i'}  # Case-insensitive partial match

        # Filter by Common Encounters (string partial match)
        if Common_Encounters:
            query['#1 Common encounters'] = {'$regex': Common_Encounters, '$options': 'i'}  # Case-insensitive partial match

        # Filter by Other Remarks (string partial match)
        if Other_Remarks:
            query['#1 Other remarks'] = {'$regex': Other_Remarks, '$options': 'i'}  # Case-insensitive partial match


        
        query_params = request.args.to_dict()
        query_params['page'] = page
        query_params['limit'] = limit

        # Construct base URL for pagination links
        base_url = request.path
        pagination_base_url = f"{base_url}?"
        # Get total entries for pagination
        total_entries = services_collection.count_documents(query)
        

        # Fetch data with pagination
        services_collection_list = services_collection.find(query, {'_id': 0}) \
                        .skip((page - 1) * limit) \
                        .limit(limit)

        # Add month and year fields to the data
        processed_data = []
        for entry in services_collection_list:
            month_year_date = entry.get('month_year')
            if isinstance(month_year_date, datetime):
                entry['month'] = month_year_date.month
                entry['year'] = month_year_date.year
            try:
                entry["S/N"] = int(entry["S/N"])
            except Exception as e:
                entry["S/N"] = 0
            processed_data.append(entry)


        # Calculate total pages
        total_pages = (total_entries + limit - 1) // limit
        
        return render_template("reports.html", 
                               username=session["username"], 
                               data=processed_data, 
                               page=page, 
                               total_pages=total_pages,
                               limit=limit,
                               pagination_base_url=pagination_base_url,
                               query_params=query_params
                               )
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for("admin_login"))

@app.route('/pack-list',methods=['GET'])
def pack_list():
    if 'username' in session:
        # Pagination parameters
        page = int(request.args.get('page', 1))  # Current page (default: 1)
        limit = int(request.args.get('limit', 10))  # Entries per page (default: 10)

        device_page = int(request.args.get('device_page', 1))  # Current page (default: 1)
        device_limit = int(request.args.get('device_limit', 10))  # Entries per page (default: 10)

        bottle_page = int(request.args.get('bottle_page', 1))  # Current page (default: 1)
        bottle_limit = int(request.args.get('bottle_limit', 10))  # Entries per page (default: 10)

        straw_page = int(request.args.get('straw_page', 1))  # Current page (default: 1)
        straw_limit = int(request.args.get('straw_limit', 10))  # Entries per page (default: 10)

        # Get filter parameters
        month = request.args.get('month','').strip()
        year = request.args.get('year','').strip()
        eo = request.args.get('eo_name')
        ml_required = request.args.get('ml_required')
        packed = request.args.get('packed')
        ready_supply = request.args.get('ready_supply')
        ml_fresh_supply = request.args.get('ml_fresh_supply')
        ml_balance = request.args.get('ml_balance')
        perc_balance = request.args.get('perc_balance')


        device_month = request.args.get('device_month','').strip()
        device_year = request.args.get('device_year','').strip()
        devices = request.args.get('devices')
        device_quantity = request.args.get('device_quantity')

        bottle_month = request.args.get('bottle_month','').strip()
        bottle_year = request.args.get('bottle_year','').strip()
        empty_bottle = request.args.get('empty_bottle')
        bottle_volume = request.args.get('bottle_volume')

        straw_month = request.args.get('straw_month','').strip()
        straw_year = request.args.get('straw_year','').strip()
        model_others = request.args.get('model_others')
        final_quantity = request.args.get('final_quantity')
        actual_quantity = request.args.get('actual_quantity')
        extra = request.args.get('extra')

        device_query = {}
        query={}
        bottle_query={}
        other_query={}
        if device_month and device_year:
            device_months = [int(m) for m in device_month.split(',')]
            device_month_list = [int(m.strip()) for m in device_month.split(',') if m.strip().isdigit()]

            device_query['$expr'] = {
                '$and': [
                    {'$in': [{'$month': '$month_year'}, device_month_list]},
                    {'$eq': [{'$year': '$month_year'}, int(device_year)]}
                ]
            }
        if month and year:
            months = [int(m) for m in month.split(',')]
            month_list = [int(m.strip()) for m in month.split(',') if m.strip().isdigit()]

            query['$expr'] = {
                
                '$and': [
                    {'$in': [{'$month': '$month_year'}, month_list]},
                    {'$eq': [{'$year': '$month_year'}, int(year)]}
                ]
            }
        if bottle_month and bottle_year:
            bottle_months = [int(m) for m in bottle_month.split(',')]
            bottle_month_list = [int(m.strip()) for m in bottle_month.split(',') if m.strip().isdigit()]

            bottle_query['$expr'] = {
                '$and': [
                    {'$in': [{'$month': '$month_year'}, bottle_month_list]},
                    {'$eq': [{'$year': '$month_year'}, int(bottle_year)]}
                ]
            }
       
        if straw_month and straw_year:
            straw_months = [int(m) for m in straw_month.split(',')]
            straw_month_list = [int(m.strip()) for m in straw_month.split(',') if m.strip().isdigit()]

            other_query['$expr'] = {
                '$and': [
                    {'$in': [{'$month': '$month_year'}, straw_month_list]},
                    {'$eq': [{'$year': '$month_year'}, int(straw_year)]}
                ]
            }
        if device_quantity:
            device_query['quantity'] = int(device_quantity)
        
        if empty_bottle:
            bottle_query['empty_bottles'] = int(empty_bottle)

        if bottle_volume:
            bottle_query['volume'] = int(bottle_volume)

        if actual_quantity:
            other_query['actual_quantity'] = int(actual_quantity)

        if final_quantity:
            other_query['final_quantity'] = int(final_quantity)
        
        if ml_required:
            query['ml_required'] = int(ml_required)

        if packed:
            query['packed'] = int(packed)

        if ready_supply:
            query['ready_supply'] = int(ready_supply)

        if ml_fresh_supply:
            query['ml_fresh_supply'] = int(ml_fresh_supply)

        if ml_balance:
            query['ml_balance'] = int(ml_balance)
        
        if perc_balance:
            query['perc_balance'] = int(perc_balance)

        if extra:
            other_query['extra'] = int(extra)
        
        if model_others:
            other_query['model'] = {'$regex': model_others, '$options': 'i'}  # Case-insensitive partial match
        
        if eo:
            query['eo_name'] = {'$regex': eo, '$options': 'i'}  # Case-insensitive partial match
        
        if devices:
            device_query['devices'] = {'$regex': devices, '$options': 'i'}

        query_params = request.args.to_dict()
        query_params['page'] = page
        query_params['limit'] = limit
        base_url = request.path
        pagination_base_url = f"{base_url}?"

        query_params_device = request.args.to_dict()
        query_params_device['device_page'] = device_page
        query_params_device['device_limit'] = device_limit
        base_url_device = request.path
        pagination_base_url_device = f"{base_url_device}?"

        query_params_bottle = request.args.to_dict()
        query_params_bottle['bottle_page'] = bottle_page
        query_params_bottle['bottle_limit'] = bottle_limit
        base_url_bottle = request.path
        pagination_base_url_bottle = f"{base_url_bottle}?"

        query_params_straw = request.args.to_dict()
        query_params_straw['straw_page'] = straw_page
        query_params_straw['straw_limit'] = straw_limit
        base_url_straw = request.path
        pagination_base_url_straw = f"{base_url_straw}?"


        total_page = eo_pack_collection.count_documents(query)
        total_device_page = others_list_collection.count_documents(device_query)
        total_bottle_page = empty_bottles_list_collection.count_documents(bottle_query)
        total_straw_page = straw_list_collection.count_documents(other_query)
    
        data_eo_pack_list = eo_pack_collection.find(query, {'_id':0}).skip((page-1)*limit).limit(limit)
        data_device_pack_list = others_list_collection.find(device_query, {'_id':0}).skip((device_page-1)*device_limit).limit(device_limit)
        data_bottle_pack_list = empty_bottles_list_collection.find(bottle_query, {'_id':0}).skip((bottle_page-1)*bottle_limit).limit(bottle_limit)
        data_other_pack_list = straw_list_collection.find(other_query, {'_id':0}).skip((straw_page-1)*straw_limit).limit(straw_limit)

       
        processed_data_eo_pack_list = []
        processed_data_device_pack_list = []
        processed_data_bottle_pack_list = []
        processed_data_other_pack_list = []

        for entry in data_eo_pack_list:
            month_year_date = entry.get('month_year')
            if isinstance(month_year_date, datetime):
                entry['month'] = month_year_date.month
                entry['year'] = month_year_date.year
            processed_data_eo_pack_list.append(entry)

        for entry in data_device_pack_list:
            month_year_date = entry.get('month_year')
            if isinstance(month_year_date, datetime):
                entry['month'] = month_year_date.month
                entry['year'] = month_year_date.year
            processed_data_device_pack_list.append(entry)

        for entry in data_bottle_pack_list:
            month_year_date = entry.get('month_year')
            if isinstance(month_year_date, datetime):
                entry['month'] = month_year_date.month
                entry['year'] = month_year_date.year
            processed_data_bottle_pack_list.append(entry)

        for entry in data_other_pack_list:
            month_year_date = entry.get('month_year')
            if isinstance(month_year_date, datetime):
                entry['month'] = month_year_date.month
                entry['year'] = month_year_date.year
            processed_data_other_pack_list.append(entry)

        # Calculate total pages
        total_pages = (total_page + limit - 1) // limit
        total_device_pages = (total_device_page + device_limit - 1) // device_limit
        total_bottle_pages = (total_bottle_page + bottle_limit - 1) // bottle_limit
        total_straw_pages = (total_straw_page + straw_limit - 1) // straw_limit

        
        return render_template("pack-list.html", 
                               username=session["username"], 
                               data=processed_data_eo_pack_list,
                               device_data = processed_data_device_pack_list,
                               bottle_data = processed_data_bottle_pack_list,
                               straw_data = processed_data_other_pack_list,
                               device_page=device_page, 
                               total_device_pages=total_device_pages,
                               device_limit=device_limit,
                               bottle_page=bottle_page, 
                               total_bottle_pages=total_bottle_pages,
                               bottle_limit=bottle_limit,
                               straw_page=straw_page, 
                               total_straw_pages=total_straw_pages,
                               straw_limit=straw_limit,
                               page=page, 
                               total_pages=total_pages,
                               limit=limit,
                               pagination_base_url=pagination_base_url,
                               query_params=query_params,
                               pagination_base_url_device=pagination_base_url_device,
                               query_params_device=query_params_device,
                               pagination_base_url_bottle=pagination_base_url_bottle,
                               query_params_bottle=query_params_bottle,
                               pagination_base_url_straw=pagination_base_url_straw,
                               query_params_straw=query_params_straw
                               )
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for("admin_login"))
    
@app.route('/eo-list',methods=['GET'])
def eo_list():
    if 'username' in session:
        # Pagination parameters
        page = int(request.args.get('page', 1))  # Current page (default: 1)
        limit = int(request.args.get('limit', 10))  # Entries per page (default: 10)

        model_page = int(request.args.get('model_page', 1))  # Current page (default: 1)
        model_limit = int(request.args.get('model_limit', 10))  # Entries per page (default: 10)

        # Get filter parameters
        month = request.args.get('month','').strip()
        year = request.args.get('year','').strip()
        eo = request.args.get('EO')
        volume = request.args.get('Volume')

        model_month = request.args.get('model_month','').strip()
        model_year = request.args.get('model_year','').strip()
        quantity = request.args.get('Quantity')
        total_batteries = request.args.get('total_batteries')
        model_type = request.args.get('model_type')
        battery_type = request.args.get('battery_type')
        remark = request.args.get('Remark')

        model_query = {}
        if model_month and model_year:
            model_months = [int(m) for m in model_month.split(',')]
            model_month_list = [int(m.strip()) for m in model_month.split(',') if m.strip().isdigit()]

            model_query['$expr'] = {
                '$and': [
                    {'$in': [{'$month': '$month_year'}, model_month_list]},
                    {'$eq': [{'$year': '$month_year'}, int(model_year)]}
                ]
            }
        
       
        
        if quantity:
            model_query['quantity'] = int(quantity)
        
        # Filter by Total Batteries (integer exact match)
        if total_batteries:
            model_query['total_batteries'] = int(total_batteries)
        
        # Filter by Model Type (string partial match)
        if model_type:
            model_query['model2'] = {'$regex': model_type, '$options': 'i'}  # Case-insensitive partial match
        
        # Filter by Battery Type (string partial match)
        if battery_type:
            model_query['battery_type'] = {'$regex': battery_type, '$options': 'i'}  # Case-insensitive partial match
        
        # Filter by Remark (integer exact match)
        if remark:
            model_query['remark'] = {'$regex': remark, '$options': 'i'}

        # Build MongoDB query
        query = {}
        if month and year:
            months = [int(m) for m in month.split(',')]
            month_list = [int(m.strip()) for m in month.split(',') if m.strip().isdigit()]

            query['$expr'] = {
                '$and': [
                    {'$in': [{'$month': '$month_year'}, month_list]},
                    {'$eq': [{'$year': '$month_year'}, int(year)]}
                ]
            }
        if eo:
            query['EO2'] = {'$regex': eo, '$options': 'i'} 
        if volume:
            query['Volume'] = int(volume)

        query_params = request.args.to_dict()
        query_params['page'] = page
        query_params['limit'] = limit
        base_url = request.path
        pagination_base_url = f"{base_url}?"

        query_params_model = request.args.to_dict()
        query_params_model['model_page'] = model_page
        query_params_model['model_limit'] = model_limit
        base_url_model = request.path
        pagination_base_url_model = f"{base_url_model}?"

        # Get total entries for pagination
        total_entries_eo_list = eo_list_collection.count_documents(query)
        total_entries_model_list = model_list_collection.count_documents(model_query)
        

        # Fetch data with pagination
        data_eo_list = eo_list_collection.find(query, {'_id': 0}) \
                        .skip((page - 1) * limit) \
                        .limit(limit)
        data_model_list = model_list_collection.find(model_query, {'_id':0}).skip((model_page-1)*model_limit).limit(model_limit)

        # Add month and year fields to the data
        processed_data_eo_list = []
        processed_data_model_list = []
        for entry in data_eo_list:
            month_year_date = entry.get('month_year')
            if isinstance(month_year_date, datetime):
                entry['month'] = month_year_date.month
                entry['year'] = month_year_date.year
            processed_data_eo_list.append(entry)

        for entry in data_model_list:
            month_year_date = entry.get('month_year')
            if isinstance(month_year_date, datetime):
                entry['month'] = month_year_date.month
                entry['year'] = month_year_date.year
            processed_data_model_list.append(entry)

        # Calculate total pages
        total_pages = (total_entries_eo_list + limit - 1) // limit
        total_model_pages = (total_entries_model_list + model_limit -1) // model_limit
        
        return render_template("eo-list.html", 
                               username=session["username"], 
                               data=processed_data_eo_list, 
                               model_data=processed_data_model_list,
                               model_page=model_page,
                               page=page, 
                               total_model_pages=total_model_pages,
                               total_pages=total_pages,
                               model_limit=model_limit, 
                               limit=limit,
                               pagination_base_url=pagination_base_url,
                               query_params=query_params,
                               pagination_base_url_model=pagination_base_url_model,
                               query_params_model=query_params_model,
                               )
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for("admin_login"))
        

@app.route("/dashboard")
def dashboard():
    if "username" in session:
        remarks = list(remark_collection.find({}))  # Fetch all remarks from MongoDB
        urgent_remarks = [r for r in remarks if r.get('urgent')]
        non_urgent_remarks = [r for r in remarks if not r.get('urgent')]
        help_request = list(collection.find({}))
        change = list(change_collection.find({}))
        refund = list(refund_collection.find({}))

        
        return render_template("dashboard.html", 
                               username=session["username"], 
                               remarks_count=len(non_urgent_remarks), 
                               urgent_remarks_count=len(urgent_remarks),
                               help_request_count=len(help_request),
                               change_count = len(change),
                               refund_count=len(refund)
                               )
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for("admin_login"))


@app.route('/change-form', methods=['GET', 'POST'])
def change_form():
    if 'username' not in session:
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        # data = request.json
        # collection = "refund" if data.get("collectBack") else "change"
        
        # dashboard_db[collection].insert_one(data)

        # print(data)
        # print(dashboard_db[collection])

        data = {
        "user": request.form.get("user"),
        "company": request.form.get("companyName"),
        "date": request.form.get("date"),
        "month": request.form.get("month"),
        "year": request.form.get("year"),
        "premises": request.form.getlist("premises"),
        "devices": request.form.getlist("devices"),
        "change_scent": request.form.get("changeScent") == "on",
        "change_scent_to": request.form.get("changeScentText"),
        "redo_settings": request.form.get("redoSettings") == "on",
        "reduce_intensity": request.form.get("reduceIntensity") == "on",
        "increase_intensity": request.form.get("increaseIntensity") == "on",
        "move_device": request.form.get("moveDevice") == "on",
        "move_device_to": request.form.get("moveDeviceText"),
        "relocate_device": request.form.get("relocateDevice") == "on",
        "relocate_device_to": request.form.get("relocateDeviceDropdown"),
        "collect_back": request.form.get("collectBack") == "on",
        "remark": request.form.get("remark"),
        "submitted_at": datetime.now()
        }

        print(data)

        if data["collect_back"]:
            refund_collection.insert_one(data)
            log_activity(session["username"],"collected back : " +str(data['premises']) + str(data['devices']),logs_collection)
        else:
            change_collection.insert_one(data)
            log_activity(session["username"],"updated settings : " +str(data['premises']) + str(data['devices']),logs_collection)


        # return jsonify({"message": "Form submitted successfully!"}), 200
        flash("Data updated", "success")

        return redirect(url_for("dashboard"))

    companies = services_collection.distinct('company')
    premises = services_collection.distinct('Premise Name')
    devices = services_collection.distinct('Model')

    # premises = services_collection.distinct('Premise Name', {'company': company_name})


    return render_template(
        'change-form.html',
        username=session.get('username'),
        companies=companies,
        premises=premises,
        devices=devices,
        current_date=datetime.now().strftime('%Y-%m-%d')
    )

@app.route('/remarks/<remark_type>')
def view_remarks(remark_type):
    if 'username' not in session:
        return redirect(url_for('admin_login'))
    is_urgent = True if remark_type == 'urgent' else False
    remarks = list(remark_collection.find({'urgent': is_urgent}))
    log_activity(session["username"],"added remarks : " +str(remarks),logs_collection)

    return render_template('view_remarks.html', remarks=remarks, remark_type=remark_type)

@app.route("/logout")
def logout():
    if "user_id" in session:
        try:
            log_activity(session["username"],"logout" ,logs_collection)
        except Exception as e:
            pass
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("index"))

@app.route("/client-login", methods=["GET", "POST"])
def client_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        # Query MongoDB for the user
        user = login_cust_collection.find_one({"email": email})

        if user and check_password_hash(user["password"], password):  # Assuming passwords are hashed
            # Set session for the logged-in user
            session["user_id"] = str(user["_id"])
            session["customer_email"] = user["email"]
            flash("Login successful!", "success")
            return redirect(url_for("customer_form"))  # Redirect to the dashboard
        else:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("index"))

    return render_template("index.html")

@app.route('/image/<image_id>')
def get_image(image_id):
    """Route to retrieve and display an image from GridFS"""
    image = fs.get(ObjectId(image_id))  # Fetch the image from GridFS
    return send_file(image, mimetype='image/jpeg')  # Return the image as a response

#Getting the image later on frontend
#<img src="{{ url_for('get_image', image_id=case['image_id']) }}" alt="Case Image" />

@app.route('/new-customer',methods=['GET', 'POST'])
def new_customer():
    if 'username' not in session:
        return redirect(url_for('admin_login'))
    if request.method == "POST":
        # Extract and format date
        date_str = request.form.get("dateCreated")
        dateCreated = datetime.strptime(date_str, "%Y-%m-%d") if date_str else None  

        companyName = request.form.get("companyName")
        industry = request.form.get("industry")

        # Initialize lists
        premises = []
        pic_records = []
        device_records = []
        master_list = []

        # Extract premise details
        premise_name = request.form.get('premiseName')
        premise_area = request.form.get('premiseArea')
        premise_address = request.form.get('premiseAddress')
        contact_premise = request.form.get('contactPremise')

        if premise_name and premise_area and premise_address:
            premise_record = {
                "company": companyName,
                "month_year": dateCreated,
                "industry": industry,
                "premise_name": premise_name,
                "premise_area": premise_area,
                "premise_address": premise_address,
                "contact_premise": contact_premise,
                "created_at": datetime.now(),
            }
            premises.append(premise_record)
            master_list.append(premise_record)

            # Extract and store each PIC as a separate record
            i = 1
            while True:
                pic_name = request.form.get(f'picName{i}')
                pic_designation = request.form.get(f'picDesignation{i}')
                pic_contact = request.form.get(f'picContact{i}')
                pic_email = request.form.get(f'picEmail{i}')

                if not pic_name:
                    break

                pic_records.append({
                    "company": companyName,
                    "premise_name": premise_name,
                    "name": pic_name,
                    "designation": pic_designation,
                    "contact": pic_contact,
                    "email": pic_email,
                    "created_at": datetime.now(),
                })
                i += 1  # Move to the next PIC

            # Extract and store each device with ALL schedules inside
            j = 1
            while True:
                device_location = request.form.get(f'deviceLocation{j}')
                device_sn = request.form.get(f'deviceSN{j}')
                device_model = request.form.get(f'deviceModel{j}')
                device_colour = request.form.get(f'deviceColour{j}')
                device_volume = request.form.get(f'deviceVolume{j}')
                device_scent = request.form.get(f'deviceScent{j}')

                if not device_sn:
                    break

                device_record = {
                    "company": companyName,
                    "premise_name": premise_name,
                    "location": device_location,
                    "S/N": device_sn,
                    "Model": device_model,
                    "Color": device_colour,
                    "Volume": device_volume,
                    "Current EO": device_scent,
                    "E1 - DAYS": request.form.get("E1Days"),
                    "E1 - START": request.form.get("E1StartTime"),
                    "E1 - END": request.form.get("E1EndTime"),
                    "E1 - PAUSE": request.form.get("E1Pause"),
                    "E1 - WORK": request.form.get("E1Work"),
                    "E2 - DAYS": request.form.get("E2Days"),
                    "E2 - START": request.form.get("E2StartTime"),
                    "E2 - END": request.form.get("E2EndTime"),
                    "E2 - PAUSE": request.form.get("E2Pause"),
                    "E2 - WORK": request.form.get("E2Work"),
                    "E3 - DAYS": request.form.get("E3Days"),
                    "E3 - START": request.form.get("E3StartTime"),
                    "E3 - END": request.form.get("E3EndTime"),
                    "E3 - PAUSE": request.form.get("E3Pause"),
                    "E3 - WORK": request.form.get("E3Work"),
                    "E4 - DAYS": request.form.get("E4Days"),
                    "E4 - START": request.form.get("E4StartTime"),
                    "E4 - END": request.form.get("E4EndTime"),
                    "E4 - PAUSE": request.form.get("E4Pause"),
                    "E4 - WORK": request.form.get("E4Work"),
                    "created_at": datetime.now(),
                }
                device_records.append(device_record)
                master_list.append(device_record)


                j += 1  # Move to the next device

        # Debugging
        print("Premises:", premises)
        print("PIC Records:", pic_records)
        print("Device Records:", device_records)
        print("Master:",master_list)

        # Insert into MongoDB
        if premises:
            profile_list_collection.insert_many(premises)

        if pic_records:
            profile_list_collection.insert_many(pic_records)  # Store PICs separately

        if device_records:
            device_list_collection.insert_many(device_records)  # Store devices with schedules in the same document
        if master_list:
            test_collection.insert_many(device_records)  # Store devices with schedules in the same document
        
        log_activity(session["username"],"added new customer : " +str(companyName),logs_collection)

        flash(f"Company {companyName} added successfully!", "success")

        return redirect(url_for("dashboard"))

    return render_template('new-customer.html')



@app.route('/pre-service')
def pre_service():
    if "username" in session:

        # log_activity(session["username"],"pre-service : " +str(remarks),logs_collection)

        return render_template('pre-service.html')
    else:
        return redirect(url_for('admin_login'))

    
@app.route('/service')
def service():
    if "username" in session:
        # log_activity(session["username"],"service : " +str(remarks),logs_collection)

        return render_template('service.html')
    else:
        return redirect(url_for('admin_login'))


@app.route('/remark', methods=['GET', 'POST'])
def remark():
    if 'username' not in session:
        return redirect(url_for('admin_login'))

    username = session['username']  # Get the logged-in user's username
    if request.method == 'POST':
        remark_text = request.form['remark']
        is_urgent = 'urgent' in request.form  # Checkbox value
        
        # Push data to MongoDB
        log_activity(session["username"],"added remarks : " +str(remark_text),logs_collection)

        remark_collection.insert_one({
            'username': username,
            'remark': remark_text,
            'urgent': is_urgent
        })
        return redirect(url_for('dashboard'))

    return render_template('remark.html', username=username)

# @app.route('/get-devices', methods=['GET'])
# def get_devices():
#     company_name = request.args.get('companyName')
#     if not company_name:
#         return jsonify({"devices": []}), 400

#     # Find devices associated with the company
#     devices = services_collection.find({"Premise Name": company_name}, {"Model": 1})
#     devices = [device["Model"] for device in devices if "Model" in device]

#     return jsonify({"devices": devices}), 200

@app.route("/get-devices")
def get_devices():
    premise_name = request.args.get("premiseName")
    devices = services_collection.find({"Premise Name": premise_name})
    devices_list = [device["Model"] for device in devices]
    return jsonify({"devices": devices_list})

@app.route("/get_companies", methods=["GET"])
def get_companies():
    companies = services_collection.find({}, {"company": 1, "_id": 0})
    unique_companies = sorted({company.get("company") for company in companies if "company" in company})
    return jsonify(unique_companies)



@app.route("/get_essential_oils", methods=["GET"])
def get_essential_oils():
    essential_oils = eo_pack_collection.find({}, {"eo_name": 1, "_id": 0})
    return jsonify([eo["eo_name"] for eo in essential_oils])

# @app.route("/get_premises", methods=["POST"])
# def get_premises():
#     company_name = request.json.get("company_name")
#     company = services_collection.find_one({"name": company_name})
#     return jsonify(company.get("Premise Name", [])) if company else jsonify([])

# @app.route("/get_premises", methods=["GET"])
# def get_premises():
#     company_name = request.args.get("company_name")
#     if not company_name:
#         return jsonify([])  # Return an empty list if no company is selected
    
#     # Find premises for the selected company
#     premises = services_collection.find(
#         {"company": company_name},  # Filter by the selected company
#         {"premise": 1, "_id": 0}   # Fetch only the premise field
#     )
    
#     # Extract unique premises
#     unique_premises = sorted({premise.get("Premise Name") for premise in premises if "Premise Name" in premise})
#     return jsonify(unique_premises)

@app.route("/get-premises")
def get_premises():
    company_name = request.args.get("companyName")
    premises = services_collection.find({"company": company_name})
    premises_list = [premise["Premise Name"] for premise in premises]
    return jsonify({"premises": premises_list})

@app.route("/get_devices_post", methods=["POST"])
def get_devices_post():
    premise = request.json.get("premise")
    company_name = request.json.get("company_name")
    company = services_collection.find_one({"name": company_name})
    premises = company.get("Premise Name", []) if company else []
    for p in premises:
        if p["name"] == premise:
            return jsonify(p.get("Model", []))
    return jsonify([])

@app.route("/post-service", methods=["POST", "GET"])
def post_service():
    if 'username' not in session:
        return redirect(url_for('admin_login'))

    username = session['username']  # Get the logged-in user's username
    
    if request.method == "POST":
        # Collect data from the form
        essential_oil = request.form.get("essential_oil")
        oil_balance = int(request.form.get("oil_balance"))
        balance_brought_back = int(request.form.get("balance_brought_back"))
        balance_brought_back_percent = request.form.get("balance_brought_back_percent")
        refill_amount = int(request.form.get("refill_amount"))
        refill_amount_percent = request.form.get("refill_amount_percent")
        month_year = datetime.now()

        # Define the query and the update
        query = {"essential_oil": essential_oil}  # Match based on the essential oil
        update = {
            "$set": {
                "oil_balance": oil_balance,
                "balance_brought_back": balance_brought_back,
                "balance_brought_back_percent": balance_brought_back_percent,
                "refill_amount": refill_amount,
                "refill_amount_percent": refill_amount_percent,
                "month_year": month_year
            }
        }

        # Perform the upsert (update or insert if not found)
        eo_pack_collection.update_one(query, update, upsert=True)

        # Log the activity
        log_activity(username, f"Updated/added post-service record for essential oil: {essential_oil}", logs_collection)

        flash(f"Record for {essential_oil} updated successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template('post-service.html', username=username)

@app.route('/view-users', methods=['GET'])
def view_users():
    if 'username' not in session:
        return redirect(url_for('admin_login'))
    
    users = list(login_cust_collection.find({}, {'username': 1,'email':1}))

    page = int(request.args.get('page', 1))  # Current page (default: 1)
    limit = int(request.args.get('limit', 10))  # Entries per page (default: 10)

    username = request.args.get('username')
    email = request.args.get('email')

    query = {}

    # Filter by user
    if username:
        query["username"] = {"$regex": username, "$options": "i"}  # Case-insensitive search

    # Filter by action
    if email:
        query["email"] = {"$regex": email, "$options": "i"}  # Case-insensitive search

    # Pagination logic
    total_list = login_cust_collection.count_documents(query)

    users = list(
        login_cust_collection.find(query, {'username': 1, 'email': 1, '_id': 0})
        .skip((page - 1) * limit)
        .limit(limit)
    )

    total_pages = (total_list + limit - 1) // limit
    base_url = request.path
    query_params = request.args.to_dict()
    query_params['page'] = page
    query_params['limit'] = limit
    pagination_base_url = f"{base_url}?"


    return render_template('view-users.html',users=users,
                           page=page, 
                           total_pages=total_pages,
                           limit=limit,
                           pagination_base_url=pagination_base_url,
                           query_params=query_params,
                           )

@app.route('/view-admins', methods=['GET'])
def view_admins():
    if 'username' not in session:
        return redirect(url_for('admin_login'))
    
    admins = list(login_collection.find({}, {'username': 1}))

    page = int(request.args.get('page', 1))  # Current page (default: 1)
    limit = int(request.args.get('limit', 10))  # Entries per page (default: 10)

    username = request.args.get('username')

    query = {}

    # Filter by user
    if username:
        query["username"] = {"$regex": username, "$options": "i"}  # Case-insensitive search
    
    total_list = login_collection.count_documents(query)

    admins = list(
        login_collection.find(query, {'username': 1,  '_id': 0})
        .skip((page - 1) * limit)
        .limit(limit)
    )

    total_pages = (total_list + limit - 1) // limit
    base_url = request.path
    query_params = request.args.to_dict()
    query_params['page'] = page
    query_params['limit'] = limit
    pagination_base_url = f"{base_url}?"




    return render_template('view-admins.html',admins=admins,
                           page=page, 
                           total_pages=total_pages,
                           limit=limit,
                           pagination_base_url=pagination_base_url,
                           query_params=query_params,
                           )


@app.route('/logs', methods=['GET','POST'])
def get_logs():
    if 'username' not in session:
        return redirect(url_for('admin_login'))

    logs = list(logs_collection.find({}).sort("timestamp", -1)) 
    
    formatted_logs = []
    for log in logs:
        timestamp = log.get("timestamp")
        if isinstance(timestamp, str):  # If timestamp is already a string
            dt_object = datetime.fromisoformat(timestamp)
        elif isinstance(timestamp, datetime):  # If timestamp is a datetime object
            dt_object = timestamp
        else:
            continue  # Skip log if timestamp is invalid
        
        formatted_logs.append({
            "user": log.get("user"),
            "action": log.get("action"),
            "date": dt_object.strftime("%Y-%m-%d"),
            "time": dt_object.strftime("%H:%M:%S")
        })

    page = int(request.args.get('page', 1))  # Current page (default: 1)
    limit = int(request.args.get('limit', 10))  # Entries per page (default: 10)

    date = request.args.get('date','').strip()
    time = request.args.get('time','').strip()
    user = request.args.get('user')
    action = request.args.get('action')

    query = {}

    # Filter by date and time
    if date and time:
        try:
            datetime_start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            datetime_end = datetime_start.replace(second=59)  # Include the entire minute
            query["timestamp"] = {"$gte": datetime_start, "$lte": datetime_end}
        except ValueError:
            pass  # Ignore invalid date/time inputs

    elif date:
        try:
            date_start = datetime.strptime(date, "%Y-%m-%d")
            date_end = date_start.replace(hour=23, minute=59, second=59)  # End of day
            query["timestamp"] = {"$gte": date_start, "$lte": date_end}
        except ValueError:
            pass  # Ignore invalid date inputs

    # Filter by user
    if user:
        query["user"] = {"$regex": user, "$options": "i"}  # Case-insensitive search

    # Filter by action
    if action:
        query["action"] = {"$regex": action, "$options": "i"}  # Case-insensitive search

    # Pagination logic
    total_list = logs_collection.count_documents(query)

    data_logs_list = logs_collection.find(query).sort("timestamp", -1) \
                        .skip((page - 1) * limit) \
                        .limit(limit)

    # Format logs for frontend
    processed_data_logs_list = []
    for log in data_logs_list:
        timestamp = log.get("timestamp")
        if isinstance(timestamp, datetime):
            log["date"] = timestamp.strftime("%Y-%m-%d")
            log["time"] = timestamp.strftime("%H:%M:%S")
        processed_data_logs_list.append(log)

    # Pagination details
    total_pages = (total_list + limit - 1) // limit
    base_url = request.path
    query_params = request.args.to_dict()
    query_params['page'] = page
    query_params['limit'] = limit
    pagination_base_url = f"{base_url}?"
    
    
    return render_template('activity-log.html', 
                            username=session["username"],
                            logs=formatted_logs,
                            data=processed_data_logs_list,
                            page=page, 
                            total_pages=total_pages,
                            limit=limit,
                            pagination_base_url=pagination_base_url,
                            query_params=query_params,
                           )




@app.route('/new-customer-submit', methods=['POST','GET'])
def new_customer_submit():
    # Extract company information
    company_name = request.form.get("companyName")
    # contact_info = request.form.get("contact_info")

    # Extract premises data (assuming multiple premises can be submitted as comma-separated values)
    premises = request.form.getlist("premises[]")  # Using getlist for multiple premises

    # Extract devices data (assuming devices are tied to premises)
    devices = request.form.getlist("devices[]")  # Using getlist for multiple devices

    contact_info = request.form.getlist("contacts[]")

    # if not company_name or not premises:
    #     return jsonify({"error": "Company name and premises are required!"}), 400

    # Push premises to MongoDB
    for premise in premises:
        for i in contact_info:
            premise_record = {
                "company_name": company_name,
                "contact_info": i,
                "premise": premise,
            }
        test_db["premises"].insert_one(premise_record)

    # Push devices to MongoDB
    for device in devices:
        # Here, you can split the device details to tie them to the respective premise if needed
        device_record = {
            "company_name": company_name,
            "device_name": device,
        }
        test_db["devices"].insert_one(device_record)

    return jsonify({"message": "Data successfully submitted!"}), 200

if __name__ == "__main__":
    app.run(debug=True)
