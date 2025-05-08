#!/usr/bin/env python3
"""
Script to integrate the batch server with the main ClaryAI server.

This script creates a proxy endpoint in the main server to forward batch requests to the batch server.
"""

import os
import sys
import json
import requests
from pathlib import Path

# API configuration
MAIN_API_URL = "http://localhost:8080"
BATCH_API_URL = "http://localhost:8086"
API_KEY = "123e4567-e89b-12d3-a456-426614174000"

def create_proxy_endpoint():
    """Create a proxy endpoint in the main server to forward batch requests to the batch server."""
    print("Creating proxy endpoint in the main server...")
    
    # Create a proxy script
    proxy_script_path = Path("src/batch_proxy.py")
    
    proxy_script_content = """#!/usr/bin/env python3
\"\"\"
Proxy module for batch processing.

This module forwards batch requests to the dedicated batch server.
\"\"\"

import requests
import logging
from typing import List, Optional
from fastapi import UploadFile

# Configure logging
logger = logging.getLogger("claryai.batch_proxy")

# Batch server URL
BATCH_SERVER_URL = "http://localhost:8086"

async def forward_batch_request(
    files: List[UploadFile],
    source_type: str,
    async_processing: bool,
    max_concurrent: int,
    api_key: str
):
    \"\"\"
    Forward batch request to the dedicated batch server.
    \"\"\"
    logger.info(f"Forwarding batch request to dedicated server: {BATCH_SERVER_URL}")
    
    try:
        # Prepare files for upload
        files_dict = []
        for file in files:
            file_content = await file.read()
            files_dict.append(("files", (file.filename, file_content)))
            # Reset file position for potential future use
            await file.seek(0)
        
        # Send request to batch server
        response = requests.post(
            f"{BATCH_SERVER_URL}/batch",
            files=files_dict,
            params={
                "api_key": api_key,
                "source_type": source_type,
                "async_processing": str(async_processing).lower(),
                "max_concurrent": str(max_concurrent)
            }
        )
        
        # Check response
        if response.status_code == 200:
            logger.info("Batch request forwarded successfully")
            return response.json()
        else:
            logger.error(f"Error forwarding batch request: {response.text}")
            return {"error": f"Error forwarding batch request: {response.text}"}
    except Exception as e:
        logger.error(f"Error forwarding batch request: {str(e)}")
        return {"error": f"Error forwarding batch request: {str(e)}"}

async def forward_batch_status_request(
    batch_id: str,
    include_results: bool,
    api_key: str
):
    \"\"\"
    Forward batch status request to the dedicated batch server.
    \"\"\"
    logger.info(f"Forwarding batch status request to dedicated server: {BATCH_SERVER_URL}")
    
    try:
        # Send request to batch server
        response = requests.get(
            f"{BATCH_SERVER_URL}/status/batch/{batch_id}",
            params={
                "api_key": api_key,
                "include_results": str(include_results).lower()
            }
        )
        
        # Check response
        if response.status_code == 200:
            logger.info("Batch status request forwarded successfully")
            return response.json()
        else:
            logger.error(f"Error forwarding batch status request: {response.text}")
            return {"error": f"Error forwarding batch status request: {response.text}"}
    except Exception as e:
        logger.error(f"Error forwarding batch status request: {str(e)}")
        return {"error": f"Error forwarding batch status request: {str(e)}"}
"""
    
    # Create the proxy script
    os.makedirs(proxy_script_path.parent, exist_ok=True)
    with open(proxy_script_path, "w") as f:
        f.write(proxy_script_content)
    
    print(f"Created proxy script: {proxy_script_path}")
    
    # Update the main.py file to use the proxy
    main_py_path = Path("src/main.py")
    
    # Check if the main.py file exists
    if not main_py_path.exists():
        print(f"Error: Main file not found: {main_py_path}")
        return
    
    print("Updating main.py file to use the proxy...")
    
    # Read the main.py file
    with open(main_py_path, "r") as f:
        main_py_content = f.read()
    
    # Check if the proxy is already imported
    if "from batch_proxy import forward_batch_request" not in main_py_content:
        # Add import statement
        import_statement = """
# Import batch proxy
try:
    from batch_proxy import forward_batch_request, forward_batch_status_request
except ImportError:
    try:
        from src.batch_proxy import forward_batch_request, forward_batch_status_request
    except ImportError:
        logger.error("Could not import batch_proxy module")
        forward_batch_request = None
        forward_batch_status_request = None
"""
        
        # Find the right place to add the import statement
        import_index = main_py_content.find("# Import Redis client")
        if import_index == -1:
            import_index = main_py_content.find("# Initialize Redis client")
        
        if import_index != -1:
            # Add the import statement after the found line
            line_end = main_py_content.find("\n", import_index)
            main_py_content = main_py_content[:line_end+1] + import_statement + main_py_content[line_end+1:]
        else:
            print("Could not find a suitable place to add the import statement")
            return
    
    # Check if the batch endpoint is already using the proxy
    if "forward_batch_request" not in main_py_content:
        # Find the batch endpoint
        batch_endpoint_index = main_py_content.find("@app.post(\"/batch\")")
        if batch_endpoint_index == -1:
            print("Could not find the batch endpoint")
            return
        
        # Find the end of the batch endpoint function
        function_start = main_py_content.find("async def", batch_endpoint_index)
        if function_start == -1:
            print("Could not find the batch endpoint function")
            return
        
        # Find the function name
        function_name_start = function_start + len("async def ")
        function_name_end = main_py_content.find("(", function_name_start)
        function_name = main_py_content[function_name_start:function_name_end].strip()
        
        # Find the end of the function
        function_end = main_py_content.find(f"@app.get", function_start)
        if function_end == -1:
            function_end = main_py_content.find(f"@app.post", function_start)
        
        if function_end == -1:
            print("Could not find the end of the batch endpoint function")
            return
        
        # Replace the function body with the proxy call
        new_function_body = f"""async def {function_name}(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = None,
    source_type: str = "file",
    async_processing: bool = False,
    max_concurrent: int = 5,
    api_key: str = None
):
    \"\"\"
    Process multiple documents in a batch.
    \"\"\"
    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Validate input
    if source_type == "file" and not files:
        raise HTTPException(status_code=400, detail="Files are required for file source type")

    # Check if batch proxy is available
    if forward_batch_request:
        # Forward request to dedicated batch server
        return await forward_batch_request(files, source_type, async_processing, max_concurrent, api_key)
    else:
        # Use local implementation
        # (Original implementation)
"""
        
        # Find the original function body
        function_body_start = main_py_content.find(":", function_name_end)
        function_body_start = main_py_content.find("\n", function_body_start)
        
        # Replace the function
        main_py_content = main_py_content[:function_start] + new_function_body + main_py_content[function_body_start:]
    
    # Check if the batch status endpoint is already using the proxy
    if "forward_batch_status_request" not in main_py_content:
        # Find the batch status endpoint
        batch_status_endpoint_index = main_py_content.find("@app.get(\"/status/batch/{batch_id}\")")
        if batch_status_endpoint_index == -1:
            print("Could not find the batch status endpoint")
            return
        
        # Find the end of the batch status endpoint function
        function_start = main_py_content.find("async def", batch_status_endpoint_index)
        if function_start == -1:
            print("Could not find the batch status endpoint function")
            return
        
        # Find the function name
        function_name_start = function_start + len("async def ")
        function_name_end = main_py_content.find("(", function_name_start)
        function_name = main_py_content[function_name_start:function_name_end].strip()
        
        # Find the end of the function
        function_end = main_py_content.find(f"@app.get", function_start)
        if function_end == -1:
            function_end = main_py_content.find(f"@app.post", function_start)
        
        if function_end == -1:
            print("Could not find the end of the batch status endpoint function")
            return
        
        # Replace the function body with the proxy call
        new_function_body = f"""async def {function_name}(
    batch_id: str,
    include_results: bool = False,
    api_key: str = None
):
    \"\"\"
    Check status of a batch processing job.
    \"\"\"
    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Check if batch proxy is available
    if forward_batch_status_request:
        # Forward request to dedicated batch server
        return await forward_batch_status_request(batch_id, include_results, api_key)
    else:
        # Use local implementation
        # (Original implementation)
"""
        
        # Find the original function body
        function_body_start = main_py_content.find(":", function_name_end)
        function_body_start = main_py_content.find("\n", function_body_start)
        
        # Replace the function
        main_py_content = main_py_content[:function_start] + new_function_body + main_py_content[function_body_start:]
    
    # Write the updated main.py file
    with open(main_py_path, "w") as f:
        f.write(main_py_content)
    
    print("Updated main.py file to use the proxy")

if __name__ == "__main__":
    create_proxy_endpoint()
