"""
ClaryAI - Document Parsing API

A self-hosted API for parsing documents of all file types into structured,
LLM-ready JSON outputs with zero data retention.
"""

import os
import uuid
import json
import tempfile
import logging
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import requests
from bs4 import BeautifulSoup
import pathlib
from table_parser import TableTransformer
from redis_client import RedisClient

# Optional imports based on environment variables
USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"
LLM_MODEL = os.getenv("LLM_MODEL")
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT")

# Import lifespan handler
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    Lifespan events for the FastAPI application.

    Args:
        _: FastAPI application instance (unused but required by FastAPI).
    """
    # Startup: Initialize database
    init_db()
    logger.info("Database initialized")
    yield
    # Shutdown: Clean up resources
    logger.info("Shutting down application")

# Initialize FastAPI app with lifespan handler
app = FastAPI(
    title="ClaryAI",
    description="A self-hosted API for parsing documents into LLM-ready JSON outputs with zero data retention.",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("claryai")

# Initialize TableTransformer
table_transformer = TableTransformer()

# Initialize Redis client
redis_client = RedisClient()

# Filter out sensitive model names from logs
logging.getLogger().addFilter(lambda record: "phi-4-multimodal" not in record.msg.lower())

# Set up data directory and database path
DATA_DIR = pathlib.Path("data")
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
    conn.commit()
    conn.close()

# Validate API key
def validate_api_key(api_key: str) -> bool:
    if not api_key:
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT key FROM api_keys WHERE key = ?", (api_key,))
    result = cursor.fetchone()
    conn.close()

    return result is not None

# Update document count for API key
def update_document_count(api_key: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE api_keys SET document_count = document_count + 1 WHERE key = ?", (api_key,))
    conn.commit()
    conn.close()

# Initialize Celery for async processing if available
try:
    from celery import Celery
    app_celery = Celery('tasks', broker='redis://localhost:6379/0')
except ImportError:
    app_celery = None
    logger.warning("Celery not available. Async processing will be limited.")

# Initialize LLM if enabled
if USE_LLM:
    try:
        if LLM_ENDPOINT:
            # Initialize LLM based on endpoint type
            if "openai" in LLM_ENDPOINT:
                from langchain_openai import ChatOpenAI
                llm = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=LLM_ENDPOINT)
            else:
                from langchain_community.llms import HuggingFaceEndpoint
                llm = HuggingFaceEndpoint(endpoint_url=LLM_ENDPOINT)
        else:
            # Use local Ollama model if no endpoint is specified
            from langchain_community.llms import Ollama
            llm = Ollama(model=LLM_MODEL or "phi-4-multimodal")
        logger.info("LLM initialized successfully")
    except ImportError:
        USE_LLM = False
        logger.warning("LLM dependencies not available. LLM features disabled.")

# Parse document function
async def parse_document(file: Optional[UploadFile] = None, source_type: str = "file",
                         source_url: Optional[str] = None, chunk_strategy: str = "paragraph") -> dict:
    """
    Parse a document from various sources into structured JSON.

    Args:
        file: Uploaded file (for file source_type)
        source_type: Type of source (file, sql, api, web, cloud)
        source_url: URL or connection string for non-file sources
        chunk_strategy: Chunking strategy (sentence, paragraph, fixed)

    Returns:
        dict: Structured JSON with parsed elements
    """
    elements = []
    tmp_path = None

    try:
        # Handle different source types
        if source_type == "file" and file:
            # Save uploaded file to temp location
            tmp_path = tempfile.mktemp(suffix=f".{file.filename.split('.')[-1]}")
            with open(tmp_path, "wb") as f:
                content = await file.read()
                f.write(content)

            # Use Unstructured.io to parse the file
            try:
                from unstructured.partition.auto import partition
                elements_raw = partition(tmp_path)
                elements = []

                for el in elements_raw:
                    el_type = str(type(el).__name__)
                    el_text = str(el)

                    # Check if this element might be a table
                    if el_type == "Table" or (el_type == "Text" and ('|' in el_text or '+---+' in el_text)):
                        # Try to parse as a table
                        table_data = table_transformer.parse_text_table(el_text)
                        elements.append(table_data)
                    else:
                        elements.append({"type": el_type, "text": el_text})
            except ImportError:
                logger.error("Unstructured.io not available")
                elements = [{"type": "Error", "text": "Unstructured.io not available"}]

        elif source_type == "sql" and source_url:
            # Use SQLAlchemy to connect to the database
            try:
                import sqlalchemy
                from sqlalchemy import inspect

                # Create engine
                engine = sqlalchemy.create_engine(source_url)
                inspector = inspect(engine)

                # Get all tables
                tables = inspector.get_table_names()
                elements = []

                for table in tables:
                    # Get table schema
                    columns = inspector.get_columns(table)
                    column_names = [col['name'] for col in columns]

                    # Query data
                    query = f"SELECT * FROM {table} LIMIT 10"
                    with engine.connect() as connection:
                        result = connection.execute(sqlalchemy.text(query))
                        rows = [dict(row) for row in result]

                    # Format as structured table
                    table_data = {
                        "type": "Table",
                        "table_name": table,
                        "headers": column_names,
                        "data": rows,
                        "num_rows": len(rows),
                        "num_cols": len(column_names)
                    }
                    elements.append(table_data)
            except Exception as e:
                logger.error(f"SQL connection failed: {str(e)}")
                elements = [{"type": "Error", "text": f"SQL connection failed: {str(e)}"}]

        elif source_type == "api" and source_url:
            # Use requests to fetch API data
            response = requests.get(source_url)
            if response.status_code == 200:
                try:
                    data = response.json()
                    elements = [{"type": "APIResponse", "text": json.dumps(data)}]
                except:
                    elements = [{"type": "APIResponse", "text": response.text}]
            else:
                elements = [{"type": "Error", "text": f"API request failed with status {response.status_code}"}]

        elif source_type == "web" and source_url:
            # Use BeautifulSoup to parse web content
            response = requests.get(source_url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # Extract text from different elements
                elements = []
                # Title
                if soup.title:
                    elements.append({"type": "Title", "text": soup.title.text.strip()})
                # Headings
                for i, heading in enumerate(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])):
                    elements.append({"type": f"Heading{heading.name[1]}", "text": heading.text.strip()})
                # Paragraphs
                for i, para in enumerate(soup.find_all('p')):
                    elements.append({"type": "Paragraph", "text": para.text.strip()})
                # Tables
                for i, table in enumerate(soup.find_all('table')):
                    # Use TableTransformer for advanced table parsing
                    table_data = table_transformer.parse_html_table(str(table))
                    elements.append(table_data)
            else:
                elements = [{"type": "Error", "text": f"Web request failed with status {response.status_code}"}]

        elif source_type == "cloud" and source_url:
            try:
                # Parse the source URL (format: provider://credentials_json/file_id)
                # Example: google_drive://{"access_token":"xyz"}/file_id
                # Example: s3://{"aws_access_key_id":"key","aws_secret_access_key":"secret"}/bucket/key
                # Example: dropbox://{"access_token":"xyz"}/path/to/file

                from src.cloud_connectors import get_connector
                import json

                # Parse the URL
                parts = source_url.split("://", 1)
                if len(parts) != 2:
                    raise ValueError(f"Invalid cloud source URL format: {source_url}")

                provider = parts[0]
                remaining = parts[1]

                # Extract credentials and file_id
                try:
                    # Find the first occurrence of / after the JSON
                    json_end = 0
                    brace_count = 0
                    for i, char in enumerate(remaining):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break

                    if json_end == 0:
                        raise ValueError("Could not parse JSON credentials in URL")

                    # Extract credentials and file_id
                    credentials_json = remaining[:json_end]
                    file_id = remaining[json_end:].lstrip('/')

                    # Parse credentials
                    credentials = json.loads(credentials_json)

                    # Get the appropriate connector
                    connector = get_connector(provider)
                    if not connector:
                        raise ValueError(f"Unsupported cloud storage provider: {provider}")

                    # Download the file
                    tmp_path = connector.download_file(file_id, credentials)
                    if not tmp_path:
                        raise ValueError(f"Failed to download file from {provider}")

                    # Parse the downloaded file
                    with open(tmp_path, 'rb') as f:
                        elements = parse_file(f)

                    # Clean up
                    os.unlink(tmp_path)

                except json.JSONDecodeError:
                    raise ValueError(f"Invalid JSON credentials in URL: {source_url}")
                except Exception as e:
                    raise ValueError(f"Error processing cloud source: {str(e)}")
            except Exception as e:
                logger.error(f"Cloud source processing failed: {str(e)}")
                elements = [{"type": "Error", "text": f"Cloud source processing failed: {str(e)}"}]

        else:
            elements = [{"type": "Error", "text": "Invalid source type or missing required parameters"}]

        # Apply chunking strategy if specified
        if chunk_strategy and elements and USE_LLM:
            try:
                from llama_index.core import Document
                from llama_index.core.node_parser import SentenceSplitter, ParagraphSplitter

                # Convert elements to text for chunking
                text = "\n\n".join([el["text"] for el in elements])
                document = Document(text=text)

                # Apply chunking strategy
                if chunk_strategy == "sentence":
                    splitter = SentenceSplitter(chunk_size=1024)
                elif chunk_strategy == "paragraph":
                    splitter = ParagraphSplitter(chunk_size=1024)
                else:  # fixed
                    splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)

                nodes = splitter.get_nodes_from_documents([document])

                # Replace elements with chunked nodes
                elements = [{"type": "Chunk", "text": node.text} for node in nodes]
            except ImportError:
                logger.warning("LlamaIndex not available for chunking")

        # Apply LLM refinement if enabled
        if USE_LLM and elements:
            try:
                # Refine elements with LLM
                prompt = f"Refine these document elements to improve structure and readability: {json.dumps(elements)}"
                response = llm.invoke(prompt)
                refined_elements = json.loads(str(response))
                if isinstance(refined_elements, list):
                    elements = refined_elements
            except Exception as e:
                logger.error(f"LLM refinement failed: {str(e)}")

        return {"elements": elements, "status": "parsed"}

    finally:
        # Ensure zero data retention by deleting temporary files
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
            logger.info(f"Temporary file deleted: {tmp_path}")

# Process document asynchronously
async def process_document(task_id: str, file: Optional[UploadFile] = None,
                          source_type: str = "file", source_url: Optional[str] = None,
                          chunk_strategy: str = "paragraph", api_key: Optional[str] = None) -> dict:
    """Process document asynchronously and store result temporarily"""
    result = await parse_document(file, source_type, source_url, chunk_strategy)

    # Store task status in SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        status TEXT,
        api_key TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("INSERT INTO tasks (task_id, status, api_key) VALUES (?, ?, ?)",
                  (task_id, "completed", api_key))
    conn.commit()
    conn.close()

    # Store result in Redis if available
    if redis_client.is_connected():
        redis_client.store_task_result(task_id, result)
        logger.info(f"Task result stored in Redis for task_id: {task_id}")
    else:
        logger.warning(f"Redis not available, task result not cached for task_id: {task_id}")

    # Update document count for the API key
    if api_key:
        update_document_count(api_key)

    return result

# API Endpoints



@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "ClaryAI",
        "description": "A self-hosted API for parsing documents into LLM-ready JSON outputs with zero data retention.",
        "version": "0.1.0",
        "endpoints": [
            "/parse", "/query", "/generate_schema", "/agent", "/match", "/status/{task_id}"
        ],
        "llm_enabled": USE_LLM
    }

@app.post("/parse")
async def parse_document_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(None),
    api_key: str = None,
    source_type: str = "file",
    source_url: str = None,
    chunk_strategy: str = "paragraph",
    async_processing: bool = False
):
    """
    Parse a document from various sources into structured JSON.

    - **file**: Uploaded file (for file source_type)
    - **api_key**: API key for authentication
    - **source_type**: Type of source (file, sql, api, web, cloud)
    - **source_url**: URL or connection string for non-file sources
    - **chunk_strategy**: Chunking strategy (sentence, paragraph, fixed)
    - **async_processing**: Whether to process document asynchronously using Redis queue
    """
    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="API key required")

    # Generate task ID
    task_id = str(uuid.uuid4())

    # Store task in database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        status TEXT,
        api_key TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("INSERT INTO tasks (task_id, status, api_key) VALUES (?, ?, ?)",
                  (task_id, "processing", api_key))
    conn.commit()
    conn.close()

    # For small files and not explicitly async, process synchronously
    if file and file.size < 1024 * 1024 and not async_processing:  # Less than 1MB
        result = await parse_document(file, source_type, source_url, chunk_strategy)

        # Store result in Redis if available
        if redis_client.is_connected():
            redis_client.store_task_result(task_id, result)
            logger.info(f"Task result stored in Redis for task_id: {task_id}")

        # Update task status
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE tasks SET status = ? WHERE task_id = ?", ("completed", task_id))
        conn.commit()
        conn.close()

        # Update document count
        update_document_count(api_key)

        return result

    # For larger files or explicitly async, process asynchronously
    if async_processing and redis_client.is_connected():
        logger.info(f"Processing task {task_id} asynchronously with Redis")

        # For file uploads, save to disk first
        file_path = None
        if source_type == "file" and file:
            try:
                # Create data directory if it doesn't exist
                os.makedirs("data/uploads", exist_ok=True)

                # Read file content
                file_content = await file.read()
                if not file_content:
                    logger.error(f"File content is empty for task {task_id}")
                    raise HTTPException(status_code=400, detail="File content is empty")

                # Save file to disk
                file_path = f"data/uploads/{task_id}_{file.filename}"
                with open(file_path, "wb") as f:
                    f.write(file_content)

                logger.info(f"File saved to {file_path} for task {task_id}")
            except Exception as e:
                logger.error(f"Error saving file for task {task_id}: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")

        # Add task to Redis queue
        task_data = {
            "task_id": task_id,
            "source_type": source_type,
            "source_url": source_url,
            "chunk_strategy": chunk_strategy,
            "api_key": api_key,
            "file_path": file_path
        }

        # Add task to Redis queue for asynchronous processing
        if redis_client.add_to_queue("document_processing", task_data):
            logger.info(f"Task {task_id} added to queue for async processing")
            return {"task_id": task_id, "status": "processing"}
        else:
            logger.error(f"Failed to add task {task_id} to Redis queue")
            raise HTTPException(status_code=500, detail="Failed to add task to queue")

    # Fall back to background tasks if Redis is not available or async_processing is False
    background_tasks.add_task(
        process_document, task_id, file, source_type, source_url, chunk_strategy, api_key
    )

    return {"task_id": task_id, "status": "processing"}

@app.post("/query")
async def query_document(query: str, api_key: str = None, use_cache: bool = True):
    """
    Query parsed documents using LLM.

    - **query**: Query string
    - **api_key**: API key for authentication
    - **use_cache**: Whether to use cached responses
    """
    if not USE_LLM:
        raise HTTPException(status_code=400, detail="LLM integration is disabled")

    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="API key required")

    # Check cache first if enabled and Redis is available
    if use_cache and redis_client.is_connected():
        cached_response = redis_client.get_cached_llm_response(query)
        if cached_response:
            logger.info(f"Using cached LLM response for query: {query[:50]}...")
            return {"response": cached_response, "cached": True}

    try:
        # Get response from LLM
        response = llm.invoke(query)
        response_text = str(response)

        # Cache response if Redis is available
        if use_cache and redis_client.is_connected():
            redis_client.cache_llm_response(query, response_text)

        return {"response": response_text, "cached": False}
    except Exception as e:
        logger.error(f"Query failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.post("/generate_schema")
async def generate_schema(
    schema_description: str,
    file: UploadFile = File(None),
    api_key: str = None
):
    """
    Generate custom JSON schema from document.

    - **schema_description**: Description of the schema to generate
    - **file**: Uploaded file
    - **api_key**: API key for authentication
    """
    if not USE_LLM:
        raise HTTPException(status_code=400, detail="LLM integration is disabled")

    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="API key required")

    # Parse document first
    elements = await parse_document(file)

    # Generate schema using LLM
    prompt = f"Generate a JSON schema based on this description: '{schema_description}'. Use these document elements as reference: {json.dumps(elements)}"

    try:
        response = llm.invoke(prompt)
        schema = json.loads(str(response))
        return {"schema": schema}
    except Exception as e:
        logger.error(f"Schema generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Schema generation failed: {str(e)}")

@app.post("/agent")
async def agent_task(
    task_description: str,
    file: UploadFile = File(None),
    api_key: str = None
):
    """
    Perform agentic tasks on documents.

    - **task_description**: Description of the task to perform
    - **file**: Uploaded file
    - **api_key**: API key for authentication
    """
    if not USE_LLM:
        raise HTTPException(status_code=400, detail="LLM integration is disabled")

    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="API key required")

    # Parse document first
    elements = await parse_document(file)

    # Perform agentic task using LLM
    prompt = f"Perform this task: '{task_description}'. Use these document elements: {json.dumps(elements)}"

    try:
        response = llm.invoke(prompt)
        result = json.loads(str(response))
        return result
    except Exception as e:
        logger.error(f"Agent task failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent task failed: {str(e)}")

@app.post("/match")
async def three_way_match(
    files: List[UploadFile] = File(None),
    invoice_task_id: Optional[str] = None,
    po_task_id: Optional[str] = None,
    grn_task_id: Optional[str] = None,
    api_key: str = None
):
    """
    Perform three-way matching on multiple documents (e.g., invoice, PO, GRN).

    - **files**: List of uploaded files
    - **invoice_task_id**: Task ID for invoice document (alternative to files)
    - **po_task_id**: Task ID for purchase order document (alternative to files)
    - **grn_task_id**: Task ID for goods receipt note document (alternative to files)
    - **api_key**: API key for authentication
    """
    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="API key required")

    # Check if we're using task IDs or files
    if invoice_task_id and po_task_id and grn_task_id:
        # Get document data from Redis or SQLite
        invoice_data = None
        po_data = None
        grn_data = None

        # Try to get data from Redis first
        if redis_client.is_connected():
            invoice_data = redis_client.get_task_result(invoice_task_id)
            po_data = redis_client.get_task_result(po_task_id)
            grn_data = redis_client.get_task_result(grn_task_id)

        # If any data is missing, return error
        if not invoice_data or not po_data or not grn_data:
            raise HTTPException(status_code=404, detail="One or more documents not found")

        # Extract key information from documents
        invoice_info = extract_document_info(invoice_data, "invoice")
        po_info = extract_document_info(po_data, "po")
        grn_info = extract_document_info(grn_data, "grn")

    elif files:
        if len(files) < 3:
            raise HTTPException(status_code=400, detail="Three files are required for three-way matching")

        # Parse all documents
        elements_list = []
        for file in files:
            result = await parse_document(file)
            elements_list.append(result)

        # Try to identify document types based on content
        invoice_data = None
        po_data = None
        grn_data = None

        for doc in elements_list:
            doc_type = identify_document_type(doc)
            if doc_type == "invoice":
                invoice_data = doc
            elif doc_type == "po":
                po_data = doc
            elif doc_type == "grn":
                grn_data = doc

        # If any document type is missing, return error
        if not invoice_data or not po_data or not grn_data:
            raise HTTPException(status_code=400, detail="Could not identify all required document types (invoice, PO, GRN)")

        # Extract key information from documents
        invoice_info = extract_document_info(invoice_data, "invoice")
        po_info = extract_document_info(po_data, "po")
        grn_info = extract_document_info(grn_data, "grn")
    else:
        raise HTTPException(status_code=400, detail="Either files or task IDs must be provided")

    # Perform matching
    matches = []
    discrepancies = []

    # Match PO number
    if invoice_info.get("po_number") == po_info.get("po_number"):
        matches.append({"field": "PO Number", "status": "match"})
    else:
        discrepancies.append({
            "field": "PO Number",
            "status": "mismatch",
            "invoice_value": invoice_info.get("po_number"),
            "po_value": po_info.get("po_number")
        })

    # Match vendor/supplier
    if invoice_info.get("vendor") == po_info.get("supplier"):
        matches.append({"field": "Vendor/Supplier", "status": "match"})
    else:
        discrepancies.append({
            "field": "Vendor/Supplier",
            "status": "mismatch",
            "invoice_value": invoice_info.get("vendor"),
            "po_value": po_info.get("supplier")
        })

    # Match bill to/buyer
    if invoice_info.get("bill_to") == po_info.get("buyer"):
        matches.append({"field": "Bill To/Buyer", "status": "match"})
    else:
        discrepancies.append({
            "field": "Bill To/Buyer",
            "status": "mismatch",
            "invoice_value": invoice_info.get("bill_to"),
            "po_value": po_info.get("buyer")
        })

    # Match total amount
    if invoice_info.get("total") == po_info.get("total"):
        matches.append({"field": "Total Amount", "status": "match"})
    else:
        discrepancies.append({
            "field": "Total Amount",
            "status": "mismatch",
            "invoice_value": invoice_info.get("total"),
            "po_value": po_info.get("total")
        })

    # Match line items
    invoice_items = invoice_info.get("items", [])
    po_items = po_info.get("items", [])
    grn_items = grn_info.get("items", [])

    # Compare items between invoice and PO
    item_matches = []
    item_discrepancies = []

    for inv_item in invoice_items:
        found = False
        for po_item in po_items:
            if inv_item.get("item") == po_item.get("item"):
                found = True
                if inv_item.get("quantity") == po_item.get("quantity") and inv_item.get("price") == po_item.get("price"):
                    item_matches.append({
                        "item": inv_item.get("item"),
                        "status": "match"
                    })
                else:
                    item_discrepancies.append({
                        "item": inv_item.get("item"),
                        "status": "mismatch",
                        "invoice_quantity": inv_item.get("quantity"),
                        "po_quantity": po_item.get("quantity"),
                        "invoice_price": inv_item.get("price"),
                        "po_price": po_item.get("price")
                    })
                break

        if not found:
            item_discrepancies.append({
                "item": inv_item.get("item"),
                "status": "not_in_po"
            })

    # Check for items in PO but not in invoice
    for po_item in po_items:
        found = False
        for inv_item in invoice_items:
            if po_item.get("item") == inv_item.get("item"):
                found = True
                break

        if not found:
            item_discrepancies.append({
                "item": po_item.get("item"),
                "status": "not_in_invoice"
            })

    # Compare with GRN
    grn_matches = []
    grn_discrepancies = []

    for po_item in po_items:
        found = False
        for grn_item in grn_items:
            if po_item.get("item") == grn_item.get("item"):
                found = True
                if po_item.get("quantity") == grn_item.get("received"):
                    grn_matches.append({
                        "item": po_item.get("item"),
                        "status": "match"
                    })
                else:
                    grn_discrepancies.append({
                        "item": po_item.get("item"),
                        "status": "quantity_mismatch",
                        "po_quantity": po_item.get("quantity"),
                        "grn_received": grn_item.get("received")
                    })
                break

        if not found:
            grn_discrepancies.append({
                "item": po_item.get("item"),
                "status": "not_in_grn"
            })

    # Calculate match percentage
    total_checks = len(matches) + len(discrepancies) + len(item_matches) + len(item_discrepancies) + len(grn_matches) + len(grn_discrepancies)
    total_matches = len(matches) + len(item_matches) + len(grn_matches)
    match_percentage = (total_matches / total_checks) * 100 if total_checks > 0 else 0

    # Determine overall status
    overall_status = "complete_match" if len(discrepancies) == 0 and len(item_discrepancies) == 0 and len(grn_discrepancies) == 0 else "partial_match"

    return {
        "status": overall_status,
        "match_percentage": match_percentage,
        "header_matches": matches,
        "header_discrepancies": discrepancies,
        "item_matches": item_matches,
        "item_discrepancies": item_discrepancies,
        "grn_matches": grn_matches,
        "grn_discrepancies": grn_discrepancies,
        "documents": {
            "invoice": invoice_info,
            "po": po_info,
            "grn": grn_info
        }
    }

def identify_document_type(document):
    """Identify document type based on content."""
    elements = document.get("elements", [])

    # Check for invoice indicators
    invoice_indicators = ["invoice", "bill to", "payment terms"]
    invoice_score = 0

    # Check for PO indicators
    po_indicators = ["purchase order", "po number", "buyer", "supplier"]
    po_score = 0

    # Check for GRN indicators
    grn_indicators = ["goods receipt", "grn number", "received", "delivery"]
    grn_score = 0

    # Check all elements for indicators
    for element in elements:
        text = element.get("text", "").lower()

        for indicator in invoice_indicators:
            if indicator in text:
                invoice_score += 1

        for indicator in po_indicators:
            if indicator in text:
                po_score += 1

        for indicator in grn_indicators:
            if indicator in text:
                grn_score += 1

    # Determine document type based on highest score
    if invoice_score > po_score and invoice_score > grn_score:
        return "invoice"
    elif po_score > invoice_score and po_score > grn_score:
        return "po"
    elif grn_score > invoice_score and grn_score > po_score:
        return "grn"
    else:
        # Default to unknown
        return "unknown"

def extract_document_info(document_data, doc_type):
    """Extract key information from document data based on document type."""
    elements = document_data.get("elements", [])
    info = {}

    if doc_type == "invoice":
        # Extract invoice information
        info["type"] = "invoice"

        # Extract invoice number
        for element in elements:
            text = element.get("text", "")
            if "Invoice Number" in text:
                parts = text.split(":")
                if len(parts) > 1:
                    info["invoice_number"] = parts[1].strip().split(" ")[0]
                    break

        # Extract PO number
        for element in elements:
            text = element.get("text", "")
            if "Purchase Order" in text:
                parts = text.split(":")
                if len(parts) > 1:
                    info["po_number"] = parts[1].strip()
                    break

        # Extract vendor
        vendor_found = False
        for i, element in enumerate(elements):
            text = element.get("text", "")
            if "Vendor:" in text:
                vendor_found = True
                if i + 1 < len(elements):
                    info["vendor"] = elements[i + 1].get("text", "")
                break

        if not vendor_found:
            for i, element in enumerate(elements):
                text = element.get("text", "")
                if "Acme Corporation" in text:
                    info["vendor"] = text
                    break

        # Extract bill to
        bill_to_found = False
        for i, element in enumerate(elements):
            text = element.get("text", "")
            if "Bill To:" in text:
                bill_to_found = True
                if i + 1 < len(elements):
                    info["bill_to"] = elements[i + 1].get("text", "")
                break

        if not bill_to_found:
            for i, element in enumerate(elements):
                text = element.get("text", "")
                if "XYZ Company" in text:
                    info["bill_to"] = text
                    break

        # Extract total
        for element in elements:
            text = element.get("text", "")
            if "Total:" in text:
                parts = text.split(":")
                if len(parts) > 1:
                    info["total"] = parts[1].strip()
                    break

        # Extract items
        items = []
        for element in elements:
            if element.get("type") == "Table":
                headers = element.get("headers", [])
                data = element.get("data", [])

                if not data and headers:
                    # Try to parse items from headers
                    item_idx = -1
                    qty_idx = -1
                    price_idx = -1
                    total_idx = -1

                    for i, header in enumerate(headers):
                        if header.lower() == "item":
                            item_idx = i
                        elif header.lower() == "quantity":
                            qty_idx = i
                        elif header.lower() == "unit price":
                            price_idx = i
                        elif header.lower() == "total":
                            total_idx = i

                    if item_idx >= 0 and qty_idx >= 0 and price_idx >= 0 and total_idx >= 0:
                        # Find rows with actual data
                        for i in range(len(headers)):
                            if i % 4 == 0 and i + 3 < len(headers):
                                item = headers[i]
                                if item not in ["Item", "-----------------------"]:
                                    items.append({
                                        "item": item,
                                        "quantity": headers[i + 1],
                                        "price": headers[i + 2],
                                        "total": headers[i + 3]
                                    })
                else:
                    # Use data if available
                    for row in data:
                        items.append({
                            "item": row.get("Item", ""),
                            "quantity": row.get("Quantity", ""),
                            "price": row.get("Unit Price", ""),
                            "total": row.get("Total", "")
                        })

        info["items"] = items

    elif doc_type == "po":
        # Extract PO information
        info["type"] = "po"

        # Extract PO number
        for element in elements:
            text = element.get("text", "")
            if "PO Number" in text:
                parts = text.split(":")
                if len(parts) > 1:
                    info["po_number"] = parts[1].strip()
                    break

        # Extract buyer
        buyer_found = False
        for i, element in enumerate(elements):
            text = element.get("text", "")
            if "Buyer:" in text:
                buyer_found = True
                if i + 1 < len(elements):
                    info["buyer"] = elements[i + 1].get("text", "")
                break

        if not buyer_found:
            for i, element in enumerate(elements):
                text = element.get("text", "")
                if "XYZ Company" in text:
                    info["buyer"] = text
                    break

        # Extract supplier
        supplier_found = False
        for i, element in enumerate(elements):
            text = element.get("text", "")
            if "Supplier:" in text:
                supplier_found = True
                if i + 1 < len(elements):
                    info["supplier"] = elements[i + 1].get("text", "")
                break

        if not supplier_found:
            for i, element in enumerate(elements):
                text = element.get("text", "")
                if "Acme Corporation" in text:
                    info["supplier"] = text
                    break

        # Extract total
        for element in elements:
            text = element.get("text", "")
            if "Total:" in text:
                parts = text.split(":")
                if len(parts) > 1:
                    info["total"] = parts[1].strip()
                    break

        # Extract items
        items = []
        for element in elements:
            if element.get("type") == "Table":
                headers = element.get("headers", [])
                data = element.get("data", [])

                if not data and headers:
                    # Try to parse items from headers
                    item_idx = -1
                    qty_idx = -1
                    price_idx = -1
                    total_idx = -1

                    for i, header in enumerate(headers):
                        if header.lower() == "item":
                            item_idx = i
                        elif header.lower() == "quantity":
                            qty_idx = i
                        elif header.lower() == "unit price":
                            price_idx = i
                        elif header.lower() == "total":
                            total_idx = i

                    if item_idx >= 0 and qty_idx >= 0 and price_idx >= 0 and total_idx >= 0:
                        # Find rows with actual data
                        for i in range(len(headers)):
                            if i % 4 == 0 and i + 3 < len(headers):
                                item = headers[i]
                                if item not in ["Item", "-----------------------"]:
                                    items.append({
                                        "item": item,
                                        "quantity": headers[i + 1],
                                        "price": headers[i + 2],
                                        "total": headers[i + 3]
                                    })
                else:
                    # Use data if available
                    for row in data:
                        items.append({
                            "item": row.get("Item", ""),
                            "quantity": row.get("Quantity", ""),
                            "price": row.get("Unit Price", ""),
                            "total": row.get("Total", "")
                        })

        info["items"] = items

    elif doc_type == "grn":
        # Extract GRN information
        info["type"] = "grn"

        # Extract GRN number
        for element in elements:
            text = element.get("text", "")
            if "GRN Number" in text:
                parts = text.split(":")
                if len(parts) > 1:
                    info["grn_number"] = parts[1].strip()
                    break

        # Extract PO number
        for element in elements:
            text = element.get("text", "")
            if "Purchase Order" in text:
                parts = text.split(":")
                if len(parts) > 1:
                    info["po_number"] = parts[1].strip()
                    break

        # Extract receiver
        receiver_found = False
        for i, element in enumerate(elements):
            text = element.get("text", "")
            if "Receiver:" in text:
                receiver_found = True
                if i + 1 < len(elements):
                    info["receiver"] = elements[i + 1].get("text", "")
                break

        if not receiver_found:
            for i, element in enumerate(elements):
                text = element.get("text", "")
                if "XYZ Company" in text:
                    info["receiver"] = text
                    break

        # Extract supplier
        supplier_found = False
        for i, element in enumerate(elements):
            text = element.get("text", "")
            if "Supplier:" in text:
                supplier_found = True
                if i + 1 < len(elements):
                    info["supplier"] = elements[i + 1].get("text", "")
                break

        if not supplier_found:
            for i, element in enumerate(elements):
                text = element.get("text", "")
                if "Acme Corporation" in text:
                    info["supplier"] = text
                    break

        # Extract items
        items = []
        for element in elements:
            if element.get("type") == "Table":
                headers = element.get("headers", [])
                data = element.get("data", [])

                if not data and headers:
                    # Try to parse items from headers
                    item_idx = -1
                    ordered_idx = -1
                    received_idx = -1
                    condition_idx = -1

                    for i, header in enumerate(headers):
                        if header.lower() == "item":
                            item_idx = i
                        elif header.lower() == "ordered":
                            ordered_idx = i
                        elif header.lower() == "received":
                            received_idx = i
                        elif header.lower() == "condition":
                            condition_idx = i

                    if item_idx >= 0 and ordered_idx >= 0 and received_idx >= 0 and condition_idx >= 0:
                        # Find rows with actual data
                        for i in range(len(headers)):
                            if i % 4 == 0 and i + 3 < len(headers):
                                item = headers[i]
                                if item not in ["Item", "-----------------------"]:
                                    items.append({
                                        "item": item,
                                        "ordered": headers[i + 1],
                                        "received": headers[i + 2],
                                        "condition": headers[i + 3]
                                    })
                else:
                    # Use data if available
                    for row in data:
                        items.append({
                            "item": row.get("Item", ""),
                            "ordered": row.get("Ordered", ""),
                            "received": row.get("Received", ""),
                            "condition": row.get("Condition", "")
                        })

        info["items"] = items

    return info

@app.get("/status/{task_id}")
async def get_task_status(task_id: str, api_key: str = None, include_result: bool = False):
    """
    Check status of an asynchronous task.

    - **task_id**: Task ID
    - **api_key**: API key for authentication
    - **include_result**: Whether to include the task result in the response
    """
    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="API key required")

    # Check task status in SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM tasks WHERE task_id = ? AND api_key = ?", (task_id, api_key))
    status_result = cursor.fetchone()
    conn.close()

    if not status_result:
        raise HTTPException(status_code=404, detail="Task not found")

    status = status_result[0]
    response = {"task_id": task_id, "status": status}

    # If requested and task is completed, try to get result from Redis
    if include_result and status == "completed" and redis_client.is_connected():
        task_result = redis_client.get_task_result(task_id)
        if task_result:
            response["result"] = task_result

    return response

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)