import smtplib
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
from bson import json_util


app = Flask(__name__)

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


fs = gridfs.GridFS(db)



app.config['MAIL_SERVER'] = os.getenv('SMTP_GOOGLE_SERVER')
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = False
# app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('SMTP_GOOGLE')
app.config['MAIL_PASSWORD'] = os.getenv('SMTP_APP_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)

# Routes
@app.route("/customer-help", methods=["GET", "POST"])
def customer_form():
    """Form for customers to create new cases."""
    if "customer_email" not in session:
        return redirect(url_for("client_login"))  # Redirect to login if not logged in

    user_email = session["customer_email"] 
    if request.method == "POST":
        # Auto-increment case number
        case_no = collection.count_documents({}) + 1

        # Extract customer form data
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
    send_email(user_email, subject, body)


def send_email_to_admin(case_no):
    """Notify admin about a new case creation."""
    subject = f"New Case #{case_no} Created"
    body = f"A new case with case number #{case_no} has been created. Please check the system for details."
    send_email(app.config['MAIL_USERNAME'], subject, body)


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

def send_email(to_email, subject, body):
    """Generic function to send an email using Flask-Mail."""
    try:
        msg = Message(subject, recipients=[to_email])
        msg.body = body
        mail.send(msg)
    except Exception as e:
        print(f"Failed to send email: {e}")

@app.route('/register', methods=['GET', 'POST'])
def register():
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
        return redirect(url_for('index'))

    return render_template('register.html')


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
            return redirect(url_for("dashboard"))  # Redirect to the dashboard
        else:
            flash("Invalid username or password.", "danger")
            return redirect(url_for("admin_login"))

    return render_template("login.html")

@app.route('/all-list',methods=['GET'])
def reports():
    if 'user_id' in session:
        # Pagination parameters
        page = int(request.args.get('page', 1))  # Current page (default: 1)
        limit = int(request.args.get('limit', 10))  # Entries per page (default: 10)


        # Get filter parameters
        month = request.args.get('month','').strip()
        year = request.args.get('year','').strip()
        EO = request.args.get("EO")
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
            query['$expr'] = {
                '$and': [
                    {'$eq': [{'$month': '$month_year'}, int(month)]},
                    {'$eq': [{'$year': '$month_year'}, int(year)]}
                ]
            }
        
       
        
        # Filter by EO (string partial match)

        if EO:
            query['EO'] = {'$regex': EO, '$options': 'i'}  # Case-insensitive partial match


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
            query['Colour'] = {'$regex': Colour, '$options': 'i'}  # Case-insensitive partial match

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
            processed_data.append(entry)


        # Calculate total pages
        total_pages = (total_entries + limit - 1) // limit
        
        return render_template("reports.html", 
                               username=session["username"], 
                               data=processed_data, 
                               page=page, 
                               total_pages=total_pages,
                               limit=limit
                               )
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for("login"))

@app.route('/pack-list',methods=['GET'])
def pack_list():
    if 'user_id' in session:
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
            device_query['$expr'] = {
                '$and': [
                    {'$eq': [{'$month': '$month_year'}, int(device_month)]},
                    {'$eq': [{'$year': '$month_year'}, int(device_year)]}
                ]
            }
        if month and year:
            query['$expr'] = {
                '$and': [
                    {'$eq': [{'$month': '$month_year'}, int(month)]},
                    {'$eq': [{'$year': '$month_year'}, int(year)]}
                ]
            }
        if bottle_month and bottle_year:
            bottle_query['$expr'] = {
                '$and': [
                    {'$eq': [{'$month': '$month_year'}, int(bottle_month)]},
                    {'$eq': [{'$year': '$month_year'}, int(bottle_year)]}
                ]
            }
       
        if straw_month and straw_year:
            other_query['$expr'] = {
                '$and': [
                    {'$eq': [{'$month': '$month_year'}, int(straw_month)]},
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
                               limit=limit
                               )
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for("login"))
    
@app.route('/eo-list',methods=['GET'])
def eo_list():
    if 'user_id' in session:
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
            model_query['$expr'] = {
                '$and': [
                    {'$eq': [{'$month': '$month_year'}, int(model_month)]},
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
            query['$expr'] = {
                '$and': [
                    {'$eq': [{'$month': '$month_year'}, int(month)]},
                    {'$eq': [{'$year': '$month_year'}, int(year)]}
                ]
            }
        if eo:
            query['EO2'] = {'$regex': eo, '$options': 'i'} 
        if volume:
            query['Volume'] = int(volume)

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
                               limit=limit
                               )
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for("login"))
        

@app.route("/dashboard")
def dashboard():
    if "user_id" in session:
        remarks = list(remark_collection.find({}))  # Fetch all remarks from MongoDB
        urgent_remarks = [r for r in remarks if r.get('urgent')]
        non_urgent_remarks = [r for r in remarks if not r.get('urgent')]
        
        return render_template("dashboard.html", 
                               username=session["username"], 
                               remarks_count=len(non_urgent_remarks), 
                               urgent_remarks_count=len(urgent_remarks)
                               )
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for("login"))



@app.route('/remarks/<remark_type>')
def view_remarks(remark_type):
    is_urgent = True if remark_type == 'urgent' else False
    remarks = list(remark_collection.find({'urgent': is_urgent}))
    return render_template('view_remarks.html', remarks=remarks, remark_type=remark_type)

@app.route("/logout")
def logout():
    if "user_id" in session:
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
            return redirect(url_for("client_login"))

    return render_template("client-login.html")

@app.route('/image/<image_id>')
def get_image(image_id):
    """Route to retrieve and display an image from GridFS"""
    image = fs.get(ObjectId(image_id))  # Fetch the image from GridFS
    return send_file(image, mimetype='image/jpeg')  # Return the image as a response

#Getting the image later on frontend
#<img src="{{ url_for('get_image', image_id=case['image_id']) }}" alt="Case Image" />

@app.route('/new-client')
def new_customer():
    if "user_id" in session:
        return render_template('new-customer.html')

@app.route('/pre-service')
def pre_service():
    if "user_id" in session:
        return render_template('pre-service.html')
    
@app.route('/service')
def service():
    if "user_id" in session:
        return render_template('service.html')


@app.route('/remark', methods=['GET', 'POST'])
def remark():
    if 'username' not in session:
        return redirect(url_for('admin_login'))

    username = session['username']  # Get the logged-in user's username
    if request.method == 'POST':
        remark_text = request.form['remark']
        is_urgent = 'urgent' in request.form  # Checkbox value
        
        # Push data to MongoDB
        remark_collection.insert_one({
            'username': username,
            'remark': remark_text,
            'urgent': is_urgent
        })
        return redirect(url_for('dashboard'))

    return render_template('remark.html', username=username)

if __name__ == "__main__":
    app.run(debug=True)
