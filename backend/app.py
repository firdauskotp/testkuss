from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_pymongo import MongoClient
from werkzeug.security import check_password_hash
from flask_mail import Mail, Message
from datetime import datetime
import certifi  # Only needed for Mac
from werkzeug.utils import secure_filename
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.security import generate_password_hash
import gridfs


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secretkey'

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# MongoDB Configuration
MONGO_URI = 'mongodb+srv://firdauskotp:stayhumbleeh@cluster0.msdva.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
mongo = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = mongo['customer']
collection = db['case_issue']

login_db=mongo['login_admin']
login_collection=login_db['log']

login_cust_db=mongo['login_cust']
login_cust_collection=login_cust_db['logg']

fs = gridfs.GridFS(db)

# Configure email settings
SMTP_SERVER = "your_smtp_server"
SMTP_PORT = 587
SMTP_USERNAME = "firdausbeacon@gmail.com"
SMTP_PASSWORD = ""

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'firdausbeacon@gmail.com'
app.config['MAIL_PASSWORD'] = ''
mail = Mail(app)

# Routes
@app.route("/customer-help", methods=["GET", "POST"])
def customer_form():
    """Form for customers to create new cases."""
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
            "created_at": datetime.now(),
        })

        # Send emails to the customer and admin
        send_email_to_customer(case_no)
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
        msg = Message("Case Updated", sender="firdausbeacon@gmail.com", recipients=["team-email@example.com"])
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

@app.route("/case-success/<int:case_no>")
def case_success(case_no):
    """Success page after creating a case."""
    return render_template("case-success.html", case_no=case_no)


def send_email_to_customer(case_no):
    """Send a confirmation email to the customer."""
    subject = f"Case #{case_no} Created Successfully"
    body = f"Thank you for submitting your case. Your case number is #{case_no}. Our staff will get in touch with you shortly."
    send_email("customer_email@example.com", subject, body)


def send_email_to_admin(case_no):
    """Notify admin about a new case creation."""
    subject = f"New Case #{case_no} Created"
    body = f"A new case with case number #{case_no} has been created. Please check the system for details."
    send_email("admin_email@example.com", subject, body)


def send_email(to_email, subject, body):
    """Generic function to send an email."""
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USERNAME
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Failed to send email: {e}")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Hash the password
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

        # Store the username and hashed password in MongoDB
        login_cust_collection.insert_one({'username': username, 'password': hashed_password})
        
        flash("User registered successfully!", "success")
        return redirect(url_for('index'))
    
    
    return render_template('register.html')

@app.route('/new_customer', methods=['GET'])
def new_customer():
    return render_template('new-customer.html') 

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

@app.route("/dashboard")
def dashboard():
    if "user_id" in session:
        return render_template("dashboard.html", username=session["username"])
    else:
        flash("Please log in to access the dashboard.", "warning")
        return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))

@app.route("/client-login", methods=["GET", "POST"])
def client_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Query MongoDB for the user
        user = login_cust_collection.find_one({"username": username})

        if user and check_password_hash(user["password"], password):  # Assuming passwords are hashed
            # Set session for the logged-in user
            session["user_id"] = str(user["_id"])
            session["username"] = user["username"]
            flash("Login successful!", "success")
            return redirect(url_for("customer_form"))  # Redirect to the dashboard
        else:
            flash("Invalid username or password.", "danger")
            return redirect(url_for("client_login"))

    return render_template("client-login.html")

@app.route('/image/<image_id>')
def get_image(image_id):
    """Route to retrieve and display an image from GridFS"""
    image = fs.get(ObjectId(image_id))  # Fetch the image from GridFS
    return send_file(image, mimetype='image/jpeg')  # Return the image as a response

#Getting the image later on frontend
#<img src="{{ url_for('get_image', image_id=case['image_id']) }}" alt="Case Image" />


if __name__ == "__main__":
    app.run(debug=True)
