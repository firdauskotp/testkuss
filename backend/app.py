from libs import *
from col import *
from fpdf import FPDF
import io
from utils import *

app = Flask(__name__)

CORS(app)

load_dotenv()

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

scheduler = APScheduler()

from datetime import datetime

fs = gridfs.GridFS(db)

app.config['MAIL_SERVER'] = os.getenv('SMTP_GOOGLE_SERVER')
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('SMTP_TEST_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('SMTP_TEST_APP_PASSWORD')
app.config['MODE'] = os.getenv('MODE')

mail = Mail(app)

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

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/case-success/<int:case_no>",methods=["GET","POST"])
def case_success(case_no):
    return render_template("case-success.html", case_no=case_no)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('register'))
        existing_user = login_cust_collection.find_one({'email': email})
        if existing_user:
            flash("This email is already registered. Please use a different email.", "danger")
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        login_cust_collection.insert_one({'email': email, 'password': hashed_password})
        flash("User registered successfully!", "success")
        log_activity(session["username"],"added user : " +str(email),logs_collection)
        return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/register-admin', methods=['GET', 'POST'])
def register_admin():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('register_admin'))
        existing_user = login_collection.find_one({'username': username})
        if existing_user:
            flash("This username is already registered. Please use a different username.", "danger")
            return redirect(url_for('register_admin'))
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        login_collection.insert_one({'username': username, 'password': hashed_password})
        flash("User registered successfully!", "success")
        log_activity(session["username"],"added user : " +str(username),logs_collection)
        return redirect(url_for('register_admin'))
    return render_template('register-admin.html')

@app.route('/delete_user', methods=['POST'])
def delete_user():
    if 'username' not in session:
        return redirect(url_for('login'))
    user_id = request.form['user_id']
    user = login_cust_collection.find_one({'_id': ObjectId(user_id)})
    email = user.get('email', 'Unknown')
    login_cust_collection.delete_one({'_id': ObjectId(user_id)})
    flash("User deleted successfully!", "success")
    log_activity(session["username"], f"deleted user with email: {email}", logs_collection)
    return redirect(url_for('view_users'))

@app.route('/delete_admin', methods=['POST'])
def delete_admin():
    if 'username' not in session:
        return redirect(url_for('login'))
    user_id = request.form['user_id']
    user = login_collection.find_one({'_id': ObjectId(user_id)})
    username = user.get('username', 'Unknown')
    login_collection.delete_one({'_id': ObjectId(user_id)})
    flash("User deleted successfully!", "success")
    log_activity(session["username"], f"deleted user with username: {username}", logs_collection)
    return redirect(url_for('view_admins'))

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = login_collection.find_one({"username": username})
        if user and check_password_hash(user["password"], password):
            session["user_id"] = str(user["_id"])
            session["username"] = user["username"]
            flash("Login successful!", "success")
            log_activity(session["username"],"login",logs_collection)
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "danger")
            return redirect(url_for("admin_login"))
    return render_template("login.html")

@app.route('/all-list',methods=['GET'])
def reports():
    if 'username' in session:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
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
        E1_Work = request.args.get("E1_Work"); E1_Pause = request.args.get("E1_Pause"); E1_Days = request.args.get("E1_Days")
        E1_Start = request.args.get("E1_Start"); E1_End = request.args.get("E1_End")
        E2_Work = request.args.get("E2_Work"); E2_Pause = request.args.get("E2_Pause"); E2_Days = request.args.get("E2_Days")
        E2_Start = request.args.get("E2_Start"); E2_End = request.args.get("E2_End")
        E3_Work = request.args.get("E3_Work"); E3_Pause = request.args.get("E3_Pause"); E3_Days = request.args.get("E3_Days")
        E3_Start = request.args.get("E3_Start"); E3_End = request.args.get("E3_End")
        E4_Work = request.args.get("E4_Work"); E4_Pause = request.args.get("E4_Pause"); E4_Days = request.args.get("E4_Days")
        premiseAddress = request.args.get('premiseAddress', '').strip()
        premise = request.args.get('premise', '').strip()
        E4_Start = request.args.get("E4_Start"); E4_End = request.args.get("E4_End")
        Colour = request.args.get("Colour")
        Current_EO = request.args.get("Current_EO"); New_EO = request.args.get("New_EO")
        Scent_Effectiveness = request.args.get("Scent_Effectiveness")
        Common_Encounters = request.args.get("Common_Encounters"); Other_Remarks = request.args.get("Other_Remarks")
        industry = request.args.get('industry', '').strip(); premise = request.args.get('premise', '').strip(); pic = request.args.get('pic', '').strip()
        query = {}
        if month and year:
            month_list = [int(m.strip()) for m in month.split(',') if m.strip().isdigit()]
            query['$expr'] = {'$and': [{'$in': [{'$month': '$month_year'}, month_list]}, {'$eq': [{'$year': '$month_year'}, int(year)]}]}
        if industry: query["industry"] = {'$regex': industry, '$options': 'i'}
        # if premise: query["premise_name"] = {'$regex': premise, '$options': 'i'}
        if premise:
            query["Premise Name"] = {'$regex': premise, '$options': 'i'}

        if premiseAddress:
            query["Premise Address"] = {'$regex': premiseAddress, '$options': 'i'}
        if pic: query["name"] = {'$regex': pic, '$options': 'i'}
        if EO: query['Current EO'] = {'$regex': EO, '$options': 'i'}
        if Company: query['company'] = {'$regex': Company, '$options': 'i'}
        if Volume: query['Volume'] = int(Volume)
        if SN: query['S/N'] = int(SN)
        if Balance: query['Balance'] = int(Balance)
        if Consumption: query['Consumption'] = int(Consumption)
        if Refilled: query['Refilled'] = int(Refilled)
        if E1_Work: query['E1 - WORK'] = int(E1_Work);
        if E1_Pause: query['E1 - PAUSE'] = int(E1_Pause)
        if E1_Days: query['E1 - DAYS'] = {'$regex': E1_Days, '$options': 'i'}
        if E1_Start: query['E1 - START'] = {'$regex': E1_Start, '$options': 'i'}
        if E1_End: query['E1 - END'] = {'$regex': E1_End, '$options': 'i'}
        if E2_Work: query['E2 - WORK'] = int(E2_Work)
        if E2_Pause: query['E2 - PAUSE'] = int(E2_Pause)
        if E2_Days: query['E2 - DAYS'] = {'$regex': E2_Days, '$options': 'i'}
        if E2_Start: query['E2 - START'] = {'$regex': E2_Start, '$options': 'i'}
        if E2_End: query['E2 - END'] = {'$regex': E2_End, '$options': 'i'}
        if E3_Work: query['E3 - WORK'] = int(E3_Work)
        if E3_Pause: query['E3 - PAUSE'] = int(E3_Pause)
        if E3_Days: query['E3 - DAYS'] = {'$regex': E3_Days, '$options': 'i'}
        if E3_Start: query['E3 - START'] = {'$regex': E3_Start, '$options': 'i'}
        if E3_End: query['E3 - END'] = {'$regex': E3_End, '$options': 'i'}
        if E4_Work: query['E4 - WORK'] = int(E4_Work)
        if E4_Pause: query['E4 - PAUSE'] = int(E4_Pause)
        if E4_Days: query['E4 - DAYS'] = {'$regex': E4_Days, '$options': 'i'}
        if E4_Start: query['E4 - START'] = {'$regex': E4_Start, '$options': 'i'}
        if E4_End: query['E4 - END'] = {'$regex': E4_End, '$options': 'i'}
        if Model: query['Model'] = {'$regex': Model, '$options': 'i'}
        if Colour: query['Color'] = {'$regex': Colour, '$options': 'i'}
        if Current_EO: query['Current EO'] = {'$regex': Current_EO, '$options': 'i'}
        if New_EO: query['New EO'] = {'$regex': New_EO, '$options': 'i'}
        if Scent_Effectiveness: query['#1 Scent Effectiveness'] = {'$regex': Scent_Effectiveness, '$options': 'i'}
        if Common_Encounters: query['#1 Common encounters'] = {'$regex': Common_Encounters, '$options': 'i'}
        if Other_Remarks: query['#1 Other remarks'] = {'$regex': Other_Remarks, '$options': 'i'}
        query_params = request.args.to_dict(); query_params['page'] = page; query_params['limit'] = limit
        total_entries = services_collection.count_documents(query)
        services_collection_list = services_collection.find(query, {'_id': 0}).skip((page - 1) * limit).limit(limit)
        processed_data = []
        for entry in services_collection_list:
            month_year_date = entry.get('month_year')
            if isinstance(month_year_date, datetime): entry['month'] = month_year_date.month; entry['year'] = month_year_date.year
            try: entry["S/N"] = int(entry["S/N"])
            except Exception: entry["S/N"] = 0
            processed_data.append(entry)
        total_pages = (total_entries + limit - 1) // limit
        return render_template("reports.html", username=session["username"], data=processed_data, page=page, total_pages=total_pages,limit=limit,pagination_base_url=f"{request.path}?",query_params=query_params)
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for("login"))

