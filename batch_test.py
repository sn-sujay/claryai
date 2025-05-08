#!/usr/bin/env python3
"""
Batch processing test script for ClaryAI API.

This script implements a simple batch processing endpoint that can be used to test
multi-batch processing functionality.

Usage:
    python batch_test.py
"""

import os
import sys
import json
import uuid
import tempfile
import logging
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("claryai.batch_test")

# Initialize FastAPI app
app = FastAPI(
    title="ClaryAI Batch Test",
    description="A simple batch processing endpoint for ClaryAI",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for tasks and batches
tasks = {}
batches = {}

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "ClaryAI Batch Test",
        "description": "A simple batch processing endpoint for ClaryAI",
        "version": "0.1.0",
        "endpoints": ["/batch"]
    }

@app.post("/batch")
async def batch_process_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(None),
    source_type: str = "file",
    chunk_strategy: str = "paragraph",
    async_processing: bool = False,
    max_concurrent: int = 5,
    api_key: str = None
):
    """
    Process multiple documents in a batch.

    - **files**: List of uploaded files
    - **source_type**: Type of source (file, sql, api, web, cloud)
    - **chunk_strategy**: Chunking strategy (sentence, paragraph, fixed)
    - **async_processing**: Whether to process documents asynchronously
    - **max_concurrent**: Maximum number of concurrent tasks
    - **api_key**: API key for authentication
    """
    # Validate input
    if not files:
        raise HTTPException(status_code=400, detail="Files are required")

    # Generate batch ID
    batch_id = str(uuid.uuid4())

    # Process files
    task_ids = []

    # Insert batch record
    batches[batch_id] = {
        "status": "processing",
        "api_key": api_key,
        "total_tasks": len(files),
        "completed_tasks": 0
    }

    for file in files:
        task_id = str(uuid.uuid4())
        task_ids.append(task_id)

        # Insert task record
        tasks[task_id] = {
            "status": "queued",
            "api_key": api_key,
            "batch_id": batch_id,
            "file_name": file.filename
        }

        # Process the file in the background
        background_tasks.add_task(
            process_document, task_id, file, batch_id
        )

    return {
        "batch_id": batch_id,
        "status": "processing",
        "total_tasks": len(task_ids),
        "task_ids": task_ids
    }

@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """
    Check status of a task.

    - **task_id**: Task ID
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "status": tasks[task_id]["status"],
        "file_name": tasks[task_id]["file_name"]
    }

@app.get("/status/batch/{batch_id}")
async def get_batch_status(batch_id: str):
    """
    Check status of a batch processing job.

    - **batch_id**: Batch ID
    """
    if batch_id not in batches:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Get all tasks in this batch
    batch_tasks = []
    for task_id, task in tasks.items():
        if task.get("batch_id") == batch_id:
            batch_tasks.append({
                "task_id": task_id,
                "status": task["status"],
                "file_name": task["file_name"]
            })

    return {
        "batch_id": batch_id,
        "status": batches[batch_id]["status"],
        "total_tasks": batches[batch_id]["total_tasks"],
        "completed_tasks": batches[batch_id]["completed_tasks"],
        "progress_percentage": (batches[batch_id]["completed_tasks"] / batches[batch_id]["total_tasks"] * 100) 
            if batches[batch_id]["total_tasks"] > 0 else 0,
        "tasks": batch_tasks
    }

async def process_document(task_id: str, file: UploadFile, batch_id: str):
    """Process a document asynchronously"""
    try:
        # Update task status to processing
        tasks[task_id]["status"] = "processing"

        # Simulate processing
        import time
        time.sleep(2)  # Simulate processing time

        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Simulate parsing
        elements = [{"type": "Text", "text": f"Processed content of {file.filename}"}]

        # Clean up
        os.unlink(tmp_path)

        # Update task status to completed
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["result"] = elements

        # Update batch status
        batches[batch_id]["completed_tasks"] += 1
        if batches[batch_id]["completed_tasks"] == batches[batch_id]["total_tasks"]:
            batches[batch_id]["status"] = "completed"

        logger.info(f"Task {task_id} completed successfully")
    except Exception as e:
        logger.error(f"Task {task_id} failed: {str(e)}")
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8082)
