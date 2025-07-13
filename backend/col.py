from libs import *

load_dotenv()

# MongoDB Configuration
MONGO_URI = os.getenv('MONGO_URL')
mongo = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = mongo['customer']
collection = db['case_issue']

login_db=mongo['login_admin']
login_collection=login_db['log']

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
industry_list_collection = dashboard_db['industry']


# customer_collection = dashboard_db['customer']
# device_collection = dashboard_db['device']
change_collection = dashboard_db['change']
refund_collection = dashboard_db['refund']
changed_models_collection = dashboard_db["changed_models"]
discontinue_collection = dashboard_db["discontinue"]

logs_db=mongo['logs']
logs_collection=logs_db['logs']

test_db=mongo['test']
test_collection=test_db['test']