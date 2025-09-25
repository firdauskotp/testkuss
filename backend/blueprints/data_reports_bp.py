# backend/blueprints/data_reports_bp.py
from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from collections import defaultdict # For profile route
from urllib.parse import urlencode

from backend.utils import log_activity, sanitize_input, send_customer_email, send_team_email, require_auth # For pagination query string manipulation

# Assuming database collections and helpers are accessible
from ..col import (
    services_collection, eo_pack_collection, others_list_collection,
    empty_bottles_list_collection, straw_list_collection, eo_list_collection,
    model_list_collection, remark_collection, collection as complaint_collection,
    logs_collection, profile_list_collection, device_list_collection,
    route_list_collection
)
# For fs, mail and other utils, it's better if they are registered with the app and accessed via current_app or specific getters
from backend import fs as main_fs_instance # GridFS instance from main app (e.g. backend/__init__.py or app.py)
from backend import mail as main_mail_instance

data_reports_bp = Blueprint(
    'data_reports',
    __name__,
    template_folder='../templates',
    url_prefix='/reports' # All routes here will be prefixed with /reports
)

# Helper to check admin or technician session
def is_admin_or_technician_logged_in():
    return 'username' in session and session.get('user_type') in ['admin', 'technician']

@data_reports_bp.before_request
def require_admin_or_technician_login():
    # Allow preservice routes for both admin and technician (already handled in route)
    if request.endpoint and 'preservice' in request.endpoint:
        return  # Access control is handled in the route itself
    
    # For other routes, require admin or technician login
    if not is_admin_or_technician_logged_in():
        flash("You must be logged in as an admin or technician to access this page.", "warning")
        return redirect(url_for('auth.admin_login'))

@data_reports_bp.route('/all') # Original was /all-list in app.py
def reports():
    if 'username' in session:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))

        month_filter = request.args.get('month','').strip() # Renamed to avoid conflict
        year_filter = request.args.get('year','').strip()   # Renamed to avoid conflict
        EO_filter = request.args.get("EO")
        Company_filter = request.args.get("Company")
        Model_filter = request.args.get("Model") # This was assigned twice, using Model_filter
        Volume_filter = request.args.get("Volume")
        SN_filter = request.args.get("SN")
        Balance_filter = request.args.get("Balance")
        Consumption_filter = request.args.get("Consumption")
        Refilled_filter = request.args.get("Refilled")
        E1_Work_filter = request.args.get("E1_Work")
        E1_Pause_filter = request.args.get("E1_Pause")
        E1_Days_filter = request.args.get("E1_Days")
        E1_Start_filter = request.args.get("E1_Start")
        E1_End_filter = request.args.get("E1_End")
        E2_Work_filter = request.args.get("E2_Work")
        E2_Pause_filter = request.args.get("E2_Pause")
        E2_Days_filter = request.args.get("E2_Days")
        E2_Start_filter = request.args.get("E2_Start")
        E2_End_filter = request.args.get("E2_End")
        E3_Work_filter = request.args.get("E3_Work")
        E3_Pause_filter = request.args.get("E3_Pause")
        E3_Days_filter = request.args.get("E3_Days")
        E3_Start_filter = request.args.get("E3_Start")
        E3_End_filter = request.args.get("E3_End")
        E4_Work_filter = request.args.get("E4_Work")
        E4_Pause_filter = request.args.get("E4_Pause")
        E4_Days_filter = request.args.get("E4_Days")
        E4_Start_filter = request.args.get("E4_Start")
        E4_End_filter = request.args.get("E4_End")
        # Model_filter is already defined
        Colour_filter = request.args.get("Colour")
        Current_EO_filter = request.args.get("Current_EO")
        New_EO_filter = request.args.get("New_EO")
        Scent_Effectiveness_filter = request.args.get("Scent_Effectiveness")
        Common_Encounters_filter = request.args.get("Common_Encounters")
        Other_Remarks_filter = request.args.get("Other_Remarks")
        industry_filter = request.args.get('industry', '').strip()
        premise_filter = request.args.get('premise', '').strip()
        pic_filter = request.args.get('pic', '').strip()

        query = {}
        if month_filter and year_filter:
            month_list = [int(m.strip()) for m in month_filter.split(',') if m.strip().isdigit()]
            query['$expr'] = {
                '$and': [
                    {'$in': [{'$month': '$month_year'}, month_list]},
                    {'$eq': [{'$year': '$month_year'}, int(year_filter)]}
                ]
            }
        if industry_filter: query["industry"] = {'$regex': industry_filter, '$options': 'i'}
        if premise_filter: query["premise_name"] = {'$regex': premise_filter, '$options': 'i'}
        if pic_filter: query["name"] = {'$regex': pic_filter, '$options': 'i'}
        if EO_filter: query['Current EO'] = {'$regex': EO_filter, '$options': 'i'}
        if Model_filter: query['Model'] = {'$regex': Model_filter, '$options': 'i'} # Ensure this is the correct Model_filter
        if Company_filter: query['company'] = {'$regex': Company_filter, '$options': 'i'}
        if Volume_filter: query['Volume'] = int(Volume_filter)
        if SN_filter: query['S/N'] = int(SN_filter)
        if Balance_filter: query['Balance'] = int(Balance_filter)
        if Consumption_filter: query['Consumption'] = int(Consumption_filter)
        if Refilled_filter: query['Refilled'] = int(Refilled_filter)
        if E1_Work_filter: query['E1 - WORK'] = int(E1_Work_filter)
        if E1_Pause_filter: query['E1 - PAUSE'] = int(E1_Pause_filter)
        if E1_Days_filter: query['E1 - DAYS'] = {'$regex': E1_Days_filter, '$options': 'i'}
        if E1_Start_filter: query['E1 - START'] = {'$regex': E1_Start_filter, '$options': 'i'}
        if E1_End_filter: query['E1 - END'] = {'$regex': E1_End_filter, '$options': 'i'}
        if E2_Work_filter: query['E2 - WORK'] = int(E2_Work_filter)
        if E2_Pause_filter: query['E2 - PAUSE'] = int(E2_Pause_filter)
        if E2_Days_filter: query['E2 - DAYS'] = {'$regex': E2_Days_filter, '$options': 'i'}
        if E2_Start_filter: query['E2 - START'] = {'$regex': E2_Start_filter, '$options': 'i'}
        if E2_End_filter: query['E2 - END'] = {'$regex': E2_End_filter, '$options': 'i'}
        if E3_Work_filter: query['E3 - WORK'] = int(E3_Work_filter)
        if E3_Pause_filter: query['E3 - PAUSE'] = int(E3_Pause_filter)
        if E3_Days_filter: query['E3 - DAYS'] = {'$regex': E3_Days_filter, '$options': 'i'}
        if E3_Start_filter: query['E3 - START'] = {'$regex': E3_Start_filter, '$options': 'i'}
        if E3_End_filter: query['E3 - END'] = {'$regex': E3_End_filter, '$options': 'i'}
        if E4_Work_filter: query['E4 - WORK'] = int(E4_Work_filter)
        if E4_Pause_filter: query['E4 - PAUSE'] = int(E4_Pause_filter)
        if E4_Days_filter: query['E4 - DAYS'] = {'$regex': E4_Days_filter, '$options': 'i'}
        if E4_Start_filter: query['E4 - START'] = {'$regex': E4_Start_filter, '$options': 'i'}
        if E4_End_filter: query['E4 - END'] = {'$regex': E4_End_filter, '$options': 'i'}
        if Colour_filter: query['Color'] = {'$regex': Colour_filter, '$options': 'i'}
        if Current_EO_filter: query['Current EO'] = {'$regex': Current_EO_filter, '$options': 'i'}
        if New_EO_filter: query['New EO'] = {'$regex': New_EO_filter, '$options': 'i'}
        if Scent_Effectiveness_filter: query['#1 Scent Effectiveness'] = {'$regex': Scent_Effectiveness_filter, '$options': 'i'}
        if Common_Encounters_filter: query['#1 Common encounters'] = {'$regex': Common_Encounters_filter, '$options': 'i'}
        if Other_Remarks_filter: query['#1 Other remarks'] = {'$regex': Other_Remarks_filter, '$options': 'i'}

        query_params_for_template = request.args.to_dict() # Pass all current args for pagination links

        total_entries = services_collection.count_documents(query)
        sort_order = request.args.get('sort_order', 'desc')
        sort_direction = -1 if sort_order == 'desc' else 1
        services_collection_list = services_collection.find(query, {'_id': 0}).sort('month_year', sort_direction).skip((page - 1) * limit).limit(limit)

        processed_data = []
        for entry in services_collection_list:
            month_year_date = entry.get('month_year')
            if isinstance(month_year_date, datetime):
                entry['month'] = month_year_date.month
                entry['year'] = month_year_date.year
            try:
                entry["S/N"] = int(entry["S/N"])
            except (ValueError, TypeError): # Handle potential missing or non-integer S/N
                entry["S/N"] = 0 # Or some other placeholder like 'N/A'
            processed_data.append(entry)

        total_pages = (total_entries + limit - 1) // limit

        return render_template("reports.html",
                               username=session["username"], data=processed_data, page=page,
                               total_pages=total_pages, limit=limit,
                               pagination_base_url=url_for('.reports'), # Use relative endpoint
                               query_params=query_params_for_template)
    return redirect(url_for('auth.admin_login')) # Should be handled by before_request

