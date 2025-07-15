# backend/blueprints/forms_bp.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, jsonify
from datetime import datetime
from werkzeug.utils import secure_filename
from bson import ObjectId

from ..col import (
    services_collection, route_list_collection, remark_collection,
    profile_list_collection, device_list_collection, test_collection,
    model_list_collection, eo_pack_collection, industry_list_collection,
    change_collection as change_form_collection, # Renamed for clarity
    refund_collection, logs_collection
)
from ..utils import log_activity, safe_int

forms_bp = Blueprint(
    'forms',
    __name__,
    template_folder='../templates',
    url_prefix='/forms'
)

def is_admin_logged_in():
    return 'username' in session

@forms_bp.before_request
def require_admin_login():
    if not is_admin_logged_in():
        flash("You must be logged in as an admin to access this page.", "warning")
        return redirect(url_for('auth.admin_login'))

@forms_bp.route('/new-customer', methods=['GET', 'POST'])
def new_customer():
    raw_models = list(model_list_collection.find().sort("order", 1))
    models = [{k: v for k, v in model.items() if k != '_id'} for model in raw_models]

    eo_raw = list(eo_pack_collection.find().sort("order", 1))
    essential_oils = [{k: v for k, v in eo.items() if k != '_id'} for eo in eo_raw]

    industry_raw = list(industry_list_collection.find().sort("order", 1))
    industries = [{k: v for k, v in industry.items() if k != '_id'} for industry in industry_raw]

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
            if current_app.config.get('MODE') == "PROD":
                services_collection.insert_many(master_list)
            else:
                test_collection.insert_many(master_list)

        log_activity(session["username"], f"added new customer: {companyName}", logs_collection)
        flash(f"Company {companyName} added successfully!", "success")
        return redirect(url_for(".new_customer"))

    return render_template('new-customer.html', models=models, essential_oils=essential_oils, industries=industries, username=session.get("username"))

@forms_bp.route('/change-form', methods=['GET', 'POST'])
def change_form():
    if request.method == 'POST':
        data = {
            "user": session.get("username"), "company": request.form.get("companyName"),
            "date": request.form.get("date"), "month": request.form.get("month"), "year": request.form.get("year"),
            "premises": request.form.getlist("premises"), "devices": request.form.getlist("devices"),
            "change_scent": request.form.get("changeScent") == "on", "change_scent_to": request.form.get("changeScentText"),
            "redo_settings": request.form.get("redoSettings") == "on", "reduce_intensity": request.form.get("reduceIntensity") == "on",
            "increase_intensity": request.form.get("increaseIntensity") == "on", "move_device": request.form.get("moveDevice") == "on",
            "move_device_to": request.form.get("moveDeviceText"), "relocate_device": request.form.get("relocateDevice") == "on",
            "relocate_device_to": request.form.get("relocateDeviceDropdown"), "collect_back": request.form.get("collectBack") == "on",
            "remark": request.form.get("remark"), "submitted_at": datetime.now() }
        if data["collect_back"]:
            refund_collection.insert_one(data)
            log_activity(session["username"],"collected back : " +str(data['premises']) + str(data['devices']),logs_collection)
        else:
            change_form_collection.insert_one(data)
            log_activity(session["username"],"updated settings : " +str(data['premises']) + str(data['devices']),logs_collection)
        flash("Data updated", "success")
        return redirect(url_for("dashboard"))
    companies = services_collection.distinct('company')
    premises_for_template = []
    if request.args.get("companyName"):
        premises_for_template = services_collection.distinct('Premise Name', {'company': request.args.get("companyName")})
    return render_template('change-form.html', username=session.get('username'),
                           companies=companies, premises=premises_for_template,
                           current_date=datetime.now().strftime('%Y-%m-%d'))

@forms_bp.route('/pre-service', methods=['GET', 'POST'])
def pre_service():
    companies = services_collection.distinct('company')
    if request.method == 'POST':
        date_str = request.form.get('date')
        date_obj = datetime.fromisoformat(date_str.rstrip("Z")) if date_str else None
        entry = {"date": date_obj, "company": request.form.get('company'), "premise": request.form.get('premise'), "model": request.form.get('model'), "color": request.form.get('color'), "eo": request.form.get('eo')}

        # Check for duplicate entry
        existing_route = route_list_collection.find_one(entry)
        if existing_route and not request.form.get('confirm_duplicate'):
            return jsonify({'status': 'duplicate'})

        route_list_collection.insert_one(entry)
        flash(f"Company: {request.form.get('company')}, Premise: {request.form.get('premise')} preservice added successfully!", "success")
        log_activity(session["username"],"pre-service : " +str(request.form.get('company')) + " : " +str(request.form.get('premise')),logs_collection)
        return jsonify({'status': 'success'})
    return render_template('pre-service.html', companies=companies)

