from .libs import *
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB Configuration
MONGO_URI = os.getenv('MONGO_URL')
if MONGO_URI:
    # Remove quotes if present
    MONGO_URI = MONGO_URI.strip("'\"")
    
    # Try to connect without SSL first since local MongoDB typically doesn't use SSL
    try:
        mongo = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tls=False)
        # Test the connection
        mongo.admin.command('ping')
        print("Connected to MongoDB successfully in col.py")
    except Exception as error:
        print(f"Connection failed in col.py: {error}")
        # Try with SSL as fallback
        try:
            mongo = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
            mongo.admin.command('ping')
            print("Connected to MongoDB with SSL in col.py")
        except Exception as ssl_error:
            print(f"SSL connection also failed in col.py: {ssl_error}")
            raise Exception("Could not connect to MongoDB in col.py")
else:
    raise Exception("MONGO_URL not found in environment variables")
db = mongo['customer']
collection = db['case_issue']

login_db=mongo['login_admin']
login_collection=login_db['log']

# Add is_super_admin field to existing users if not present
# This ensures backward compatibility
try:
    for user in login_collection.find({'is_super_admin': {'$exists': False}}):
        login_collection.update_one(
            {'_id': user['_id']},
            {'$set': {'is_super_admin': False}}
        )

    # Set the first user as super admin if no super admin exists
    if login_collection.count_documents({'is_super_admin': True}) == 0:
        first_user = login_collection.find_one()
        if first_user:
            login_collection.update_one(
                {'_id': first_user['_id']},
                {'$set': {'is_super_admin': True}}
            )
            print("First user set as super admin")
except Exception as e:
    print(f"Could not update super admin status: {e}")

login_cust_db=mongo['login_cust']
login_cust_collection=login_cust_db['logg']

remark_db=mongo['remark']
remark_collection=remark_db['cases']

dashboard_db = mongo['dashboard_db']
services_collection = dashboard_db['services']
eo_list_collection = dashboard_db['eo_list']
eo_pack_collection = dashboard_db['eo_pack']
model_list_collection = dashboard_db['model_list']
others_list_collection = dashboard_db['others_devices_pack']
empty_bottles_list_collection = dashboard_db['others_empty_bottle_pack']
straw_list_collection = dashboard_db['straw_mist_heads_pack']
profile_list_collection = dashboard_db['profile']
device_list_collection = dashboard_db['device']
route_list_collection = dashboard_db['routes']

# customer_collection = dashboard_db['customer']
# device_collection = dashboard_db['device']
change_collection = dashboard_db['change']
refund_collection = dashboard_db['refund']
industry_list_collection = dashboard_db['industry']
logs_db=mongo['logs']
logs_collection=logs_db['logs']

test_db=mongo['test']
test_collection=test_db['test']