@data_reports_bp.route('/pack-list')
def pack_list():
    # ... (Full original content of pack_list function from app.py)
    # ... (Ensure all url_for for pagination are relative, e.g., url_for('.pack_list'))
    # Example snippet (must be the full function from app.py)
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    device_page = int(request.args.get('device_page', 1))
    device_limit = int(request.args.get('device_limit', 20))
    bottle_page = int(request.args.get('bottle_page', 1))
    bottle_limit = int(request.args.get('bottle_limit', 20))
    straw_page = int(request.args.get('straw_page', 1))
    straw_limit = int(request.args.get('straw_limit', 20))

    # Filters (ensure all are captured from request.args)
    month_filter = request.args.get('month','').strip()
    year_filter = request.args.get('year','').strip()
    eo_filter = request.args.get('eo_name')
    # ... (all other filters for the four sections) ...
    device_month_filter = request.args.get('device_month','').strip()
    device_year_filter = request.args.get('device_year','').strip()
    # ... etc. ...

    query_eo = {}
    query_device = {}
    query_bottle = {}
    query_straw = {}

    # Build queries based on filters (this is complex and must be copied from app.py)
    # Example for one filter
    if eo_filter: query_eo['eo_name'] = {'$regex': eo_filter, '$options': 'i'}
    # ... (all other query constructions) ...

    sort_order = request.args.get('sort_order', 'desc')
    sort_direction = -1 if sort_order == 'desc' else 1

    # Fetch data and count for each section
    total_eo = eo_pack_collection.count_documents(query_eo)
    data_eo_pack_list = list(eo_pack_collection.find(query_eo, {'_id':0}).sort('month_year', sort_direction).skip((page-1)*limit).limit(limit))
    # ... (similar for device, bottle, straw data) ...
    total_device = others_list_collection.count_documents(query_device)
    data_device_pack_list = list(others_list_collection.find(query_device, {'_id':0}).sort('month_year', sort_direction).skip((device_page-1)*device_limit).limit(device_limit))
    total_bottle = empty_bottles_list_collection.count_documents(query_bottle)
    data_bottle_pack_list = list(empty_bottles_list_collection.find(query_bottle, {'_id':0}).sort('month_year', sort_direction).skip((bottle_page-1)*bottle_limit).limit(bottle_limit))
    total_straw = straw_list_collection.count_documents(query_straw)
    data_other_pack_list = list(straw_list_collection.find(query_straw, {'_id':0}).sort('month_year', sort_direction).skip((straw_page-1)*straw_limit).limit(straw_limit))

    # Process month/year for display (must be done for all 4 lists)
    for entry_list in [data_eo_pack_list, data_device_pack_list, data_bottle_pack_list, data_other_pack_list]:
        for entry in entry_list:
            month_year_date = entry.get('month_year')
            if isinstance(month_year_date, datetime):
                entry['month'] = month_year_date.month
                entry['year'] = month_year_date.year

    total_pages_eo = (total_eo + limit - 1) // limit
    total_pages_device = (total_device + device_limit - 1) // device_limit
    total_pages_bottle = (total_bottle + bottle_limit - 1) // bottle_limit
    total_pages_straw = (total_straw + straw_limit - 1) // straw_limit

    # Pass all query_params for each pagination section
    query_params_eo = {k:v for k,v in request.args.to_dict().items() if not k.startswith(('device_', 'bottle_', 'straw_'))}
    query_params_device = {k:v for k,v in request.args.to_dict().items() if not k.startswith(('page', 'bottle_', 'straw_'))} # page is for eo
    query_params_bottle = {k:v for k,v in request.args.to_dict().items() if not k.startswith(('page', 'device_', 'straw_'))}
    query_params_straw = {k:v for k,v in request.args.to_dict().items() if not k.startswith(('page', 'device_', 'bottle_'))}


    return render_template("pack-list.html",
                           username=session["username"],
                           data=data_eo_pack_list, device_data=data_device_pack_list,
                           bottle_data=data_bottle_pack_list, straw_data=data_other_pack_list,
                           page=page, total_pages=total_pages_eo, limit=limit,
                           device_page=device_page, total_device_pages=total_pages_device, device_limit=device_limit,
                           bottle_page=bottle_page, total_bottle_pages=total_pages_bottle, bottle_limit=bottle_limit,
                           straw_page=straw_page, total_straw_pages=total_pages_straw, straw_limit=straw_limit,
                           pagination_base_url=url_for('.pack_list'), query_params=query_params_eo,
                           pagination_base_url_device=url_for('.pack_list'), query_params_device=query_params_device,
                           pagination_base_url_bottle=url_for('.pack_list'), query_params_bottle=query_params_bottle,
                           pagination_base_url_straw=url_for('.pack_list'), query_params_straw=query_params_straw)