@forms_bp.route('/service', methods=['GET', 'POST'])
def service():
    technician_name = session["username"]
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    companies = services_collection.distinct('company')

    device_entries = []
    if request.method == 'POST':
        premise_name = request.form.get("premiseName")
        actions_taken = request.form.getlist("actions")
        remarks = request.form.get("remarks")
        staff_name = request.form.get("staffName")
        signature = request.form.get("signature")

        # Fetch selected premise details
        premise_details = profile_list_collection.find_one({"premise_name": premise_name})
        if not premise_details:
            flash("Invalid premise selected!", "danger")
            return redirect(url_for("field_service"))

        # Fetch devices linked to the premise
        devices = list(device_list_collection.find({"tied_to_premise": premise_name}))

        # Fetch PICs linked to the premise
        pic_records = list(profile_list_collection.find({"tied_to_premise": premise_name}))

        # Process devices
        for i, device in enumerate(devices, start=1):
            balance = int(request.form.get(f'balance{i}', 0))
            volume_required = int(device.get("Volume", 0))
            consumption = volume_required - balance

            device_entry = {
                "location": device.get("location"),
                "serial_number": device.get("S/N"),
                "model": device.get("Model"),
                "scent": device.get("Current EO"),
                "volume_required": volume_required,
                "balance": balance,
                "consumption": consumption,
                "events": []
            }

            # Process events (E1 to E4)
            for e in range(1, 5):
                event_data = {
                    "days": device.get(f"E{e} - DAYS"),
                    "start_time": device.get(f"E{e} - START"),
                    "end_time": device.get(f"E{e} - END"),
                    "work": device.get(f"E{e} - WORK"),
                    "pause": device.get(f"E{e} - PAUSE"),
                }
                device_entry["events"].append(event_data)

            device_entries.append(device_entry)

        # Create a record for MongoDB
        field_service_record = {
            "technician_name": technician_name,
            "timestamp": current_time,
            "premise_name": premise_name,
            "client_pics": pic_records,
            "devices": device_entries,
            "actions_taken": actions_taken,
            "remarks": remarks,
            "staff_name": staff_name,
            "signature": signature,
        }

        change_form_collection.insert_one(field_service_record)

        flash("Field service report submitted successfully!", "success")
        return redirect(url_for("field_service", companies=companies))

    # Fetch all premises for dropdown
    premises = list(profile_list_collection.find({}, {"premise_name": 1, "_id": 0}))

    # Fetch all devices for GET (optional: you may want to show all or none until a premise is selected)
    # For now, just pass an empty list for devices
    return render_template(
        "service.html",
        devices=device_entries,  # Always a list
        companies=companies,
        technician_name=technician_name,
        current_time=current_time
    )

@forms_bp.route('/service2', methods=['GET', 'POST'])
def service2():
    # This route was not in the provided app.py.
    # Assuming it might be a variant of the 'service' route.
    # For now, providing a basic structure.
    technician_name = session["username"]
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    companies = services_collection.distinct('company')
    # If this form has POST logic, it would be here.
    # if request.method == 'POST':
    #    ...
    #    flash("Service2 form submitted (Placeholder).", "success")
    #    return redirect(url_for('.service2'))
    return render_template("service2.html", technician_name=technician_name, current_time=current_time, companies=companies)

@forms_bp.route('/post-service', methods=['POST', 'GET'])
def post_service():
    username = session['username']
    if request.method == "POST":
        essential_oil = request.form.get("essential_oil")
        oil_balance = int(request.form.get("oil_balance"))
        balance_brought_back = int(request.form.get("balance_brought_back"))
        balance_brought_back_percent = request.form.get("balance_brought_back_percent")
        refill_amount = int(request.form.get("refill_amount"))
        refill_amount_percent = request.form.get("refill_amount_percent")
        month_year = datetime.now()
        query = {"essential_oil": essential_oil}
        update_data = {
            "oil_balance": oil_balance, "balance_brought_back": balance_brought_back,
            "balance_brought_back_percent": balance_brought_back_percent,
            "refill_amount": refill_amount, "refill_amount_percent": refill_amount_percent,
            "month_year": month_year
        }
        # Add username to the data being updated/inserted
        update_data['username'] = username
        update = { "$set": update_data }
        eo_pack_collection.update_one(query, update, upsert=True)
        log_activity(username, f"Updated/added post-service record for EO: {essential_oil}", logs_collection)
        flash(f"Record for {essential_oil} updated successfully!", "success")
        return redirect(url_for("dashboard"))
    return render_template('post-service.html', username=username)

@forms_bp.route('/remark', methods=['GET', 'POST'])
def remark():
    username = session['username']
    if request.method == 'POST':
        remark_text = request.form['remark']
        is_urgent = 'urgent' in request.form
        log_activity(username,"added remark: " +str(remark_text) + ", urgent: " + str(is_urgent), logs_collection) # Corrected log
        remark_collection.insert_one({'username': username, 'remark': remark_text, 'urgent': is_urgent, 'timestamp': datetime.now()})
        flash("Remark submitted successfully!", "success")
        return redirect(url_for('dashboard'))
    return render_template('remark.html', username=username)
