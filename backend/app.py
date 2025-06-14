from libs import *
from col import * # This should ideally define db and all collections
from fpdf import FPDF
import io
from utils import * # Assuming safe_int is here, will add safe_float
import traceback # For logging full tracebacks

app = Flask(__name__)

CORS(app)

load_dotenv()

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

scheduler = APScheduler()

from datetime import datetime

fs = gridfs.GridFS(db) # Assuming db is initialized in col.py or similar

# Define collections (ensure all are here and db is defined)
collection = db["customer_issues"]
login_collection = db["login_admin"]
login_cust_collection = db["login_customer"]
remark_collection = db["remarks"]
services_collection = db["services_list"]
device_list_collection = db["device_list"]
profile_list_collection = db["profile_list"]
eo_pack_collection = db["eo_pack_list"]
route_list_collection = db["route_list"]
changed_models_collection = db["changed_models"]
discontinue_collection = db["discontinued_items"]
logs_collection = db["logs"]
model_list_collection = db["model_list"]
others_list_collection = db["others_list"]
empty_bottles_list_collection = db["empty_bottles_list"]
straw_list_collection = db["straw_list"]
eo_list_collection = db["eo_list"]
test_collection = db["test_collection"]
change_collection = db["change_requests"]
removed_devices_collection = db["removed_devices"]
monthly_services_collection = db["monthly_services"]


app.config['MAIL_SERVER'] = os.getenv('SMTP_GOOGLE_SERVER')
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('SMTP_TEST_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('SMTP_TEST_APP_PASSWORD')
app.config['MODE'] = os.getenv('MODE')

mail = Mail(app)

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

@scheduler.task('cron', day=1, hour=0, minute=0)
def scheduled_route_update():
    replicate_monthly_routes(route_list_collection)

@scheduler.task('cron', day='*', hour=0, minute=5)
def clear_discontinued_items():
    try:
        current_datetime = datetime.now()
        result = discontinue_collection.update_many(
            {"collect_back_date_dt": {"$lte": current_datetime}, "$or": [{"is_active": {"$exists": False}}, {"is_active": True}]},
            {"$set": {"is_active": False}}
        )
        modified_count = result.modified_count
        if modified_count > 0:
            print(f"[{current_datetime}] Clear Discontinued Items: Disabled {modified_count} records in discontinue_collection.")
        else:
            print(f"[{current_datetime}] Clear Discontinued Items: No records found to disable in discontinue_collection.")
    except Exception as e:
        print(f"[{datetime.now()}] Error in clear_discontinued_items scheduled task: {e}")

scheduler.init_app(app)
scheduler.start()

@app.route('/update-data', methods=['POST'])
def update_data():
    data = request.get_json()
    record_id = data.pop('sn')
    result = services_collection.update_one({'S/N': record_id}, {'$set': data})
    if result.modified_count > 0:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False})

@app.context_processor
def inject_builtin_functions():
    return dict(max=max, min=min)

@app.template_filter('to_querystring')
def to_querystring(query_params):
    return urlencode(query_params)

@app.template_filter('update_querystring')
def update_querystring(querystring, key, value):
    query_dict = dict([kv.split('=') for kv in querystring.split('&') if '=' in kv])
    query_dict[key] = value
    return urlencode(query_dict)

@app.route("/customer-help", methods=["GET", "POST"])
def customer_form():
    if "customer_email" not in session:
        return redirect(url_for("client_login"))
    if request.method == "POST":
        case_no = collection.count_documents({}) + 1
        user_email = session["customer_email"]
        premise_name = request.form.get("premise_name")
        location = request.form.get("location")
        model = request.form.get("model")
        issues = request.form.getlist("issues")
        remarks = request.form.get("remarks", "")
        image_id = None
        if 'image' in request.files:
            image = request.files['image']
            if image and image.filename:
                filename = secure_filename(image.filename)
                image_id = fs.put(image.read(), filename=filename, content_type=image.content_type)

        collection.insert_one({
            "case_no": case_no, "premise_name": premise_name, "location": location,
            "image_id": image_id, "model": model, "issues": issues, "remarks": remarks,
            "email": user_email, "created_at": datetime.now(),
        })
        send_email_to_customer(case_no, user_email, app.config['MAIL_USERNAME'], mail)
        send_email_to_admin(case_no, user_email, app.config['MAIL_USERNAME'], mail)
        return redirect(url_for("case_success", case_no=case_no))
    return render_template("customer-complaint-form.html")