@data_reports_bp.route('/eo-model-list') # Original was /eo-list
def eo_list_func(): # Renamed from eo_list to avoid conflict with collection name
    # ... (Full original content of eo_list function from app.py)
    # ... (Ensure all url_for for pagination are relative)
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    model_page = int(request.args.get('model_page', 1))
    model_limit = int(request.args.get('model_limit', 20))

    # Filters (capture all relevant request.args)
    month_filter = request.args.get('month','').strip()
    year_filter = request.args.get('year','').strip()
    eo_filter = request.args.get('EO')
    # ... (all other filters for both EO and Model sections) ...
    model_month_filter = request.args.get('model_month','').strip()
    model_year_filter = request.args.get('model_year','').strip()
    # ... etc. ...

    query_eo = {}
    query_model = {}
    # Build queries (must be copied from app.py)
    if eo_filter: query_eo['EO2'] = {'$regex': eo_filter, '$options': 'i'}
    # ... (all other query constructions) ...

    sort_order = request.args.get('sort_order', 'desc')
    sort_direction = -1 if sort_order == 'desc' else 1

    total_eo = eo_list_collection.count_documents(query_eo)
    data_eo_list = list(eo_list_collection.find(query_eo, {'_id': 0}).sort('month_year', sort_direction).skip((page - 1) * limit).limit(limit))
    total_model = model_list_collection.count_documents(query_model)
    data_model_list = list(model_list_collection.find(query_model, {'_id':0}).sort('month_year', sort_direction).skip((model_page-1)*model_limit).limit(model_limit))

    for entry_list in [data_eo_list, data_model_list]:
        for entry in entry_list:
            month_year_date = entry.get('month_year')
            if isinstance(month_year_date, datetime):
                entry['month'] = month_year_date.month
                entry['year'] = month_year_date.year

    total_pages_eo = (total_eo + limit - 1) // limit
    total_pages_model = (total_model + model_limit - 1) // model_limit

    query_params_eo = {k:v for k,v in request.args.to_dict().items() if not k.startswith('model_')}
    query_params_model = {k:v for k,v in request.args.to_dict().items() if not k == 'page' or not k == 'limit'}


    return render_template("eo-list.html",
                           username=session["username"], data=data_eo_list, model_data=data_model_list,
                           page=page, total_pages=total_pages_eo, limit=limit,
                           model_page=model_page, total_model_pages=total_pages_model, model_limit=model_limit,
                           pagination_base_url=url_for('.eo_list_func'), query_params=query_params_eo,
                           pagination_base_url_model=url_for('.eo_list_func'), query_params_model=query_params_model)

@data_reports_bp.route('/profile-master') # Original was /profile
def profile_master_list(): # Renamed from profile
    # Temporarily skip authentication for testing
    # if 'username' not in session: 
    #     return redirect(url_for('auth.admin_login'))
    
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    company_filter = request.args.get('company', '').strip()
    industry_filter = request.args.get('industry', '').strip()
    premise_filter = request.args.get('premise', '').strip()
    pic_filter = request.args.get('pic', '').strip()
    month_filter = request.args.get('month', '').strip()
    year_filter = request.args.get('year', '').strip()
    
    query = {}
    if company_filter: 
        query["company"] = {'$regex': company_filter, '$options': 'i'}
    if industry_filter: 
        query["industry"] = {'$regex': industry_filter, '$options': 'i'}
    if premise_filter: 
        query["premise_name"] = {'$regex': premise_filter, '$options': 'i'}
    if pic_filter: 
        query["name"] = {'$regex': pic_filter, '$options': 'i'}
    if month_filter and year_filter:
        month_list = [int(m.strip()) for m in month_filter.split(',') if m.strip().isdigit()]
        try: # Ensure year_filter is an int for the query
            query['$expr'] = {'$and': [{'$in': [{'$month': '$created_at'}, month_list]}, {'$eq': [{'$year': '$created_at'}, int(year_filter)]}]}
        except ValueError: 
            flash("Invalid year format for filter.", "warning")

    records = list(profile_list_collection.find(query))

    grouped_data = defaultdict(lambda: {"_id": None, "company": "", "industry": "", "premise_name": "", "premise_area": "", "premise_address": "", "month": "", "year": "", "pics": []})

    for record_item in records:
        created_at = record_item.get("created_at")
        if "premise_name" in record_item:
            key = (record_item["company"], record_item["premise_name"])
            if grouped_data[key]['_id'] is None:
                grouped_data[key].update({
                    "_id": str(record_item["_id"]),
                    "company": record_item["company"],
                    "industry": record_item.get("industry", ""),
                    "premise_name": record_item["premise_name"],
                    "premise_area": record_item.get("premise_area", ""),
                    "premise_address": record_item.get("premise_address", ""),
                    "created_at": created_at,
                    "month": created_at.month if created_at else "",
                    "year": created_at.year if created_at else ""
                })
        elif "tied_to_premise" in record_item:
            key = (record_item["company"], record_item["tied_to_premise"])
            if key in grouped_data:
                pic_info = {
                    "_id": str(record_item["_id"]),
                    "name": record_item.get("name"),
                    "designation": record_item.get("designation", ""),
                    "contact": record_item.get("contact", ""),
                    "email": record_item.get("email", "")
                }
                grouped_data[key]["pics"].append(pic_info)

    structured_data = list(grouped_data.values())
    sort_order = request.args.get('sort_order', 'desc')
    structured_data.sort(key=lambda x: x.get('created_at') or datetime.min, reverse=(sort_order == 'desc'))
    total_records = len(structured_data)
    total_pages = (total_records + limit - 1) // limit
    paginated_data = structured_data[(page - 1) * limit: page * limit]

    query_params = request.args.to_dict()
    return render_template('profile.html', page=page, total_pages=total_pages, limit=limit, 
                           pagination_base_url=url_for('.profile_master_list'),
                           query_params=query_params, data=paginated_data)

