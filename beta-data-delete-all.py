import os
import pymongo
import json
from datetime import datetime
import pytz


def delete_records():
    # Configuration from environment variables
    DATABASE_NAME = os.getenv('MONGO_DB_NAME', 'auto-serving-results')
    COLLECTION_NAME = os.getenv('MONGO_COLL_NAME', 'results')
    HOST = os.getenv('MONGO_HOST', 'localhost')
    PORT = int(os.getenv('MONGO_PORT', 27017))

    print("=== MongoDB Data Deletion Tool ===")
    print("This script will delete records based on date range, user ID, and labels.\n")

    # Get user ID from environment variable
    user_id = os.getenv('USER_ID')
    if not user_id:
        print("Error: USER_ID not found in environment variables")
        return
    print(f"Using user ID from environment: {user_id}")
    
    # Get date range from environment variables
    try:
        start_date_str = os.getenv('START_DATETIME')
        end_date_str = os.getenv('END_DATETIME')
        
        if not start_date_str or not end_date_str:
            print("Error: START_DATETIME and/or END_DATETIME not found in environment variables")
            return
            
        print(f"Using date range from environment: {start_date_str} to {end_date_str}")
        
        # Convert input dates to datetime objects in UTC
        timezone = pytz.utc
        start_dt = timezone.localize(datetime.strptime(start_date_str, '%d-%m-%Y %H:%M:%S'))
        end_dt = timezone.localize(datetime.strptime(end_date_str, '%d-%m-%Y %H:%M:%S'))
        
    except ValueError as e:
        print(f"\nError: Invalid date format in environment variables. Expected format: DD-MM-YYYY HH:MM:SS")
        print(f"Details: {str(e)}")
        return
    
    # Get use cases from environment variable
    usecases_json = os.getenv('USECASES_LIST')
    if not usecases_json:
        print("Error: USECASES_LIST not found in environment variables")
        return
        
    try:
        labels = json.loads(usecases_json.replace("'", '"'))  # Convert single quotes to double quotes for JSON parsing
        print(f"Using use cases from environment: {', '.join(labels)}")
    except json.JSONDecodeError as e:
        print(f"Error parsing USECASES_LIST from environment variables: {str(e)}")
        return

    # Connect to MongoDB
    try:
        client = pymongo.MongoClient(host=HOST, port=PORT)
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]

        # Test the connection
        client.admin.command('ping')

        # Build the query
        query = {
            "user_id": str(user_id),
            "is_hide": False,
            "created_date": {"$gte": start_dt, "$lte": end_dt}
        }

        # Add label matching condition if labels are provided
        if labels:
            query["result.detection.label"] = {"$in": labels}

        # First, count matching records
        total_matching = collection.count_documents(query)
        print(f"\nFound {total_matching} matching records in the specified date range")

        if total_matching == 0:
            print("No records to delete.")
            return

        # # Show sample of records to be deleted
        # sample = collection.find(query).limit(3)
        # print("\nSample of matching records:")
        # for i, doc in enumerate(sample, 1):
        #     print(f"\nRecord {i}:")
        #     print(f"  ID: {doc.get('_id')}")
        #     print(f"  Created: {doc.get('created_date')}")
        #     print(f"  Labels: {[d.get('label') for d in doc.get('result', {}).get('detection', [])]}")

        # # Confirm before deletion
        # confirm = input(f"\nDo you want to delete {total_matching} records? (yes/no): ").strip().lower()
        # if confirm != 'yes':
        #     print("Deletion cancelled.")
        #     return

        # Perform deletion
        result = collection.delete_many(query)

        # Print results
        print(f"\nDeletion Summary:")
        print(f"- Total matching records: {total_matching}")
        print(f"- Successfully deleted: {result.deleted_count}")

    except pymongo.errors.ConnectionFailure:
        print("Error: Could not connect to MongoDB. Please check your connection settings.")
    except pymongo.errors.PyMongoError as e:
        print(f"\nMongoDB error: {str(e)}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {str(e)}")
    finally:
        if 'client' in locals():
            client.close()


if __name__ == "__main__":
    delete_records()
    print("\nOperation completed.")