@app.route("/api/case/<int:case_no>", methods=["GET"])
def get_case_details(case_no):
    case_data = collection.find_one({"case_no": case_no}, {"_id": 0})
    if not case_data:
        return jsonify({"error": "Case not found"}), 404
    return jsonify(case_data)

@app.route("/staff-help/<int:case_no>", methods=["GET", "POST"])
def staff_form(case_no):
    case_data = collection.find_one({"case_no": case_no})
    if not case_data:
        flash(f"Case #{case_no} not found!", "danger")
        return redirect(url_for("customer_form"))
    case_data["_id"] = str(case_data["_id"])
    if request.method == "POST":
        actions_done = request.form.getlist("actions")
        remarks = request.form.get("remarks", "")
        case_closed = request.form.get("case_closed")
        revisit_date = request.form.get("appointment_date")
        revisit_time = request.form.get("appointment_time")
        staff_name = request.form.get("staff_name")
        signature_data = request.form.get("signature")
        image_id = case_data.get("image_id")
        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename:
                image_id = fs.put(file.read(), filename=file.filename, content_type=file.content_type)
        if case_closed == "Yes":
            collection.delete_one({"case_no": case_no})
            flash(f"Case #{case_no} has been closed and removed.", "success")
            return render_template("view-complaint.html")
        collection.update_one(
            {"case_no": case_no},
            {"$set": {
                "actions_done": actions_done, "remarks": remarks, "case_closed": case_closed,
                "revisit_date": revisit_date, "revisit_time": revisit_time, "staff_name": staff_name,
                "updated_at": datetime.now(), "image_id": image_id, "signature": signature_data
            }})
        flash(f"Case #{case_no} updated successfully!", "success")
        return redirect(url_for("dashboard", case_no=case_no))
    return render_template("staff-complaint-form.html", case_no=case_no, case_data=case_data)

# ... (All other existing routes are assumed to be here) ...

