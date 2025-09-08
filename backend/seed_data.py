import os
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timedelta
from bson import ObjectId

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/")
DB_NAME = "kuss" # Assuming the database name is 'kuss' based on common practice. Adjust if needed.

# --- Data Definitions ---
def get_seed_data():
    """Returns a list of 10 customers with their premises, PICs, and devices."""
    customers = []
    for i in range(1, 11):
        company_name = f"Test Company {i}"
        industry = "Retail" if i % 2 == 0 else "F&B"

        customer = {
            "company_name": company_name,
            "industry": industry,
            "premises": [
                {
                    "name": f"Main Outlet {i}",
                    "area": f"{i * 100} sqft",
                    "address": f"{i} Main Street, Cityville",
                    "pics": [
                        {
                            "name": f"Manager {i}",
                            "designation": "Store Manager",
                            "contact": f"1234-567{i}",
                            "email": f"manager{i}@testcompany.com"
                        }
                    ],
                    "devices": [
                        {
                            "sn": 1000 + i,
                            "model": "VOX",
                            "color": "White",
                            "volume": 100,
                            "current_eo": "Lavender",
                            "location": "Entrance"
                        },
                        {
                            "sn": 2000 + i,
                            "model": "AERO",
                            "color": "Black",
                            "volume": 120,
                            "current_eo": "Peppermint",
                            "location": "Restroom"
                        }
                    ]
                }
            ]
        }
        customers.append(customer)
    return customers

def seed_database():
    """Connects to the database and populates it with seed data."""
    try:
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        print(f"Connected to MongoDB database: {DB_NAME}")

        # Get collections
        profile_list_collection = db["profile_list"]
        device_list_collection = db["device_list"]
        services_collection = db["services"]
        route_list_collection = db["route_list"]

        # Clear existing data
        profile_list_collection.delete_many({})
        device_list_collection.delete_many({})
        services_collection.delete_many({})
        route_list_collection.delete_many({})
        print("Cleared existing data from collections.")

        customers_data = get_seed_data()

        for customer in customers_data:
            company_name = customer["company_name"]
            industry = customer["industry"]

            for premise_data in customer["premises"]:
                premise_name = premise_data["name"]

                # Insert premise profile
                premise_profile = {
                    "company": company_name,
                    "industry": industry,
                    "premise_name": premise_name,
                    "premise_area": premise_data["area"],
                    "premise_address": premise_data["address"],
                    "created_at": datetime.now()
                }
                profile_list_collection.insert_one(premise_profile)

                for pic_data in premise_data["pics"]:
                    # Insert PIC profile
                    pic_profile = {
                        "company": company_name,
                        "tied_to_premise": premise_name,
                        **pic_data,
                        "created_at": datetime.now()
                    }
                    profile_list_collection.insert_one(pic_profile)

                for device_data in premise_data["devices"]:
                    # Insert device document
                    device_doc = {
                        "company": company_name,
                        "tied_to_premise": premise_name,
                        "S/N": device_data["sn"],
                        "Model": device_data["model"],
                        "Color": device_data["color"],
                        "Volume": device_data["volume"],
                        "Current EO": device_data["current_eo"],
                        "location": device_data["location"],
                        "inactive": False,
                        "created_at": datetime.now()
                    }
                    device_list_collection.insert_one(device_doc)

                    # Create an initial service record for the device installation
                    service_record = {
                        **device_doc,
                        "month_year": datetime.now(),
                        "technician": "installer",
                        "remarks": "Initial installation.",
                        "signature": "", # No signature for initial install
                        "Consumption": 0,
                        "Balance": device_data["volume"]
                    }
                    del service_record["_id"] # remove the _id from device_doc
                    services_collection.insert_one(service_record)

        print(f"Seeded {len(customers_data)} customers with their profiles, PICs, and devices.")

        # Create some routes for today
        today = datetime.now()
        routes_to_create = [
            {"date": today, "company": "Test Company 1", "premise": "Main Outlet 1", "model": "VOX", "color": "White", "eo": "Lavender"},
            {"date": today, "company": "Test Company 2", "premise": "Main Outlet 2", "model": "AERO", "color": "Black", "eo": "Peppermint"},
            {"date": today + timedelta(days=1), "company": "Test Company 3", "premise": "Main Outlet 3", "model": "VOX", "color": "White", "eo": "Lavender"},
        ]
        route_list_collection.insert_many(routes_to_create)
        print(f"Created {len(routes_to_create)} service routes.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client.close()
        print("Database connection closed.")

if __name__ == "__main__":
    seed_database()
