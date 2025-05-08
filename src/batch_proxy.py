#!/usr/bin/env python3
"""
Proxy module for batch processing.

This module forwards batch requests to the dedicated batch server.
"""

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
    """
    Forward batch request to the dedicated batch server.
    """
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
    """
    Forward batch status request to the dedicated batch server.
    """
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