@app.route('/pack-list',methods=['GET'])
def pack_list():
    if 'username' in session:
        page = int(request.args.get('page', 1)); limit = int(request.args.get('limit', 20))
        device_page = int(request.args.get('device_page', 1)); device_limit = int(request.args.get('device_limit', 20))
        bottle_page = int(request.args.get('bottle_page', 1)); bottle_limit = int(request.args.get('bottle_limit', 20))
        straw_page = int(request.args.get('straw_page', 1)); straw_limit = int(request.args.get('straw_limit', 20))
        month = request.args.get('month','').strip(); year = request.args.get('year','').strip()
        eo = request.args.get('eo_name'); ml_required = request.args.get('ml_required')
        packed = request.args.get('packed'); ready_supply = request.args.get('ready_supply')
        ml_fresh_supply = request.args.get('ml_fresh_supply'); ml_balance = request.args.get('ml_balance')
        perc_balance = request.args.get('perc_balance')
        device_month = request.args.get('device_month','').strip(); device_year = request.args.get('device_year','').strip()
        devices = request.args.get('devices'); device_quantity = request.args.get('device_quantity')
        bottle_month = request.args.get('bottle_month','').strip(); bottle_year = request.args.get('bottle_year','').strip()
        empty_bottle = request.args.get('empty_bottle'); bottle_volume = request.args.get('bottle_volume')
        straw_month = request.args.get('straw_month','').strip(); straw_year = request.args.get('straw_year','').strip()
        model_others = request.args.get('model_others'); final_quantity = request.args.get('final_quantity')
        actual_quantity = request.args.get('actual_quantity'); extra = request.args.get('extra')
        device_query, query, bottle_query, other_query = {}, {}, {}, {}
        def apply_month_year_filter(q, m, y_str):
            if m and y_str:
                month_list = [int(val.strip()) for val in m.split(',') if val.strip().isdigit()]
                q['$expr'] = {'$and': [{'$in': [{'$month': '$month_year'}, month_list]}, {'$eq': [{'$year': '$month_year'}, int(y_str)]}]}
        apply_month_year_filter(query, month, year); apply_month_year_filter(device_query, device_month, device_year)
        apply_month_year_filter(bottle_query, bottle_month, bottle_year); apply_month_year_filter(other_query, straw_month, straw_year)
        if device_quantity: device_query['quantity'] = int(device_quantity)
        if empty_bottle: bottle_query['empty_bottles'] = int(empty_bottle)
        if bottle_volume: bottle_query['volume'] = int(bottle_volume)
        if actual_quantity: other_query['actual_quantity'] = int(actual_quantity)
        if final_quantity: other_query['final_quantity'] = int(final_quantity)
        if ml_required: query['ml_required'] = int(ml_required)
        if packed: query['packed'] = int(packed)
        if ready_supply: query['ready_supply'] = int(ready_supply)
        if ml_fresh_supply: query['ml_fresh_supply'] = int(ml_fresh_supply)
        if ml_balance: query['ml_balance'] = int(ml_balance)
        if perc_balance: query['perc_balance'] = int(perc_balance)
        if extra: other_query['extra'] = int(extra)
        if model_others: other_query['model'] = {'$regex': model_others, '$options': 'i'}
        if eo: query['eo_name'] = {'$regex': eo, '$options': 'i'}
        if devices: device_query['devices'] = {'$regex': devices, '$options': 'i'}
        query_params = request.args.to_dict(); query_params.update({'page': page, 'limit': limit})
        query_params_device = request.args.to_dict(); query_params_device.update({'device_page': device_page, 'device_limit': device_limit})
        query_params_bottle = request.args.to_dict(); query_params_bottle.update({'bottle_page': bottle_page, 'bottle_limit': bottle_limit})
        query_params_straw = request.args.to_dict(); query_params_straw.update({'straw_page': straw_page, 'straw_limit': straw_limit})
        pagination_base_url = f"{request.path}?"
        total_eo_pack = eo_pack_collection.count_documents(query); total_device_pack = others_list_collection.count_documents(device_query)
        total_bottle_pack = empty_bottles_list_collection.count_documents(bottle_query); total_straw_pack = straw_list_collection.count_documents(other_query)
        data_eo_pack_list = list(eo_pack_collection.find(query, {'_id':0}).skip((page-1)*limit).limit(limit))
        data_device_pack_list = list(others_list_collection.find(device_query, {'_id':0}).skip((device_page-1)*device_limit).limit(device_limit))
        data_bottle_pack_list = list(empty_bottles_list_collection.find(bottle_query, {'_id':0}).skip((bottle_page-1)*bottle_limit).limit(bottle_limit))
        data_other_pack_list = list(straw_list_collection.find(other_query, {'_id':0}).skip((straw_page-1)*straw_limit).limit(straw_limit))
        def process_entries(entries):
            processed = []
            for entry in entries:
                month_year_date = entry.get('month_year')
                if isinstance(month_year_date, datetime): entry['month'] = month_year_date.month; entry['year'] = month_year_date.year
                processed.append(entry)
            return processed
        return render_template("pack-list.html", username=session["username"],
            data=process_entries(data_eo_pack_list), device_data=process_entries(data_device_pack_list),
            bottle_data=process_entries(data_bottle_pack_list), straw_data=process_entries(data_other_pack_list),
            page=page, total_pages=(total_eo_pack + limit - 1) // limit, limit=limit, query_params=query_params,
            device_page=device_page, total_device_pages=(total_device_pack + device_limit - 1) // device_limit, device_limit=device_limit, query_params_device=query_params_device,
            bottle_page=bottle_page, total_bottle_pages=(total_bottle_pack + bottle_limit - 1) // bottle_limit, bottle_limit=bottle_limit, query_params_bottle=query_params_bottle,
            straw_page=straw_page, total_straw_pages=(total_straw_pack + straw_limit - 1) // straw_limit, straw_limit=straw_limit, query_params_straw=query_params_straw,
            pagination_base_url=pagination_base_url)
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for("login"))

@app.route('/eo-list',methods=['GET'])
def eo_list():
    if 'username' in session:
        page = int(request.args.get('page', 1)); limit = int(request.args.get('limit', 20))
        model_page = int(request.args.get('model_page', 1)); model_limit = int(request.args.get('model_limit', 20))
        month = request.args.get('month','').strip(); year = request.args.get('year','').strip()
        eo = request.args.get('EO'); volume = request.args.get('Volume')
        model_month = request.args.get('model_month','').strip(); model_year = request.args.get('model_year','').strip()
        quantity = request.args.get('Quantity'); total_batteries = request.args.get('total_batteries')
        model_type = request.args.get('model_type'); battery_type = request.args.get('battery_type'); remark = request.args.get('Remark')
        model_query, query = {}, {}
        def apply_month_year_filter(q, m, y_str):
            if m and y_str:
                month_list = [int(val.strip()) for val in m.split(',') if val.strip().isdigit()]
                q['$expr'] = {'$and': [{'$in': [{'$month': '$month_year'}, month_list]}, {'$eq': [{'$year': '$month_year'}, int(y_str)]}]}
        apply_month_year_filter(query, month, year); apply_month_year_filter(model_query, model_month, model_year)
        if quantity: model_query['quantity'] = int(quantity)
        if total_batteries: model_query['total_batteries'] = int(total_batteries)
        if model_type: model_query['model2'] = {'$regex': model_type, '$options': 'i'}
        if battery_type: model_query['battery_type'] = {'$regex': battery_type, '$options': 'i'}
        if remark: model_query['remark'] = {'$regex': remark, '$options': 'i'}
        if eo: query['EO2'] = {'$regex': eo, '$options': 'i'}
        if volume: query['Volume'] = int(volume)
        query_params = request.args.to_dict(); query_params.update({'page': page, 'limit': limit})
        query_params_model = request.args.to_dict(); query_params_model.update({'model_page': model_page, 'model_limit': model_limit})
        base_url = request.path
        total_entries_eo_list = eo_list_collection.count_documents(query); total_entries_model_list = model_list_collection.count_documents(model_query)
        data_eo_list = list(eo_list_collection.find(query, {'_id': 0}).skip((page - 1) * limit).limit(limit))
        data_model_list = list(model_list_collection.find(model_query, {'_id':0}).skip((model_page-1)*model_limit).limit(model_limit))
        def process_entries(entries):
            processed = []
            for entry in entries:
                month_year_date = entry.get('month_year')
                if isinstance(month_year_date, datetime): entry['month'] = month_year_date.month; entry['year'] = month_year_date.year
                processed.append(entry)
            return processed
        return render_template("eo-list.html", username=session["username"], data=process_entries(data_eo_list), model_data=process_entries(data_model_list),
            model_page=model_page, total_model_pages=(total_entries_model_list + model_limit -1) // model_limit, model_limit=model_limit, query_params_model=query_params_model,
            page=page, total_pages=(total_entries_eo_list + limit - 1) // limit, limit=limit, query_params=query_params,
            pagination_base_url=f"{base_url}?", pagination_base_url_model=f"{base_url}?")
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for("login"))
        
