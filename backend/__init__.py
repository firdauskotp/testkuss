from .libs import *
from .col import *
import logging
from logging.handlers import RotatingFileHandler
import os

# Blueprint imports are moved after app, fs, and mail are defined to avoid circular imports.

app = Flask(__name__)

CORS(app)

load_dotenv()

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# Configure logging for production
if not app.debug:
    # Create logs directory if it doesn't exist
    if not os.path.exists('backend/logs'):
        os.makedirs('backend/logs')
    
    # Set up file handler with rotation
    file_handler = RotatingFileHandler('backend/logs/app.log', maxBytes=10240000, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    
    app.logger.setLevel(logging.INFO)
    app.logger.info('Application startup')

# Validate critical environment variables
required_env_vars = ['SECRET_KEY', 'MONGO_URL']
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    app.logger.error(f"Missing required environment variables: {missing_vars}")
    raise ValueError(f"Missing required environment variables: {missing_vars}")

# Session security configuration
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['SESSION_COOKIE_SECURE'] = not app.debug  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent XSS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection

# Initialize Flask-Limiter for rate limiting
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

scheduler = APScheduler()

# Key initializations before blueprint imports
fs = gridfs.GridFS(db)
mail = Mail(app) # mail needs app, so app must be defined before mail

# Now import blueprints
from .blueprints.auth_bp import auth_bp
from .blueprints.user_management_bp import user_management_bp
from .blueprints.customer_actions_bp import customer_actions_bp
from .blueprints.staff_actions_bp import staff_actions_bp
from .blueprints.data_reports_bp import data_reports_bp
from .blueprints.forms_bp import forms_bp
from .blueprints.global_settings_bp import global_settings_bp
from .blueprints.api_helpers_bp import api_helpers_bp

app.config['MAIL_SERVER'] = os.getenv('SMTP_GOOGLE_SERVER')
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('SMTP_TEST_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('SMTP_TEST_APP_PASSWORD')
app.config['MODE'] = os.getenv('MODE')
app.config['MAIL_SENDER_ADDRESS'] = os.getenv('MAIL_SENDER_ADDRESS')

# Validate email configuration
email_vars = ['SMTP_GOOGLE_SERVER', 'SMTP_TEST_USERNAME', 'SMTP_TEST_APP_PASSWORD', 'MAIL_SENDER_ADDRESS']
missing_email_vars = [var for var in email_vars if not os.getenv(var)]
if missing_email_vars:
    app.logger.warning(f"Missing email configuration variables: {missing_email_vars}")
    app.logger.warning("Email functionality may not work properly")

# mail instance is already created above, just ensure all configs are set before it's potentially used by scheduler or other parts.

@scheduler.task('cron', day=1, hour=0, minute=0)  # Runs every 1st of the month at midnight
def scheduled_route_update():
    replicate_monthly_routes(route_list_collection)

scheduler.init_app(app)
scheduler.start()

# Security headers for production
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;"
    return response

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

# --- Health Check Route ---
@app.route("/health")
def health_check():
    """Health check endpoint for production monitoring."""
    from .utils import handle_route_error
    
    @handle_route_error
    def _health_check():
        # Test database connection
        db.command('ping')
        
        # Test Redis connection if available
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'version': '1.0.0'
        }
        
        app.logger.info("Health check completed successfully")
        return jsonify(health_status), 200
    
    return _health_check()

# --- Dashboard Route ---
@app.route("/dashboard")
def dashboard():
    """Main dashboard route with enhanced error handling and logging"""
    from .utils import handle_route_error, require_auth
    
    @require_auth('admin')
    @handle_route_error
    def _dashboard():
        username = session.get("username", "unknown")
        app.logger.info(f"Dashboard accessed by admin: {username}")
        
        try:
            # Fetch counts for dashboard cards with error handling
            help_request_count = collection.count_documents({})
            change_count = change_collection.count_documents({})
            refund_count = refund_collection.count_documents({})
            remarks_count = remark_collection.count_documents({'urgent': False})
            urgent_remarks_count = remark_collection.count_documents({'urgent': True})
            
            dashboard_data = {
                "username": username,
                "help_request_count": help_request_count,
                "change_count": change_count,
                "refund_count": refund_count,
                "remarks_count": remarks_count,
                "urgent_remarks_count": urgent_remarks_count
            }
            
            app.logger.info(f"Dashboard data loaded for {username}: {dashboard_data}")
            
            return render_template("dashboard.html", **dashboard_data)
            
        except Exception as e:
            app.logger.error(f"Dashboard data loading failed for {username}: {e}")
            # Return dashboard with default values if data loading fails
            return render_template("dashboard.html", 
                                username=username,
                                help_request_count=0,
                                change_count=0,
                                refund_count=0,
                                remarks_count=0,
                                urgent_remarks_count=0)
    
    return _dashboard()

# --- Global Error Handlers ---
@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    app.logger.warning(f"404 error: {request.url} - IP: {request.environ.get('REMOTE_ADDR')}")
    if request.is_json:
        return jsonify({'error': 'Resource not found'}), 404
    flash("The requested page could not be found.", "warning")
    return redirect(url_for('auth.index'))

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    error_id = f"server_error_{int(datetime.now().timestamp())}"
    app.logger.error(f"500 error [{error_id}]: {error} - URL: {request.url}")
    if request.is_json:
        return jsonify({
            'error': 'Internal server error',
            'error_id': error_id
        }), 500
    flash("An internal error occurred. Please try again later.", "danger")
    return redirect(url_for('auth.index'))

@app.errorhandler(403)
def forbidden_error(error):
    """Handle 403 errors"""
    app.logger.warning(f"403 error: {request.url} - IP: {request.environ.get('REMOTE_ADDR')}")
    if request.is_json:
        return jsonify({'error': 'Access forbidden'}), 403
    flash("You don't have permission to access this resource.", "danger")
    return redirect(url_for('auth.admin_login'))

# --- End Dashboard Route ---

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