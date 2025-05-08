#!/usr/bin/env python3
"""
Test script for the dedicated batch server.

This script tests the dedicated batch server for the batch endpoint.
"""

import os
import sys
import json
import requests
from pathlib import Path

# API configuration
API_URL = "http://localhost:8086"  # Dedicated batch server port
API_KEY = "123e4567-e89b-12d3-a456-426614174000"

def test_batch_server():
    """Test the dedicated batch server."""
    print("Testing dedicated batch server...")
    
    # Test root endpoint
    try:
        response = requests.get(f"{API_URL}/")
        
        print(f"Root endpoint response status code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("Available endpoints:")
            for endpoint in result.get("endpoints", []):
                print(f"  {endpoint}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {str(e)}")
        return
    
    # Get test files
    test_files_dir = Path("test_files/multi_batch")
    if not test_files_dir.exists():
        print(f"Test files directory not found: {test_files_dir}")
        return
    
    test_files = list(test_files_dir.glob("*.txt"))[:2]  # Use first 2 text files
    if not test_files:
        print("No test files found")
        return
    
    print(f"\nUsing test files: {[f.name for f in test_files]}")
    
    # Prepare files for upload
    files = []
    for file_path in test_files:
        with open(file_path, "rb") as f:
            files.append(("files", (file_path.name, f.read())))
    
    # Send request to batch endpoint
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
        
        print(f"Batch endpoint response status code: {response.status_code}")
        
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
    print(f"\nChecking status of batch {batch_id}...")
    
    try:
        response = requests.get(
            f"{API_URL}/status/batch/{batch_id}",
            params={"api_key": API_KEY}
        )
        
        print(f"Status endpoint response status code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Batch status: {result.get('status')}")
            print(f"Progress: {result.get('completed_tasks')}/{result.get('total_tasks')} ({result.get('progress_percentage')}%)")
            print(f"Tasks: {result.get('tasks')}")
            
            # If batch is still processing, check again after a delay
            if result.get('status') == "processing":
                import time
                print("Waiting 5 seconds...")
                time.sleep(5)
                check_batch_status(batch_id)
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_batch_server()