@app.route("/dashboard")
def dashboard():
    if "username" in session:
        remarks = list(remark_collection.find({}))
        urgent_remarks = [r for r in remarks if r.get('urgent')]
        non_urgent_remarks = [r for r in remarks if not r.get('urgent')]
        help_request = list(collection.find({}))
        change = list(changed_models_collection.find({}))
        refund = list(discontinue_collection.find({}))
        return render_template("dashboard.html", username=session["username"], remarks_count=len(non_urgent_remarks), urgent_remarks_count=len(urgent_remarks), help_request_count=len(help_request), change_count = len(change), refund_count=len(refund))
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for("login"))

@app.route('/change-form', methods=['GET', 'POST'])
def change_form():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        form_data_dict = {
            "user": request.form.get("user") or session.get("username"),
            "companyName": request.form.get("companyName"),
            "date": request.form.get("date") or datetime.now().strftime('%Y-%m-%d'),
            "month": request.form.get("month"),
            "year": request.form.get("year"),
            "premises": request.form.getlist("premises"),
            "devices": request.form.getlist("devices"),
            "changeScent": request.form.get("changeScent") == "on",
            "changeScentText": request.form.get("changeScentText"),
            "redoSettings": request.form.get("redoSettings") == "on",
            "reduceIntensity": request.form.get("reduceIntensity") == "on",
            "increaseIntensity": request.form.get("increaseIntensity") == "on",
            "moveDevice": request.form.get("moveDevice") == "on",
            "moveDeviceText": request.form.get("moveDeviceText"),
            "relocateDevice": request.form.get("relocateDevice") == "on",
            "relocateDeviceDropdown": request.form.get("relocateDeviceDropdown"),
            "collectBack": request.form.get("collectBack") == "on",
            "remark": request.form.get("remark"),
            "submitted_at": datetime.now()
        }

        data_for_db = { # This dictionary is used for DB insertion
            "user": form_data_dict["user"], "company": form_data_dict["companyName"],
            "date": form_data_dict["date"], "month": form_data_dict["month"], "year": form_data_dict["year"],
            "premises": form_data_dict["premises"], "devices": form_data_dict["devices"],
            "change_scent": form_data_dict["changeScent"], "change_scent_to": form_data_dict["changeScentText"],
            "redo_settings": form_data_dict["redoSettings"], "reduce_intensity": form_data_dict["reduceIntensity"],
            "increase_intensity": form_data_dict["increaseIntensity"], "move_device": form_data_dict["moveDevice"],
            "move_device_to": form_data_dict["moveDeviceText"], "relocate_device": form_data_dict["relocateDevice"],
            "relocate_device_to": form_data_dict["relocateDeviceDropdown"], "collect_back": form_data_dict["collectBack"],
            "remark": form_data_dict["remark"], "submitted_at": form_data_dict["submitted_at"]
        }

        month_str_to_int = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}

        if data_for_db["collect_back"]:
            month_name = data_for_db.get("month")
            year_str = data_for_db.get("year")
            if month_name and year_str:
                try:
                    month_int = month_str_to_int[month_name.upper()]
                    year_int = int(year_str)
                    data_for_db["collect_back_date_dt"] = datetime(year_int, month_int, 1)
                except (ValueError, KeyError) as e:
                    flash(f"Invalid month or year provided for collect back date: {e}", "danger")
            discontinue_collection.insert_one(data_for_db)
            log_activity(session["username"], f"collected back (discontinue_collection): {data_for_db.get('premises')} {data_for_db.get('devices')}", logs_collection)
        else:
            changed_models_collection.insert_one(data_for_db)
            log_activity(session["username"], f"updated settings (changed_models_collection): {data_for_db.get('premises')} {data_for_db.get('devices')}", logs_collection)

            # Update services_collection based on the change form
            if not data_for_db["collect_back"]:
                service_update_query = {
                    "company": data_for_db.get("company"),
                    "Premise Name": {"$in": data_for_db.get("premises", [])},
                    "Model": {"$in": data_for_db.get("devices", [])}
                }

                service_update_values = {"$set": {}}

                if data_for_db.get("change_scent") and data_for_db.get("change_scent_to"):
                    service_update_values["$set"]["Current EO"] = data_for_db["change_scent_to"]

                if data_for_db.get("move_device") and data_for_db.get("move_device_to"):
                    service_update_values["$set"]["Location"] = data_for_db["move_device_to"]

                if data_for_db.get("relocate_device") and data_for_db.get("relocate_device_to"):
                    service_update_values["$set"]["Premise Name"] = data_for_db["relocate_device_to"]
                    # Assuming Location should also reflect the new premise, or a more specific location within it.
                    # For now, setting it to the new premise name for simplicity.
                    service_update_values["$set"]["Location"] = data_for_db["relocate_device_to"]

                # Regarding Model, Color, Volume updates:
                # The current form structure (form_data_dict/data_for_db) does not provide explicit fields for *new* Model, Color, or Volume.
                # The 'devices' field in the form is used to *identify* existing devices to apply changes to, not to specify a new model type.
                # 'redoSettings' might imply resetting to defaults, but the form doesn't specify what those defaults are or where they'd come from.
                # Therefore, updating Model, Color, and Volume "based on new settings provided in the change form" is not possible
                # without either new form fields for these values or a different interpretation of existing fields.
                # For now, only Current EO and Location/Premise Name are updated as per clear form fields.
                # If `redoSettings` is true and implies changing Model, Color, Volume, the specific new values are not provided by the form.
                # For example, if `data_for_db.get("redo_settings")` is true:
                #   if data_for_db.get("devices"):
                #       service_update_values["$set"]["Model"] = data_for_db.get("devices")[0] # Highly speculative
                #   service_update_values["$set"]["Color"] = "" # No source from form
                #   service_update_values["$set"]["Volume"] = 0 # No source from form
                # Due to this ambiguity and lack of direct form fields, Model, Color, Volume are not being updated in this modification.

                if service_update_values["$set"]:
                    update_result = services_collection.update_many(service_update_query, service_update_values)
                    log_activity(session["username"], f"Applied changes to services_collection: {update_result.modified_count} devices updated for company {data_for_db.get('company')}", logs_collection)
                    flash(f"{update_result.modified_count} devices updated in services records.", "info")

        try:
            pdf_bytes = generate_change_form_pdf_bytes(form_data_dict) # Use the consistent dict
            client_emails = []
            company_name_for_email = form_data_dict.get("companyName")
            if company_name_for_email:
                pic_records = profile_list_collection.find({"company": company_name_for_email, "email": {"$exists": True, "$ne": ""}})
                for record in pic_records:
                    if record.get("email") and record.get("email") not in client_emails:
                        client_emails.append(record.get("email"))

            admin_email = app.config.get('MAIL_USERNAME')
            email_subject = f"Change Request Summary - {form_data_dict.get('companyName')}"
            email_body = "Please find attached the summary of the recent change request."
            attachment_details = {'filename': 'Change_Form_Summary.pdf', 'content_type': 'application/pdf', 'data': pdf_bytes}

            if client_emails:
                for c_email in client_emails:
                    send_email(to_email=c_email, from_email=app.config['MAIL_USERNAME'], subject=email_subject, body=email_body, mail=mail, attachments=[attachment_details])
                flash(f"Change form submitted and email sent to client(s) at {', '.join(client_emails)}.", "success")
            else:
                 flash("Change form submitted. No client email found for notification.", "warning")
            if admin_email: # Also send to admin
                send_email(to_email=admin_email, from_email=app.config['MAIL_USERNAME'], subject=f"Admin Copy: {email_subject}", body=email_body, mail=mail, attachments=[attachment_details])
        except Exception as e:
            print(f"Error during PDF generation or emailing: {e}")
            flash(f"Data saved, but failed to generate or email PDF: {e}", "danger")
        return redirect(url_for("dashboard"))

    companies = services_collection.distinct('company')
    premises = []

    return render_template(
        'change-form.html',
        username=session.get('username'),
        companies=companies,
        premises=premises,
        current_date=datetime.now().strftime('%Y-%m-%d')
    )

