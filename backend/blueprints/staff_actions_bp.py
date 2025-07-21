# backend/blueprints/staff_actions_bp.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from werkzeug.utils import secure_filename
from datetime import datetime
from bson import ObjectId # Make sure ObjectId is imported if used for _id string conversion (though not explicitly in this snippet)

from ..col import collection,industry_list_collection # Customer cases/complaints
from ..utils import handle_route_error, require_auth, sanitize_input # Error handling utilities
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
@require_auth('admin')
@handle_route_error
def get_case_details(case_no):
    """Enhanced API endpoint to get case details with validation and logging"""
    admin_username = session.get('username', 'unknown')
    current_app.logger.info(f"Case API access for case #{case_no} by admin: {admin_username}")
    
    # Validate case number
    if case_no <= 0:
        current_app.logger.warning(f"Invalid case number API request: {case_no} by: {admin_username}")
        return jsonify({"error": "Invalid case number"}), 400
    
    # This route is protected by before_request, so admin is logged in.
    case_data = collection.find_one({"case_no": case_no}, {"_id": 0}) # Exclude ObjectId
    if not case_data:
        current_app.logger.warning(f"Case not found API request: {case_no} by: {admin_username}")
        return jsonify({"error": "Case not found"}), 404
    
    current_app.logger.info(f"Case data retrieved via API for case #{case_no} by: {admin_username}")
    return jsonify(case_data)

@staff_actions_bp.route("/help/<int:case_no>", methods=["GET", "POST"]) # was /staff-help/
@require_auth('admin')
@handle_route_error
def staff_form(case_no):
    """Enhanced staff complaint form with comprehensive validation and error handling"""
    admin_username = session.get('username', 'unknown')
    current_app.logger.info(f"Staff form accessed for case #{case_no} by admin: {admin_username}")
    
    # Validate case number
    if case_no <= 0:
        current_app.logger.warning(f"Invalid case number accessed: {case_no} by: {admin_username}")
        flash("Invalid case number.", "danger")
        return redirect(url_for("dashboard"))
    
    case_data = collection.find_one({"case_no": case_no})
    if not case_data:
        current_app.logger.warning(f"Case not found: #{case_no} by admin: {admin_username}")
        flash(f"Case #{case_no} not found!", "danger")
        return redirect(url_for("dashboard"))
    
    case_data["_id"] = str(case_data["_id"])
    
    if request.method == "GET":
        return render_template("staff-complaint-form.html", case_no=case_no, case_data=case_data)
    
    current_app.logger.info(f"Staff form submission for case #{case_no} by admin: {admin_username}")
    
    try:
        if case_data.get("status") == "closed":
            current_app.logger.warning(f"Attempt to edit closed case #{case_no} by: {admin_username}")
            flash("This case is closed and cannot be edited.", "warning")
            return redirect(url_for("dashboard"))
        
        # Input validation and sanitization
        actions_done = request.form.getlist("actions")
        remarks = sanitize_input(request.form.get("remarks", ""), 1000)
        case_closed = request.form.get("case_closed")
        revisit_date = sanitize_input(request.form.get("appointment_date", ""), 20)
        revisit_time = sanitize_input(request.form.get("appointment_time", ""), 20)
        staff_name = sanitize_input(request.form.get("staff_name", ""), 100)
        signature_data = request.form.get("signature", "")
        
        # Validate required fields
        if not staff_name:
            current_app.logger.warning(f"Staff name missing in case #{case_no} update by: {admin_username}")
            flash("Staff name is required.", "danger")
            return render_template("staff-complaint-form.html", case_no=case_no, case_data=case_data)
        
        if case_closed not in ["Yes", "No"]:
            current_app.logger.warning(f"Invalid case closed value in case #{case_no} by: {admin_username}")
            flash("Please specify whether the case is closed.", "danger")
            return render_template("staff-complaint-form.html", case_no=case_no, case_data=case_data)
        
        image_id = case_data.get("image_id")
        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename:
                # Validate file type and size
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
                filename = secure_filename(file.filename)
                if '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions:
                    # Check file size (10MB limit)
                    file.seek(0, 2)  # Seek to end
                    file_size = file.tell()
                    file.seek(0)  # Reset to beginning
                    
                    if file_size > 10 * 1024 * 1024:  # 10MB
                        current_app.logger.warning(f"File too large in case #{case_no} by: {admin_username}")
                        flash("Image file is too large. Maximum size is 10MB.", "danger")
                        return render_template("staff-complaint-form.html", case_no=case_no, case_data=case_data)
                    
                    image_id = main_fs_instance.put(file.read(), filename=filename, content_type=file.content_type)
                    current_app.logger.info(f"Image uploaded for case #{case_no} by: {admin_username}")
                else:
                    current_app.logger.warning(f"Invalid file type in case #{case_no} by: {admin_username}")
                    flash("Invalid file type. Please use PNG, JPG, JPEG, GIF, or PDF.", "danger")
                    return render_template("staff-complaint-form.html", case_no=case_no, case_data=case_data)
        
        if case_closed == "Yes":
            collection.update_one({"case_no": case_no}, {"$set": {"status": "closed", "closed_by": admin_username, "closed_at": datetime.now()}})
            current_app.logger.info(f"Case #{case_no} closed by admin: {admin_username}")
            flash(f"Case #{case_no} has been closed.", "success")
            return redirect(url_for("dashboard"))
        
        # Update case with all fields
        update_fields = {
            "actions_done": actions_done,
            "remarks": remarks,
            "case_closed": case_closed,
            "revisit_date": revisit_date,
            "revisit_time": revisit_time,
            "staff_name": staff_name,
            "updated_at": datetime.now(),
            "updated_by": admin_username,
            "image_id": image_id,
            "signature": signature_data
        }
        
        collection.update_one({"case_no": case_no}, {"$set": update_fields})
        current_app.logger.info(f"Case #{case_no} updated successfully by admin: {admin_username}")
        flash(f"Case #{case_no} updated successfully!", "success")
        return redirect(url_for("dashboard"))
    
    except Exception as e:
        current_app.logger.error(f"Error updating case #{case_no} by {admin_username}: {str(e)}")
        flash("An error occurred while updating the case. Please try again.", "danger")
        return render_template("staff-complaint-form.html", case_no=case_no, case_data=case_data)

