import pymongo

DATABASE_NAME = "auto-serving-results"
COLLECTION_NAME = "results"
HOST = "localhost"
PORT = 27017

year = 2025
month = 9
user_id = 97

client = pymongo.MongoClient(host=HOST, port=PORT)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

delete_condition = {
    "user_id": str(user_id),
    "is_hide": True,
    "$expr": {
        "$and": [
            {"$eq": [{"$year": "$created_date"}, year]},
            {"$eq": [{"$month": "$created_date"}, month]},
        ]
    },
}

result = collection.delete_many(delete_condition)
print("FINAL OUTPUT :: :: :: :: ")
print(result.deleted_count)
