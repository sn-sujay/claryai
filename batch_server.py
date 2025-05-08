#!/usr/bin/env python3
"""
Dedicated server for the batch endpoint.

This script creates a dedicated FastAPI server for the batch endpoint.
"""

import os
import sys
import uuid
import json
import logging
import sqlite3
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("claryai.batch")

# Create app
app = FastAPI(
    title="ClaryAI Batch Server",
    description="Dedicated server for batch processing in ClaryAI",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up data directory and database path
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "claryai.db"

# Initialize SQLite for API key validation
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        key TEXT PRIMARY KEY,
        document_count INTEGER DEFAULT 0,
        reset_date TEXT
    )
    """)
    # Add a test API key for development
    cursor.execute("INSERT OR IGNORE INTO api_keys (key, document_count, reset_date) VALUES (?, ?, date('now'))",
                  ("123e4567-e89b-12d3-a456-426614174000", 0))

    # Create tasks table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        status TEXT,
        api_key TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Check if batch_id column exists in tasks table
    cursor.execute("PRAGMA table_info(tasks)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]

    # Add batch_id column if it doesn't exist
    if "batch_id" not in column_names:
        cursor.execute("ALTER TABLE tasks ADD COLUMN batch_id TEXT")

    # Create batches table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS batches (
        batch_id TEXT PRIMARY KEY,
        status TEXT,
        api_key TEXT,
        total_tasks INTEGER,
        completed_tasks INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

# Initialize database
init_db()

# Validate API key
def validate_api_key(api_key: str) -> bool:
    if not api_key:
        logger.warning("API key is None or empty")
        return False

    logger.info(f"Validating API key: {api_key}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT key FROM api_keys WHERE key = ?", (api_key,))
    result = cursor.fetchone()
    conn.close()

    logger.info(f"API key validation result: {result}")
    return result is not None

# Process document function (simplified for testing)
async def process_document(task_id: str, file_content: bytes, file_name: str,
                          api_key: str, batch_id: Optional[str] = None):
    """Process document asynchronously and update status"""
    try:
        # Update task status to processing
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE tasks SET status = ? WHERE task_id = ?", ("processing", task_id))
        conn.commit()

        # Simulate processing
        import time
        time.sleep(2)  # Simulate processing time

        # Update task status to completed
        cursor.execute("UPDATE tasks SET status = ? WHERE task_id = ?", ("completed", task_id))

        # If part of a batch, update batch status
        if batch_id:
            # Increment completed_tasks count
            cursor.execute("UPDATE batches SET completed_tasks = completed_tasks + 1 WHERE batch_id = ?", (batch_id,))

            # Check if all tasks in the batch are completed
            cursor.execute("SELECT total_tasks, completed_tasks FROM batches WHERE batch_id = ?", (batch_id,))
            batch_info = cursor.fetchone()

            if batch_info and batch_info[0] == batch_info[1]:
                # All tasks completed, update batch status
                cursor.execute("UPDATE batches SET status = ? WHERE batch_id = ?", ("completed", batch_id))
                logger.info(f"Batch {batch_id} completed")

        conn.commit()
        conn.close()

        logger.info(f"Document processed successfully: {file_name}")
        return {"status": "completed", "task_id": task_id, "file_name": file_name}
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")

        # Update task status to failed
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE tasks SET status = ? WHERE task_id = ?", ("failed", task_id))
        conn.commit()
        conn.close()

        return {"status": "failed", "task_id": task_id, "error": str(e)}

@app.post("/batch")
async def batch_process_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = None,
    source_type: str = "file",
    async_processing: bool = False,
    max_concurrent: int = 5,
    api_key: str = None
):
    """
    Process multiple documents in a batch.
    """
    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Validate input
    if source_type == "file" and not files:
        raise HTTPException(status_code=400, detail="Files are required for file source type")

    # Generate batch ID
    batch_id = str(uuid.uuid4())

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Process files
    task_ids = []

    if source_type == "file" and files:
        # Insert batch record
        cursor.execute(
            "INSERT INTO batches (batch_id, status, api_key, total_tasks) VALUES (?, ?, ?, ?)",
            (batch_id, "processing", api_key, len(files))
        )
        conn.commit()

        for file in files:
            task_id = str(uuid.uuid4())
            task_ids.append(task_id)

            # Insert task record
            cursor.execute(
                "INSERT INTO tasks (task_id, status, api_key, batch_id) VALUES (?, ?, ?, ?)",
                (task_id, "queued", api_key, batch_id)
            )

            # Read file content
            file_content = await file.read()

            # Process the file
            background_tasks.add_task(
                process_document, task_id, file_content, file.filename, api_key, batch_id
            )

    conn.commit()
    conn.close()

    return {
        "batch_id": batch_id,
        "status": "processing",
        "total_tasks": len(task_ids),
        "task_ids": task_ids
    }

@app.get("/status/batch/{batch_id}")
async def get_batch_status(
    batch_id: str,
    include_results: bool = False,
    api_key: str = None
):
    """
    Check status of a batch processing job.
    """
    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Check batch status in SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT status, total_tasks, completed_tasks FROM batches WHERE batch_id = ? AND api_key = ?",
                  (batch_id, api_key))
    batch_result = cursor.fetchone()

    if not batch_result:
        raise HTTPException(status_code=404, detail="Batch not found")

    batch_status, total_tasks, completed_tasks = batch_result

    # Get all tasks in this batch
    cursor.execute("SELECT task_id, status FROM tasks WHERE batch_id = ? AND api_key = ?",
                  (batch_id, api_key))
    task_results = cursor.fetchall()
    conn.close()

    tasks = [{"task_id": task_id, "status": status} for task_id, status in task_results]

    return {
        "batch_id": batch_id,
        "status": batch_status,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "progress_percentage": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
        "tasks": tasks
    }

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "ClaryAI Batch Server",
        "description": "Dedicated server for batch processing in ClaryAI",
        "version": "0.1.0",
        "endpoints": ["/batch", "/status/batch/{batch_id}"]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8086)