@app.route('/service', methods=['GET', 'POST'])
def service():
    if 'username' not in session: return redirect(url_for('login'))
    technician_name_from_session_outer = session.get("username", "Unknown Technician") # Renamed for clarity
    current_time_for_get = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Renamed for clarity
    
    if request.method == 'POST':
        try:
            technician_name_from_session = session.get("username", "Unknown Technician")
            service_day_str = request.form.get('service_day')
            service_month_str = request.form.get('service_month')
            service_year_str = request.form.get('service_year')

            company_name_from_form = request.form.get('company')
            selected_premises_from_checkboxes = request.form.getlist('selected_premises')

            actions_done_from_form = request.form.getlist('actions_done')
            acknowledgement_remarks_from_form = request.form.get('acknowledgement_remarks')
            acknowledgement_staff_name_from_form = request.form.get('acknowledgement_staff_name')
            signature_data_from_form = request.form.get('signature')

            serviced_device_original_sns_from_form = request.form.getlist('serviced_device_sns')
            serviced_devices_data_for_db = []

            month_str_to_int = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}
            service_month_int = month_str_to_int.get(service_month_str.upper()) if service_month_str else None

            service_date_obj = None
            if service_year_str and service_month_int and service_day_str:
                try:
                    service_date_obj = datetime(int(service_year_str), service_month_int, int(service_day_str))
                except ValueError as e:
                    current_app.logger.error(f"Invalid service date component: {e}")

            for original_sn_str in serviced_device_original_sns_from_form:
                device_master_info = device_list_collection.find_one({"S/N": original_sn_str, "company": company_name_from_form})
                if not device_master_info and original_sn_str.isdigit():
                     device_master_info = device_list_collection.find_one({"S/N": int(original_sn_str), "company": company_name_from_form})

                if not device_master_info:
                    log_activity(technician_name_from_session, f"SERVICE FORM SUBMISSION: Device master info NOT FOUND for S/N '{original_sn_str}' in company '{company_name_from_form}'. Skipping this device entry for monthly_services.", logs_collection)
                    continue

                submitted_sn_on_form = request.form.get(f'sn_{original_sn_str}')

                device_data = {
                    "original_sn_from_card": original_sn_str,
                    "submitted_sn_on_form": submitted_sn_on_form,
                    "original_model": device_master_info.get('Model'),
                    "original_color": device_master_info.get('Color'),
                    "submitted_color_on_form": request.form.get(f'color_{original_sn_str}'),
                    "original_current_eo": device_master_info.get('Current EO'),
                    "original_premise": device_master_info.get('tied_to_premise'),
                    "device_capacity_volume": device_master_info.get('Volume'),
                    "location_serviced": request.form.get(f'location_{original_sn_str}'),
                    "scent_volume_actual": safe_float(request.form.get(f'scent_volume_{original_sn_str}')),
                    "scent_balance": safe_float(request.form.get(f'scent_balance_{original_sn_str}')),
                    "scent_consumption": safe_float(request.form.get(f'scent_consumption_{original_sn_str}')),
                    "changed_scent_to": request.form.get(f'scent_change_{original_sn_str}'),
                    "is_marked_inactive": request.form.get(f'inactive_{original_sn_str}') == '1',
                    "relocated_to_premise_on_form": request.form.get(f'relocate_{original_sn_str}'),
                    "event_settings_current_from_master": {
                        f"E{e_num}": {
                            "days": device_master_info.get(f'E{e_num} - DAYS'), "start": device_master_info.get(f'E{e_num} - START'),
                            "end": device_master_info.get(f'E{e_num} - END'), "work": device_master_info.get(f'E{e_num} - WORK'),
                            "pause": device_master_info.get(f'E{e_num} - PAUSE'),
                        } for e_num in range(1,5)
                    },
                    "event_settings_new_submission": []
                }

                for e_num in range(1, 5):
                    event_setting = {
                        "event_number": e_num,
                        "days": request.form.get(f'event_{original_sn_str}_days{e_num}'),
                        "start_time": request.form.get(f'event_{original_sn_str}_start{e_num}'),
                        "end_time": request.form.get(f'event_{original_sn_str}_end{e_num}'),
                        "work": request.form.get(f'event_{original_sn_str}_work{e_num}'),
                        "pause": request.form.get(f'event_{original_sn_str}_pause{e_num}')
                    }
                    device_data["event_settings_new_submission"].append(event_setting)

                serviced_devices_data_for_db.append(device_data)

                if device_data["is_marked_inactive"] and service_date_obj :
                    discontinue_entry = {
                        "user": technician_name_from_session, "company": company_name_from_form,
                        "date": datetime.now(), "month": service_month_str, "year": service_year_str,
                        "premises": [device_master_info.get('tied_to_premise')],
                        "devices": [device_master_info.get('Model')],
                        "specific_sn_marked": original_sn_str,
                        "collect_back": True, "collect_back_date_dt": service_date_obj,
                        "remark": f"Marked inactive via service form by {technician_name_from_session} for S/N: {original_sn_str}. Original Premise: {device_master_info.get('tied_to_premise')}",
                        "submitted_at": datetime.now(), "is_active": True
                    }
                    discontinue_collection.insert_one(discontinue_entry)
                    log_activity(technician_name_from_session, f"Device S/N {original_sn_str} marked for discontinuation in company {company_name_from_form} effective {service_date_obj.strftime('%Y-%m-%d')}.", logs_collection)

            service_date_for_db_iso = service_date_obj.isoformat() if service_date_obj else f"{service_year_str}-{service_month_str}-{service_day_str}"

            monthly_service_doc = {
                "technician_name": technician_name_from_session,
                "service_date_iso": service_date_for_db_iso,
                "service_date_parts": { "day": service_day_str, "month": service_month_str, "year": service_year_str },
                "company_name": company_name_from_form,
                "premises_serviced_on_form": selected_premises_from_checkboxes,
                "devices_serviced_details": serviced_devices_data_for_db,
                "acknowledgement": {
                    "actions_done": actions_done_from_form, "remarks": acknowledgement_remarks_from_form,
                    "staff_name": acknowledgement_staff_name_from_form, "signature_data": signature_data_from_form
                },
                "submission_timestamp": datetime.now()
            }

            monthly_services_collection.insert_one(monthly_service_doc)
            log_activity(technician_name_from_session, f"Submitted monthly service report for company: {company_name_from_form}, premises: {', '.join(selected_premises_from_checkboxes)}", logs_collection)
            flash("Monthly service report submitted successfully!", "success")
            return redirect(url_for("dashboard"))

        except Exception as e:
            current_app.logger.error(f"Error in service POST: {e}")
            traceback.print_exc()
            flash(f"An error occurred while submitting the service report: {str(e)}", "danger")
            return redirect(url_for("service"))

    # For GET request
    companies_for_get = sorted(list(services_collection.distinct('company'))) # Renamed for clarity
    initial_company_for_get = companies_for_get[0] if companies_for_get else None
    all_premises_list_for_get = sorted(list(profile_list_collection.distinct("premise_name")))
    eo_list_for_get = sorted(list(eo_pack_collection.distinct("eo_name")))

    return render_template("service.html",
                           companies=companies_for_get,
                           technician_name=technician_name_from_session_outer, # Use the one defined at start of function
                           current_time=current_time_for_get, # Use the one defined at start of function
                           devices=[], # Pass empty list for GET, devices loaded via JS
                           initial_company=initial_company_for_get,
                           eo_list=eo_list_for_get,
                           all_premises_list=all_premises_list_for_get)

