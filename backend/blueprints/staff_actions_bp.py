# backend/blueprints/staff_actions_bp.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from werkzeug.utils import secure_filename
from datetime import datetime
from bson import ObjectId # Make sure ObjectId is imported if used for _id string conversion (though not explicitly in this snippet)

from ..col import collection # Customer cases/complaints
# For fs, mail and other utils, it's better if they are registered with the app and accessed via current_app or specific getters
from backend import fs as main_fs_instance # GridFS instance from main app (e.g. backend/__init__.py or app.py)
# from ..app import mail as main_mail_instance # If mail is needed in this blueprint

staff_actions_bp = Blueprint(
    'staff',
    __name__,
    template_folder='../templates', # Points to backend/templates
    static_folder='../static',     # Points to backend/static
    url_prefix='/staff'
)

# Helper to check admin session
def is_admin_logged_in():
    return 'username' in session

@staff_actions_bp.before_request
def require_admin_login():
    # Protect all routes in this blueprint
    if not is_admin_logged_in():
        flash("You must be logged in as an admin to access this page.", "warning")
        return redirect(url_for('auth.admin_login')) # Redirect to auth blueprint's admin_login

@staff_actions_bp.route("/api/case/<int:case_no>", methods=["GET"])
def get_case_details(case_no):
    # This route is protected by before_request, so admin is logged in.
    case_data = collection.find_one({"case_no": case_no}, {"_id": 0}) # Exclude ObjectId
    if not case_data:
        return jsonify({"error": "Case not found"}), 404
    return jsonify(case_data)

@staff_actions_bp.route("/help/<int:case_no>", methods=["GET", "POST"]) # was /staff-help/
def staff_form(case_no):
    # This route is protected by before_request, so admin is logged in.
    case_data = collection.find_one({"case_no": case_no})
    if not case_data:
        flash(f"Case #{case_no} not found!", "danger")
        return redirect(url_for("data_reports.view_complaints_list", _external=True) if 'data_reports.view_complaints_list' in current_app.view_functions else url_for("dashboard", _external=True))


    if request.method == "POST":
        actions_done = request.form.getlist("actions")
        remarks = request.form.get("remarks", "")
        case_closed = request.form.get("case_closed")
        revisit_date = request.form.get("appointment_date")
        revisit_time = request.form.get("appointment_time")
        staff_name = request.form.get("staff_name", session.get("username")) # Default to logged-in admin
        signature_data = request.form.get("signature")

        image_id = case_data.get("image_id")
        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename:
                # Consider deleting old image from GridFS if one exists (fs.delete(old_image_id))
                # For now, just adds new image, potentially orphaning old one.
                image_id = main_fs_instance.put(file.read(), filename=secure_filename(file.filename), content_type=file.content_type)

        if case_closed == "Yes":
            collection.delete_one({"case_no": case_no})
            flash(f"Case #{case_no} has been closed and removed.", "success")
            # Redirect to a list of help requests. Assuming 'view_help' will be in a 'data_reports' blueprint.
            # If 'data_reports.view_help' isn't set up, this will error. Fallback to dashboard.
            target_url = url_for("dashboard") # Default fallback
            try:
                # This is a forward reference, will only work if data_reports_bp is registered and has view_complaints_list
                target_url = url_for('data_reports.view_complaints_list')
            except Exception: # pylint: disable=broad-except
                flash("Redirecting to dashboard as case list view is not available.", "info")
            return redirect(target_url)

        update_fields = {
            "actions_done": actions_done,
            "remarks": remarks,
            "case_closed": case_closed, # Should be "No" if not "Yes"
            "revisit_date": revisit_date if case_closed == "No" else "",
            "revisit_time": revisit_time if case_closed == "No" else "",
            "staff_name": staff_name,
            "updated_at": datetime.now(),
            "image_id": image_id,
            "signature": signature_data
        }
        collection.update_one({"case_no": case_no}, {"$set": update_fields})

        flash(f"Case #{case_no} updated successfully!", "success")
        return redirect(url_for(".staff_form", case_no=case_no)) # Redirect to the same form to see updates

    # Ensure _id is a string for template if it's used (e.g. in hidden fields for some JS)
    if "_id" in case_data:
        case_data["_id_str"] = str(case_data["_id"]) # Pass as new key to avoid type issues with original ObjectId

    return render_template("staff-complaint-form.html", case_no=case_no, case_data=case_data)
