from datetime import datetime

def log_activity(name, action, database):
    log_entry = {
        "user": name,
        "action": action,
        "timestamp": datetime.now(),
    }
    database.insert_one(log_entry)