@app.route('/get-devices-for-premises', methods=['POST'])
def get_devices_for_premises():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    selected_premises = data.get('selected_premises', [])
    company_name = data.get('company_name')
    if not company_name or not selected_premises:
        return jsonify({"error": "Company and selected premises are required."}), 400
    query = {"company": company_name, "tied_to_premise": {"$in": selected_premises}}
    devices_cursor = device_list_collection.find(query)
    devices_by_premise = defaultdict(list)
    for device in devices_cursor:
        device['_id'] = str(device['_id'])
        important_notes = []
        device_premise = device.get('tied_to_premise')
        device_model = device.get('Model')
        if device_premise and device_model:
            change_query_refined = {
                "company": company_name,
                "premises": {"$in": [device_premise]},
                "devices": {"$in": [device_model]}
            }
            change_requests = list(changed_models_collection.find(change_query_refined))
            for req in change_requests:
                if req.get("collect_back"):
                    continue
                note_parts = []
                if req.get("change_scent") and req.get("change_scent_to"):
                    note_parts.append(f"Change Scent to: {req['change_scent_to']}")
                if req.get("redo_settings"):
                    note_parts.append("Redo Settings")
                if req.get("move_device") and req.get("move_device_to"):
                    note_parts.append(f"Move Device to: {req['move_device_to']}")
                if req.get("relocate_device") and req.get("relocate_device_to"):
                    note_parts.append(f"Relocate Device to Premise: {req['relocate_device_to']}")
                remark = req.get("remark")
                if remark: note_parts.append(f"Remark: {remark}")
                if note_parts:
                    date_of_change = req.get("date", "N/A")
                    if isinstance(date_of_change, datetime):
                        date_of_change = date_of_change.strftime('%Y-%m-%d')
                    important_notes.append(f"Change Request ({date_of_change}): " + ", ".join(note_parts))
            discontinue_query_refined = {
                "company": company_name,
                "premises": {"$in": [device_premise]},
                "devices": {"$in": [device_model]}
            }
            discontinue_requests = list(discontinue_collection.find(discontinue_query_refined))
            for disc_req in discontinue_requests:
                collect_date = disc_req.get("collect_back_date_dt")
                date_str = collect_date.strftime('%Y-%m-%d') if isinstance(collect_date, datetime) else disc_req.get("date", "N/A")
                is_active = disc_req.get("is_active", True)
                status_note = "Currently Active Discontinuation" if is_active else "Discontinuation Processed/Inactive"
                important_notes.append(f"Marked for Discontinuation/Collection. Effective Date: {date_str}. Status: {status_note}")
        device['important_notes'] = important_notes
        devices_by_premise[device['tied_to_premise']].append(device)
    return jsonify(devices_by_premise)