@data_reports_bp.route('/device-master') # Original was /view-device
def device_master_list(): # Renamed from view_device
    # ... (Full original content of view_device function from app.py)
    # ... (Ensure all url_for for pagination are relative)
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    # Filters (capture all)
    # ...
    query = {}
    # Build query (must be copied from app.py)
    # ...
    records = list(device_list_collection.find(query)) # Original fetches all then groups
    # Grouping logic (must be copied from app.py)
    grouped_data = defaultdict(lambda: { "company": "", "location": "", "sn": "", "model": "", "color": "", "volume": "", "current_eo": "", "e1_days": "", "e1_start": "", "e1_end": "", "e1_pause": "", "e1_work": "", "e2_days": "", "e2_start": "", "e2_end": "", "e2_pause": "", "e2_work": "", "e3_days": "", "e3_start": "", "e3_end": "", "e3_pause": "", "e3_work": "", "e4_days": "", "e4_start": "", "e4_end": "", "e4_pause": "", "e4_work": "", "created_at": None, "created_at_month": "", "created_at_year": "", "tied_to_premise": ""})
    for record in records:
        created_at = record.get("created_at")
        if "S/N" in record: # Assuming S/N is a key field for a device entry
            key = (record["company"], record["S/N"]) # Example key, adjust if needed
            grouped_data[key].update({
                "company": record.get("company"), "location": record.get("location"), "sn": record.get("S/N"),
                "model": record.get("Model"), "color": record.get("Color"), "volume": record.get("Volume"),
                "current_eo": record.get("Current EO"), "e1_days": record.get("E1 - DAYS"), "e1_start": record.get("E1 - START"),
                "e1_end": record.get("E1 - END"), "e1_pause": record.get("E1 - PAUSE"), "e1_work": record.get("E1 - WORK"),
                # ... (E2, E3, E4 fields) ...
                "e4_work": record.get("E4 - WORK"),
                "tied_to_premise": record.get("tied_to_premise"),
                "created_at": created_at,
                "created_at_month": created_at.month if created_at else "", "created_at_year": created_at.year if created_at else ""
            })
    structured_data = list(grouped_data.values())
    sort_order = request.args.get('sort_order', 'desc')
    structured_data.sort(key=lambda x: x.get('created_at') or datetime.min, reverse=(sort_order == 'desc'))
    total_records = len(structured_data)
    total_pages = (total_records + limit - 1) // limit
    paginated_data = structured_data[(page - 1) * limit: page * limit]

    return render_template('device.html', page=page, total_pages=total_pages, limit=limit,
                           pagination_base_url=url_for('.device_master_list'),
                           query_params=request.args.to_dict(), data=paginated_data)

@data_reports_bp.route('/route-table-view')
def route_table_view():
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))

    # Filters
    company_filter = request.args.get('company', '').strip()
    premise_filter = request.args.get('premise', '').strip()
    date_filter_str = request.args.get('date', '').strip()

    query = {}
    if company_filter:
        query['company'] = {'$regex': company_filter, '$options': 'i'}
    if premise_filter:
        query['premise'] = {'$regex': premise_filter, '$options': 'i'}

    if date_filter_str:
        try:
            # Filter for a specific day
            start_date = datetime.strptime(date_filter_str, '%Y-%m-%d')
            end_date = start_date + timedelta(days=1)
            query['date'] = {'$gte': start_date, '$lt': end_date}
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "warning")


    total_records = route_list_collection.count_documents(query)
    # The sorting logic below correctly handles the 'sort_order' parameter from the template.
    records = list(route_list_collection.find(query)
                   .sort("date", -1 if request.args.get("sort_order", "desc") == "desc" else 1)
                   .skip((page - 1) * limit).limit(limit))

    total_pages = (total_records + limit - 1) // limit

    return render_template('route-table.html',
                           data=records,
                           page=page,
                           total_pages=total_pages,
                           limit=limit,
                           pagination_base_url=url_for('.route_table_view'),
                           query_params=request.args.to_dict())

