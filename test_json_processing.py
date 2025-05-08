#!/usr/bin/env python3
"""
Test script for JSON file processing.

This script tests the JSON file processing functionality.
"""

import os
import sys
import json
import requests
from pathlib import Path

# API configuration
API_URL = "http://localhost:8080"
API_KEY = "123e4567-e89b-12d3-a456-426614174000"

# Test files
TEST_FILES_DIR = Path("test_files/multi_batch")
if not TEST_FILES_DIR.exists():
    print(f"Test files directory not found: {TEST_FILES_DIR}")
    sys.exit(1)

def test_json_processing():
    """Test JSON file processing."""
    print("Testing JSON file processing...")
    
    # Get test files
    json_files = list(TEST_FILES_DIR.glob("*.json"))
    if not json_files:
        print("No JSON test files found")
        return
    
    for json_file in json_files:
        print(f"\nTesting with JSON file: {json_file}")
        
        # First, check if the JSON file is valid
        try:
            with open(json_file, "r") as f:
                json_data = json.load(f)
            print(f"JSON file is valid: {json_file}")
        except json.JSONDecodeError as e:
            print(f"Invalid JSON file: {json_file} - {str(e)}")
            continue
        
        # Send request to the API
        try:
            with open(json_file, "rb") as f:
                response = requests.post(
                    f"{API_URL}/parse",
                    files={"file": (json_file.name, f)},
                    params={
                        "api_key": API_KEY,
                        "source_type": "file"
                    }
                )
            
            print(f"Response status code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("Parsed JSON result:")
                print(json.dumps(result, indent=2))
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Error: {str(e)}")

def create_test_json_files():
    """Create test JSON files if they don't exist."""
    print("Creating test JSON files...")
    
    # Create test directory if it doesn't exist
    TEST_FILES_DIR.mkdir(exist_ok=True, parents=True)
    
    # Create a small JSON file
    small_json_path = TEST_FILES_DIR / "test_small.json"
    if not small_json_path.exists():
        small_json_data = {
            "name": "Test User",
            "email": "test@example.com",
            "age": 30,
            "address": {
                "street": "123 Main St",
                "city": "Test City",
                "state": "TS",
                "zip": "12345"
            },
            "phone_numbers": [
                {
                    "type": "home",
                    "number": "555-1234"
                },
                {
                    "type": "work",
                    "number": "555-5678"
                }
            ]
        }
        
        with open(small_json_path, "w") as f:
            json.dump(small_json_data, f, indent=2)
        
        print(f"Created small JSON file: {small_json_path}")
    
    # Create a medium JSON file
    medium_json_path = TEST_FILES_DIR / "test_medium.json"
    if not medium_json_path.exists():
        medium_json_data = {
            "users": [
                {
                    "id": 1,
                    "name": "User 1",
                    "email": "user1@example.com",
                    "active": True
                },
                {
                    "id": 2,
                    "name": "User 2",
                    "email": "user2@example.com",
                    "active": False
                },
                {
                    "id": 3,
                    "name": "User 3",
                    "email": "user3@example.com",
                    "active": True
                }
            ],
            "products": [
                {
                    "id": 101,
                    "name": "Product 1",
                    "price": 19.99,
                    "in_stock": True
                },
                {
                    "id": 102,
                    "name": "Product 2",
                    "price": 29.99,
                    "in_stock": False
                }
            ],
            "settings": {
                "theme": "dark",
                "notifications": True,
                "language": "en"
            }
        }
        
        with open(medium_json_path, "w") as f:
            json.dump(medium_json_data, f, indent=2)
        
        print(f"Created medium JSON file: {medium_json_path}")

if __name__ == "__main__":
    create_test_json_files()
    test_json_processing()
