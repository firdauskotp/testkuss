# import pandas as pd
import certifi
from pymongo import MongoClient
from datetime import datetime, time

# Load Excel file
# file_path = '2024 - 12 - A. Service List.xlsx'  # Path to your Excel file
# df = pd.read_excel(file_path, sheet_name='Pack List')  # Adjust sheet name as needed

# Convert all `datetime` and `time` objects to strings
def convert_to_string(value):
    if isinstance(value, (datetime, time)):
        return value.strftime('%H:%M:%S')  # Convert to string (HH:MM:SS)
    return value  # Return the value as is if not a datetime or time object

# df = df.applymap(convert_to_string)

# Convert to dictionary
# data = df.to_dict(orient='records')

# MongoDB connection
client = MongoClient('mongodb+srv://firdauskotp:stayhumbleeh@cluster0.msdva.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0', tlsCAFile=certifi.where())
db = client['dashboard_db']
collection = db['model_list']

# Insert data into MongoDB
# try:
#     collection.insert_many(data)
#     print("Data successfully imported into MongoDB!")
# except Exception as e:
#     print(e)

eos = list(collection.find().sort("model1", 1))

# 🛠️ Update each document with an incremental order number
for index, eo in enumerate(eos):
    collection.update_one(
        {"_id": eo["_id"]},
        {"$set": {"order": index}}
    )

print("Order field added to all EO documents!")
