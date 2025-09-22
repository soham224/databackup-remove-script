import json
import os
from datetime import datetime, timedelta, timezone

import boto3
import cv2
import numpy as np
import requests
from pymongo import MongoClient


def parse_datetime(datetime_str: str) -> datetime:
    """Parse a datetime string in format DD-MM-YYYY[ HH:MM:SS] to a timezone-aware UTC datetime object.
    If time is not provided, it defaults to 00:00:00 in the local timezone and converts to UTC.
    
    Raises a ValueError if parsing fails.
    """
    try:
        # Try to parse with time
        naive_dt = datetime.strptime(datetime_str, "%d-%m-%Y %H:%M:%S")
    except ValueError:
        # Fall back to date only (time will be 00:00:00)
        naive_dt = datetime.strptime(datetime_str, "%d-%m-%Y")
    
    # Get local timezone
    local_tz = datetime.now().astimezone().tzinfo
    
    # Make datetime timezone-aware using the local timezone
    local_dt = naive_dt.replace(tzinfo=local_tz)
    
    # Convert to UTC and make it timezone-naive (MongoDB stores as UTC without timezone)
    utc_dt = local_dt.astimezone(timezone.utc)
    return utc_dt.replace(tzinfo=None)

# from dotenv import load_dotenv
#
# load_dotenv()  # Load environment variables from .env

# -----------------------------
# Constants
# -----------------------------

usecases_list = json.loads(os.getenv("USECASES_LIST"))
# Try to get datetime first, fall back to date for backward compatibility
START_DATETIME_STR = os.getenv("START_DATETIME") or os.getenv("START_DATE")  # e.g., 20-05-2025 or 20-05-2025 14:30:00
END_DATETIME_STR = os.getenv("END_DATETIME") or os.getenv("END_DATE")  # e.g., 20-06-2025 or 20-06-2025 23:59:59
# -----------------------------
# Environment Variables
# -----------------------------

MONGO_HOST = os.environ["MONGO_HOST"]
MONGO_USER = os.environ["MONGO_USER"]
MONGO_PASS = os.environ["MONGO_PASS"]
MONGO_DB = os.environ["MONGO_DB_NAME"]
MONGO_PORT = os.environ["MONGO_PORT"]
MONGO_AUTH_DB_NAME = os.environ["MONGO_AUTH_DB_NAME"]
MONGO_COLL_NAME = os.environ["MONGO_COLL_NAME"]

AWS_BUCKET = os.getenv("AWS_BUCKET")

ONEDRIVE_CLIENT_ID = os.getenv("ONEDRIVE_CLIENT_ID")
ONEDRIVE_CLIENT_SECRET = os.getenv("ONEDRIVE_CLIENT_SECRET")
ONEDRIVE_REFRESH_TOKEN = os.getenv("ONEDRIVE_REFRESH_TOKEN")

ROOT_FOLDER = os.getenv("ROOT_FOLDER")
USER_ID = os.getenv("USER_ID")
# -----------------------------
# MongoDB Functions
# -----------------------------


def connect_mongodb():
    mongo_client = MongoClient(
        host=MONGO_HOST,
        port=int(MONGO_PORT),
        username=MONGO_USER,
        password=MONGO_PASS,
        authSource=MONGO_AUTH_DB_NAME,
    )

    db = mongo_client[MONGO_DB]
    return db[MONGO_COLL_NAME]


def get_data(collection):
    """Retrieve data from MongoDB for the specified datetime range if provided,
    otherwise for the previous calendar month.

    Date/Time filtering uses the `created_date` field inclusive between start and end.
    START_DATETIME/END_DATETIME (or START_DATE/END_DATE for backward compatibility) 
    env vars are expected in format DD-MM-YYYY or DD-MM-YYYY HH:MM:SS.
    Times are interpreted in local timezone and converted to UTC for the query.
    """
    # If no datetimes provided, default to previous calendar month in UTC
    if not START_DATETIME_STR or not END_DATETIME_STR:
        now_utc = datetime.utcnow()
        first_day_prev_month = (now_utc.replace(day=1) - timedelta(days=1)).replace(day=1)
        start_date = first_day_prev_month
        end_date = (now_utc.replace(day=1) - timedelta(microseconds=1))  # Last microsecond of previous month
    else:
        # Parse the provided datetime strings (converted to UTC in parse_datetime)
        start_date = parse_datetime(START_DATETIME_STR)
        end_date = parse_datetime(END_DATETIME_STR)
        
        # If end datetime is at midnight, adjust to include the entire end day
        if end_date.hour == 0 and end_date.minute == 0 and end_date.second == 0:
            end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    print(f"Querying MongoDB for dates between {start_date} and {end_date} (UTC)")

    query = {
        "user_id": USER_ID,
        "is_hide": False,
        "status": True,
        "created_date": {"$gte": start_date, "$lte": end_date},
        "result.detection": {"$exists": True, "$not": {"$size": 0}},
    }

    return list(collection.find(query))


