import os
from pymongo import MongoClient
from datetime import datetime, timedelta

# Hardcoded values for testing in the sandbox
# In a real scenario, these should come from a secure configuration or environment
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "app_db" # Replace with the actual DB name if known, otherwise this is a guess

print(f"Attempting to connect to MongoDB with URI: {MONGO_URI} and DB: {DB_NAME}")

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000) # Added timeout
    # Check connection
    client.admin.command('ping')
    print("MongoDB connection successful.")
except Exception as e:
    print(f"MongoDB connection failed: {e}")
    exit(1)

db = client[DB_NAME]
discontinue_collection = db.discontinue_collection

# Add a record with a past collect_back_date_dt and is_active: True
past_date = datetime.now() - timedelta(days=5)
test_record_1 = {
    "_id": "test_discontinued_1", # Using a predictable ID
    "user": "test_user_discontinue",
    "company": "TestCompanyForDiscontinue",
    "date": (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'),
    "month": (datetime.now() - timedelta(days=10)).strftime('%B').upper()[:3],
    "year": str((datetime.now() - timedelta(days=10)).year),
    "premises": ["TestPremiseDiscontinue"],
    "devices": ["TestDeviceDiscontinue"],
    "collect_back": True,
    "remark": "Test record for clear_discontinued_items",
    "submitted_at": datetime.now() - timedelta(days=10),
    "collect_back_date_dt": past_date,
    "is_active": True
}
# Using update_one with upsert=True to ensure the test can be re-run
discontinue_collection.update_one({"_id": test_record_1["_id"]}, {"$set": test_record_1}, upsert=True)
print(f"Upserted record with ID: {test_record_1['_id']} into discontinue_collection.")

# Also add a record without is_active field
test_record_2 = {
    "_id": "test_discontinued_2", # Using a predictable ID
    "user": "test_user_discontinue_no_active",
    "company": "TestCompanyForDiscontinueNoActive",
    "date": (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'),
    "month": (datetime.now() - timedelta(days=10)).strftime('%B').upper()[:3],
    "year": str((datetime.now() - timedelta(days=10)).year),
    "premises": ["TestPremiseDiscontinueNoActive"],
    "devices": ["TestDeviceDiscontinueNoActive"],
    "collect_back": True,
    "remark": "Test record (no is_active) for clear_discontinued_items",
    "submitted_at": datetime.now() - timedelta(days=10),
    "collect_back_date_dt": past_date
}
# Remove is_active if it exists from previous runs for this predictable _id
discontinue_collection.update_one({"_id": test_record_2["_id"]}, {"$set": test_record_2, "$unset": {"is_active": ""}}, upsert=True)
print(f"Upserted record (no is_active) with ID: {test_record_2['_id']} into discontinue_collection.")

# Store IDs for verification later (using the predictable IDs)
with open("test_ids.txt", "w") as f:
    f.write(f"{test_record_1['_id']}\n")
    f.write(f"{test_record_2['_id']}\n")

client.close()
print("Script finished.")
