from libs import *
from col import *
from backend.blueprints.auth_bp import auth_bp
from backend.blueprints.user_management_bp import user_management_bp
from backend.blueprints.customer_actions_bp import customer_actions_bp
from backend.blueprints.staff_actions_bp import staff_actions_bp
from backend.blueprints.data_reports_bp import data_reports_bp
from backend.blueprints.forms_bp import forms_bp
from backend.blueprints.global_settings_bp import global_settings_bp
from backend.blueprints.api_helpers_bp import api_helpers_bp # Import api_helpers blueprint

app = Flask(__name__)

CORS(app)

load_dotenv()

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

scheduler = APScheduler()




fs = gridfs.GridFS(db)



app.config['MAIL_SERVER'] = os.getenv('SMTP_GOOGLE_SERVER')
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('SMTP_TEST_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('SMTP_TEST_APP_PASSWORD')
app.config['MODE'] = os.getenv('MODE')
app.config['MAIL_SENDER_ADDRESS'] = os.getenv('MAIL_SENDER_ADDRESS')

mail = Mail(app)

@scheduler.task('cron', day=1, hour=0, minute=0)  # Runs every 1st of the month at midnight
def scheduled_route_update():
    replicate_monthly_routes(route_list_collection)

scheduler.init_app(app)
scheduler.start()

# update_data() is now in api_helpers_bp
@app.context_processor
def inject_builtin_functions():
    # Inject Python built-in functions into the Jinja2 environment
    return dict(max=max, min=min)

@app.template_filter('to_querystring')
def to_querystring(query_params):
    """Converts a dictionary into a query string."""
    return urlencode(query_params)

@app.template_filter('update_querystring')
def update_querystring(querystring, key, value):
    """Updates or adds a key-value pair in the query string."""
    query_dict = dict([kv.split('=') for kv in querystring.split('&') if '=' in kv])
    query_dict[key] = value
    return urlencode(query_dict)


# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(user_management_bp)
app.register_blueprint(customer_actions_bp)
app.register_blueprint(staff_actions_bp)
app.register_blueprint(data_reports_bp)
app.register_blueprint(forms_bp)
app.register_blueprint(global_settings_bp)
app.register_blueprint(api_helpers_bp)
# Add other blueprints here as they are created

# The dashboard route is the only one remaining directly in app.py
# All other routes have been moved to their respective blueprints.
# Comments below were kept for historical reference during refactoring but can be removed.
# # customer_form() route is now in customer_actions_bp
# # get_case_details() is now in staff_actions_bp
# # staff_form() is now in staff_actions_bp
# # index() route is now in auth_bp
# # case_success() route is now in customer_actions_bp
# # register() route is now in auth_bp
# # register_admin() route is now in auth_bp
# # delete_user() is now in user_management_bp
# # delete_admin() is now in user_management_bp
# # admin_login() route is now in auth_bp
# # reports() route is now in data_reports_bp
# # pack_list() route is now in data_reports_bp
# # eo_list() route is now in data_reports_bp
# # dashboard() route remains for now, but its login redirect is to auth.admin_login
# # change_form() route is now in forms_bp
# # view_remarks() route is now in data_reports_bp
# # new_customer() route is now in forms_bp
# # pre_service() route is now in forms_bp
# # remark() route is now in forms_bp
# # post_service() route is now in forms_bp
# # view_users() is now in user_management_bp
# # view_admins() is now in user_management_bp
# # get_logs() is now in data_reports_bp
# # profile() is now in data_reports_bp
# # view_device() is now in data_reports_bp
# # route_table() is now in data_reports_bp
# # view_helpss() and view_help() are now in data_reports_bp (renamed to view_complaints_list)
# # service() route is now in forms_bp
# # eo_global() and device_global() routes are now in global_settings_bp
# # save_all_eo_global_changes and save_model1_changes are now in global_settings_bp
# # API routes like get-premises, get_image etc. are in api_helpers_bp