# backend/blueprints/api_helpers_bp.py
from flask import Blueprint, request, jsonify, current_app, send_file, render_template, Response, session, redirect, url_for, flash
import io # For send_file with BytesIO for GridFS
from bson import ObjectId # For GridFS file IDs
from werkzeug.utils import secure_filename # Though not used in these specific routes, good for general API file handling
from datetime import datetime # Though not used in these specific routes

from backend import fs # GridFS instance from main app, changed from `from .. import fs`
from ..col import (
    services_collection, model_list_collection, eo_pack_collection,
    device_list_collection, profile_list_collection, change_collection
)
# Note: 'collection' (complaint_collection) was not used by the routes moved here.
# 'logs_collection' was not used by the routes moved here.
# 'route_list_collection' was not used by the routes moved here.
# 'safe_int' was not used by the routes moved here.
# 'log_activity' was not used by the routes moved here.


api_helpers_bp = Blueprint(
    'api_helpers',
    __name__,
    template_folder='../templates', # For render_template used in get_client_details, etc.
    static_folder='../static',
    url_prefix='/api' # All routes here will be prefixed with /api
)

# Helper to check admin session
def is_admin_logged_in():
    return 'username' in session

@api_helpers_bp.before_request
def require_admin_login():
    # Protect all routes in this blueprint by default
    # Specific public routes would need to be handled differently if any exist
    # (e.g. by checking request.endpoint against a list of public endpoints)
    if not is_admin_logged_in():
        # For API routes, returning a JSON error is often preferred over redirecting to HTML login page
        # However, if these are typically called by frontend JS that expects a redirect on auth failure,
        # then a redirect might be what the existing frontend JS expects.
        # The other admin blueprints redirect to 'auth.admin_login'. Let's be consistent.
        flash("Admin access required for this API.", "warning")
        return redirect(url_for('auth.admin_login')) # Or return jsonify(error="Unauthorized"), 401/403

@api_helpers_bp.route('/update-data', methods=['POST'])
def update_data():
    data = request.get_json()
    record_id = data.pop('sn') # Assuming 'sn' is the S/N to match services_collection
    # Ensure record_id is converted to the correct type if necessary, e.g., int
    try:
        record_id_int = int(record_id)
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid S/N format'}), 400

    result = services_collection.update_one({'S/N': record_id_int}, {'$set': data})
    if result.modified_count > 0:
        return jsonify({'success': True})
    else:
        # Could also indicate 'not found' if that's distinguishable from 'no change'
        return jsonify({'success': False, 'message': 'Record not found or no changes made'})

@api_helpers_bp.route('/image2/<image_id>')
def get_image2(image_id):
    try:
        image_object_id = ObjectId(image_id)
        image_file = fs.get(image_object_id)
        return send_file(io.BytesIO(image_file.read()), mimetype='image/jpeg') # Original specified jpeg
    except Exception as e:
        # Log error e
        return jsonify({"error": "Image not found or error retrieving image"}), 404

@api_helpers_bp.route("/image/<file_id>")
def get_image(file_id):
    try:
        image_object_id = ObjectId(file_id)
        image_file = fs.get(image_object_id)
        return send_file(io.BytesIO(image_file.read()), mimetype=image_file.content_type)
    except Exception as e:
        return jsonify({"error": "Image not found or error retrieving image"}), 404

@api_helpers_bp.route("/signature/<file_id>")
def get_signature(file_id):
    try:
        sig_object_id = ObjectId(file_id)
        sig_file = fs.get(sig_object_id)
        return send_file(io.BytesIO(sig_file.read()), mimetype=sig_file.content_type)
    except Exception as e:
        return jsonify({"error": "Signature not found or error retrieving image"}), 404

@api_helpers_bp.route("/device-image/<image_id>")
def get_device_image(image_id):
    try:
        image_object_id = ObjectId(image_id)
        image_file = fs.get(image_object_id)
        return Response(image_file.read(), mimetype=image_file.content_type)
    except Exception as e:
        # Log error e
        return jsonify({"error": "Device image not found"}), 404

@api_helpers_bp.route('/get-models/<premise>')
def get_models(premise):
    # This used services_collection in original app.py
    models_cursor = services_collection.find({"Premise Name": premise}, {"Model": 1, "_id": 0})
    return jsonify([m['Model'] for m in models_cursor if 'Model' in m])

