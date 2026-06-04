from pymongo import MongoClient
from dotenv import load_dotenv
import certifi
import os
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

uri = os.getenv("MONGO_URI")
db_name = os.getenv("MONGO_DB", "unisys_project")
client = MongoClient(uri, tlsCAFile=certifi.where())
db = client[db_name]

print("Recent reports in database:")
for doc in db.reports.find().sort("created_at", -1).limit(5):
    print(f"\nCase ID: {doc.get('report_id')}")
    print(f"Status: {doc.get('status')}")
    print(f"Media: {doc.get('media_filename')}")
    print(f"Legal Docs: {doc.get('legal_documents')}")
