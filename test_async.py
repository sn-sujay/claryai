#!/usr/bin/env python3
"""
Test script for ClaryAI asynchronous processing.
"""

import os
import sys
import time
import json
import requests
import argparse

# API key for testing
API_KEY = "123e4567-e89b-12d3-a456-426614174000"

def parse_document(file_path, async_processing=False):
    """Parse document using ClaryAI API."""
    url = "http://localhost:8080/parse"
    
    # Prepare file
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f)}
        
        # Prepare parameters
        params = {
            "api_key": API_KEY,
            "async_processing": "true" if async_processing else "false"
        }
        
        # Send request
        response = requests.post(url, files=files, params=params)
        
        # Check response
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None

def check_status(task_id):
    """Check task status."""
    url = f"http://localhost:8080/status/{task_id}"
    
    # Prepare parameters
    params = {
        "api_key": API_KEY,
        "include_result": "true"
    }
    
    # Send request
    response = requests.get(url, params=params)
    
    # Check response
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test ClaryAI asynchronous processing.")
    parser.add_argument("file", help="File to parse")
    parser.add_argument("--async", dest="async_processing", action="store_true", help="Use asynchronous processing")
    args = parser.parse_args()
    
    # Check if file exists
    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}")
        return 1
    
    # Parse document
    print(f"Parsing document: {args.file}")
    print(f"Async processing: {args.async_processing}")
    
    result = parse_document(args.file, args.async_processing)
    if not result:
        return 1
    
    # If synchronous processing, print result
    if not args.async_processing:
        print(json.dumps(result, indent=2))
        return 0
    
    # If asynchronous processing, check status
    task_id = result.get("task_id")
    if not task_id:
        print("Error: No task ID returned")
        return 1
    
    print(f"Task ID: {task_id}")
    print("Checking status...")
    
    # Poll for status
    max_attempts = 30
    for i in range(max_attempts):
        status_result = check_status(task_id)
        if not status_result:
            return 1
        
        status = status_result.get("status")
        print(f"Status: {status}")
        
        if status == "completed":
            # Print result if available
            if "result" in status_result:
                print("Result:")
                print(json.dumps(status_result["result"], indent=2))
            else:
                print("Result not available")
            return 0
        elif status == "failed":
            print("Task failed")
            return 1
        
        # Wait before checking again
        time.sleep(1)
    
    print(f"Timeout after {max_attempts} attempts")
    return 1

if __name__ == "__main__":
    sys.exit(main())