@app.route('/remarks/<remark_type>')
def view_remarks(remark_type):
    if 'username' not in session:
        return redirect(url_for('login'))
    is_urgent = True if remark_type == 'urgent' else False
    remarks = list(remark_collection.find({'urgent': is_urgent}))
    return render_template('view_remarks.html', remarks=remarks, remark_type=remark_type)


@app.route('/discontinue-list', methods=['GET'])
def discontinued_reports():
    if 'username' not in session:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('login'))

    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    skip = (page - 1) * limit

    # Get filters
    query = {}
    user = request.args.get('user', '').strip()
    company = request.args.get('company', '').strip()
    month = request.args.get('month', '').strip()
    year = request.args.get('year', '').strip()
    collect_back = request.args.get('collect_back', '').strip()
    change_scent = request.args.get('change_scent', '').strip()

    if user:
        query['user'] = {'$regex': user, '$options': 'i'}
    if company:
        query['company'] = {'$regex': company, '$options': 'i'}
    if month and year:
        query['$expr'] = {
            '$and': [
                {'$eq': [{'$month': '$date'}, int(month)]},
                {'$eq': [{'$year': '$date'}, int(year)]}
            ]
        }
    if collect_back:
        query['collect_back'] = True if collect_back.lower() == 'true' else False
    if change_scent:
        query['change_scent'] = True if change_scent.lower() == 'true' else False

    total_entries = discontinue_collection.count_documents(query)
    results = list(discontinue_collection.find(query).skip(skip).limit(limit))

    # Convert ISO date strings if needed
    for r in results:
        if isinstance(r.get("date"), str):
            r["date"] = r["date"][:10]
        if isinstance(r.get("submitted_at"), str):
            r["submitted_at"] = r["submitted_at"][:16]
        if isinstance(r.get("collect_back_date_dt"), str):
            r["collect_back_date_dt"] = r["collect_back_date_dt"][:16]

    total_pages = (total_entries + limit - 1) // limit
    query_params = request.args.to_dict()
    query_params['page'] = page
    query_params['limit'] = limit

    return render_template("discontinue_list.html",
                           data=results,
                           page=page,
                           total_pages=total_pages,
                           pagination_base_url=request.path,
                           query_params=query_params)


@app.route("/logout")
def logout():
    if "user_id" in session:
        try: log_activity(session["username"],"logout" ,logs_collection)
        except Exception: pass
        session.clear()
        flash("You have been logged out.", "success")
    return redirect(url_for("index"))

@app.route("/client-login", methods=["GET", "POST"])
def client_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = login_cust_collection.find_one({"email": email})
        if user and check_password_hash(user["password"], password):
            session["user_id"] = str(user["_id"])
            session["customer_email"] = user["email"]
            flash("Login successful!", "success")
            return redirect(url_for("customer_form"))
        else:
            flash("Invalid email or password.", "danger")
    return render_template("index.html") # Should redirect to index or login if already on index

@app.route('/image2/<image_id>')
def get_image2(image_id):
    image = fs.get(ObjectId(image_id))
    return send_file(io.BytesIO(image.read()), mimetype=image.content_type)

@app.route('/new-customer',methods=['GET', 'POST'])
def new_customer():
    if 'username' not in session:
        return redirect(url_for('login'))

    raw_models = list(model_list_collection.find().sort("order", 1))
    models = [{k: v for k, v in model.items() if k != '_id'} for model in raw_models]

    eo_raw = list(eo_pack_collection.find().sort("order", 1))
    essential_oils = [{k: v for k, v in eo.items() if k != '_id'} for eo in eo_raw]

    if request.method == "POST":
        date_str = request.form.get("dateCreated")
        dateCreated = datetime.strptime(date_str, "%Y-%m-%d") if date_str else None

        companyName = request.form.get("companyName")
        industry = request.form.get("industry")

        premises = []
        pic_records = []
        device_records = []
        master_list = []

        if companyName:
            premise_map = {}
            pic_map = {}

            # Extract Premises
            k = 1
            while True:
                pname = request.form.get(f'premiseName{k}')
                parea = request.form.get(f'premiseArea{k}')
                paddr = request.form.get(f'premiseAddress{k}')
                if not pname:
                    break

                prem = {
                    "company": companyName,
                    "month_year": datetime.now(),
                    "industry": industry,
                    "premise_name": pname,
                    "premise_area": parea,
                    "premise_address": paddr,
                    "created_at": datetime.now(),
                }
                premises.append(prem)
                premise_map[pname] = prem
                k += 1

            # Extract PICs
            i = 1
            while True:
                pic_name = request.form.get(f'picName{i}')
                if not pic_name:
                    break
                picdata = {
                    "company": companyName,
                    "tied_to_premise": request.form.get(f'contactPremise{i}'),
                    "name": pic_name,
                    "designation": request.form.get(f'picDesignation{i}'),
                    "contact": request.form.get(f'picContact{i}'),
                    "email": request.form.get(f'picEmail{i}'),
                    "created_at": datetime.now(),
                }
                pic_records.append(picdata)

                tied = picdata["tied_to_premise"]
                if tied:
                    if tied == "all":
                        for pname in premise_map:
                            pic_map.setdefault(pname, []).append(picdata)
                    else:
                        pic_map.setdefault(tied, []).append(picdata)
                i += 1

            # Extract Devices and Build Master List
            j = 1
            while True:
                sn = request.form.get(f'deviceSN{j}')
                if not sn:
                    break

                devicedata = {
                    "company": companyName,
                    "tied_to_premise": request.form.get(f'devicePremise{j}'),
                    "location": request.form.get(f'deviceLocation{j}'),
                    "S/N": safe_int(sn),
                    "Model": request.form.get(f'deviceModel{j}'),
                    "Color": request.form.get(f'deviceColour{j}'),
                    "Volume": safe_int(request.form.get(f'deviceVolume{j}')),
                    "Current EO": request.form.get(f'deviceScent{j}'),
                    "E1 - DAYS": request.form.get(f"E1Days{j}"),
                    "E1 - START": request.form.get(f"E1StartTime{j}"),
                    "E1 - END": request.form.get(f"E1EndTime{j}"),
                    "E1 - PAUSE": safe_int(request.form.get(f"E1Pause{j}")),
                    "E1 - WORK": safe_int(request.form.get(f"E1Work{j}")),
                    "E2 - DAYS": request.form.get(f"E2Days{j}"),
                    "E2 - START": request.form.get(f"E2StartTime{j}"),
                    "E2 - END": request.form.get(f"E2EndTime{j}"),
                    "E2 - PAUSE": safe_int(request.form.get(f"E2Pause{j}")),
                    "E2 - WORK": safe_int(request.form.get(f"E2Work{j}")),
                    "E3 - DAYS": request.form.get(f"E3Days{j}"),
                    "E3 - START": request.form.get(f"E3StartTime{j}"),
                    "E3 - END": request.form.get(f"E3EndTime{j}"),
                    "E3 - PAUSE": safe_int(request.form.get(f"E3Pause{j}")),
                    "E3 - WORK": safe_int(request.form.get(f"E3Work{j}")),
                    "E4 - DAYS": request.form.get(f"E4Days{j}"),
                    "E4 - START": request.form.get(f"E4StartTime{j}"),
                    "E4 - END": request.form.get(f"E4EndTime{j}"),
                    "E4 - PAUSE": safe_int(request.form.get(f"E4Pause{j}")),
                    "E4 - WORK": safe_int(request.form.get(f"E4Work{j}")),
                    "created_at": datetime.now(),
                }
                device_records.append(devicedata)

                premise_name = devicedata["tied_to_premise"]
                premise_data = premise_map.get(premise_name, {})
                assigned_pics = pic_map.get(premise_name, [])
                if not assigned_pics:
                    # If no valid PICs found, skip this device for master list
                    continue

                premise_data = premise_map.get(premise_name)
                if not premise_data:
                    # If no valid premise found, skip this device for master list
                    continue

                for pic in assigned_pics:
                    if not pic.get("name"):  # Skip empty PICs
                        continue

                    master_record = {
                        "company": companyName,
                        "industry": industry,
                        "month_year": dateCreated,

                        # Remapped Premise Info
                        "Premise Name": premise_data.get("premise_name"),
                        "Premise Area": premise_data.get("premise_area"),
                        "Premise Address": premise_data.get("premise_address"),

                        # Remapped PIC Info
                        "PIC Name": pic.get("name"),
                        "Designation": pic.get("designation"),
                        "Contact": pic.get("contact"),
                        "Email": pic.get("email"),

                        # Device Info
                        "S/N": devicedata["S/N"],
                        "Model": devicedata["Model"],
                        "Color": devicedata["Color"],
                        "Volume": devicedata["Volume"],
                        "Location": devicedata["location"],
                        "Current EO": devicedata["Current EO"],
                        "E1 - DAYS": devicedata.get("E1 - DAYS"),
                        "E1 - START": devicedata.get("E1 - START"),
                        "E1 - END": devicedata.get("E1 - END"),
                        "E1 - WORK": devicedata.get("E1 - WORK"),
                        "E1 - PAUSE": devicedata.get("E1 - PAUSE"),
                        "E2 - DAYS": devicedata.get("E2 - DAYS"),
                        "E2 - START": devicedata.get("E2 - START"),
                        "E2 - END": devicedata.get("E2 - END"),
                        "E2 - WORK": devicedata.get("E2 - WORK"),
                        "E2 - PAUSE": devicedata.get("E2 - PAUSE"),
                        "E3 - DAYS": devicedata.get("E3 - DAYS"),
                        "E3 - START": devicedata.get("E3 - START"),
                        "E3 - END": devicedata.get("E3 - END"),
                        "E3 - WORK": devicedata.get("E3 - WORK"),
                        "E3 - PAUSE": devicedata.get("E3 - PAUSE"),
                        "E4 - DAYS": devicedata.get("E4 - DAYS"),
                        "E4 - START": devicedata.get("E4 - START"),
                        "E4 - END": devicedata.get("E4 - END"),
                        "E4 - WORK": devicedata.get("E4 - WORK"),
                        "E4 - PAUSE": devicedata.get("E4 - PAUSE"),
                    }
                    master_list.append(master_record)


                j += 1

        # Insert into MongoDB
        if premises:
            profile_list_collection.insert_many(premises)
        if pic_records:
            profile_list_collection.insert_many(pic_records)
        if device_records:
            device_list_collection.insert_many(device_records)
        if master_list:
            if app.config['MODE'] == "PROD":
                services_collection.insert_many(master_list)
            else:
                test_collection.insert_many(master_list)

        log_activity(session["username"], f"added new customer: {companyName}", logs_collection)
        flash(f"Company {companyName} added successfully!", "success")
        return redirect(url_for("new_customer"))

    return render_template('new-customer.html', models=models, essential_oils=essential_oils)