@api_helpers_bp.route('/get-colors/<model>/<premise>')
def get_colors(model, premise):
    colors_cursor = services_collection.find({"Model": model, "Premise Name": premise}, {"Color": 1, "_id": 0})
    unique_colors = list(set(c.get('Color') for c in colors_cursor if c.get('Color')))
    return jsonify(unique_colors)

@api_helpers_bp.route('/get-eo/<model>/<premise>/<color>')
def get_eo(model, premise, color):
    eos_cursor = services_collection.find(
        {"Model": model, "Premise Name": premise, "Color": color},
        {"Current EO": 1, "_id": 0}
    )
    unique_eos = list(set(e.get('Current EO') for e in eos_cursor if e.get('Current EO')))
    return jsonify(unique_eos)

@api_helpers_bp.route("/get-devices1") # Path kept from original
def get_devices1(): # Function name kept from original
    premise_name = request.args.get("premiseName")
    # Original used services_collection, this seems more appropriate for device specific info
    devices_cursor = device_list_collection.find({"tied_to_premise": premise_name}, {"Model":1, "_id":0})
    devices_list = [device["Model"] for device in devices_cursor if "Model" in device]
    return jsonify({"devices": devices_list})

@api_helpers_bp.route("/get_companies", methods=["GET"])
def get_companies():
    # Original used services_collection
    companies_cursor = services_collection.find({}, {"company": 1, "_id": 0})
    unique_companies = sorted(list(set(c.get("company") for c in companies_cursor if c.get("company"))))
    return jsonify(unique_companies)

@api_helpers_bp.route("/get_essential_oils", methods=["GET"])
def get_essential_oils():
    essential_oils_cursor = eo_pack_collection.find({}, {"eo_name": 1, "_id": 0})
    return jsonify([eo["eo_name"] for eo in essential_oils_cursor if "eo_name" in eo])

@api_helpers_bp.route("/get-premises-test") # Path kept from original
def get_premises_test(): # Function name kept from original
    company_name = request.args.get("companyName")
    # Original used services_collection
    premises_cursor = services_collection.find({"company": company_name}, {"Premise Name": 1, "_id":0})
    premises_list = [p["Premise Name"] for p in premises_cursor if "Premise Name" in p]
    return jsonify({"premises": premises_list})

@api_helpers_bp.route("/get_devices_post", methods=["POST"]) # Path kept from original
def get_devices_post(): # Function name kept from original
    premise = request.json.get("premise")
    # company_name = request.json.get("company_name") # This was unused in original effective logic
    # Using device_list_collection as it seems more direct
    devices_cursor = device_list_collection.find({"tied_to_premise": premise}, {"Model":1, "_id":0})
    return jsonify([d["Model"] for d in devices_cursor if "Model" in d])

@api_helpers_bp.route('/get-client-details/<premise_name>')
def get_client_details(premise_name):
    pics_cursor = profile_list_collection.find({"tied_to_premise": premise_name})
    pics = []
    for pic in pics_cursor:
        if '_id' in pic: pic['_id'] = str(pic['_id'])
        pics.append(pic)
    return jsonify(html=render_template("partials/client-details.html", pics=pics))

@api_helpers_bp.route('/get-device-details/<premise_name>')
def get_device_details(premise_name):
    devices_cursor = device_list_collection.find({"tied_to_premise": premise_name})
    devices = []
    for device in devices_cursor:
        if '_id' in device: device['_id'] = str(device['_id'])
        # Convert other ObjectIds if present and needed by template, e.g. image_id
        if 'image_id' in device and isinstance(device['image_id'], ObjectId):
             device['image_id'] = str(device['image_id'])
        devices.append(device)
    return jsonify(html=render_template("partials/device-details.html", devices=devices))

@api_helpers_bp.route('/get-premises/<company>') # Path from original app.py
def get_premises(company):
    # This was used in change-form.html to render a partial template with checkboxes
    premises_names = services_collection.distinct('Premise Name', {'company': company})
    return render_template('partials/premise_checkboxes.html', premises=premises_names)