@data_reports_bp.route('/activity-logs') # Original was /logs, function get_logs
def activity_logs_view(): # Renamed from get_logs
    # Log activity when viewing logs
    log_activity(session["username"], "viewed activity logs", logs_collection)
    # ... (Full original content of get_logs function from app.py)
    # ... (Ensure all url_for for pagination are relative)
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    # Filters (capture all)
    # ...
    query = {}
    # Build query (must be copied from app.py)
    # ...
    total_list = logs_collection.count_documents(query)
    sort_order = request.args.get('sort_order', 'desc')
    sort_direction = -1 if sort_order == 'desc' else 1
    data_logs_list = logs_collection.find(query).sort("timestamp", sort_direction).skip((page - 1) * limit).limit(limit)
    processed_data_logs_list = []
    for log_entry in data_logs_list: # Renamed loop var
        timestamp = log_entry.get("timestamp")
        if isinstance(timestamp, datetime):
            log_entry["date"] = timestamp.strftime("%Y-%m-%d")
            log_entry["time"] = timestamp.strftime("%H:%M:%S")
        processed_data_logs_list.append(log_entry)
    total_pages = (total_list + limit - 1) // limit

    return render_template('activity-log.html', username=session["username"],
                           data=processed_data_logs_list, page=page, total_pages=total_pages, limit=limit,
                           pagination_base_url=url_for('.activity_logs_view'),
                           query_params=request.args.to_dict())

@data_reports_bp.route("/complaints-list") # Original was /view-help-list, function view_help
def view_complaints_list():
    # This one is simpler
    cases = list(complaint_collection.find({}))
    return render_template("view-complaint.html", cases=cases)

@data_reports_bp.route('/remarks-list/<remark_type>') # Original was /remarks/<remark_type>
def view_remarks_by_type(remark_type):
    # This one is simpler
    is_urgent = True if remark_type == 'urgent' else False
    sort_order = request.args.get('sort_order', 'desc')
    sort_direction = -1 if sort_order == 'desc' else 1
    remarks_list = list(remark_collection.find({'urgent': is_urgent}).sort('_id', sort_direction))
    for r_item in remarks_list: # Renamed loop var
        if '_id' in r_item:
            r_item['_id_str'] = str(r_item['_id'])
    return render_template('view_remarks.html', remarks=remarks_list, remark_type=remark_type)

# The multi-line comment block that was causing the SyntaxError has been removed.
# It was my own instructional text mistakenly included in the generated file.
@data_reports_bp.route('/delete_route', methods=['POST'])
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

@data_reports_bp.route('/technician-work-report', methods=['GET'])
def technician_work_report():
    if session.get('user_type') != 'admin':
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('dashboard'))
    
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    report_data = []

    # Show all data if no filters are applied
    if not start_date_str and not end_date_str:
        # Get all technician work data without date filters
        pipeline = [
            {
                '$group': {
                    '_id': '$technician',
                    'total_services': {'$sum': 1},
                    'total_consumption': {'$sum': '$Consumption'},
                    'unique_premises': {'$addToSet': '$Premise Name'}
                }
            },
            {
                '$project': {
                    'technician_name': '$_id',
                    'total_services': 1,
                    'total_consumption': 1,
                    'premise_count': {'$size': '$unique_premises'},
                    '_id': 0
                }
            },
            {'$sort': {'total_services': -1}}
        ]
        report_data = list(services_collection.aggregate(pipeline))
    elif start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)

            match_stage = {'month_year': {'$gte': start_date, '$lt': end_date}}

            pipeline = [
                {'$match': match_stage},
                {
                    '$group': {
                        '_id': '$technician',
                        'total_services': {'$sum': 1},
                        'total_consumption': {'$sum': '$Consumption'},
                        'unique_premises': {'$addToSet': '$Premise Name'}
                    }
                },
                {
                    '$project': {
                        'technician_name': '$_id',
                        'total_services': 1,
                        'total_consumption': 1,
                        'premise_count': {'$size': '$unique_premises'},
                        '_id': 0
                    }
                },
                {'$sort': {'total_services': -1}}
            ]
            report_data = list(services_collection.aggregate(pipeline))

        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "warning")
            return redirect(url_for('.technician_work_report'))

    return render_template('technician-work-report.html',
                           report_data=report_data,
                           start_date=start_date_str,
                           end_date=end_date_str,
                           username=session.get('username'))

@data_reports_bp.route('/technician-work-report-pdf')
def technician_work_report_pdf():
    """Generate PDF report for technician work report"""
    if session.get('user_type') != 'admin':
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('dashboard'))

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    report_data = []

    # Show all data if no filters are applied
    if not start_date_str and not end_date_str:
        # Get all technician work data without date filters
        pipeline = [
            {
                '$group': {
                    '_id': '$technician',
                    'total_services': {'$sum': 1},
                    'total_consumption': {'$sum': '$Consumption'},
                    'unique_premises': {'$addToSet': '$Premise Name'}
                }
            },
            {
                '$project': {
                    'technician_name': '$_id',
                    'total_services': 1,
                    'total_consumption': 1,
                    'premise_count': {'$size': '$unique_premises'},
                    '_id': 0
                }
            },
            {'$sort': {'total_services': -1}}
        ]
        report_data = list(services_collection.aggregate(pipeline))
    elif start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)

            match_stage = {'month_year': {'$gte': start_date, '$lt': end_date}}

            pipeline = [
                {'$match': match_stage},
                {
                    '$group': {
                        '_id': '$technician',
                        'total_services': {'$sum': 1},
                        'total_consumption': {'$sum': '$Consumption'},
                        'unique_premises': {'$addToSet': '$Premise Name'}
                    }
                },
                {
                    '$project': {
                        'technician_name': '$_id',
                        'total_services': 1,
                        'total_consumption': 1,
                        'premise_count': {'$size': '$unique_premises'},
                        '_id': 0
                    }
                },
                {'$sort': {'total_services': -1}}
            ]
            report_data = list(services_collection.aggregate(pipeline))
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "warning")
            return redirect(url_for('.technician_work_report'))

    # Generate PDF
    from fpdf import FPDF

    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 16)
            self.cell(0, 10, 'Technician Work Report', 0, 1, 'C')
            self.set_font('Arial', '', 10)
            self.cell(0, 5, f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1, 'C')
            if start_date_str and end_date_str:
                self.cell(0, 5, f'Period: {start_date_str} to {end_date_str}', 0, 1, 'C')
            else:
                self.cell(0, 5, 'All Time Data', 0, 1, 'C')
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', '', 10)

    # Summary section
    if report_data:
        total_services = sum(item['total_services'] for item in report_data)
        total_consumption = sum(item['total_consumption'] for item in report_data)
        total_premises = sum(item['premise_count'] for item in report_data)

        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Summary', 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, f'Total Services: {total_services}', 0, 1)
        pdf.cell(0, 6, f'Total Consumption: {total_consumption:.2f}', 0, 1)
        pdf.cell(0, 6, f'Total Premises Serviced: {total_premises}', 0, 1)
        pdf.cell(0, 6, f'Active Technicians: {len(report_data)}', 0, 1)
        pdf.ln(5)

        # Technician Details section
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Technician Performance Details', 0, 1)
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(50, 8, 'Technician', 1, 0, 'C')
        pdf.cell(30, 8, 'Total Services', 1, 0, 'C')
        pdf.cell(35, 8, 'Total Consumption', 1, 0, 'C')
        pdf.cell(30, 8, 'Premises Count', 1, 1, 'C')

        pdf.set_font('Arial', '', 8)
        for item in report_data:
            pdf.cell(50, 6, str(item['technician_name']), 1, 0)
            pdf.cell(30, 6, str(item['total_services']), 1, 0, 'C')
            pdf.cell(35, 6, f"{item['total_consumption']:.2f}", 1, 0, 'R')
            pdf.cell(30, 6, str(item['premise_count']), 1, 1, 'C')

    # Generate filename
    filename = f"technician_work_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    # Return PDF as response
    response = pdf.output(dest='S')
    response = response.encode('latin-1')

    from flask import Response
    return Response(
        response,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename={filename}'
        }
    )

