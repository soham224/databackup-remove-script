import json
import os
from datetime import datetime, timedelta

import boto3
import cv2
import numpy as np
import requests
from pymongo import MongoClient

# from dotenv import load_dotenv
#
# load_dotenv()  # Load environment variables from .env

# -----------------------------
# Constants
# -----------------------------

usecases_list = json.loads(os.getenv("USECASES_LIST"))
START_DATE_STR = os.getenv("START_DATE")  # e.g., 20-05-2025
END_DATE_STR = os.getenv("END_DATE")  # e.g., 20-06-2025
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
    """Retrieve data from MongoDB for the specified date range if provided,
    otherwise for the previous calendar month.

    Date filtering uses the `created_date` field inclusive between start and end.
    START_DATE and END_DATE env vars are expected in format DD-MM-YYYY.
    """
    start_dt = None
    end_dt = None
    if START_DATE_STR and END_DATE_STR:
        try:
            start_dt = datetime.strptime(START_DATE_STR, "%d-%m-%Y")
            end_parsed = datetime.strptime(END_DATE_STR, "%d-%m-%Y")
            end_dt = end_parsed + timedelta(days=1) - timedelta(microseconds=1)
        except Exception as e:
            print(f"Failed to parse START_DATE/END_DATE: {e}. Falling back to previous month range.")

    if start_dt is None or end_dt is None:
        today = datetime.now()
        first_day_current_month = datetime(today.year, today.month, 1)
        last_day_prev_month = first_day_current_month - timedelta(days=1)
        start_dt = datetime(last_day_prev_month.year, last_day_prev_month.month, 1)
        end_dt = last_day_prev_month

    query = {
        "user_id": USER_ID,
        "is_hide": False,
        "status": True,
        "created_date": {"$gte": start_dt, "$lte": end_dt},
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
    # Validate image and coordinates
    if image is None:
        raise ValueError("Image is None; cannot draw annotations.")

    if not isinstance(coordinates, (list, tuple)) or len(coordinates) != 4:
        raise ValueError(f"Invalid coordinates for label '{label}': {coordinates}")

    try:
        x1, y1, x2, y2 = map(int, coordinates)
    except Exception:
        raise ValueError(f"Non-numeric coordinates for label '{label}': {coordinates}")
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
        if image is None:
            print(f"Failed to load image for URL: {image_url}. Skipping this file.")
            continue

        # Draw all selected detections on a copy; if any invalid annotation occurs, skip the file
        temp_image = image.copy()
        skip_image = False
        selected_detections = [d for d in detections if d.get("label") in usecases_list]

        for label_dict in selected_detections:
            try:
                temp_image = draw_annotations(temp_image, label_dict["label"], label_dict.get("location"))
            except Exception as e:
                print(f"Warning: {e}. Skipping this file: {image_name}")
                skip_image = True
                break

        if skip_image:
            continue

        created_at = record.get("created_date", datetime.now().isoformat())
        if isinstance(created_at, str):
            try:
                date_folder = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d")
            except Exception:
                # Fallback for alternate string formats
                try:
                    date_folder = datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime("%Y-%m-%d")
                except Exception:
                    date_folder = datetime.now().strftime("%Y-%m-%d")
        elif isinstance(created_at, datetime):
            date_folder = created_at.strftime("%Y-%m-%d")
        else:
            date_folder = datetime.now().strftime("%Y-%m-%d")

        # Use the first label's folder (consistent with prior behavior of saving under each label)
        # Since we now save once per image, choose a deterministic label (first selected)
        first_label = selected_detections[0]["label"] if selected_detections else "unknown"
        folder_path = f"{ROOT_FOLDER}/{first_label}/{date_folder}"

        save_image_local(temp_image, image_name, folder_path)


if __name__ == "__main__":
    main()
