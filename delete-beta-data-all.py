# Base Code
from os import name

# import pymongo
#
# DATABASE_NAME = "auto-serving-results"
# COLLECTION_NAME = "results"
# HOST = "localhost"
# PORT = 27017
#
# year = 2024
# month = 4
# user_id = 97
#
# client = pymongo.MongoClient(host=HOST, port=PORT)
# db = client[DATABASE_NAME]
# collection = db[COLLECTION_NAME]
#
# delete_condition = {
#     "user_id": str(user_id),
#     "$expr": {
#         "$and": [
#             {"$eq": [{"$year": "$created_date"}, year]},
#             {"$eq": [{"$month": "$created_date"}, month]},
#         ]
#     },
# }
# # print(delete_condition)
# result = collection.delete_many(delete_condition)
# # print(result)
# print("FINAL OUTPUT :: :: :: :: ")
# print(result.deleted_count)

# =====================================================================================================

## LAMBDA CODE :

# ============================== Beta - Delete All Data from MongoDB ====================================================

from pymongo import MongoClient


def lambda_handler(event, context):
    """
    AWS Lambda function to delete documents from MongoDB
    based on user_id, year, and month.
    """

    # =======================
    # MongoDB Connection Info
    # =======================
    MONGO_URI = "mongodb://10.0.2.187:27333/"
    DATABASE_NAME = "auto-serving-results"
    COLLECTION_NAME = "results"

    # =======================
    # Delete Criteria
    # =======================
    year = 2024
    month = 4
    user_id = 97  # RPG

    # =======================
    # MongoDB Connection
    # =======================
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]

    # =======================
    # Delete Condition
    # =======================
    delete_condition = {
        "user_id": str(user_id),
        # "is_hide": True,
        "$expr": {
            "$and": [
                {"$eq": [{"$year": "$created_date"}, year]},
                {"$eq": [{"$month": "$created_date"}, month]},
            ]
        },
    }

    # =======================
    # Perform Delete
    # =======================
    result = collection.delete_many(delete_condition)

    # =======================
    # Response
    # =======================
    response = {
        "deleted_count": result.deleted_count,
        "criteria": delete_condition,
        "status": "success" if result.deleted_count > 0 else "no_docs_found"
    }

    print("FINAL OUTPUT :: ", response)

    client.close()

    return response


# ======================================================================================================


## LOCAL CODE :

# ============================== Beta - Delete All Data from MongoDB ====================================================

from pymongo import MongoClient


def main():
    # =======================
    # MongoDB Connection Info
    # =======================
    MONGO_URI = "mongodb://localhost:27017/"
    DATABASE_NAME = "auto-serving-results"
    COLLECTION_NAME = "results"

    # =======================
    # Delete Criteria
    # =======================
    year = 2025
    month = 6
    user_id = 97  # RPG

    # =======================
    # MongoDB Connection
    # =======================
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]

    # =======================
    # Delete Condition
    # =======================
    delete_condition = {
        "user_id": str(user_id),
        # "is_hide": True,
        "$expr": {
            "$and": [
                {"$eq": [{"$year": "$created_date"}, year]},
                {"$eq": [{"$month": "$created_date"}, month]},
            ]
        },
    }

    # =======================
    # Perform Delete
    # =======================
    result = collection.delete_many(delete_condition)

    # =======================
    # Response
    # =======================
    response = {
        "deleted_count": result.deleted_count,
        "criteria": delete_condition,
        "status": "success" if result.deleted_count > 0 else "no_docs_found"
    }

    print("FINAL OUTPUT :: ", response)

    client.close()

    return response


if __name__ == "__main__":
    main()

# ======================================================================================================
