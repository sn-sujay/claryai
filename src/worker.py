"""
Worker script for ClaryAI.
This script processes documents asynchronously from Redis queues.
"""

import os
import sys
import time
import tempfile
import logging
import sqlite3
import requests
from typing import Dict, Any
import pathlib
import pandas as pd
from redis_client import RedisClient
from table_parser import TableTransformer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("claryai.worker")

# Database path
DB_PATH = os.getenv("DB_PATH", "data/claryai.db")

# Initialize Redis client
redis_client = RedisClient()

# Initialize TableTransformer
table_transformer = TableTransformer()

def init_db():
    """Initialize database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create tasks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        status TEXT,
        api_key TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create API keys table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        api_key TEXT PRIMARY KEY,
        name TEXT,
        document_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialized")

def update_document_count(api_key: str):
    """
    Update document count for API key.

    Args:
        api_key: The API key to update the document count for.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Check if api_keys table exists and has the right schema
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_keys'")
        if not cursor.fetchone():
            # Create table if it doesn't exist
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                api_key TEXT PRIMARY KEY,
                name TEXT,
                document_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()
            logger.info("Created api_keys table")

        # Check if the API key exists in the table
        cursor.execute("SELECT api_key FROM api_keys WHERE api_key = ?", (api_key,))
        if not cursor.fetchone():
            # Insert new API key if it doesn't exist
            cursor.execute("INSERT INTO api_keys (api_key, name, document_count) VALUES (?, ?, ?)",
                          (api_key, "Default", 1))
            logger.info(f"Added new API key: {api_key}")
        else:
            # Update document count for existing API key
            cursor.execute("UPDATE api_keys SET document_count = document_count + 1 WHERE api_key = ?", (api_key,))

        conn.commit()
    except Exception as e:
        logger.error(f"Error updating document count: {str(e)}")
    finally:
        if conn:
            conn.close()

def update_task_status(task_id: str, status: str):
    """Update task status in database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = ? WHERE task_id = ?", (status, task_id))
    conn.commit()
    conn.close()

def process_document_task(task: Dict[str, Any]):
    """Process document task from queue."""
    task_id = task.get("task_id")
    source_type = task.get("source_type", "file")
    source_url = task.get("source_url")
    chunk_strategy = task.get("chunk_strategy", "paragraph")
    api_key = task.get("api_key")
    file_path = task.get("file_path")

    logger.info(f"Processing task {task_id} with details: {task}")

    try:
        # Update task status to processing
        update_task_status(task_id, "processing")

        # Process document based on source type
        if source_type == "file":
            if not file_path:
                raise ValueError(f"File path not provided for task {task_id}")

            if not os.path.exists(file_path):
                raise ValueError(f"File not found at path: {file_path}")

            # Check if file is readable and has content
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                raise ValueError(f"File is empty: {file_path}")

            logger.info(f"Processing file {file_path} ({file_size} bytes) for task {task_id}")
            result = process_file(file_path, chunk_strategy)
        elif source_type == "url":
            if not source_url:
                raise ValueError("URL not provided")

            logger.info(f"Processing URL {source_url} for task {task_id}")
            result = process_url(source_url, chunk_strategy)
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

        # Store result in Redis
        if redis_client.is_connected():
            success = redis_client.store_task_result(task_id, result)
            if success:
                logger.info(f"Task result stored in Redis for task_id: {task_id}")
            else:
                logger.error(f"Failed to store task result in Redis for task_id: {task_id}")
        else:
            logger.warning(f"Redis not connected, task result not stored for task_id: {task_id}")

        # Update task status to completed
        update_task_status(task_id, "completed")

        # Update document count for API key
        if api_key:
            update_document_count(api_key)
            logger.info(f"Document count updated for API key: {api_key}")

        # Clean up file if it was created for this task
        if file_path and os.path.exists(file_path) and file_path.startswith("data/uploads/"):
            try:
                os.remove(file_path)
                logger.info(f"Temporary file deleted: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {file_path}: {str(e)}")

        logger.info(f"Task {task_id} completed successfully")
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}", exc_info=True)
        update_task_status(task_id, "failed")

def process_file(file_path: str, chunk_strategy: str = None) -> Dict[str, Any]:
    """
    Process document from file.

    Args:
        file_path: Path to the file to process.
        chunk_strategy: Strategy for chunking the document (not used in this implementation).

    Returns:
        Dict containing the processed elements and status.
    """
    from unstructured.partition.auto import partition

    logger.info(f"Processing file: {file_path}")

    # Determine file extension
    file_ext = pathlib.Path(file_path).suffix.lower()

    # Process document based on file type
    if file_ext in ['.csv', '.xlsx', '.xls']:
        # Process tabular data
        if file_ext == '.csv':
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)

        # Transform table to structured format
        result = table_transformer.transform(df)
    else:
        # Process document with unstructured
        # Note: chunk_strategy parameter is reserved for future implementation
        # of document chunking strategies
        elements = partition(file_path)

        # Convert elements to serializable format
        result = {"elements": [], "status": "parsed"}

        for element in elements:
            element_type = type(element).__name__
            element_text = str(element)

            # Handle table elements
            if element_type == "Table":
                try:
                    # Extract table data
                    headers = element.metadata.header_text if hasattr(element.metadata, "header_text") else []
                    data = []

                    # Add table element
                    result["elements"].append({
                        "type": "Table",
                        "data": data,
                        "headers": headers,
                        "error": "No data found in table"
                    })
                except Exception as e:
                    logger.error(f"Error processing table: {str(e)}")
                    result["elements"].append({
                        "type": "Table",
                        "data": [],
                        "headers": [],
                        "error": str(e)
                    })
            else:
                # Add text element
                result["elements"].append({
                    "type": element_type,
                    "text": element_text
                })

    return result

def process_url(url: str, chunk_strategy: str = "paragraph") -> Dict[str, Any]:
    """Process document from URL."""
    logger.info(f"Processing URL: {url}")

    # Fetch URL content
    response = requests.get(url)
    response.raise_for_status()

    # Create temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as temp_file:
        temp_file.write(response.content)
        temp_file_path = temp_file.name

    try:
        # Process HTML file
        result = process_file(temp_file_path, chunk_strategy)
        return result
    finally:
        # Clean up temporary file
        os.unlink(temp_file_path)

def main():
    """Main worker function."""
    logger.info("Starting ClaryAI worker")

    # Initialize database
    init_db()

    # Check Redis connection
    if not redis_client.is_connected():
        logger.error("Failed to connect to Redis. Worker cannot start.")
        return

    logger.info("Worker started. Waiting for tasks...")

    # Process tasks from queue
    while True:
        try:
            # Get task from queue
            task = redis_client.get_from_queue("document_processing")

            if task:
                logger.info(f"Got task from queue: {task.get('task_id')}")
                process_document_task(task)
            else:
                # Sleep if no tasks
                time.sleep(1)
        except Exception as e:
            logger.error(f"Error in worker main loop: {str(e)}")
            time.sleep(5)

if __name__ == "__main__":
    main()
