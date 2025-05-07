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

# Optional imports based on environment variables
USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"
LLM_MODEL = os.getenv("LLM_MODEL")
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT")

# Initialize FastAPI app
app = FastAPI(
    title="ClaryAI",
    description="A self-hosted API for parsing documents into LLM-ready JSON outputs with zero data retention.",
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("claryai")

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
            from langchain_core.language_models import BaseLanguageModel
            if "openai" in LLM_ENDPOINT:
                from langchain_openai import ChatOpenAI
                llm = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=LLM_ENDPOINT)
            else:
                from langchain_community.llms import HuggingFaceEndpoint
                llm = HuggingFaceEndpoint(endpoint_url=LLM_ENDPOINT)
        else:
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
                elements = [{"type": str(type(el).__name__), "text": str(el)} for el in elements_raw]
            except ImportError:
                logger.error("Unstructured.io not available")
                elements = [{"type": "Error", "text": "Unstructured.io not available"}]

        elif source_type == "sql" and source_url:
            # Use LlamaIndex's SQLDatabaseReader
            try:
                from llama_index.readers.database import SQLDatabase
                sql_database = SQLDatabase(source_url)
                tables = sql_database.get_tables()
                elements = []
                for table in tables:
                    query = f"SELECT * FROM {table} LIMIT 10"
                    results = sql_database.run_sql(query)
                    elements.append({"type": "Table", "text": str(results), "table_name": table})
            except ImportError:
                logger.error("LlamaIndex not available")
                elements = [{"type": "Error", "text": "LlamaIndex not available"}]

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
                    elements.append({"type": "Table", "text": str(table)})
            else:
                elements = [{"type": "Error", "text": f"Web request failed with status {response.status_code}"}]

        elif source_type == "cloud" and source_url:
            # Placeholder for cloud storage connectors
            elements = [{"type": "Error", "text": "Cloud storage connectors not implemented yet"}]

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

    # Store result in SQLite temporarily (only task_id and status, not content)
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

    # Update document count for the API key
    if api_key:
        update_document_count(api_key)

    return result

# API Endpoints

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()

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
    chunk_strategy: str = "paragraph"
):
    """
    Parse a document from various sources into structured JSON.

    - **file**: Uploaded file (for file source_type)
    - **api_key**: API key for authentication
    - **source_type**: Type of source (file, sql, api, web, cloud)
    - **source_url**: URL or connection string for non-file sources
    - **chunk_strategy**: Chunking strategy (sentence, paragraph, fixed)
    """
    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="API key required")

    # For small files, process synchronously
    if file and file.size < 1024 * 1024:  # Less than 1MB
        result = await parse_document(file, source_type, source_url, chunk_strategy)
        # Update document count
        update_document_count(api_key)
        return result

    # For larger files or non-file sources, process asynchronously
    task_id = str(uuid.uuid4())
    background_tasks.add_task(
        process_document, task_id, file, source_type, source_url, chunk_strategy, api_key
    )
    return {"task_id": task_id, "status": "processing"}

@app.post("/query")
async def query_document(query: str, api_key: str = None):
    """
    Query parsed documents using LLM.

    - **query**: Query string
    - **api_key**: API key for authentication
    """
    if not USE_LLM:
        raise HTTPException(status_code=400, detail="LLM integration is disabled")

    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="API key required")

    try:
        response = llm.invoke(query)
        return {"response": str(response)}
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
    api_key: str = None
):
    """
    Perform three-way matching on multiple documents (e.g., invoice, PO, GRN).

    - **files**: List of uploaded files
    - **api_key**: API key for authentication
    """
    if not USE_LLM:
        raise HTTPException(status_code=400, detail="LLM integration is disabled")

    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="API key required")

    if not files or len(files) < 2:
        raise HTTPException(status_code=400, detail="At least two files are required for matching")

    # Parse all documents
    elements_list = []
    for file in files:
        result = await parse_document(file)
        elements_list.append(result["elements"])

    # Perform three-way matching using LLM
    prompt = f"Compare these documents for three-way matching (invoice, PO, GRN): {json.dumps(elements_list)}. Flag mismatches and suggest actions."

    try:
        response = llm.invoke(prompt)
        result = json.loads(str(response))
        return result
    except Exception as e:
        logger.error(f"Three-way matching failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Three-way matching failed: {str(e)}")

@app.get("/status/{task_id}")
async def get_task_status(task_id: str, api_key: str = None):
    """
    Check status of an asynchronous task.

    - **task_id**: Task ID
    - **api_key**: API key for authentication
    """
    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="API key required")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM tasks WHERE task_id = ? AND api_key = ?", (task_id, api_key))
    result = cursor.fetchone()
    conn.close()

    if not result:
        raise HTTPException(status_code=404, detail="Task not found")

    return {"task_id": task_id, "status": result[0]}

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)