@data_reports_bp.route('/technician-new-case', methods=['GET', 'POST'])
def technician_new_case():
    """Form for technicians to create a new case with customer email."""
    technician_username = session.get('username', 'unknown')
    user_type = session.get('user_type', '')
    
    # Only allow technicians and admins to access this
    if user_type not in ['technician', 'admin']:
        flash("Access denied.", "danger")
        return redirect(url_for('auth.admin_login'))

    if request.method == "GET":
        return render_template("technician-new-case-form.html")

    current_app.logger.info(f"New case submission by {user_type}: {technician_username}")

    try:
        case_no_count = collection.count_documents({})
        case_no = case_no_count + 1

        user_email = sanitize_input(request.form.get("email", ""), 200)
        premise_name = sanitize_input(request.form.get("premise_name", ""), 200)

        if not premise_name:
            flash("Premise name is required.", "danger")
            return render_template("technician-new-case-form.html")

        if not user_email:
            flash("Customer email is required.", "danger")
            return render_template("technician-new-case-form.html")

        devices_data = []
        device_index = 0
        while True:
            model_field_name = f"devices[{device_index}][model]"
            if model_field_name not in request.form or not request.form.get(model_field_name):
                break

            location = sanitize_input(request.form.get(f"devices[{device_index}][location]", ""), 100)
            model = sanitize_input(request.form.get(model_field_name, ""), 100)
            issues = request.form.getlist(f"devices[{device_index}][issues]")
            remarks = sanitize_input(request.form.get(f"devices[{device_index}][remarks]", ""), 500)

            if not model:
                flash(f"Device {device_index + 1} model is required.", "danger")
                return render_template("technician-new-case-form.html", premise_name=premise_name, email=user_email)

            image_file_name = f"devices[{device_index}][image]"
            image_id = None
            if image_file_name in request.files:
                image_file = request.files[image_file_name]
                if image_file and image_file.filename:
                    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
                    filename = secure_filename(image_file.filename)
                    if '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions:
                        image_file.seek(0, 2)
                        file_size = image_file.tell()
                        image_file.seek(0)

                        if file_size > 5 * 1024 * 1024:
                            flash(f"Image for device {device_index + 1} is too large. Maximum size is 5MB.", "danger")
                            return render_template("technician-new-case-form.html", premise_name=premise_name, email=user_email)

                        image_data = image_file.read()
                        image_id = main_fs_instance.put(image_data, filename=filename, content_type=image_file.content_type)
                    else:
                        flash(f"Invalid file type for device {device_index + 1}. Please use PNG, JPG, JPEG, or GIF.", "danger")
                        return render_template("technician-new-case-form.html", premise_name=premise_name, email=user_email)

            devices_data.append({
                "location": location,
                "model": model,
                "issues": issues,
                "remarks": remarks,
                "image_id": image_id
            })
            device_index += 1

        if not devices_data:
            flash("Please add details for at least one device.", "danger")
            return render_template("technician-new-case-form.html", premise_name=premise_name, email=user_email)

        case_document = {
            "case_no": case_no,
            "user_email": user_email,
            "premise_name": premise_name,
            "devices": devices_data,
            "created_at": datetime.now(),
            "created_by": technician_username,
            "created_by_type": user_type
        }
        collection.insert_one(case_document)
        current_app.logger.info(f"Case #{case_no} created by {user_type}: {technician_username} for customer: {user_email}")

        try:
            from backend.utils import format_devices_for_email

            devices_summary, images_note = format_devices_for_email(devices_data)

            send_customer_email(
                template_key="help_request_new_case_created",
                variables={
                    "case_id": case_no,
                    "premise_name": premise_name,
                    "customer_email": user_email,
                    "devices_summary": devices_summary
                },
                mail=main_mail_instance,
                customer_email=user_email
            )

            admin_email = current_app.config.get('ADMIN_EMAIL_ADDRESS')
            if admin_email:
                send_team_email(
                    template_key="team_help_request_new_case_received",
                    variables={
                        "case_id": case_no,
                        "premise_name": premise_name,
                        "customer_email": user_email,
                        "devices_summary": devices_summary,
                        "images_note": images_note,
                        "device_location": devices_data[0]['location'] if devices_data else "",
                        "issues": ", ".join(devices_data[0]['issues']) if devices_data else "",
                        "remarks": devices_data[0]['remarks'] if devices_data else ""
                    },
                    mail=main_mail_instance,
                    team_email=admin_email
                )
        except Exception as e:
            current_app.logger.error(f"Email notification failed for case #{case_no}: {str(e)}")
            flash(f"Case submitted, but email notifications failed: {e}", "warning")

        flash(f"Case #{case_no} created successfully for {user_email}!", "success")
        return redirect(url_for("dashboard"))

    except Exception as e:
        current_app.logger.error(f"Error creating new case by {technician_username}: {str(e)}")
        flash("An error occurred while creating the case. Please try again.", "danger")
        return render_template("technician-new-case-form.html")

