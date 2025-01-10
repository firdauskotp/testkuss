from datetime import datetime

def log_activity(username, action, details=None):
    """Logs user activity to the database."""
    log_entry = {
        "username": username,
        "action": action,
        "timestamp": datetime.now(),
        "details": details or ""
    }
    db["activity_logs"].insert_one(log_entry)