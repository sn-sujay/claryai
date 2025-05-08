#!/usr/bin/env python3
"""
Comprehensive test script for all improvements.

This script tests all the improvements we've made to the ClaryAI system.
"""

import os
import sys
import json
import requests
from pathlib import Path

# Add src directory to path
sys.path.append('src')

# Import improved table parser
try:
    from table_parser_improved import TableTransformer
except ImportError:
    try:
        from src.table_parser_improved import TableTransformer
    except ImportError:
        print("Error: Could not import TableTransformer from table_parser_improved")
        sys.exit(1)

# API configuration
API_URL = "http://localhost:8080"
API_KEY = "123e4567-e89b-12d3-a456-426614174000"

# Test files
TEST_FILES_DIR = Path("test_files")
if not TEST_FILES_DIR.exists():
    print(f"Test files directory not found: {TEST_FILES_DIR}")
    sys.exit(1)

def test_table_parsing():
    """Test the improved table parser."""
    print("\n=== Testing Table Parsing ===")
    
    # Create TableTransformer instance
    table_transformer = TableTransformer()
    
    # Test with sample PO file
    sample_po_path = TEST_FILES_DIR / "sample_po.txt"
    if sample_po_path.exists():
        print(f"\nTesting with sample PO file: {sample_po_path}")
        with open(sample_po_path, "r") as f:
            content = f.read()
            
        # Find the table in the content
        table_text = ""
        capture = False
        for line in content.split('\n'):
            if "Item" in line and "Quantity" in line and "Unit Price" in line:
                table_text = line + "\n"
                capture = True
                continue
            
            if capture and line.strip():
                table_text += line + "\n"
                
            if capture and "Total:" in line:
                table_text += line + "\n"
                break
                
        if table_text:
            # Parse the table
            result = table_transformer.parse_text_table(table_text)
            print("\nParsed table result:")
            print(json.dumps(result, indent=2))
        else:
            print("No table found in sample PO file")
    
    # Test with manually created table
    print("\nTesting with manually created table")
    manual_table = """
    Item                  Quantity    Unit Price    Total
    --------------------------------------------------------
    Widget A              10          $25.00        $250.00
    Widget B              5           $30.00        $150.00
    Service Package       1           $500.00       $500.00
    --------------------------------------------------------
    Subtotal:     $900.00
    Tax (10%):    $90.00
    Total:        $990.00
    """
    
    result = table_transformer.parse_text_table(manual_table)
    print("\nParsed table result:")
    print(json.dumps(result, indent=2))

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
    print("\n=== Testing JSON Processing ===")
    
    # Get test files
    json_files = list(Path("test_files/multi_batch").glob("*.json"))
    if not json_files:
        print("No JSON test files found")
        return
    
    for json_file in json_files[:1]:  # Test only the first JSON file
        print(f"\nTesting with JSON file: {json_file}")
        
        # Process the JSON file
        elements = process_json_file(json_file)
        
        # Print the result
        print("Processed JSON result:")
        print(json.dumps(elements[:2], indent=2))  # Print only the first 2 elements
        print(f"Total elements: {len(elements)}")

def test_batch_processing():
    """Test batch processing."""
    print("\n=== Testing Batch Processing ===")
    
    # Get test files
    test_files = list(Path("test_files/multi_batch").glob("*.txt"))[:2]  # Use first 2 text files
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

def run_all_tests():
    """Run all tests."""
    print("Running all tests...")
    
    # Test table parsing
    test_table_parsing()
    
    # Test JSON processing
    test_json_processing()
    
    # Test batch processing
    test_batch_processing()
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    run_all_tests()
