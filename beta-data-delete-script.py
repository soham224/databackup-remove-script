import pymongo
import os
import json
from datetime import datetime, timedelta
from typing import List


def _parse_date(date_str: str) -> datetime:
    """Parse a date string in format DD-MM-YYYY to a datetime at 00:00:00.

    Raises a ValueError if parsing fails.
    """
    return datetime.strptime(date_str, "%d-%m-%Y")


def _end_of_day(dt: datetime) -> datetime:
    """Return the last microsecond of the day for a given datetime."""
    return dt + timedelta(days=1) - timedelta(microseconds=1)

def main() -> None:
    """Delete MongoDB documents for a user within a date range, with progress.

    Configuration is read from environment variables (source dev_envs beforehand):
      - MONGO_HOST, MONGO_PORT, MONGO_DB_NAME, MONGO_COLL_NAME
      - MONGO_USER, MONGO_PASS, MONGO_AUTH_DB_NAME (optional)
      - USER_ID
      - START_DATE, END_DATE (format: DD-MM-YYYY)
      - USECASES_LIST (JSON array string of labels to filter on)

    The script prints:
      - total records matched in the date range and criteria
      - total records deleted
    """
    # ----- Load environment variables -----
    try:
        host = os.environ["MONGO_HOST"]
        port = int(os.environ["MONGO_PORT"])  # may raise ValueError/KeyError
        db_name = os.environ["MONGO_DB_NAME"]
        coll_name = os.environ["MONGO_COLL_NAME"]

        user_id = os.environ["USER_ID"]

        start_date_str = os.getenv("START_DATE")
        end_date_str = os.getenv("END_DATE")
        usecases_raw = os.getenv("USECASES_LIST")

        mongo_user = os.getenv("MONGO_USER") or None
        mongo_pass = os.getenv("MONGO_PASS") or None
        mongo_auth_db = os.getenv("MONGO_AUTH_DB_NAME") or None
    except KeyError as ke:
        raise SystemExit(f"Missing required environment variable: {ke}")
    except ValueError as ve:
        raise SystemExit(f"Invalid environment variable value: {ve}")

    if not start_date_str or not end_date_str:
        raise SystemExit(
            "START_DATE and END_DATE must be provided in environment (format DD-MM-YYYY)."
        )
    if not usecases_raw:
        raise SystemExit(
            "USECASES_LIST must be provided in environment as a JSON array string, e.g., ['no_gloves','no_hardhat']."
        )
    try:
        usecases_list = json.loads(usecases_raw)
        if not isinstance(usecases_list, list) or not all(isinstance(x, str) for x in usecases_list):
            raise ValueError("USECASES_LIST must be a JSON array of strings.")
    except Exception as e:
        raise SystemExit(f"Failed to parse USECASES_LIST: {e}")

    # ----- Parse dates -----
    try:
        start_dt = _parse_date(start_date_str)
        end_dt = _end_of_day(_parse_date(end_date_str))
    except ValueError as ve:
        raise SystemExit(f"Failed to parse START_DATE/END_DATE: {ve}")

    # ----- Connect to MongoDB -----
    try:
        client_kwargs = {"host": host, "port": port}
        # Use credentials only if provided (to support both auth/no-auth deployments)
        if mongo_user or mongo_pass or mongo_auth_db:
            client_kwargs.update(
                {
                    "username": mongo_user,
                    "password": mongo_pass,
                    "authSource": mongo_auth_db,
                }
            )
        client = pymongo.MongoClient(**client_kwargs)
        db = client[db_name]
        collection = db[coll_name]
    except Exception as e:
        raise SystemExit(f"Failed to connect to MongoDB: {e}")

    # ----- Build query -----
    # Only delete documents whose result.detection contains at least one label in USECASES_LIST
    # Using $elemMatch to match objects within the detection array: {label: {$in: usecases_list}}
    query = {
        "user_id": user_id,
        "is_hide": False,
        "status": True,
        "created_date": {"$gte": start_dt, "$lte": end_dt},
        "result.detection": {"$elemMatch": {"label": {"$in": usecases_list}}},
    }

    # ----- Count matching records -----
    try:
        total_to_delete = collection.count_documents(query)
    except Exception as e:
        raise SystemExit(f"Failed to count documents: {e}")

    print(f"Matching records for deletion: {total_to_delete}")
    if total_to_delete == 0:
        print("No records found in the specified date range. Nothing to delete.")
        return

    # ----- Simple delete in a single operation -----
    try:
        result = collection.delete_many(query)
        print(f"Total records deleted: {result.deleted_count}")
    except Exception as e:
        raise SystemExit(f"Error while deleting documents: {e}")


if __name__ == "__main__":
    main()