@app.route('/pre-service',  methods=['GET', 'POST'])
def pre_service():
    if "username" not in session: return redirect(url_for('login'))
    companies = services_collection.distinct('company')
    if request.method == 'POST':
        date_str = request.form.get('date')
        date_obj = datetime.fromisoformat(date_str.rstrip("Z")) if date_str else None
        entry = {"date": date_obj, "company": request.form.get('company'), "premise": request.form.get('premise'), "model": request.form.get('model'), "color": request.form.get('color'), "eo": request.form.get('eo')}
        route_list_collection.insert_one(entry)
        flash(f"Company: {request.form.get('company')}, Premise: {request.form.get('premise')} preservice added successfully!", "success")
        log_activity(session["username"],"pre-service : " +str(request.form.get('company')) + " : " +str(request.form.get('premise')),logs_collection)
        return render_template('pre-service.html', companies=companies)
    return render_template('pre-service.html', companies=companies)

@app.route('/get-models/<premise>')
def get_models(premise):
    models_cursor = services_collection.find({"Premise Name": premise}, {"Model": 1, "_id": 0}) # Corrected variable name
    models_list = [m['Model'] for m in models_cursor if 'Model' in m and m['Model']] # Added check for m['Model']
    return jsonify(list(set(models_list))) # Return unique models

@app.route('/get-colors/<model>/<premise>')
def get_colors(model, premise):
    colors_cursor = services_collection.find({"Model": model, "Premise Name": premise}, {"Color": 1, "_id": 0}) # Corrected variable name
    unique_colors = list(set(c.get('Color') for c in colors_cursor if c.get('Color')))
    return jsonify(unique_colors)

@app.route('/get-eo/<model>/<premise>/<color>')
def get_eo(model, premise, color):
    eos_cursor = services_collection.find({"Model": model, "Premise Name": premise, "Color": color}, {"Current EO": 1, "_id": 0}) # Corrected variable name
    unique_eos = list(set(e.get('Current EO') for e in eos_cursor if e.get('Current EO')))
    return jsonify(unique_eos)

@app.route('/remark', methods=['GET', 'POST'])
def remark():
    if 'username' not in session: return redirect(url_for('login'))
    username = session['username']
    if request.method == 'POST':
        remark_text = request.form['remark']
        is_urgent = 'urgent' in request.form
        log_activity(session["username"],"added remarks : " +str(remark_text) + "urgent : " + str(is_urgent),logs_collection)
        remark_collection.insert_one({'username': username, 'remark': remark_text, 'urgent': is_urgent})
        return redirect(url_for('dashboard'))
    return render_template('remark.html', username=username)

@app.route("/get-devices1")
def get_devices1():
    premise_name = request.args.get("premiseName")
    devices_cursor = services_collection.find({"Premise Name": premise_name}, {"Model": 1, "_id":0}) # Corrected variable name
    devices_list = [device["Model"] for device in devices_cursor if "Model" in device]
    return jsonify({"devices": list(set(devices_list))}) # Return unique list

@app.route("/get_companies", methods=["GET"])
def get_companies():
    companies_cursor = services_collection.find({}, {"company": 1, "_id": 0}) # Corrected variable name
    unique_companies = sorted(list(set(c.get("company") for c in companies_cursor if c.get("company"))))
    return jsonify(unique_companies)

@app.route("/get_essential_oils", methods=["GET"])
def get_essential_oils():
    essential_oils_cursor = eo_pack_collection.find({}, {"eo_name": 1, "_id": 0}) # Corrected variable name
    return jsonify([eo["eo_name"] for eo in essential_oils_cursor if "eo_name" in eo])

@app.route("/get-premises-test")
def get_premises_test():
    company_name = request.args.get("companyName")
    premises_cursor = services_collection.find({"company": company_name}, {"Premise Name": 1, "_id": 0})
    premises_list = [p["Premise Name"] for p in premises_cursor if "Premise Name" in p]
    return jsonify({"premises": list(set(premises_list))}) # Return unique list

@app.route("/get_devices_post", methods=["POST"])
def get_devices_post():
    premise_name = request.json.get("premise")
    devices_cursor = device_list_collection.find({"tied_to_premise": premise_name}, {"Model": 1, "_id": 0})
    devices_list = [d["Model"] for d in devices_cursor if "Model" in d]
    return jsonify({"models": list(set(devices_list))}) # Return unique list and key 'models'

