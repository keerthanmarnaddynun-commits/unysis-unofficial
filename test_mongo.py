from pymongo import MongoClient
from dotenv import load_dotenv
import os
import certifi

load_dotenv()

uri = os.getenv("MONGO_URI")
db_name = os.getenv("MONGO_DB")
client = MongoClient(uri, tlsCAFile=certifi.where())


print("Connected successfully!")

db = client[db_name]

print("Database:", db.name)

print("Collections:", db.list_collection_names())