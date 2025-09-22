# databackup-remove-script

Data backup and image annotation utility for extracting detection results from MongoDB, downloading corresponding images from AWS S3, drawing annotated bounding boxes with labels using OpenCV, and saving the outputs organized by use-case and date on local storage.

This README covers the project flow, repository structure, configuration, and instructions to run locally or via Docker.

## Key Features

- Query MongoDB for detection results within a date range or the previous calendar month by default.
- Filter detections for a configurable list of use-cases via `USECASES_LIST`.
- Download images from S3 based on URLs stored in MongoDB.
- Draw corner-style bounding boxes and labels using OpenCV.
- Save annotated images under `ROOT_FOLDER/<label>/<YYYY-MM-DD>/`.

## Repository Structure

```
.
├── Dockerfile
├── README.md
├── data-backup-download.py        # Main script entrypoint
├── dev_envs                       # Example environment variables (bash export format)
└── requirements.txt               # Python dependencies
```

## High-level Flow

1. Connect to MongoDB using provided credentials and select the collection.
2. Compute date range:
   - If `START_DATE` and `END_DATE` are set (DD-MM-YYYY), use that inclusive range.
   - Otherwise, automatically use the previous calendar month.
3. Query for records by `user_id`, visibility/active flags, and presence of detections.
4. For each record with relevant detections (as per `USECASES_LIST`):
   - Resolve S3 key from `image_url`, download the image from `AWS_BUCKET`.
   - Draw labeled corner boxes for each matching detection.
   - Save the annotated image under `ROOT_FOLDER/<label>/<YYYY-MM-DD>/` using the original image filename.

## Requirements

- Python 3.9+
- System libraries (installed in Dockerfile): `gcc`, `libgl1-mesa-glx`, `libglib2.0-0`, `gstreamer` libs for OpenCV.
- AWS credentials with read access to the S3 bucket (if running outside AWS with an instance role). Typically provided via environment variables or IAM Role.

Python dependencies are pinned in `requirements.txt` and include: `boto3`, `opencv-python`, `numpy`, `pymongo`, `requests`.

## Configuration (Environment Variables)

You can export variables in your shell or source the provided `dev_envs` file. Required variables:

- MongoDB
  - `MONGO_HOST` (e.g., `localhost`)
  - `MONGO_PORT` (e.g., `27017`)
  - `MONGO_USER` (username; can be empty for no-auth environments)
  - `MONGO_PASS` (password)
  - `MONGO_AUTH_DB_NAME` (auth DB name, e.g., `admin`)
  - `MONGO_DB_NAME` (e.g., `auto-serving-results`)
  - `MONGO_COLL_NAME` (e.g., `results`)

- AWS S3
  - `AWS_BUCKET` (name of the bucket containing the images)
  - Ensure AWS credentials are available (env vars, shared config, or instance role).

- Query and filtering
  - `USER_ID` (numeric or string user id to filter records)
  - `USECASES_LIST` (JSON array as a string of labels to include)
    - Example:
      ```bash
      export USECASES_LIST='["blockage_found", "no_mask", "fire"]'
      ```
  - Optional date range:
    - `START_DATE` in `DD-MM-YYYY`
    - `END_DATE` in `DD-MM-YYYY`
    - If omitted, previous calendar month is used.

- Output
  - `ROOT_FOLDER` (local root directory for saving annotated images; will be created)

- OneDrive (currently unused in the main script but reserved)
  - `ONEDRIVE_CLIENT_ID`, `ONEDRIVE_CLIENT_SECRET`, `ONEDRIVE_REFRESH_TOKEN`

See `dev_envs` for an example set of exports you can adapt. Do not commit real secrets.

## How to Run (Local)

1. Create and activate a virtual environment (recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   - Either export them manually, or source the example file and edit as needed:
     ```bash
     # Review and edit values in dev_envs first
     set -a
     source dev_envs
     set +a
     ```

4. Run the script:
   ```bash
   python data-backup-download.py
   ```

Outputs will be created under `ROOT_FOLDER/<label>/<YYYY-MM-DD>/` using the original image filename.

## How to Run (Docker)

1. Build the image:
   ```bash
   docker build -t databackup-remove-script:latest .
   ```

2. Run the container with environment variables. You can pass env vars individually or via an env file.

   - Option A: Pass env file (recommended; create `env.list` without `export`):
     ```bash
     # Convert dev_envs -> env.list (remove leading `export `)
     sed 's/^export \([^=]*\)=/\1=/g' dev_envs > env.list

     docker run --rm \
       --name databackup \
       --env-file env.list \
       -v "$PWD:/workspace" \
       -v "$PWD:${PWD}" \
       -w /tusker-data-backup \
       -v "$PWD:/tusker-data-backup" \
       databackup-remove-script:latest \
       python data-backup-download.py
     ```

   - Option B: Pass selected variables explicitly:
     ```bash
     docker run --rm \
       -e MONGO_HOST=localhost -e MONGO_PORT=27017 \
       -e MONGO_USER=... -e MONGO_PASS=... -e MONGO_AUTH_DB_NAME=admin \
       -e MONGO_DB_NAME=auto-serving-results -e MONGO_COLL_NAME=results \
       -e AWS_BUCKET=tusker-img-storage-rpg-79 \
       -e USER_ID=97 \
       -e USECASES_LIST='["no_mask","fire"]' \
       -e ROOT_FOLDER=/output \
       -e START_DATE=20-05-2025 -e END_DATE=25-05-2025 \
       -v "$PWD/output:/output" \
       databackup-remove-script:latest \
       python data-backup-download.py
     ```

Note: The current `Dockerfile` uses `CMD ["python", "rpg-data-backup.py"]` which does not exist in this repository. Either:

- Update the Dockerfile CMD to: `CMD ["python", "data-backup-download.py"]`, or
- Override the command when running the container as shown above.

## Data and Output Details

- Input source: MongoDB collection specified by `MONGO_DB_NAME` and `MONGO_COLL_NAME`.
- Filtering:
  - `user_id` equals `USER_ID`
  - `is_hide` is `False`
  - `status` is `True`
  - `result.detection` exists and is non-empty
  - `created_date` within selected range
- S3 download: The image URL is parsed to extract the key after `com/`, and the object is fetched from `AWS_BUCKET`.
- Annotation style: Corner lines and a label above the box using OpenCV; thickness is simulated for better readability.
- Output path: `${ROOT_FOLDER}/${label}/${YYYY-MM-DD}/${original_image_filename}`

## Troubleshooting

- Dockerfile CMD mismatch: See note above. Update or override when running.
- OpenCV write failures: Ensure the output directory is writable and that the path exists or can be created.
- AWS access issues: Verify that AWS credentials/roles allow `s3:GetObject` on the bucket/key.
- MongoDB connection/auth errors: Confirm host/port/firewall, and that user/password/auth DB are correct.
- Date parsing errors: `START_DATE` and `END_DATE` must be `DD-MM-YYYY`. If parsing fails, the script logs a message and falls back to previous month.

## Security Notes

- Do not commit real secrets. Use environment variables or secrets managers.
- Limit IAM permissions to least privilege (read-only access to the needed S3 bucket/prefixes).
- Consider using `.env` files locally with a tool like `direnv` or `python-dotenv` (commented in the script).

## Scheduling (Optional)

To run daily via cron (example at 2:30 AM):

```cron
30 2 * * * cd /path/to/databackup-remove-script && /usr/bin/env -i bash -c 'set -a; source dev_envs; set +a; /usr/bin/python3 data-backup-download.py' >> run.log 2>&1
```

## License

Proprietary/Confidential. If you intend to open-source or redistribute, add an appropriate license.