@app.route("/post-service", methods=["POST", "GET"])
def post_service():
    if 'username' not in session: return redirect(url_for('login'))
    username = session['username']
    if request.method == "POST":
        essential_oil = request.form.get("essential_oil")
        try:
            oil_balance = int(request.form.get("oil_balance"))
            balance_brought_back = int(request.form.get("balance_brought_back"))
            refill_amount = int(request.form.get("refill_amount"))
        except (ValueError, TypeError): # Catch TypeError if value is None
            flash("Numeric fields must be valid integers.", "danger")
            return render_template('post-service.html', username=username)
        balance_brought_back_percent = request.form.get("balance_brought_back_percent")
        refill_amount_percent = request.form.get("refill_amount_percent")
        month_year = datetime.now()
        query = {"essential_oil": essential_oil}
        update = {"$set": {"oil_balance": oil_balance, "balance_brought_back": balance_brought_back, "balance_brought_back_percent": balance_brought_back_percent, "refill_amount": refill_amount, "refill_amount_percent": refill_amount_percent, "month_year": month_year}}
        eo_pack_collection.update_one(query, update, upsert=True)
        log_activity(username, f"Updated/added post-service record for essential oil: {essential_oil}", logs_collection)
        flash(f"Record for {essential_oil} updated successfully!", "success")
        return redirect(url_for("dashboard"))
    return render_template('post-service.html', username=username)

@app.route('/view-users', methods=['GET'])
def view_users():
    if 'username' not in session: return redirect(url_for('login'))
    page = int(request.args.get('page', 1)); limit = int(request.args.get('limit', 20))
    username_filter = request.args.get('username'); email_filter = request.args.get('email')
    query = {}
    if username_filter: query["username"] = {"$regex": username_filter, "$options": "i"}
    if email_filter: query["email"] = {"$regex": email_filter, "$options": "i"}
    total_list = login_cust_collection.count_documents(query)
    users = list(login_cust_collection.find(query, {'username': 1, 'email': 1, '_id': 1}).skip((page - 1) * limit).limit(limit))
    for user_item in users: user_item['_id'] = str(user_item['_id']) # Renamed user to user_item
    total_pages = (total_list + limit - 1) // limit
    query_params = request.args.to_dict(); query_params.update({'page': page, 'limit': limit})
    return render_template('view-users.html',users=users, page=page, total_pages=total_pages, limit=limit, pagination_base_url=f"{request.path}?", query_params=query_params)

@app.route('/view-admins', methods=['GET'])
def view_admins():
    if 'username' not in session: return redirect(url_for('login'))
    page = int(request.args.get('page', 1)); limit = int(request.args.get('limit', 20))
    username_filter = request.args.get('username')
    query = {}
    if username_filter: query["username"] = {"$regex": username_filter, "$options": "i"}
    total_list = login_collection.count_documents(query)
    admins = list(login_collection.find(query, {'username': 1,  '_id': 1}).skip((page - 1) * limit).limit(limit))
    for admin_item in admins: admin_item['_id'] = str(admin_item['_id']) # Renamed admin to admin_item
    total_pages = (total_list + limit - 1) // limit
    query_params = request.args.to_dict(); query_params.update({'page': page, 'limit': limit})
    return render_template('view-admins.html',admins=admins, page=page, total_pages=total_pages, limit=limit, pagination_base_url=f"{request.path}?", query_params=query_params)

@app.route('/logs', methods=['GET','POST'])
def get_logs():
    if 'username' not in session: return redirect(url_for('login'))
    page = int(request.args.get('page', 1)); limit = int(request.args.get('limit', 20))
    date_filter = request.args.get('date','').strip(); time_filter = request.args.get('time','').strip()
    user_filter = request.args.get('user'); action_filter = request.args.get('action')
    query = {}
    if date_filter and time_filter:
        try:
            datetime_start = datetime.strptime(f"{date_filter} {time_filter}", "%Y-%m-%d %H:%M")
            datetime_end = datetime_start.replace(second=59)
            query["timestamp"] = {"$gte": datetime_start, "$lte": datetime_end}
        except ValueError: pass
    elif date_filter:
        try:
            date_start = datetime.strptime(date_filter, "%Y-%m-%d")
            date_end = date_start.replace(hour=23, minute=59, second=59)
            query["timestamp"] = {"$gte": date_start, "$lte": date_end}
        except ValueError: pass
    if user_filter: query["user"] = {"$regex": user_filter, "$options": "i"}
    if action_filter: query["action"] = {"$regex": action_filter, "$options": "i"}
    total_list = logs_collection.count_documents(query)
    data_logs_list = list(logs_collection.find(query).sort("timestamp", -1).skip((page - 1) * limit).limit(limit))
    processed_data_logs_list = []
    for log_entry in data_logs_list:
        timestamp = log_entry.get("timestamp")
        if isinstance(timestamp, datetime):
            log_entry["date"] = timestamp.strftime("%Y-%m-%d")
            log_entry["time"] = timestamp.strftime("%H:%M:%S")
        processed_data_logs_list.append(log_entry)
    total_pages = (total_list + limit - 1) // limit
    query_params = request.args.to_dict(); query_params.update({'page': page, 'limit': limit})
    return render_template('activity-log.html', username=session["username"], data=processed_data_logs_list, page=page, total_pages=total_pages, limit=limit, pagination_base_url=f"{request.path}?", query_params=query_params)

@app.route('/profile', methods=['GET','POST'])
def profile():
    if 'username' not in session: return redirect(url_for('login'))
    page = int(request.args.get('page', 1)); limit = int(request.args.get('limit', 20))
    company_filter = request.args.get('company', '').strip(); industry_filter = request.args.get('industry', '').strip()
    premise_filter = request.args.get('premise', '').strip(); pic_filter = request.args.get('pic', '').strip()
    month_filter = request.args.get('month', '').strip(); year_filter = request.args.get('year', '').strip()
    query = {}
    if company_filter: query["company"] = {'$regex': company_filter, '$options': 'i'}
    if industry_filter: query["industry"] = {'$regex': industry_filter, '$options': 'i'}
    if premise_filter: query["premise_name"] = {'$regex': premise_filter, '$options': 'i'}
    if pic_filter: query["name"] = {'$regex': pic_filter, '$options': 'i'}
    if month_filter and year_filter:
        month_list = [int(m.strip()) for m in month_filter.split(',') if m.strip().isdigit()]
        try: # Ensure year_filter is an int for the query
            query['$expr'] = {'$and': [{'$in': [{'$month': '$created_at'}, month_list]}, {'$eq': [{'$year': '$created_at'}, int(year_filter)]}]}
        except ValueError: flash("Invalid year format for filter.", "warning")
    records = list(profile_list_collection.find(query))
    grouped_data = defaultdict(lambda: {"company": "", "industry": "", "premise_name": "", "premise_area": "", "premise_address": "", "month": "", "year": "", "pics": []})
    for record_item in records: # Renamed record to record_item
        created_at = record_item.get("created_at")
        if "premise_name" in record_item:
            key = (record_item["company"], record_item["premise_name"])
            grouped_data[key].update({"company": record_item["company"], "industry": record_item.get("industry", ""), "premise_name": record_item["premise_name"], "premise_area": record_item.get("premise_area", ""), "premise_address": record_item.get("premise_address", ""), "month": created_at.month if created_at else "", "year": created_at.year if created_at else ""})
        elif "tied_to_premise" in record_item:
            key = (record_item["company"], record_item["tied_to_premise"])
            if key in grouped_data:
                 grouped_data[key]["pics"].append({"name": record_item["name"], "designation": record_item.get("designation", ""), "contact": record_item.get("contact", ""), "email": record_item.get("email", "")})
    structured_data = list(grouped_data.values())
    total_records = len(structured_data); total_pages = (total_records + limit - 1) // limit
    paginated_data = structured_data[(page - 1) * limit: page * limit]
    query_params = request.args.to_dict()
    return render_template('profile.html', page=page, total_pages=total_pages, limit=limit, pagination_base_url=f"{request.path}?", query_params=query_params, data=paginated_data)