@app.route('/get-pics-for-premises', methods=['POST'])
def get_pics_for_premises():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    selected_premises = data.get('selected_premises', [])
    company_name = data.get('company_name')
    if not company_name or not selected_premises:
        return jsonify({"error": "Company and selected premises are required."}), 400
    pics_by_premise = {}
    for premise_name in selected_premises:
        pic_doc = profile_list_collection.find_one(
            {"company": company_name, "tied_to_premise": premise_name},
            {"name": 1, "contact": 1, "email": 1, "designation": 1, "_id": 0}
        )
        pics_by_premise[premise_name] = pic_doc
    return jsonify(pics_by_premise)

@app.route('/monthly-services-report', methods=['GET'])
def monthly_services_report_view():
    if 'username' not in session:
        return redirect(url_for('login'))

    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    skip = (page - 1) * limit
    current_filters = request.args.to_dict()

    technician_name_filter = current_filters.get('technician_name', '').strip()
    company_name_filter = current_filters.get('company_name', '').strip()
    premise_name_filter = current_filters.get('premise_name', '').strip()
    device_model_filter = current_filters.get('device_model', '').strip()
    device_sn_filter = current_filters.get('device_sn', '').strip()
    service_month_filter = current_filters.get('service_month', '').strip().upper()
    service_year_filter = current_filters.get('service_year', '').strip()

    pipeline = []
    match_conditions = {}

    if technician_name_filter:
        match_conditions['technician_name'] = {'$regex': technician_name_filter, '$options': 'i'}
    if company_name_filter:
        match_conditions['company_name'] = {'$regex': company_name_filter, '$options': 'i'}
    if service_year_filter:
        match_conditions['service_date_parts.year'] = service_year_filter
    if service_month_filter:
        match_conditions['service_date_parts.month'] = service_month_filter

    # These filters apply to the fields within the unwound 'serviced_device'
    device_match_conditions = {}
    if premise_name_filter:
        device_match_conditions['serviced_device.original_premise'] = {'$regex': premise_name_filter, '$options': 'i'}
    if device_model_filter:
        device_match_conditions['serviced_device.original_model'] = {'$regex': device_model_filter, '$options': 'i'} # Filter on original_model
    if device_sn_filter:
        device_match_conditions['$or'] = [
            {'serviced_device.original_sn_from_card': {'$regex': device_sn_filter, '$options': 'i'}},
            {'serviced_device.submitted_sn_on_form': {'$regex': device_sn_filter, '$options': 'i'}}
        ]

    # Initial unwind and addFields stages
    pipeline.extend([
        {"$unwind": "$devices_serviced_details"},
        {"$addFields": {"serviced_device": "$devices_serviced_details"}}
    ])

    # Add top-level match conditions first
    if match_conditions:
        pipeline.append({"$match": match_conditions})

    # Add device-specific match conditions
    if device_match_conditions:
        pipeline.append({"$match": device_match_conditions})

    # Pagination: Count total documents matching filters
    count_pipeline = pipeline[:] + [{"$count": "total"}]
    total_documents_cursor = monthly_services_collection.aggregate(count_pipeline)
    total_documents = next(total_documents_cursor, {}).get('total', 0)
    total_pages = (total_documents + limit - 1) // limit

    # Add sort, skip, and limit for data fetching
    pipeline.extend([
        {"$sort": {"submission_timestamp": -1, "service_date_iso": -1}}, # Primary sort by submission, secondary by service date
        {"$skip": skip},
        {"$limit": limit}
    ])

    records = list(monthly_services_collection.aggregate(pipeline))

    current_year_for_dropdown = datetime.now().year
    months_list_for_dropdown = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

    return render_template('monthly_services_report.html',
                           records=records,
                           page=page,
                           total_pages=total_pages,
                           limit=limit,
                           current_filters=current_filters,
                           current_year=current_year_for_dropdown,
                           months_list=months_list_for_dropdown,
                           username=session['username'])


