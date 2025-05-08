#!/usr/bin/env python3
"""
Standalone test script for JSON file processing.

This script tests the JSON file processing functionality without using the API.
"""

import os
import sys
import json
from pathlib import Path

# Test files
TEST_FILES_DIR = Path("test_files/multi_batch")
if not TEST_FILES_DIR.exists():
    print(f"Test files directory not found: {TEST_FILES_DIR}")
    sys.exit(1)

def process_json_file(file_path):
    """Process a JSON file and return structured elements."""
    try:
        # Read the file content
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        # Try to parse as JSON
        try:
            json_data = json.loads(file_content)
            
            # Convert JSON to elements
            elements = []
            if isinstance(json_data, dict):
                # Process dictionary
                for key, value in json_data.items():
                    if isinstance(value, (dict, list)):
                        elements.append({
                            "type": "JSONProperty",
                            "key": key,
                            "value": json.dumps(value, indent=2)
                        })
                    else:
                        elements.append({
                            "type": "JSONProperty",
                            "key": key,
                            "value": str(value)
                        })
                # Also add the full JSON
                elements.append({
                    "type": "JSONObject",
                    "text": json.dumps(json_data, indent=2)
                })
            elif isinstance(json_data, list):
                # Process list
                for i, item in enumerate(json_data[:10]):  # Limit to first 10 items
                    if isinstance(item, dict):
                        elements.append({
                            "type": "JSONItem",
                            "index": i,
                            "value": json.dumps(item, indent=2)
                        })
                    else:
                        elements.append({
                            "type": "JSONItem",
                            "index": i,
                            "value": str(item)
                        })
                # Also add the full JSON (limited to 100 items)
                elements.append({
                    "type": "JSONArray",
                    "text": json.dumps(json_data[:100] if len(json_data) > 100 else json_data, indent=2),
                    "total_items": len(json_data)
                })
            else:
                # Simple value
                elements = [{
                    "type": "JSONValue",
                    "text": json.dumps(json_data)
                }]
            
            print(f"Successfully parsed JSON file: {file_path}")
            return elements
        except json.JSONDecodeError as e:
            # If JSON parsing fails, treat as text
            print(f"Invalid JSON file, treating as text: {str(e)}")
            return [{
                "type": "Text",
                "text": file_content[:10000]  # Limit to first 10000 characters
            }]
    except Exception as e:
        print(f"Error processing JSON file: {str(e)}")
        return [{"type": "Error", "text": f"Error processing JSON file: {str(e)}"}]

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
        
        # Process the JSON file
        elements = process_json_file(json_file)
        
        # Print the result
        print("Processed JSON result:")
        print(json.dumps(elements, indent=2))

if __name__ == "__main__":
    test_json_processing()