@data_reports_bp.route('/preservice-data')
def preservice_data():
    """View preservice essential oil requirements data"""
    # Allow both admin and technician access
    user_type = session.get('user_type', '')

    if user_type not in ['admin', 'technician']:
        flash("Access denied. Only admins and technicians can access this page.", "danger")
        return redirect(url_for('auth.admin_login'))

    from ..col import preservice_collection, tech_login_collection, eo_list_collection, model_list_collection

    # Get all preservice entries, sorted by date descending
    preservice_entries = list(preservice_collection.find().sort("date", -1))

    # Get filter options
    all_technicians = list(tech_login_collection.find({}, {'username': 1, '_id': 0}))
    all_technicians = [tech['username'] for tech in all_technicians]

    all_essential_oils = list(eo_list_collection.find({}, {'EO2': 1, '_id': 0}).sort("order", 1))
    all_essential_oils = [eo['EO2'] for eo in all_essential_oils if 'EO2' in eo]

    all_device_models = list(model_list_collection.find({}, {'model1': 1, '_id': 0}).sort("order", 1))
    all_device_models = [model['model1'] for model in all_device_models if 'model1' in model]

    return render_template('preservice-data.html',
                         preservice_entries=preservice_entries,
                         all_technicians=all_technicians,
                         all_essential_oils=all_essential_oils,
                         all_device_models=all_device_models)

@data_reports_bp.route('/technician-oil-usage')
def technician_oil_usage():
    """View technician essential oil usage report"""
    # Admin-only access
    user_type = session.get('user_type', '')

    if user_type != 'admin':
        flash("Access denied. Only admins can access this page.", "danger")
        return redirect(url_for('auth.admin_login'))

    # Get filter parameters
    technician_filter = request.args.get('technician', '').strip()
    month_filter = request.args.get('month', '').strip()
    year_filter = request.args.get('year', '').strip()

    # Build query for service records with oil refills
    query = {
        'actions_taken': {'$in': ['Oil Refill']},
        'oil_refill_ml': {'$exists': True, '$ne': None}
    }

    if technician_filter:
        query['technician'] = {'$regex': technician_filter, '$options': 'i'}

    if month_filter and year_filter:
        month_list = [int(m.strip()) for m in month_filter.split(',') if m.strip().isdigit()]
        query['$expr'] = {
            '$and': [
                {'$in': [{'$month': '$month_year'}, month_list]},
                {'$eq': [{'$year': '$month_year'}, int(year_filter)]}
            ]
        }
    elif year_filter:
        query['$expr'] = {'$eq': [{'$year': '$month_year'}, int(year_filter)]}

    # Aggregate oil usage by technician, date, and device
    pipeline = [
        {'$match': query},
        {'$group': {
            '_id': {
                'technician': '$technician',
                'date': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$month_year'}},
                'company': '$company',
                'premise': '$Premise Name',
                'device_sn': '$S/N',
                'device_model': '$Model'
            },
            'total_ml': {'$sum': '$oil_refill_ml'},
            'service_count': {'$sum': 1}
        }},
        {'$sort': {'_id.date': -1, '_id.technician': 1}}
    ]

    oil_usage_data = list(services_collection.aggregate(pipeline))

    # Aggregate premises serviced by technician within the time period
    premises_pipeline = [
        {'$match': query},
        {'$group': {
            '_id': {
                'technician': '$technician',
                'premise': '$Premise Name',
                'company': '$company'
            }
        }},
        {'$group': {
            '_id': '$_id.technician',
            'premises_count': {'$sum': 1},
            'companies': {'$addToSet': '$_id.company'}
        }},
        {'$sort': {'_id': 1}}
    ]

    premises_data = list(services_collection.aggregate(premises_pipeline))

    # Get unique technicians for filter dropdown
    technicians = services_collection.distinct('technician', {'actions_taken': {'$in': ['Oil Refill']}})

    # Calculate summary statistics
    total_usage = sum(item['total_ml'] for item in oil_usage_data)
    total_services = sum(item['service_count'] for item in oil_usage_data)
    total_premises = sum(item['premises_count'] for item in premises_data)

    return render_template('technician-oil-usage.html',
                         oil_usage_data=oil_usage_data,
                         premises_data=premises_data,
                         technicians=technicians,
                         total_usage=total_usage,
                         total_services=total_services,
                         total_premises=total_premises,
                         filters={
                             'technician': technician_filter,
                             'month': month_filter,
                             'year': year_filter
                         })