# The following routes are assumed to be present from the original file and are kept:
@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
    
@app.route("/device-image/<image_id>")
def get_device_image(image_id):
    try:
        obj_file_id = ObjectId(image_id)
        image = fs.get(obj_file_id)
        return Response(image.read(), mimetype=image.content_type)
    except Exception as e:
        app.logger.error(f"Error fetching image: {str(e)}")
        return "Image not found", 404

@app.route('/eo-global')
def eo_global():
    if 'username' not in session: return redirect(url_for('login'))
    eos = list(eo_pack_collection.find().sort("order", 1))
    return render_template('eo-global.html', eos=eos)

@app.route('/save_all_eo_global_changes', methods=['POST'])
def save_all_eo_global_changes():
    data = request.json
    added = data.get('added', [])
    edited = data.get('edited', [])
    deleted = data.get('deleted', [])
    visual_order = data.get('visual_order', [])
    for eo_item in added:
        if eo_pack_collection.find_one({'eo_name': eo_item['eo_name']}):
            return jsonify({'status': 'error', 'message': f"EO name '{eo_item['eo_name']}' already exists."}), 400
        eo_pack_collection.insert_one({"eo_name": eo_item['eo_name'], "order": -1})
    for eo_item in edited:
        if eo_pack_collection.find_one({'eo_name': eo_item['eo_name'], '_id': {'$ne': ObjectId(eo_item['_id'])}}):
            return jsonify({'status': 'error', 'message': f"EO name '{eo_item['eo_name']}' already exists."}), 400
        eo_pack_collection.update_one({'_id': ObjectId(eo_item['_id'])}, {'$set': {'eo_name': eo_item['eo_name']}})
    for _id_str in deleted:
        eo_pack_collection.delete_one({'_id': ObjectId(_id_str)})
    for index, item in enumerate(visual_order):
        target_id_str = item.get('_id')
        if not target_id_str and 'eo_name' in item :
            new_eo_doc = eo_pack_collection.find_one({'eo_name': item['eo_name']})
            if new_eo_doc: target_id_str = str(new_eo_doc['_id'])
        if target_id_str:
             eo_pack_collection.update_one({'_id': ObjectId(target_id_str)}, {'$set': {'order': index}})
    return jsonify({'status': 'success'})

@app.route('/device-global-list')
def device_global():
    if 'username' not in session: return redirect(url_for('login'))
    models = list(model_list_collection.find().sort("order", 1))
    return render_template('device-global.html', models=models)

@app.route('/save_model1_changes', methods=['POST'])
def save_model1_changes():
    data = request.json
    added = data.get('added', [])
    edited = data.get('edited', [])
    deleted_ids = data.get('deleted', [])
    order = data.get('order', [])
    for model_data in added:
        model_name = model_data.get('model1')
        if not model_name: continue
        if model_list_collection.find_one({'model1': model_name}):
            return jsonify({'status': 'error', 'message': f"Model1 '{model_name}' already exists."}), 400
        last_item = model_list_collection.find_one(sort=[("order", -1)])
        new_order = (last_item['order'] + 1) if last_item and 'order' in last_item else 0
        model_list_collection.insert_one({"model1": model_name, "order": new_order})
    for model_data in edited:
        model_name = model_data.get('model1')
        model_id = model_data.get('_id')
        if not model_name or not model_id: continue
        if model_list_collection.find_one({'model1': model_name, '_id': {'$ne': ObjectId(model_id)}}):
            return jsonify({'status': 'error', 'message': f"Model1 '{model_name}' already exists."}), 400
        model_list_collection.update_one({'_id': ObjectId(model_id)}, {'$set': {'model1': model_name}})
    for model_id_str in deleted_ids:
        model_list_collection.delete_one({'_id': ObjectId(model_id_str)})
    for idx, model_id_str in enumerate(order):
        model_list_collection.update_one({'_id': ObjectId(model_id_str)}, {'$set': {'order': idx}})
    return jsonify({'status': 'success'})

