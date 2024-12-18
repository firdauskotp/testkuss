from flask import Flask, render_template, request, redirect, url_for, flash
from flask_pymongo import PyMongo
from flask_mail import Mail, Message
from datetime import datetime

app = Flask(__name__)
app.config['MONGO_URI'] = '<MONGO_URI>'  # Replace with your MongoDB connection string
app.config['SECRET_KEY'] = 'secretkey'

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your-password'

mongo = PyMongo(app)
mail = Mail(app)

@app.route("/", methods=["GET", "POST"])
def case_form():
    case_details = mongo.db.cases.find_one()  # Fetch the latest case details from DB
    if request.method == "POST":
        # Form Data
        case_no = case_details['case_no']
        actions = request.form.getlist('actions')
        remarks = request.form['remarks']
        revisit_date = request.form['revisit_date']
        staff_name = request.form['staff_name']
        signature = request.files['signature']

        # Save Data
        mongo.db.cases.update_one(
            {"case_no": case_no},
            {"$set": {
                "actions": actions,
                "remarks": remarks,
                "revisit_date": revisit_date,
                "staff_name": staff_name,
                "updated_at": datetime.now()
            }}
        )

        # Send Email Notification
        msg = Message("Appointment Details Saved", sender="your-email@gmail.com", recipients=["team-email@example.com"])
        msg.body = f"""
        Case No: {case_no}
        Remarks: {remarks}
        Actions: {', '.join(actions)}
        Staff Name: {staff_name}
        Revisit Date: {revisit_date}
        """
        mail.send(msg)

        flash("Case details saved and notification sent!", "success")
        return redirect(url_for("case_form"))

    return render_template("complaint-form.html", case=case_details)

if __name__ == "__main__":
    app.run(debug=True)
