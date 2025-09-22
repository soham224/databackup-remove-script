# Use the official Python 3.9 base image
FROM python:3.9-slim

# Set working directory inside the container
WORKDIR /tusker-data-backup

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgstreamer1.0-0 \
    libgstreamer-plugins-base1.0-0 \
    libgstreamer-plugins-bad1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy application files
COPY . .

# Define environment variables (to be set in ECS Task Definition)
# AWS credentials are fetched from the ECS IAM Role automatically

# Set the entry point
CMD ["python", "rpg-data-backup.py"]
