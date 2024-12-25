from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_pymongo import MongoClient
from werkzeug.security import check_password_hash
from flask_mail import Mail, Message
from datetime import datetime
import certifi  # Only needed for Mac

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secretkey'

# MongoDB Configuration
MONGO_URI = 'mongodb+srv://firdauskotp:stayhumbleeh@cluster0.msdva.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
mongo = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = mongo['customer']
collection = db['case_issue']

login_db=mongo['login_admin']
login_collection=login_db['log']

login_cust_db=mongo['login_cust']
login_cust_collection=login_cust_db['logg']

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'firdausbeacon@gmail.com'
app.config['MAIL_PASSWORD'] = 'ChihiroBlaiddyd2019'
mail = Mail(app)

# Routes
@app.route("/customer-help", methods=["GET", "POST"])
def customer_form():
    """Form for customers to create new cases."""
    if request.method == "POST":
        # Extract customer form data
        case_no = db.case_issue.count_documents({}) + 1
        premise_name = request.form.get("premise_name")
        location = request.form.get("location")
        serial_number = request.form.get("serial_number")
        model = request.form.get("model")
        issues = request.form.getlist("issues")
        remarks = request.form.get("remarks", "")

        # Insert new case
        db.case_issue.insert_one({
            "case_no": case_no,
            "premise_name": premise_name,
            "location": location,
            "serial_number": serial_number,
            "model": model,
            "issues": issues,
            "remarks": remarks,
            "revisit_date": None,
            "staff_name": None,
            "signature": None,
            "created_at": datetime.now(),
            "updated_at": None,
        })

        flash(f"New case #{case_no} created successfully!", "success")
        return redirect(url_for("customer_form"))

    return render_template("customer-complaint-form.html")


@app.route("/staff-help/<int:case_no>", methods=["GET", "POST"])
def staff_form(case_no):
    """Form for staff to update and manage cases."""
    case_details = db.case_issue.find_one({"case_no": case_no})
    if not case_details:
        flash(f"Case #{case_no} not found!", "danger")
        return redirect(url_for("customer_form"))

    if request.method == "POST":
        # Extract staff form data
        actions = request.form.getlist("actions")
        remarks = request.form.get("remarks", "")
        revisit_date = request.form.get("revisit_date", None)
        staff_name = request.form.get("staff_name", "")
        signature = request.files.get("signature")

        # Save signature file if uploaded
        signature_path = None
        if signature:
            signature_path = f"static/uploads/{case_no}_signature.png"
            signature.save(signature_path)

        # Update case
        db.case_issue.update_one(
            {"case_no": case_no},
            {"$set": {
                "actions": actions,
                "remarks": remarks,
                "revisit_date": revisit_date,
                "staff_name": staff_name,
                "signature": signature_path,
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

    return render_template("staff-complaint-form.html", case=case_details)

@app.route("/")
def index():
    return render_template("index.html")

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



if __name__ == "__main__":
    app.run(debug=True)