@app.route('/view-device', methods=['GET','POST'])
def view_device():
    if 'username' not in session: return redirect(url_for('login'))
    page = int(request.args.get('page', 1)); limit = int(request.args.get('limit', 20))
    filters = {k: request.args.get(k, '').strip() for k in ['company', 'tied_to_premise', 'location', 'sn', 'model', 'color', 'current_eo', 'e1_days', 'e1_start', 'e1_end', 'e1_pause', 'e1_work', 'e2_days', 'e2_start', 'e2_end', 'e2_pause', 'e2_work', 'e3_days', 'e3_start', 'e3_end', 'e3_pause', 'e3_work', 'e4_days', 'e4_start', 'e4_end', 'e4_pause', 'e4_work', 'month', 'year']}
    query = {}
    for key, value in filters.items():
        if not value: continue
        db_key_map = { # Map form field names to DB field names if different (e.g. S/N vs sn)
            'sn': 'S/N', 'e1_pause': 'E1 - PAUSE', 'e1_work': 'E1 - WORK',
            'e2_pause': 'E2 - PAUSE', 'e2_work': 'E2 - WORK',
            'e3_pause': 'E3 - PAUSE', 'e3_work': 'E3 - WORK',
            'e4_pause': 'E4 - PAUSE', 'e4_work': 'E4 - WORK',
            'current_eo': 'Current EO', 'e1_days': 'E1 - DAYS', 'e1_start': 'E1 - START', 'e1_end': 'E1 - END',
            'e2_days': 'E2 - DAYS', 'e2_start': 'E2 - START', 'e2_end': 'E2 - END',
            'e3_days': 'E3 - DAYS', 'e3_start': 'E3 - START', 'e3_end': 'E3 - END',
            'e4_days': 'E4 - DAYS', 'e4_start': 'E4 - START', 'e4_end': 'E4 - END',
            'color': 'Color', 'model': 'Model', 'company': 'company',
            'tied_to_premise': 'tied_to_premise', 'location': 'location'
        }
        db_key = db_key_map.get(key.lower(), key) # Default to key if no mapping

        if key in ['sn', 'e1_pause', 'e1_work', 'e2_pause', 'e2_work', 'e3_pause', 'e3_work', 'e4_pause', 'e4_work']:
            try: query[db_key] = int(value)
            except ValueError: flash(f"Invalid integer for {key}: {value}", "warning")
        elif key not in ['month', 'year']:
            query[db_key] = {'$regex': value, '$options': 'i'}

    if filters['month'] and filters['year']:
        month_list = [int(m.strip()) for m in filters['month'].split(',') if m.strip().isdigit()]
        try: query['$expr'] = {'$and': [{'$in': [{'$month': '$created_at'}, month_list]}, {'$eq': [{'$year': '$created_at'}, int(filters['year'])]}]}
        except ValueError: flash("Invalid year for filtering.", "warning")

    device_records = list(device_list_collection.find(query)) # Renamed records to device_records
    total_records = len(device_records); total_pages = (total_records + limit - 1) // limit
    paginated_data = device_records[(page - 1) * limit: page * limit]
    query_params = request.args.to_dict()
    return render_template('device.html', page=page, total_pages=total_pages, limit=limit, pagination_base_url=f"{request.path}?", query_params=query_params, data=paginated_data)

@app.route('/delete_record/<record_id>', methods=['POST'])
def delete_record(record_id): # This seems to be for profile_list_collection (PICs/Premises)
    if 'username' not in session: return jsonify({"error": "Unauthorized"}), 403
    # Also attempt to delete associated devices and master service records if a premise is deleted
    record_to_delete = profile_list_collection.find_one({"_id": ObjectId(record_id)})
    if record_to_delete and record_to_delete.get("premise_name"):
         premise_name_to_delete = record_to_delete.get("premise_name")
         company_name_of_deleted_premise = record_to_delete.get("company")
         # Delete devices tied to this premise_name and company
         device_list_collection.delete_many({"tied_to_premise": premise_name_to_delete, "company": company_name_of_deleted_premise})
         # Delete from services_collection (master list)
         services_collection.delete_many({"premise_name": premise_name_to_delete, "company": company_name_of_deleted_premise})
         test_collection.delete_many({"premise_name": premise_name_to_delete, "company": company_name_of_deleted_premise})


    result = profile_list_collection.delete_one({"_id": ObjectId(record_id)})
    if result.deleted_count > 0: return jsonify({"success": True, "message": "Record and associated data deleted successfully"}), 200
    return jsonify({"success": False, "message": "Record not found or not a premise record"}), 404


@app.route('/route_table', methods=['GET'])
def route_table():
    if 'username' not in session: return redirect(url_for('login'))
    page = int(request.args.get('page', 1)); limit = int(request.args.get('limit', 20))
    filters = {k: request.args.get(k, '').strip() for k in ['company', 'premise', 'day', 'month', 'year']}
    sort_order_arg = request.args.get("sort_order", "desc")
    query = {}
    if filters['company']: query["company"] = {'$regex': filters['company'], '$options': 'i'}
    if filters['premise']: query["premise"] = {'$regex': filters['premise'], '$options': 'i'} # field name is 'premise' in route_list_collection
    expr_conditions = []
    if filters['day']:
        try: expr_conditions.append({'$in': [{'$dayOfMonth': '$date'}, [int(d.strip()) for d in filters['day'].split(',') if d.strip().isdigit()]]})
        except ValueError: flash("Invalid day format for filter.", "warning")
    if filters['month']:
        try: expr_conditions.append({'$in': [{'$month': '$date'}, [int(m.strip()) for m in filters['month'].split(',') if m.strip().isdigit()]]})
        except ValueError: flash("Invalid month format for filter.", "warning")
    if filters['year']:
        try: expr_conditions.append({'$eq': [{'$year': '$date'}, int(filters['year'])]})
        except ValueError: flash("Invalid year for filtering", "warning")
    if expr_conditions: query['$expr'] = {'$and': expr_conditions} if len(expr_conditions) > 1 else expr_conditions[0]

    sort_mongo_order = -1 if sort_order_arg == "desc" else 1
    route_records = list(route_list_collection.find(query).sort("date", sort_mongo_order)) # Renamed records

    total_records = len(route_records); total_pages = (total_records + limit - 1) // limit
    paginated_data = route_records[(page - 1) * limit: page * limit]
    query_params = request.args.to_dict()
    return render_template('route-table.html', page=page, total_pages=total_pages, limit=limit, pagination_base_url=f"{request.path}?", query_params=query_params, data=paginated_data)

@app.route('/edit_record/<record_id>', methods=['POST'])
def edit_record(record_id):
    if 'username' not in session: return jsonify({"error": "Unauthorized"}), 403
    data = request.json
    # This route is generic. Determine collection based on fields or an explicit type field if added to data.
    # For now, assuming it's for profile_list_collection based on previous structure.
    # A 'collection_type' field in data would be better.
    collection_to_update = profile_list_collection

    # Ensure ObjectId is valid
    try: obj_id = ObjectId(record_id)
    except: return jsonify({"success": False, "message": "Invalid record ID format"}), 400

    result = collection_to_update.update_one({"_id": obj_id}, {"$set": data})
    if result.modified_count > 0: return jsonify({"success": True, "message": "Record updated"})
    elif result.matched_count > 0: return jsonify({"success": True, "message": "No changes made to the record"})
    return jsonify({"success": False, "message": "Update failed or record not found"})

@app.route('/delete_route', methods=['POST'])
def delete_route():
    if 'username' not in session: return redirect(url_for('login'))
    record_id = request.form['record_id']
    try: obj_id = ObjectId(record_id)
    except: flash("Invalid record ID format.", "danger"); return redirect(url_for('route_table'))

    record = route_list_collection.find_one({'_id': obj_id})
    if record:
        company = record.get('company', 'Unknown'); premise_val = record.get('premise', 'Unknown'); date_val = record.get('date', 'Unknown') # Renamed premise to premise_val
        route_list_collection.delete_one({'_id': obj_id})
        log_activity(session["username"], f"deleted route for Company: {company} Premise: {premise_val} Date: {date_val}", logs_collection)
        flash("Record deleted successfully!", "success")
    else:
        flash("Record not found or failed to delete!", "error") # Clarified message
    return redirect(url_for('route_table'))

@app.route('/view-help-requestssss', methods=['POST','GET'])
def view_helpss(): #This route seems unused
    if 'username' not in session: return redirect(url_for('login'))
    return render_template('view-complaint.html')

@app.route("/view-help-list", methods=['POST','GET'])
def view_help():
    if 'username' not in session: return redirect(url_for('login'))
    cases = list(collection.find({}, {"case_no": 1, "_id":0}))
    return render_template("view-complaint.html", cases=cases)

