#!/usr/bin/env python3
"""
Test script for the batch endpoint.

This script tests the batch endpoint by sending multiple files to the API.
"""

import os
import sys
import json
import requests
from pathlib import Path

# API configuration
API_URL = "http://localhost:8082"  # Use the batch test server
API_KEY = "123e4567-e89b-12d3-a456-426614174000"

# Test files
TEST_FILES_DIR = Path("test_files/multi_batch")
if not TEST_FILES_DIR.exists():
    print(f"Test files directory not found: {TEST_FILES_DIR}")
    sys.exit(1)

def test_batch_endpoint():
    """Test the batch endpoint with multiple files."""
    print("Testing batch endpoint...")

    # Get test files
    test_files = list(TEST_FILES_DIR.glob("*.txt"))[:2]  # Use first 2 text files
    if not test_files:
        print("No test files found")
        return

    print(f"Using test files: {[f.name for f in test_files]}")

    # Prepare files for upload
    files = []
    for file_path in test_files:
        with open(file_path, "rb") as f:
            files.append(("files", (file_path.name, f.read())))

    # Send request
    try:
        response = requests.post(
            f"{API_URL}/batch",
            files=files,
            params={
                "api_key": API_KEY,
                "source_type": "file",
                "async_processing": "true",
                "max_concurrent": "2"
            }
        )

        print(f"Response status code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"Batch ID: {result.get('batch_id')}")
            print(f"Task IDs: {result.get('task_ids')}")

            # Check batch status
            batch_id = result.get('batch_id')
            if batch_id:
                check_batch_status(batch_id)
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {str(e)}")

def check_batch_status(batch_id):
    """Check the status of a batch."""
    print(f"Checking status of batch {batch_id}...")

    try:
        response = requests.get(
            f"{API_URL}/status/batch/{batch_id}",
            params={"api_key": API_KEY}
        )

        print(f"Response status code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"Batch status: {result.get('status')}")
            print(f"Progress: {result.get('completed_tasks')}/{result.get('total_tasks')} ({result.get('progress_percentage')}%)")
            print(f"Tasks: {result.get('tasks')}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_batch_endpoint()