@app.route('/get-premises/<company>')
def get_premises(company):
    premises_names = services_collection.distinct('Premise Name', {'company': company})
    return render_template('partials/premise_checkboxes.html', premises=sorted(list(premises_names)))

@app.route('/get-devices/<premise>')
def get_devices(premise):
    device_docs = device_list_collection.find({'tied_to_premise': premise}, {"Model": 1, "_id": 0})
    unique_models = sorted(list(set(doc['Model'] for doc in device_docs if 'Model' in doc and doc['Model'])))
    return jsonify({'models': unique_models})

@app.route('/get-eos', methods=['POST'])
def get_eos():
    selected_device_models = request.json.get('devices', [])
    eos_set = set()
    for model_name in selected_device_models:
        device_entries = device_list_collection.find({"Model": model_name}, {"Current EO": 1})
        for entry in device_entries:
            if 'Current EO' in entry and entry['Current EO']:
                eos_set.add(entry['Current EO'])
    return jsonify({'eos': sorted(list(eos_set))})

@app.route('/get-premises-json/<company>')
def get_premises_json(company):
    premises_list = services_collection.distinct('Premise Name', {'company': company})
    return jsonify({'premises': sorted(list(set(premises_list)))})

@app.route('/generate-change-form-pdf', methods=['POST'])
def generate_change_form_pdf():
    data = request.json
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Change Form Summary", ln=1, align="C")
    pdf.ln(5)
    def add_field(key, value):
        pdf.set_font("Arial", "B", size=10)
        pdf.cell(50, 7, txt=key)
        pdf.set_font("Arial", size=10)
        if isinstance(value, bool): pdf.multi_cell(0, 7, txt="Yes" if value else "No", ln=1)
        elif isinstance(value, list):
            if not value: pdf.multi_cell(0, 7, txt="N/A", ln=1)
            else:
                pdf.ln(7);
                for item in value: pdf.cell(5); pdf.multi_cell(0, 7, txt=f"- {item}", ln=1)
        else: pdf.multi_cell(0, 7, txt=str(value) if value else "N/A", ln=1)
    add_field("User:", data.get("user")); add_field("Company Name:", data.get("companyName")); add_field("Date:", data.get("date"))
    pdf.ln(5); pdf.set_font("Arial", "B", size=11); pdf.cell(200, 10, txt="Change Details:", ln=1); pdf.set_font("Arial", size=10)
    if data.get("changeScent"): add_field("Change Scent To:", data.get("changeScentText"))
    add_field("Redo Settings:", data.get("redoSettings")); add_field("Reduce Scent Intensity:", data.get("reduceIntensity")); add_field("Increase Scent Intensity:", data.get("increaseIntensity"))
    if data.get("moveDevice"): add_field("Move Device To:", data.get("moveDeviceText"))
    if data.get("relocateDevice"): add_field("Relocate Device To Premise:", data.get("relocateDeviceDropdown"))
    pdf.ln(2); add_field("Premises Selected:", data.get("premises")); add_field("Devices Selected:", data.get("devices")); pdf.ln(2)
    add_field("Collect Back Machine:", data.get("collectBack"))
    if data.get("collectBack"): add_field("Month for Collection:", data.get("month")); add_field("Year for Collection:", data.get("year"))
    pdf.ln(5); add_field("Remarks:", data.get("remark"))
    pdf_output = io.BytesIO(); pdf.output(pdf_output, "S"); pdf_output.seek(0)
    return send_file(pdf_output, mimetype='application/pdf', as_attachment=True, download_name='change_form_summary.pdf')