@app.route("/image/<file_id>")
def get_image(file_id):
    try:
        obj_file_id = ObjectId(file_id) # Validate ObjectId
        grid_fs_file = fs.get(obj_file_id)
        return send_file(io.BytesIO(grid_fs_file.read()), mimetype=grid_fs_file.content_type)
    except Exception as e:
        app.logger.error(f"Error serving image {file_id}: {e}")
        return "Image not found", 404

@app.route("/signature/<file_id>")
def get_signature(file_id):
    try:
        obj_file_id = ObjectId(file_id) # Validate ObjectId
        grid_fs_file = fs.get(obj_file_id)
        return send_file(io.BytesIO(grid_fs_file.read()), mimetype=grid_fs_file.content_type)
    except Exception as e:
        app.logger.error(f"Error serving signature {file_id}: {e}")
        return "Signature not found", 404

@app.route('/get-client-details/<premise_name>')
def get_client_details(premise_name):
    pics = list(profile_list_collection.find({"tied_to_premise": premise_name}))
    for pic_item in pics: pic_item['_id'] = str(pic_item['_id']) # Renamed pic to pic_item
    return jsonify(html=render_template("partials/client-details.html", pics=pics))

@app.route('/get-device-details/<premise_name>')
def get_device_details(premise_name):
    devices_data = list(device_list_collection.find({"tied_to_premise": premise_name})) # Renamed devices to devices_data
    for device_item in devices_data: device_item['_id'] = str(device_item['_id']) # Renamed device to device_item
    return jsonify(html=render_template("partials/device-details.html", devices=devices_data)) # Pass correct var

@app.route('/service', methods=['GET', 'POST'])
def service():
    if 'username' not in session: return redirect(url_for('login'))
    technician_name = session["username"]
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    companies = sorted(list(services_collection.distinct('company')))

    if request.method == 'POST':
        premise_name = request.form.get("premiseName")
        actions_taken = request.form.getlist("actions")
        remarks = request.form.get("remarks")
        staff_name = request.form.get("staffName")
        signature = request.form.get("signature")

        company_info = profile_list_collection.find_one({"premise_name": premise_name}, {"company": 1}) # Get company from profile
        log_company_name = company_info.get("company", "UnknownCompany") if company_info else "UnknownCompany"

        devices_in_premise = list(device_list_collection.find({"tied_to_premise": premise_name, "company": log_company_name}))
        device_entries = []
        for i, device_doc in enumerate(devices_in_premise, start=1):
            balance_key = f'balance_{device_doc.get("S/N", device_doc.get("_id"))}' # More unique key
            balance_val_str = request.form.get(balance_key) # Renamed balance to balance_val_str
            try: balance_val = int(balance_val_str if balance_val_str is not None else 0)
            except ValueError: balance_val = 0

            volume_required = int(device_doc.get("Volume", 0))
            consumption = volume_required - balance_val if volume_required >= balance_val else 0

            device_entry = {
                "location": device_doc.get("location"), "serial_number": device_doc.get("S/N"),
                "model": device_doc.get("Model"), "scent": device_doc.get("Current EO"),
                "volume_required": volume_required, "balance": balance_val, "consumption": consumption,
                "events": [
                    {"days": device_doc.get("E1 - DAYS"), "start_time": device_doc.get("E1 - START"), "end_time": device_doc.get("E1 - END"), "work": device_doc.get("E1 - WORK"), "pause": device_doc.get("E1 - PAUSE")},
                    {"days": device_doc.get("E2 - DAYS"), "start_time": device_doc.get("E2 - START"), "end_time": device_doc.get("E2 - END"), "work": device_doc.get("E2 - WORK"), "pause": device_doc.get("E2 - PAUSE")},
                    {"days": device_doc.get("E3 - DAYS"), "start_time": device_doc.get("E3 - START"), "end_time": device_doc.get("E3 - END"), "work": device_doc.get("E3 - WORK"), "pause": device_doc.get("E3 - PAUSE")},
                    {"days": device_doc.get("E4 - DAYS"), "start_time": device_doc.get("E4 - START"), "end_time": device_doc.get("E4 - END"), "work": device_doc.get("E4 - WORK"), "pause": device_doc.get("E4 - PAUSE")},
                ]}
            device_entries.append(device_entry)

        pic_records = list(profile_list_collection.find({"company": log_company_name, "tied_to_premise": premise_name}))
        for pic_item in pic_records: pic_item['_id'] = str(pic_item['_id']) # Renamed pic to pic_item

        field_service_record = {
            "technician_name": technician_name, "timestamp": current_time,
            "company": log_company_name, "premise_name": premise_name,
            "client_pics": pic_records, "devices_serviced": device_entries,
            "actions_taken": actions_taken, "remarks": remarks,
            "client_staff_name": staff_name, "client_signature": signature,
            "month_year": datetime.now()
        }
        service_reports_collection.insert_one(field_service_record) # Changed to service_reports_collection
        log_activity(session["username"], f"submitted service report for: {log_company_name} - {premise_name}", logs_collection)
        flash("Field service report submitted successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("service.html", companies=companies, technician_name=technician_name, current_time=current_time)

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
    for eo_item in added: # Renamed eo to eo_item
        if eo_pack_collection.find_one({'eo_name': eo_item['eo_name']}):
            return jsonify({'status': 'error', 'message': f"EO name '{eo_item['eo_name']}' already exists."}), 400
        eo_pack_collection.insert_one({"eo_name": eo_item['eo_name'], "order": -1}) # Default order
    for eo_item in edited:
        if eo_pack_collection.find_one({'eo_name': eo_item['eo_name'], '_id': {'$ne': ObjectId(eo_item['_id'])}}):
            return jsonify({'status': 'error', 'message': f"EO name '{eo_item['eo_name']}' already exists."}), 400
        eo_pack_collection.update_one({'_id': ObjectId(eo_item['_id'])}, {'$set': {'eo_name': eo_item['eo_name']}})
    for _id_str in deleted:
        eo_pack_collection.delete_one({'_id': ObjectId(_id_str)})
    for index, item in enumerate(visual_order):
        target_id_str = item.get('_id')
        if not target_id_str and 'eo_name' in item :
            new_eo_doc = eo_pack_collection.find_one({'eo_name': item['eo_name']}) # Renamed new_eo to new_eo_doc
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
    eos_set = set() # Renamed eos to eos_set
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
    def add_field(key, value): # Local helper function
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
    limit = int(request.args.get('limit', 20)) # Default to 20 items per page
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

    # Date filtering - assumes 'date' field in changed_models_collection is a string like 'YYYY-MM-DD'
    # or a datetime object. If it's a string, this query needs adjustment or data needs conversion.
    # For changed_models_collection, 'date' is form.get("date") or datetime.now().strftime('%Y-%m-%d')
    # 'submitted_at' is datetime.now()
    # Let's filter by 'submitted_at' for month/year as it's a proper datetime object.
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
    elif year_filter: # Filter by year only if month is not provided
        try:
            year_int = int(year_filter)
            query['$expr'] = {'$eq': [{'$year': '$submitted_at'}, year_int]}
        except ValueError:
            flash("Invalid year format.", "danger")


    total_entries = changed_models_collection.count_documents(query)
    # Sort by submission date, newest first
    results = list(changed_models_collection.find(query).sort("submitted_at", -1).skip(skip).limit(limit))

    # Format dates if necessary for display, e.g., 'submitted_at'
    for r in results:
        if isinstance(r.get("submitted_at"), datetime):
            r["submitted_at"] = r["submitted_at"].strftime("%Y-%m-%d %H:%M:%S")
        # 'date' field is likely already a string 'YYYY-MM-DD' from the form
        # If 'premises' or 'devices' can be None, ensure template handles it (already done with |join(', ') if X else '')

    total_pages = (total_entries + limit - 1) // limit

    # Preserve other query parameters for pagination links
    query_params_for_template = request.args.to_dict()
    if 'page' in query_params_for_template:
        del query_params_for_template['page']


    return render_template("changed_settings_list.html",
                           data=results,
                           page=page,
                           total_pages=total_pages,
                           limit=limit, # Though limit is not directly used in this template's pagination macro
                           query_params=query_params_for_template, # Pass the filtered dict
                           username=session.get('username'))

if __name__ == "__main__":
    app.run(debug=True)