@api_helpers_bp.route('/get-devices/<premise>') # Path from original app.py
def get_devices(premise): # Used in change-form.html
    # This was used to return a list of device locations (which might be device names or identifiers)
    devices_cursor = device_list_collection.find({'tied_to_premise': premise}, {'location': 1, '_id':0})
    return jsonify({'devices': [d['location'] for d in devices_cursor if 'location' in d]})

@api_helpers_bp.route('/get-eos', methods=['POST']) # Path from original app.py
def get_eos(): # Used in change-form.html
    devices_locations = request.json.get('devices', []) # List of device locations/names
    eos = set()
    # Querying by 'location' assuming 'location' is a unique identifier for devices from device_list_collection
    for d_item in device_list_collection.find({'location': {'$in': devices_locations}}):
        if 'Current EO' in d_item and d_item['Current EO']: # Check if 'Current EO' exists and is not empty
            eos.add(d_item['Current EO'])
    return jsonify({'eos': list(eos)})


@api_helpers_bp.route('/profile/edit/<record_id>', methods=['POST'])
def edit_profile_record(record_id):
    # Individual session check removed, handled by before_request
    data = request.json
    # Prevent editing month and year if these were specific to profile list view and not actual data fields
    # Or, if they are actual data fields, this pop might be removed.
    # Based on original app.py, these were popped.
    if "month" in data: data.pop("month", None)
    if "year" in data: data.pop("year", None)

    try:
        obj_id = ObjectId(record_id)
    except Exception:
        return jsonify({"success": False, "message": "Invalid record ID format"}), 400

    result = profile_list_collection.update_one(
        {"_id": obj_id},
        {"$set": data}
    )
    if result.modified_count > 0:
        return jsonify({"success": True, "message": "Record updated successfully"})
    else:
        # Check if the record exists, maybe data was the same
        if profile_list_collection.count_documents({"_id": obj_id}) > 0:
            return jsonify({"success": True, "message": "No changes detected or record already up-to-date"})
        return jsonify({"success": False, "message": "Record not found or not updated"}), 404

@api_helpers_bp.route('/profile/delete/<record_id>', methods=['POST']) # Using POST for delete as per original JS
def delete_profile_record(record_id):
    # Individual session check removed, handled by before_request
    try:
        obj_id = ObjectId(record_id)
    except Exception:
        return jsonify({"success": False, "message": "Invalid record ID format"}), 400

    result = profile_list_collection.delete_one({"_id": obj_id})
    if result.deleted_count > 0:
        return jsonify({"success": True, "message": "Record deleted successfully"})
    else:
        return jsonify({"success": False, "message": "Record not found"}), 404


@api_helpers_bp.route('/pic-details/<premise_name>') # Changed from /get-pic/ to be more descriptive
def get_pic_details_for_premise(premise_name):
    # Individual session check removed, handled by before_request
    # Fetch the first PIC found for that premise for simplicity
    # In reality, a premise might have multiple PICs; the JS might need to handle a list
    pic_data = profile_list_collection.find_one(
        {"tied_to_premise": premise_name, "designation": {"$exists": True}}, # Filter for actual PIC entries
        {"name": 1, "contact": 1, "email": 1, "_id": 0} # Projection
    )
    if pic_data:
        return jsonify(pic_data)
    return jsonify({"name": "N/A", "contact": "N/A"}) # Default if no PIC found

@api_helpers_bp.route('/change-notes-for-premise/<premise_name>')
def get_change_notes_for_premise(premise_name):
    # Individual session check removed, handled by before_request
    # Placeholder logic for change notes.
    # This needs to be implemented based on how change notes are stored and retrieved.
    # Example: query 'change_collection' or 'refund_collection' for entries related to premise_name.
    # For now, returning placeholder:
    # notes = f"Change notes for {premise_name} would be fetched here. Placeholder."
    # A more realistic query might be:
    related_changes = list(change_collection.find({"premises": premise_name}, {"remark": 1, "submitted_at": 1, "_id":0}).sort("submitted_at", -1).limit(3))
    notes = "; ".join([f"({r.get('submitted_at','').strftime('%Y-%m-%d') if isinstance(r.get('submitted_at'), datetime) else r.get('submitted_at', '')}): {r.get('remark','')}" for r in related_changes])
    if not notes: notes = "No recent change notes found."

    return jsonify({"notes": notes})
