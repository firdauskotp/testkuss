from datetime import datetime

def log_activity(name, action, database):
    log_entry = {
        "user": name,
        "action": action,
        "timestamp": datetime.now(),
    }
    database.insert_one(log_entry)

def safe_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return value