def generate_change_form_pdf_bytes(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Change Form Summary", ln=1, align="C"); pdf.ln(5)
    def add_field(key, value):
        pdf.set_font("Arial", "B", size=10); pdf.cell(50, 7, txt=key); pdf.set_font("Arial", size=10)
        if isinstance(value, bool): pdf.multi_cell(0, 7, txt="Yes" if value else "No", ln=1)
        elif isinstance(value, list):
            if not value: pdf.multi_cell(0, 7, txt="N/A", ln=1)
            else: pdf.ln(7);
            for item in value: pdf.cell(5); pdf.multi_cell(0, 7, txt=f"- {item}", ln=1)
        else: pdf.multi_cell(0, 7, txt=str(value) if value else "N/A", ln=1)
    add_field("User:", data.get("user")); add_field("Company Name:", data.get("companyName")); add_field("Date:", data.get("date"))
    pdf.ln(5); pdf.set_font("Arial", "B", size=11); pdf.cell(200, 10, txt="Change Details:", ln=1); pdf.set_font("Arial", size=10)
    if data.get("changeScent"): add_field("Change Scent To:", data.get("changeScentText"))
    add_field("Redo Settings:", data.get("redoSettings")); add_field("Reduce Scent Intensity:", data.get("reduceIntensity")); add_field("Increase Scent Intensity:", data.get("increaseIntensity"))
    if data.get("moveDevice"): add_field("Move Device To:", data.get("moveDeviceText"))
    if data.get("relocateDevice"): add_field("Relocate Device To Premise:", data.get("relocateDeviceDropdown"))
    pdf.ln(2); add_field("Premises Selected:", data.get("premises")); add_field("Devices Selected:", data.get("devices")); pdf.ln(2)
    add_field("Collect Back Machine:", data.get("collectBack"))
    if data.get("collectBack"): add_field("Month for Collection:", data.get("month")); add_field("Year for Collection:", data.get("year"))
    pdf.ln(5); add_field("Remarks:", data.get("remark"))
    return pdf.output(dest="S").encode('latin-1')

@app.route('/changed-settings-list', methods=['GET'])
def changed_settings_list():
    if 'username' not in session:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('login'))

    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    skip = (page - 1) * limit

    query = {}
    user_filter = request.args.get('user', '').strip()
    company_filter = request.args.get('company', '').strip()
    month_filter = request.args.get('month', '').strip()
    year_filter = request.args.get('year', '').strip()

    if user_filter:
        query['user'] = {'$regex': user_filter, '$options': 'i'}
    if company_filter:
        query['company'] = {'$regex': company_filter, '$options': 'i'}

    if month_filter and year_filter:
        try:
            month_int = int(month_filter)
            year_int = int(year_filter)
            query['$expr'] = {
                '$and': [
                    {'$eq': [{'$month': '$submitted_at'}, month_int]},
                    {'$eq': [{'$year': '$submitted_at'}, year_int]}
                ]
            }
        except ValueError:
            flash("Invalid month or year format.", "danger")
    elif year_filter:
        try:
            year_int = int(year_filter)
            query['$expr'] = {'$eq': [{'$year': '$submitted_at'}, year_int]}
        except ValueError:
            flash("Invalid year format.", "danger")


    total_entries = changed_models_collection.count_documents(query)
    results = list(changed_models_collection.find(query).sort("submitted_at", -1).skip(skip).limit(limit))

    for r in results:
        submitted_at_dt = r.get("submitted_at")
        if isinstance(submitted_at_dt, datetime):
            r["submitted_month"] = submitted_at_dt.month
            r["submitted_day"] = submitted_at_dt.day
            r["submitted_at"] = submitted_at_dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            r["submitted_month"] = None
            r["submitted_day"] = None

    total_pages = (total_entries + limit - 1) // limit
    query_params_for_template = request.args.to_dict()
    if 'page' in query_params_for_template:
        del query_params_for_template['page']

    return render_template("changed_settings_list.html",
                           data=results,
                           page=page,
                           total_pages=total_pages,
                           limit=limit,
                           query_params=query_params_for_template,
                           username=session.get('username'))

if __name__ == "__main__":
    app.run(debug=True)