@staff_actions_bp.route('/industry-global')
@require_auth('admin')
@handle_route_error
def industry_global():
    """Enhanced industry global list management with comprehensive error handling"""
    admin_username = session.get('username', 'unknown')
    current_app.logger.info(f"Industry global list accessed by admin: {admin_username}")
    
    try:
        # Fetch industries sorted by order, then by name as secondary sort
        eos = list(industry_list_collection.find().sort([("order", 1), ("eo_name", 1)]))
        
        # Ensure all items have an order field (for backward compatibility)
        for i, eo in enumerate(eos):
            if 'order' not in eo or eo['order'] == -1:
                industry_list_collection.update_one(
                    {'_id': eo['_id']}, 
                    {'$set': {'order': i}}
                )
                eos[i]['order'] = i
        
        current_app.logger.info(f"Industry list loaded successfully with {len(eos)} items by: {admin_username}")
        return render_template('industry-list.html', eos=eos)
        
    except Exception as e:
        current_app.logger.error(f"Error loading industry global list by {admin_username}: {str(e)}")
        flash("An error occurred while loading the industry list.", "error")
        return redirect(url_for('dashboard'))

@staff_actions_bp.route('/save_all_industry_global_changes', methods=['POST'])
@require_auth('admin')
@handle_route_error
def save_all_industry_global_changes():
    """Enhanced industry global list changes with comprehensive validation and error handling"""
    admin_username = session.get('username', 'unknown')
    current_app.logger.info(f"Industry global changes initiated by admin: {admin_username}")
    
    try:
        # Validate request data
        if not request.json:
            current_app.logger.warning(f"No JSON data provided for industry changes by: {admin_username}")
            return jsonify({'status': 'error', 'message': 'No JSON data provided'}), 400
        
        data = request.json
        added = data.get('added', [])
        edited = data.get('edited', [])
        deleted = data.get('deleted', [])
        reordered = data.get('reordered', [])
        
        current_app.logger.info(f"Industry changes: {len(added)} added, {len(edited)} edited, {len(deleted)} deleted, {len(reordered)} reordered by: {admin_username}")
        
        # Validate input data
        if not isinstance(added, list) or not isinstance(edited, list) or not isinstance(deleted, list) or not isinstance(reordered, list):
            current_app.logger.warning(f"Invalid data types in industry changes by: {admin_username}")
            return jsonify({'status': 'error', 'message': 'Invalid data format'}), 400
        edited = data.get('edited', [])
        deleted = data.get('deleted', [])
        visual_order = data.get('visual_order', [])
        
        # Validate data types
        if not isinstance(added, list) or not isinstance(edited, list) or not isinstance(deleted, list) or not isinstance(visual_order, list):
            return jsonify({'status': 'error', 'message': 'Invalid data format. Expected lists for all operations.'}), 400
        
        # Validate industry names in added items
        for eo_item in added:
            if not isinstance(eo_item, dict) or 'eo_name' not in eo_item:
                return jsonify({'status': 'error', 'message': 'Invalid format for added items. Expected dictionary with eo_name.'}), 400
            
            eo_name = eo_item['eo_name'].strip()
            if not eo_name:
                return jsonify({'status': 'error', 'message': 'Industry name cannot be empty.'}), 400
            
            if len(eo_name) > 100:  # Set reasonable limit
                return jsonify({'status': 'error', 'message': 'Industry name too long. Maximum 100 characters.'}), 400
            
            # Check for duplicate in database
            if industry_list_collection.find_one({'eo_name': eo_name}):
                return jsonify({'status': 'error', 'message': f"Industry name '{eo_name}' already exists."}), 400
        
        # Validate edited items
        for eo_item in edited:
            if not isinstance(eo_item, dict) or 'eo_name' not in eo_item or '_id' not in eo_item:
                return jsonify({'status': 'error', 'message': 'Invalid format for edited items. Expected dictionary with eo_name and _id.'}), 400
            
            eo_name = eo_item['eo_name'].strip()
            if not eo_name:
                return jsonify({'status': 'error', 'message': 'Industry name cannot be empty.'}), 400
            
            if len(eo_name) > 100:
                return jsonify({'status': 'error', 'message': 'Industry name too long. Maximum 100 characters.'}), 400
            
            # Validate ObjectId format
            try:
                ObjectId(eo_item['_id'])
            except Exception:
                return jsonify({'status': 'error', 'message': f"Invalid ID format: {eo_item['_id']}"}), 400
            
            # Check for duplicate (excluding current item)
            if industry_list_collection.find_one({'eo_name': eo_name, '_id': {'$ne': ObjectId(eo_item['_id'])}}):
                return jsonify({'status': 'error', 'message': f"Industry name '{eo_name}' already exists."}), 400
        
        # Validate deleted items
        for _id_str in deleted:
            if not isinstance(_id_str, str):
                return jsonify({'status': 'error', 'message': 'Invalid format for deleted items. Expected string IDs.'}), 400
            
            try:
                ObjectId(_id_str)
            except Exception:
                return jsonify({'status': 'error', 'message': f"Invalid ID format for deletion: {_id_str}"}), 400
        
        # Process operations in a transaction-like manner
        processed_added = []
        processed_edited = []
        processed_deleted = []
        
        # Process added items
        for eo_item in added:
            try:
                eo_name = eo_item['eo_name'].strip()
                result = industry_list_collection.insert_one({
                    "eo_name": eo_name, 
                    "order": -1,  # Default order, will be updated later
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                })
                processed_added.append(str(result.inserted_id))
            except Exception as e:
                current_app.logger.error(f"Error adding industry '{eo_item['eo_name']}': {str(e)}")
                return jsonify({'status': 'error', 'message': f"Failed to add industry '{eo_item['eo_name']}': {str(e)}"}), 500
        
        # Process edited items
        for eo_item in edited:
            try:
                eo_name = eo_item['eo_name'].strip()
                result = industry_list_collection.update_one(
                    {'_id': ObjectId(eo_item['_id'])}, 
                    {'$set': {
                        'eo_name': eo_name,
                        'updated_at': datetime.now()
                    }}
                )
                if result.matched_count == 0:
                    return jsonify({'status': 'error', 'message': f"Industry with ID '{eo_item['_id']}' not found."}), 404
                processed_edited.append(eo_item['_id'])
            except Exception as e:
                current_app.logger.error(f"Error editing industry '{eo_item['eo_name']}': {str(e)}")
                return jsonify({'status': 'error', 'message': f"Failed to edit industry '{eo_item['eo_name']}': {str(e)}"}), 500
        
        # Process deleted items
        for _id_str in deleted:
            try:
                result = industry_list_collection.delete_one({'_id': ObjectId(_id_str)})
                if result.deleted_count == 0:
                    current_app.logger.warning(f"Industry with ID '{_id_str}' not found for deletion")
                processed_deleted.append(_id_str)
            except Exception as e:
                current_app.logger.error(f"Error deleting industry with ID '{_id_str}': {str(e)}")
                return jsonify({'status': 'error', 'message': f"Failed to delete industry with ID '{_id_str}': {str(e)}"}), 500
        
        # Process visual order
        if visual_order:
            try:
                for index, item in enumerate(visual_order):
                    if not isinstance(item, dict):
                        continue
                    
                    target_id_str = item.get('_id')
                    
                    # Handle newly added items that don't have _id yet
                    if not target_id_str and 'eo_name' in item:
                        eo_name = item['eo_name'].strip()
                        new_eo_doc = industry_list_collection.find_one({'eo_name': eo_name})
                        if new_eo_doc:
                            target_id_str = str(new_eo_doc['_id'])
                    
                    if target_id_str:
                        try:
                            result = industry_list_collection.update_one(
                                {'_id': ObjectId(target_id_str)}, 
                                {'$set': {
                                    'order': index,
                                    'updated_at': datetime.now()
                                }}
                            )
                            if result.matched_count == 0:
                                current_app.logger.warning(f"Industry with ID '{target_id_str}' not found for order update")
                        except Exception as e:
                            current_app.logger.error(f"Error updating order for ID '{target_id_str}': {str(e)}")
                            # Continue with other items even if one fails
                            
            except Exception as e:
                current_app.logger.error(f"Error processing visual order: {str(e)}")
                return jsonify({'status': 'error', 'message': f"Failed to update order: {str(e)}"}), 500
        
        # Log successful operation
        current_app.logger.info(f"Industry global changes saved successfully. Added: {len(processed_added)}, Edited: {len(processed_edited)}, Deleted: {len(processed_deleted)}")
        
        return jsonify({
            'status': 'success',
            'summary': {
                'added': len(processed_added),
                'edited': len(processed_edited),
                'deleted': len(processed_deleted),
                'reordered': len(visual_order)
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Unexpected error in save_all_industry_global_changes: {str(e)}")
        return jsonify({'status': 'error', 'message': 'An unexpected error occurred. Please try again.'}), 500