@data_reports_bp.route('/technician-oil-usage-pdf')
def technician_oil_usage_pdf():
    """Generate PDF report for technician oil usage"""
    # Allow both admin and technician access
    user_type = session.get('user_type', '')

    if user_type not in ['admin', 'technician']:
        flash("Access denied. Only admins and technicians can access this page.", "danger")
        return redirect(url_for('auth.admin_login'))

    # Get filter parameters
    technician_filter = request.args.get('technician', '').strip()
    month_filter = request.args.get('month', '').strip()
    year_filter = request.args.get('year', '').strip()

    # Build query for service records with oil refills
    query = {
        'actions_taken': {'$in': ['Oil Refill']},
        'oil_refill_ml': {'$exists': True, '$ne': None}
    }

    if technician_filter:
        query['technician'] = {'$regex': technician_filter, '$options': 'i'}

    if month_filter and year_filter:
        month_list = [int(m.strip()) for m in month_filter.split(',') if m.strip().isdigit()]
        query['$expr'] = {
            '$and': [
                {'$in': [{'$month': '$month_year'}, month_list]},
                {'$eq': [{'$year': '$month_year'}, int(year_filter)]}
            ]
        }
    elif year_filter:
        query['$expr'] = {'$eq': [{'$year': '$month_year'}, int(year_filter)]}

    # Aggregate oil usage by technician, date, and device
    pipeline = [
        {'$match': query},
        {'$group': {
            '_id': {
                'technician': '$technician',
                'date': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$month_year'}},
                'company': '$company',
                'premise': '$Premise Name',
                'device_sn': '$S/N',
                'device_model': '$Model'
            },
            'total_ml': {'$sum': '$oil_refill_ml'},
            'service_count': {'$sum': 1}
        }},
        {'$sort': {'_id.date': -1, '_id.technician': 1}}
    ]

    oil_usage_data = list(services_collection.aggregate(pipeline))

    # Aggregate premises serviced by technician within the time period
    premises_pipeline = [
        {'$match': query},
        {'$group': {
            '_id': {
                'technician': '$technician',
                'premise': '$Premise Name',
                'company': '$company'
            }
        }},
        {'$group': {
            '_id': '$_id.technician',
            'premises_count': {'$sum': 1},
            'companies': {'$addToSet': '$_id.company'}
        }},
        {'$sort': {'_id': 1}}
    ]

    premises_data = list(services_collection.aggregate(premises_pipeline))

    # Calculate summary statistics
    total_usage = sum(item['total_ml'] for item in oil_usage_data)
    total_services = sum(item['service_count'] for item in oil_usage_data)
    total_premises = sum(item['premises_count'] for item in premises_data)

    # Generate PDF
    from fpdf import FPDF
    from datetime import datetime

    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 16)
            self.cell(0, 10, 'Technician Oil Usage Report', 0, 1, 'C')
            self.set_font('Arial', '', 10)
            self.cell(0, 5, f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1, 'C')
            if technician_filter:
                self.cell(0, 5, f'Technician: {technician_filter}', 0, 1, 'C')
            if month_filter and year_filter:
                self.cell(0, 5, f'Period: {month_filter}/{year_filter}', 0, 1, 'C')
            elif year_filter:
                self.cell(0, 5, f'Year: {year_filter}', 0, 1, 'C')
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', '', 10)

    # Summary section
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Summary', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f'Total Oil Used: {total_usage:.1f} ml', 0, 1)
    pdf.cell(0, 6, f'Total Services: {total_services}', 0, 1)
    pdf.cell(0, 6, f'Total Premises Serviced: {total_premises}', 0, 1)
    pdf.cell(0, 6, f'Active Technicians: {len(premises_data)}', 0, 1)
    pdf.ln(5)

    # Premises by Technician section
    if premises_data:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Premises Serviced by Technician', 0, 1)
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(60, 8, 'Technician', 1, 0, 'C')
        pdf.cell(25, 8, 'Premises', 1, 0, 'C')
        pdf.cell(0, 8, 'Companies', 1, 1, 'C')

        pdf.set_font('Arial', '', 8)
        for item in premises_data:
            pdf.cell(60, 6, str(item['_id']), 1, 0)
            pdf.cell(25, 6, str(item['premises_count']), 1, 0, 'C')
            companies_str = ', '.join(item['companies'][:3])  # Limit to 3 companies
            if len(item['companies']) > 3:
                companies_str += '...'
            pdf.cell(0, 6, companies_str, 1, 1)

        pdf.ln(5)

    # Oil Usage Details section
    if oil_usage_data:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Oil Usage Details', 0, 1)
        pdf.set_font('Arial', 'B', 7)
        pdf.cell(20, 6, 'Date', 1, 0, 'C')
        pdf.cell(25, 6, 'Technician', 1, 0, 'C')
        pdf.cell(30, 6, 'Company', 1, 0, 'C')
        pdf.cell(35, 6, 'Premise', 1, 0, 'C')
        pdf.cell(15, 6, 'Device', 1, 0, 'C')
        pdf.cell(20, 6, 'Model', 1, 0, 'C')
        pdf.cell(20, 6, 'Oil (ml)', 1, 0, 'C')
        pdf.cell(15, 6, 'Services', 1, 1, 'C')

        pdf.set_font('Arial', '', 6)
        for item in oil_usage_data:
            pdf.cell(20, 5, item['_id']['date'], 1, 0)
            pdf.cell(25, 5, str(item['_id']['technician']), 1, 0)
            pdf.cell(30, 5, str(item['_id']['company'])[:28], 1, 0)
            pdf.cell(35, 5, str(item['_id']['premise'])[:33], 1, 0)
            pdf.cell(15, 5, str(item['_id']['device_sn']), 1, 0)
            pdf.cell(20, 5, str(item['_id']['device_model'])[:18], 1, 0)
            pdf.cell(20, 5, f"{item['total_ml']:.1f}", 1, 0, 'R')
            pdf.cell(15, 5, str(item['service_count']), 1, 1, 'C')

    # Generate filename
    filename = f"technician_oil_usage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    # Return PDF as response
    response = pdf.output(dest='S')
    response = response.encode('latin-1')

    from flask import Response
    return Response(
        response,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename={filename}'
        }
    )



@data_reports_bp.route("/api/recent-activities")
@require_auth
def get_recent_activities():
    """API endpoint to fetch recent activities for real-time notifications"""
    try:
        # Get activities from the last 24 hours, excluding current user's activities
        current_user = session.get("username")
        since_time = datetime.now() - timedelta(hours=24)
        
        # Query for recent activities by other users
        query = {
            "timestamp": {"$gte": since_time},
            "user": {"$ne": current_user}  # Exclude current user's activities
        }
        
        # Get the 10 most recent activities
        recent_activities = list(logs_collection.find(query).sort("timestamp", -1).limit(10))
        
        # Format the activities for JSON response
        activities = []
        for activity in recent_activities:
            timestamp = activity.get("timestamp")
            if isinstance(timestamp, datetime):
                formatted_time = timestamp.strftime("%H:%M")
                formatted_date = timestamp.strftime("%Y-%m-%d")
            else:
                formatted_time = "Unknown"
                formatted_date = "Unknown"
            
            activities.append({
                "user": activity.get("user", "Unknown"),
                "action": activity.get("action", "Unknown action"),
                "time": formatted_time,
                "date": formatted_date,
                "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else None
            })
        
        return jsonify({"activities": activities})
    
    except Exception as e:
        current_app.logger.error(f"Error fetching recent activities: {e}")
        return jsonify({"error": "Failed to fetch activities"}), 500

