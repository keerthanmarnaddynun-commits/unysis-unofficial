from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timezone
import certifi
import os

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"), tlsCAFile=certifi.where())
db = client[os.getenv("MONGO_DB")]
collection = db["authorized_ids"]

roles = {
    "citizen": "CTZ",
    "journalist": "JRN",
    "police": "POL",
    "authority": "ATH",
}

docs = []

for role, prefix in roles.items():
    for i in range(1, 11):
        docs.append({
            "role": role,
            "official_id": f"{prefix}-BS-{i:04d}",
            "name": f"Demo {role.title()} {i:02d}",
            "organization": "BharatShield Demo",
            "status": "active",
            "created_at": datetime.now(timezone.utc)
        })

collection.delete_many({})
result = collection.insert_many(docs)

print(f"Inserted {len(result.inserted_ids)} records into authorized_ids")
print("Total records:", collection.count_documents({}))
print("Collections:", db.list_collection_names())
print("Authorized IDs:", db.authorized_ids.count_documents({}))