# -----------------------------
# S3 Functions
# -----------------------------


def download_image_s3(image_url, bucket):
    """Download image from S3 and return it as an OpenCV image"""
    s3 = boto3.client("s3")
    image_key = image_url.split("com/")[-1]

    image_data = s3.get_object(Bucket=bucket, Key=image_key)["Body"].read()

    # Convert bytes to OpenCV image
    image_np = np.frombuffer(image_data, np.uint8)
    image = cv2.imdecode(image_np, cv2.IMREAD_COLOR)

    return image


def to_xywh(x1, y1, x2, y2):
    x = min(x1, x2)
    y = min(y1, y2)
    w = abs(x2 - x1)
    h = abs(y2 - y1)
    return x, y, w, h


# -----------------------------
# Image Annotation with OpenCV
# -----------------------------


def draw_annotations(image, label, coordinates):
    x1, y1, x2, y2 = map(int, coordinates)
    x, y, w, h = to_xywh(x1, y1, x2, y2)
    corner_length_h = w // 3
    corner_length_v = h // 3

    # Draw the corners
    cv2.line(image, (x, y), (x + corner_length_h, y), (0, 0, 255), 2)
    cv2.line(image, (x, y), (x, y + corner_length_v), (0, 0, 255), 2)

    cv2.line(image, (x + w, y), (x + w - corner_length_h, y), (0, 0, 255), 2)
    cv2.line(image, (x + w, y), (x + w, y + corner_length_v), (0, 0, 255), 2)

    cv2.line(image, (x, y + h), (x + corner_length_h, y + h), (0, 0, 255), 2)
    cv2.line(image, (x, y + h), (x, y + h - corner_length_v), (0, 0, 255), 2)

    cv2.line(image, (x + w, y + h), (x + w - corner_length_h, y + h), (0, 0, 255), 2)
    cv2.line(image, (x + w, y + h), (x + w, y + h - corner_length_v), (0, 0, 255), 2)

    # Draw label
    (label_width, label_height), baseline = cv2.getTextSize(
        label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1
    )
    label_bg_topleft = (x, y - label_height - baseline)
    label_bg_bottomright = (x + label_width, y)
    cv2.rectangle(image, label_bg_topleft, label_bg_bottomright, (0, 0, 0), -1)

    # cv2.putText(image, label, (x, y - baseline), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)
    # Simulating fractional thickness (1.5) for label text
    cv2.putText(
        image, label, (x, y - baseline), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1
    )  # Regular thickness
    cv2.putText(
        image,
        label,
        (x + 1, y - baseline),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 0, 255),
        1,
    )  # Slight offset
    cv2.putText(
        image,
        label,
        (x + 2, y - baseline),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 0, 255),
        1,
    )  # Slight offset
    return image


# -----------------------------
# Local Save Helper
# -----------------------------


def save_image_local(image, file_name, folder_path):
    os.makedirs(folder_path, exist_ok=True)
    output_path = os.path.join(folder_path, file_name)
    success = cv2.imwrite(output_path, image)
    if success:
        print(f"Saved {file_name} to {folder_path} successfully.")
    else:
        print(f"Failed to save {file_name} to {folder_path}.")


# -----------------------------
# Main Execution
# -----------------------------


def main():
    collection = connect_mongodb()
    records = get_data(collection)

    if not records:
        print("No records found.")
        return

    print(f"Records found: {len(records)}")
    try:
        matching_count = 0
        for r in records:
            detections = r.get("result", {}).get("detection", [])
            if any((det.get("label") in usecases_list) for det in detections):
                matching_count += 1
        print(f"Records with matching labels (USECASES_LIST): {matching_count}")
    except Exception as e:
        print(f"Failed to compute label-matching count: {e}")

    for record in records:
        image_url = record["image_url"]
        image_name = image_url.split("/")[-1]
        detections = record["result"]["detection"]

        if not any(det["label"] in usecases_list for det in detections):
            continue

        print(f"Downloading image from: {image_url}")

        image = download_image_s3(image_url, AWS_BUCKET)

        for label_dict in detections:
            if label_dict["label"] in usecases_list:
                annotated_image = draw_annotations(image, label_dict["label"], label_dict["location"])

                created_at = record.get("created_date", datetime.now().isoformat())
                if isinstance(created_at, str):
                    date_folder = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d")
                elif isinstance(created_at, datetime):
                    date_folder = created_at.strftime("%Y-%m-%d")
                else:
                    date_folder = datetime.now().strftime("%Y-%m-%d")

                folder_path = f"{ROOT_FOLDER}/{label_dict['label']}/{date_folder}"

                save_image_local(annotated_image, image_name, folder_path)


if __name__ == "__main__":
    main()
