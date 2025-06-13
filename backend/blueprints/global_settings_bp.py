# backend/blueprints/global_settings_bp.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from bson import ObjectId # For save operations that might use ObjectIds

from ..col import eo_pack_collection, model_list_collection
# Assuming these are the only collections needed for these routes

global_settings_bp = Blueprint(
    'global_settings',
    __name__,
    template_folder='../templates', # Points to backend/templates
    static_folder='../static',     # Points to backend/static
    url_prefix='/admin/settings'
)

@global_settings_bp.before_request
def require_admin_login():
    if 'username' not in session:
        flash("You must be logged in as an admin to access this page.", "warning")
        return redirect(url_for('auth.admin_login'))

@global_settings_bp.route('/eo-global')
def eo_global_view():
    eos = list(eo_pack_collection.find().sort("order", 1))
    return render_template('eo-global.html', eos=eos)

@global_settings_bp.route('/save-eo-global', methods=['POST'])
def save_eo_global_changes():
    data = request.json
    added = data.get('added', [])
    edited = data.get('edited', [])
    deleted = data.get('deleted', [])
    visual_order = data.get('visual_order', []) # List of items in current display order

    # 1. Handle added EOs
    newly_added_ids_map = {} # To map temp client ID to new server ObjectId
    for idx, eo_data in enumerate(added):
        eo_name = eo_data['eo_name'].strip()
        if not eo_name:
            return jsonify({'status': 'error', 'message': f"EO name cannot be empty."}), 400
        existing = eo_pack_collection.find_one({'eo_name': eo_name})
        if existing:
            return jsonify({'status': 'error', 'message': f"EO name '{eo_name}' already exists."}), 400

        # For newly added items, their 'order' will be set later based on visual_order
        new_eo = eo_pack_collection.insert_one({"eo_name": eo_name, "order": -1 }) # temp order
        # If visual_order uses temp client-side IDs for new items, map them
        client_temp_id = eo_data.get('temp_id') # Assuming client might send a temp ID
        if client_temp_id:
            newly_added_ids_map[client_temp_id] = new_eo.inserted_id


    # 2. Handle edited EOs
    for eo_data in edited:
        eo_id_str = eo_data['_id']
        eo_name = eo_data['eo_name'].strip()
        if not eo_name:
            return jsonify({'status': 'error', 'message': f"EO name cannot be empty for ID {eo_id_str}."}), 400

        eo_id = ObjectId(eo_id_str) if isinstance(eo_id_str, str) else eo_id_str

        existing = eo_pack_collection.find_one({
            'eo_name': eo_name,
            '_id': {'$ne': eo_id}
        })
        if existing:
            return jsonify({'status': 'error', 'message': f"EO name '{eo_name}' already exists (for ID {eo_id_str})."}), 400
        eo_pack_collection.update_one({'_id': eo_id}, {'$set': {'eo_name': eo_name}})

    # 3. Handle deleted EOs
    for _id_str in deleted:
        eo_pack_collection.delete_one({'_id': ObjectId(_id_str)})

    # 4. Assign order based on visual list
    for index, item_identifier in enumerate(visual_order):
        # item_identifier could be an ObjectId string (for existing/edited) or a temp client ID or name (for new)
        eo_to_order = None
        if isinstance(item_identifier, dict) and item_identifier.get('_id'): # If full object sent
             item_id_str = item_identifier['_id']
             eo_to_order = eo_pack_collection.find_one({'_id': ObjectId(item_id_str)})
        elif isinstance(item_identifier, str) and ObjectId.is_valid(item_identifier):
             eo_to_order = eo_pack_collection.find_one({'_id': ObjectId(item_identifier)})
        elif isinstance(item_identifier, dict) and item_identifier.get('eo_name'): # For newly added items identified by name
            # This case needs careful handling if names are not unique before this transaction committed
            # Best if client sends back the temp_id for new items within visual_order
            temp_id = item_identifier.get('temp_id')
            if temp_id and temp_id in newly_added_ids_map:
                 eo_to_order = eo_pack_collection.find_one({'_id': newly_added_ids_map[temp_id]})
            else: # Fallback to name, less reliable for items just added and not yet having unique constraint fully effective
                 eo_to_order = eo_pack_collection.find_one({'eo_name': item_identifier['eo_name'], 'order': -1})

        if eo_to_order:
            eo_pack_collection.update_one({'_id': eo_to_order['_id']}, {'$set': {'order': index}})

    return jsonify({'status': 'success'})


@global_settings_bp.route('/device-global')
def device_global_view():
    models = list(model_list_collection.find().sort("order", 1))
    return render_template('device-global.html', models=models)

@global_settings_bp.route('/save-device-global', methods=['POST'])
def save_device_global_changes():
    data = request.json
    added = data.get('added', []) # List of dicts, e.g., [{'model1': 'New Name', 'temp_id': 'client-id-1'}]
    edited = data.get('edited', []) # List of dicts, e.g., [{'_id': 'mongoId', 'model1': 'Updated Name'}]
    deleted = data.get('deleted', []) # List of _id strings
    # 'order' from original JS was list of _id strings.
    # For new items, client should send a temporary ID or the name itself in the order list.
    visual_order = data.get('order', []) # List of identifiers (mongo _id or temp client ID for new items)

    newly_added_ids_map = {} # Maps client temp ID to new server ObjectId

    for model_data in added:
        model_name = model_data['model1'].strip()
        if not model_name:
            return jsonify({'status': 'error', 'message': "Model name cannot be empty."}), 400
        existing = model_list_collection.find_one({'model1': model_name})
        if existing:
            return jsonify({'status': 'error', 'message': f"Model name '{model_name}' already exists."}), 400

        # Order for new items will be set based on visual_order later
        new_model = model_list_collection.insert_one({"model1": model_name, "order": -1}) # Temp order
        client_temp_id = model_data.get('temp_id') # Assuming client sends a temp ID like 'new-xxxx'
        if client_temp_id:
            newly_added_ids_map[client_temp_id] = new_model.inserted_id


    for model_data in edited:
        model_id_str = model_data['_id']
        model_name = model_data['model1'].strip()
        if not model_name:
            return jsonify({'status': 'error', 'message': f"Model name cannot be empty for ID {model_id_str}."}), 400

        model_id = ObjectId(model_id_str) if isinstance(model_id_str, str) else model_id_str
        existing = model_list_collection.find_one({
            'model1': model_name,
            '_id': {'$ne': model_id}
        })
        if existing:
            return jsonify({'status': 'error', 'message': f"Model name '{model_name}' already exists (for ID {model_id_str})."}), 400
        model_list_collection.update_one({'_id': model_id}, {'$set': {'model1': model_name}})

    for _id_str in deleted:
        model_list_collection.delete_one({'_id': ObjectId(_id_str)})

    # Re-order based on the full list of IDs/tempIDs provided in visual_order
    for idx, item_identifier in enumerate(visual_order):
        model_to_order = None
        if ObjectId.is_valid(item_identifier): # It's an existing item's ObjectId string
            model_to_order = model_list_collection.find_one({'_id': ObjectId(item_identifier)})
        elif item_identifier in newly_added_ids_map: # It's a temp client ID for a newly added item
             model_to_order = model_list_collection.find_one({'_id': newly_added_ids_map[item_identifier]})

        if model_to_order:
            model_list_collection.update_one({'_id': model_to_order['_id']}, {'$set': {'order': idx}})

    return jsonify({'status': 'success'})
