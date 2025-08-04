from backend.utils import handle_route_error, replicate_monthly_routes, require_auth
from .libs import *
from .col import *
from .config import get_config, validate_environment
import logging
from logging.handlers import RotatingFileHandler
import os

# Validate environment variables before anything else
validate_environment()

# Blueprint imports are moved after app, fs, and mail are defined to avoid circular imports.
app = Flask(__name__)

# Load configuration based on environment
config_class = get_config()
app.config.from_object(config_class)

CORS(app)

# Configure logging based on environment
log_dir = 'backend/logs'
os.makedirs(log_dir, exist_ok=True)

# Set up file handler with rotation
log_file = getattr(config_class, 'LOG_FILE', 'backend/logs/app.log')
max_bytes = getattr(config_class, 'LOG_MAX_BYTES', 10240000)
backup_count = getattr(config_class, 'LOG_BACKUP_COUNT', 10)

file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))

# Set logging level based on configuration
log_level = getattr(config_class, 'LOG_LEVEL', 'INFO')
file_handler.setLevel(getattr(logging, log_level))
app.logger.addHandler(file_handler)
app.logger.setLevel(getattr(logging, log_level))

app.logger.info(f'Application startup - Mode: {config_class.__name__}')

# Initialize Flask-Limiter for rate limiting
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=app.config['RATELIMIT_DEFAULT'],
    storage_uri=app.config['RATELIMIT_STORAGE_URL']
)

# Create upload folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

scheduler = APScheduler()

# Key initializations before blueprint imports
fs = gridfs.GridFS(db)
mail = Mail(app)  # Configuration is already loaded from config class

# Check email configuration and log warnings if needed
missing_email_vars = config_class.get_missing_email_vars()
if missing_email_vars:
    app.logger.warning(f"Missing email configuration variables: {missing_email_vars}")
    app.logger.warning("Email functionality may not work properly")

# Now import blueprints
from .blueprints.auth_bp import auth_bp
from .blueprints.user_management_bp import user_management_bp
from .blueprints.customer_actions_bp import customer_actions_bp
from .blueprints.staff_actions_bp import staff_actions_bp
from .blueprints.data_reports_bp import data_reports_bp
from .blueprints.forms_bp import forms_bp
from .blueprints.global_settings_bp import global_settings_bp
from .blueprints.api_helpers_bp import api_helpers_bp

# mail instance is already created above, just ensure all configs are set before it's potentially used by scheduler or other parts.

@scheduler.task('cron', day=1, hour=0, minute=0)  # Runs every 1st of the month at midnight
def scheduled_route_update():
    replicate_monthly_routes(route_list_collection)

scheduler.init_app(app)
scheduler.start()

# Security headers based on configuration
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses based on environment configuration."""
    for header, value in app.config['SECURITY_HEADERS'].items():
        response.headers[header] = value
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

# --- Development/Testing Route to Clear Rate Limiter ---
@app.route("/clear-limiter")
def clear_rate_limiter():
    """Clear rate limiter memory - DEVELOPMENT/TESTING ONLY"""
    if not app.config.get('DEBUG', False) and not app.config.get('TESTING', False):
        app.logger.warning("Attempt to clear rate limiter in production mode - blocked")
        return jsonify({'error': 'Not allowed in production'}), 403
    
    try:
        # Clear all rate limit storage
        limiter.storage.reset()
        app.logger.info("Rate limiter memory cleared successfully")
        return jsonify({
            'status': 'success', 
            'message': 'Rate limiter memory cleared',
            'mode': app.config.get('MODE', 'unknown'),
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        app.logger.error(f"Failed to clear rate limiter: {e}")
        return jsonify({'error': 'Failed to clear rate limiter'}), 500

# --- Dashboard Route ---
@app.route("/dashboard")
@require_auth('admin')
@handle_route_error
def dashboard():
    """Main dashboard route with enhanced error handling and logging"""
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
