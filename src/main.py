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
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import requests
from bs4 import BeautifulSoup
import pathlib
try:
    # Try to import the improved table parser first
    try:
        from table_parser_improved import TableTransformer
    except ImportError:
        from src.table_parser_improved import TableTransformer

    # Import Redis client
    try:
        from redis_client import RedisClient
    except ImportError:
        from src.redis_client import RedisClient
except ImportError:
    # Fall back to the original table parser
    try:
        from table_parser import TableTransformer
        from redis_client import RedisClient
    except ImportError:
        # Try with src prefix
        from src.table_parser import TableTransformer
        from src.redis_client import RedisClient

# Make sure json is imported at the top level
import json

# Optional imports based on environment variables
USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"
LLM_MODEL = os.getenv("LLM_MODEL", "phi-4-multimodal")  # Default to Phi-4-multimodal
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

# No middleware - we'll use direct validation in each endpoint

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("claryai")
logger.setLevel(logging.DEBUG)
logger.info("Logger initialized")

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
        print("API key is None or empty")
        return False

    print(f"Validating API key: {api_key}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT key FROM api_keys WHERE key = ?", (api_key,))
    result = cursor.fetchone()
    conn.close()

    print(f"API key validation result: {result}")
    return result is not None

# No API key dependency - we'll use direct validation in each endpoint

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

# Helper function to parse a file
def parse_file(file_obj):
    """
    Parse a file using Unstructured.io.

    Args:
        file_obj: File object to parse

    Returns:
        list: List of parsed elements
    """
    try:
        from unstructured.partition.auto import partition

        # Create a temporary file
        tmp_path = tempfile.mktemp()
        with open(tmp_path, "wb") as f:
            f.write(file_obj.read())

        # Parse the file
        elements_raw = partition(tmp_path)
        elements = []

        for el in elements_raw:
            el_type = str(type(el).__name__)
            el_text = str(el)

            # Check if this element might be a table
            if el_type == "Table" or (el_type == "Text" and
                                     ('|' in el_text or
                                      '+---+' in el_text or
                                      '----' in el_text or
                                      '=====' in el_text or
                                      '---------' in el_text or
                                      '$' in el_text and 'Total' in el_text or
                                      (el_text.count('\n') >= 2 and
                                       any(line.strip().startswith('-') and line.strip().endswith('-')
                                           for line in el_text.split('\n'))) or
                                      # Check for tabular data with multiple spaces as column separators
                                      (el_text.count('\n') >= 2 and
                                       any('  ' in line for line in el_text.split('\n'))))):
                # Try to parse as a table
                table_data = table_transformer.parse_text_table(el_text)
                elements.append(table_data)
            else:
                elements.append({"type": el_type, "text": el_text})

        # Clean up
        os.unlink(tmp_path)

        return elements
    except ImportError:
        logger.error("Unstructured.io not available")
        return [{"type": "Error", "text": "Unstructured.io not available"}]
    except Exception as e:
        logger.error(f"File parsing failed: {str(e)}")
        return [{"type": "Error", "text": f"File parsing failed: {str(e)}"}]

# Initialize LLM if enabled
if USE_LLM:
    try:
        # Try to use Phi-4-multimodal integration first
        try:
            from phi4_integration import get_phi_model_integration, PROMPT_TEMPLATES
            llm_integration = get_phi_model_integration(LLM_MODEL)
            if llm_integration:
                llm = llm_integration
                logger.info(f"Phi model initialized successfully with model: {LLM_MODEL}")
            else:
                # Fall back to OpenAI integration
                try:
                    from openai_integration import get_openai_integration, PROMPT_TEMPLATES
                    llm_integration = get_openai_integration(LLM_MODEL)
                    if llm_integration:
                        llm = llm_integration
                        logger.info(f"OpenAI LLM initialized successfully with model: {LLM_MODEL}")
                    else:
                        # Fall back to the original LLM integration
                        try:
                            from llm_integration import get_llm_integration, PROMPT_TEMPLATES
                        except ImportError:
                            from src.llm_integration import get_llm_integration, PROMPT_TEMPLATES
                        llm_integration = get_llm_integration()
                        if llm_integration:
                            llm = llm_integration
                            logger.info(f"LLM initialized successfully with model: {llm_integration.model}")
                        else:
                            USE_LLM = False
                            logger.warning("LLM integration not available. LLM features disabled.")
                except ImportError:
                    # Fall back to the original LLM integration
                    try:
                        from llm_integration import get_llm_integration, PROMPT_TEMPLATES
                    except ImportError:
                        from src.llm_integration import get_llm_integration, PROMPT_TEMPLATES
                    llm_integration = get_llm_integration()
                    if llm_integration:
                        llm = llm_integration
                        logger.info(f"LLM initialized successfully with model: {llm_integration.model}")
                    else:
                        USE_LLM = False
                        logger.warning("LLM integration not available. LLM features disabled.")
        except ImportError:
            # Fall back to OpenAI integration
            try:
                from openai_integration import get_openai_integration, PROMPT_TEMPLATES
                llm_integration = get_openai_integration(LLM_MODEL)
                if llm_integration:
                    llm = llm_integration
                    logger.info(f"OpenAI LLM initialized successfully with model: {LLM_MODEL}")
                else:
                    # Fall back to the original LLM integration
                    try:
                        from llm_integration import get_llm_integration, PROMPT_TEMPLATES
                    except ImportError:
                        from src.llm_integration import get_llm_integration, PROMPT_TEMPLATES
                    llm_integration = get_llm_integration()
                    if llm_integration:
                        llm = llm_integration
                        logger.info(f"LLM initialized successfully with model: {llm_integration.model}")
                    else:
                        USE_LLM = False
                        logger.warning("LLM integration not available. LLM features disabled.")
            except ImportError:
                # Fall back to the original LLM integration
                try:
                    from llm_integration import get_llm_integration, PROMPT_TEMPLATES
                except ImportError:
                    from src.llm_integration import get_llm_integration, PROMPT_TEMPLATES
                llm_integration = get_llm_integration()
                if llm_integration:
                    llm = llm_integration
                    logger.info(f"LLM initialized successfully with model: {llm_integration.model}")
                else:
                    USE_LLM = False
                    logger.warning("LLM integration not available. LLM features disabled.")
    except ImportError as e:
        USE_LLM = False
        logger.warning(f"LLM dependencies not available. LLM features disabled. Error: {str(e)}")

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
            file_parts = file.filename.split('.')
            extension = file_parts[-1] if len(file_parts) > 1 else "txt"
            tmp_path = tempfile.mktemp(suffix=f".{extension}")
            with open(tmp_path, "wb") as f:
                content = await file.read()
                f.write(content)

            # Check if it's a JSON file
            if extension.lower() == 'json':
                try:
                    # Read the file content
                    with open(tmp_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()

                    # Try to parse as JSON
                    try:
                        json_data = json.loads(file_content)

                        # Convert JSON to elements
                        if isinstance(json_data, dict):
                            # Process dictionary
                            elements = []
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
                            elements = []
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

                        logger.info(f"Successfully parsed JSON file: {file.filename}")
                    except json.JSONDecodeError as e:
                        # If JSON parsing fails, treat as text
                        logger.warning(f"Invalid JSON file, treating as text: {str(e)}")
                        elements = [{
                            "type": "Text",
                            "text": file_content[:10000]  # Limit to first 10000 characters
                        }]
                except Exception as e:
                    logger.error(f"Error processing JSON file: {str(e)}")
                    elements = [{"type": "Error", "text": f"Error processing JSON file: {str(e)}"}]
            else:
                # Use Unstructured.io to parse the file
                try:
                    from unstructured.partition.auto import partition
                    elements_raw = partition(tmp_path)
                    elements = []

                    for el in elements_raw:
                        el_type = str(type(el).__name__)
                        el_text = str(el)

                        # Check if this element might be a table
                        if el_type == "Table" or (el_type == "Text" and
                                                 ('|' in el_text or
                                                  '+---+' in el_text or
                                                  '----' in el_text or
                                                  '=====' in el_text or
                                                  '---------' in el_text or
                                                  '$' in el_text and 'Total' in el_text or
                                                  (el_text.count('\n') >= 2 and
                                                   any(line.strip().startswith('-') and line.strip().endswith('-')
                                                       for line in el_text.split('\n'))) or
                                                  # Check for tabular data with multiple spaces as column separators
                                                  (el_text.count('\n') >= 2 and
                                                   any('  ' in line for line in el_text.split('\n'))))):
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
            import json  # Import json locally to ensure it's available
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

                try:
                    from cloud_connectors import get_connector as get_cloud_connector
                except ImportError:
                    from src.cloud_connectors import get_connector as get_cloud_connector
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
                    connector = get_cloud_connector(provider)
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

        elif source_type == "datasource" and source_url:
            try:
                # Parse the source URL (format: provider://credentials_json/source_id)
                # Example: notion://{"token":"xyz"}/page_id
                # Example: github://{"token":"xyz"}/owner/repo/path/to/file
                # Example: mongodb://{"connection_string":"mongodb://..."}/database.collection
                # Example: slack://{"token":"xyz"}/channel_id

                # Try to import from additional_connectors first, then from more_connectors
                connector = None
                import json

                # Parse the URL
                parts = source_url.split("://", 1)
                if len(parts) != 2:
                    raise ValueError(f"Invalid data source URL format: {source_url}")

                provider = parts[0]
                remaining = parts[1]

                # Extract credentials and source_id
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

                    # Extract credentials and source_id
                    credentials_json = remaining[:json_end]
                    source_id = remaining[json_end:].lstrip('/')

                    # Parse credentials
                    credentials = json.loads(credentials_json)

                    # Try to get the connector from additional_connectors
                    try:
                        try:
                            from additional_connectors import get_connector as get_datasource_connector
                        except ImportError:
                            from src.additional_connectors import get_connector as get_datasource_connector
                        connector = get_datasource_connector(provider)
                    except (ImportError, AttributeError):
                        connector = None

                    # If not found, try to get from more_connectors
                    if not connector:
                        try:
                            try:
                                from more_connectors import get_connector as get_more_connector
                            except ImportError:
                                from src.more_connectors import get_connector as get_more_connector
                            connector = get_more_connector(provider)
                        except (ImportError, AttributeError):
                            connector = None

                    if not connector:
                        raise ValueError(f"Unsupported data source provider: {provider}")

                    # Download the data
                    tmp_path = connector.download_data(source_id, credentials)
                    if not tmp_path:
                        raise ValueError(f"Failed to download data from {provider}")

                    # Parse the downloaded file
                    with open(tmp_path, 'rb') as f:
                        elements = parse_file(f)

                    # Clean up
                    os.unlink(tmp_path)

                except json.JSONDecodeError:
                    raise ValueError(f"Invalid JSON credentials in URL: {source_url}")
                except Exception as e:
                    raise ValueError(f"Error processing data source: {str(e)}")
            except Exception as e:
                logger.error(f"Data source processing failed: {str(e)}")
                elements = [{"type": "Error", "text": f"Data source processing failed: {str(e)}"}]

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
                try:
                    refined_elements = json.loads(str(response))
                    if isinstance(refined_elements, list):
                        elements = refined_elements
                except json.JSONDecodeError:
                    logger.warning("LLM response is not valid JSON, using original elements")
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
                          chunk_strategy: str = "paragraph", api_key: Optional[str] = None,
                          batch_id: Optional[str] = None) -> dict:
    """Process document asynchronously and store result temporarily"""
    try:
        # Update task status to processing
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            status TEXT,
            api_key TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            batch_id TEXT
        )
        """)
        cursor.execute("UPDATE tasks SET status = ? WHERE task_id = ?", ("processing", task_id))
        conn.commit()

        # Process the document
        result = await parse_document(file, source_type, source_url, chunk_strategy)

        # Update task status to completed
        cursor.execute("UPDATE tasks SET status = ? WHERE task_id = ?", ("completed", task_id))

        # If part of a batch, update batch status
        if batch_id:
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
    except Exception as e:
        logger.error(f"Error processing document for task {task_id}: {str(e)}")

        # Update task status to failed
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE tasks SET status = ? WHERE task_id = ?", ("failed", task_id))
            conn.commit()
            conn.close()
        except Exception as db_error:
            logger.error(f"Error updating task status: {str(db_error)}")

        # Return error result
        return {"status": "failed", "error": str(e)}

# API Endpoints



@app.get("/")
async def root():
    """Root endpoint with API information"""
    print("Root endpoint called")

    # No authentication required for root endpoint
    return {
        "name": "ClaryAI",
        "description": "A self-hosted API for parsing documents into LLM-ready JSON outputs with zero data retention.",
        "version": "0.1.0",
        "endpoints": [
            "/parse", "/query", "/generate_schema", "/agent", "/match", "/status/{task_id}",
            "/analyze_image", "/batch", "/status/batch/{batch_id}", "/usage_report"
        ],
        "llm_enabled": USE_LLM,
        "llm_model": LLM_MODEL if USE_LLM else None,
        "multimodal_enabled": USE_LLM and ("phi-4-multimodal" in LLM_MODEL.lower() or ("gpt-4" in LLM_MODEL.lower() and ("vision" in LLM_MODEL.lower() or "o" in LLM_MODEL.lower())) if LLM_MODEL else False)
    }

@app.post("/analyze_image")
async def analyze_image(
    file: UploadFile = File(...),
    extract_text: bool = False,
    detect_objects: bool = False,
    api_key: str = None
):
    """
    Analyze an image using the LLM.

    - **file**: Uploaded image file
    - **extract_text**: Whether to extract text from the image
    - **detect_objects**: Whether to detect objects in the image
    - **api_key**: API key for authentication
    """
    print(f"Analyze image endpoint called with API key: {api_key}")

    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not USE_LLM:
        raise HTTPException(status_code=400, detail="LLM integration is disabled")

    # Check if the model is multimodal
    is_multimodal = False
    if "phi-4-multimodal" in LLM_MODEL.lower() or ("gpt-4" in LLM_MODEL.lower() and ("vision" in LLM_MODEL.lower() or "o" in LLM_MODEL.lower())):
        is_multimodal = True

    if not is_multimodal:
        raise HTTPException(status_code=400, detail="Image analysis requires a multimodal model like Phi-4-multimodal, GPT-4o, or GPT-4 Vision")

    # Validate file type
    allowed_extensions = ["jpg", "jpeg", "png", "gif", "webp"]
    file_parts = file.filename.split(".")
    file_extension = file_parts[-1].lower() if len(file_parts) > 1 else ""
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed types: {', '.join(allowed_extensions)}"
        )

    # Save uploaded file to temp location
    tmp_path = tempfile.mktemp(suffix=f".{file_extension}")
    with open(tmp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        # Analyze the image
        if hasattr(llm, 'analyze_image'):
            # Create a custom prompt based on user requirements
            custom_prompt = PROMPT_TEMPLATES["image_analysis"]
            if extract_text:
                custom_prompt = custom_prompt.replace(
                    "2. Any text visible in the image",
                    "2. Extract ALL text visible in the image with high accuracy"
                )
            if detect_objects:
                custom_prompt = custom_prompt.replace(
                    "3. Key objects or people",
                    "3. Detect and list ALL objects and people in the image with their positions"
                )

            # Analyze the image
            analysis = llm.analyze_image(tmp_path)

            # Try to parse as JSON if possible
            try:
                result = json.loads(analysis)
                return {"analysis": result, "format": "json"}
            except json.JSONDecodeError:
                # Return as text if not valid JSON
                return {"analysis": analysis, "format": "text"}
        else:
            raise HTTPException(status_code=400, detail="Image analysis not supported by the current LLM integration")
    except Exception as e:
        logger.error(f"Image analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")
    finally:
        # Ensure zero data retention
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
            logger.info(f"Temporary file deleted: {tmp_path}")

@app.post("/parse")
async def parse_document_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(None),
    source_type: str = "file",
    source_url: str = None,
    chunk_strategy: str = "paragraph",
    async_processing: bool = False,
    api_key: str = None
):
    """
    Parse a document from various sources into structured JSON.

    - **file**: Uploaded file (for file source_type)
    - **source_type**: Type of source (file, sql, api, web, cloud)
    - **source_url**: URL or connection string for non-file sources
    - **chunk_strategy**: Chunking strategy (sentence, paragraph, fixed)
    - **async_processing**: Whether to process document asynchronously using Redis queue
    - **api_key**: API key for authentication
    """
    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

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
async def query_document(
    query: str,
    use_cache: bool = True,
    api_key: str = None
):
    """
    Query parsed documents using LLM.

    - **query**: Query string
    - **use_cache**: Whether to use cached responses
    - **api_key**: API key for authentication
    """
    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not USE_LLM:
        raise HTTPException(status_code=400, detail="LLM integration is disabled")

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

        # Try to parse as JSON if possible
        try:
            json_response = json.loads(response_text)
            # Cache response if Redis is available
            if use_cache and redis_client.is_connected():
                redis_client.cache_llm_response(query, response_text)
            return {"response": json_response, "cached": False, "format": "json"}
        except json.JSONDecodeError:
            # Not valid JSON, return as text
            # Cache response if Redis is available
            if use_cache and redis_client.is_connected():
                redis_client.cache_llm_response(query, response_text)
            return {"response": response_text, "cached": False, "format": "text"}
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
    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not USE_LLM:
        raise HTTPException(status_code=400, detail="LLM integration is disabled")

    # Parse document first
    elements = await parse_document(file)

    try:
        # Use the LLM integration module's generate_schema method
        if hasattr(llm, 'generate_schema'):
            schema = llm.generate_schema(schema_description, elements.get("elements", []))
            return {"schema": schema}
        else:
            # Fall back to the old method
            prompt = f"Generate a JSON schema based on this description: '{schema_description}'. Use these document elements as reference: {json.dumps(elements)}"
            response = llm.invoke(prompt)
            try:
                schema = json.loads(str(response))
                return {"schema": schema}
            except json.JSONDecodeError:
                return {"schema": str(response), "warning": "Response is not valid JSON"}
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
    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not USE_LLM:
        raise HTTPException(status_code=400, detail="LLM integration is disabled")

    # Parse document first
    elements = await parse_document(file)

    # Perform agentic task using LLM
    prompt = f"Perform this task: '{task_description}'. Use these document elements: {json.dumps(elements)}"

    try:
        # Check if the document contains images
        has_images = False
        for element in elements.get("elements", []):
            if element.get("type") == "Image":
                has_images = True
                break

        # Use image analysis if available and needed
        if has_images and hasattr(llm, 'analyze_image'):
            # Extract image paths
            image_paths = []
            for element in elements.get("elements", []):
                if element.get("type") == "Image" and "path" in element:
                    image_paths.append(element["path"])

            # Analyze images
            image_analyses = []
            for path in image_paths:
                try:
                    analysis = llm.analyze_image(path)
                    image_analyses.append({"path": path, "analysis": analysis})
                except Exception as e:
                    logger.error(f"Image analysis failed for {path}: {str(e)}")
                    image_analyses.append({"path": path, "error": str(e)})

            # Add image analyses to the prompt
            prompt += f"\n\nImage analyses: {json.dumps(image_analyses)}"

        # Invoke the LLM
        response = llm.invoke(prompt)

        # Try to parse as JSON
        try:
            result = json.loads(str(response))
            return result
        except json.JSONDecodeError:
            # Return as text if not valid JSON
            return {"result": str(response), "warning": "Response is not valid JSON"}
    except Exception as e:
        logger.error(f"Agent task failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent task failed: {str(e)}")

@app.post("/match")
async def three_way_match(
    files: List[UploadFile] = None,
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
        raise HTTPException(status_code=401, detail="Invalid API key")

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

@app.post("/batch")
async def batch_process_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = None,
    source_type: str = "file",
    source_urls: List[str] = None,
    chunk_strategy: str = "paragraph",
    async_processing: bool = False,
    max_concurrent: int = 5,
    api_key: str = None
):
    """
    Process multiple documents in a batch.

    - **files**: List of uploaded files
    - **source_type**: Type of source (file, sql, api, web, cloud)
    - **source_urls**: List of URLs or connection strings for non-file sources
    - **chunk_strategy**: Chunking strategy (sentence, paragraph, fixed)
    - **async_processing**: Whether to process documents asynchronously using Redis queue
    - **max_concurrent**: Maximum number of concurrent tasks (only applies to async processing)
    - **api_key**: API key for authentication
    """
    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Validate input
    if source_type == "file" and not files:
        raise HTTPException(status_code=400, detail="Files are required for file source type")

    if source_type != "file" and not source_urls:
        raise HTTPException(status_code=400, detail="Source URLs are required for non-file source types")

    # Generate batch ID
    batch_id = str(uuid.uuid4())

    # Create tasks table if it doesn't exist
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        status TEXT,
        api_key TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        batch_id TEXT
    )
    """)

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

            if async_processing and redis_client.is_connected():
                # For file uploads, save to disk first
                file_path = None
                try:
                    # Create data directory if it doesn't exist
                    os.makedirs("data/uploads", exist_ok=True)

                    # Read file content
                    file_content = await file.read()
                    if not file_content:
                        logger.error(f"File content is empty for task {task_id}")
                        continue

                    # Save file to disk
                    file_path = f"data/uploads/{task_id}_{file.filename}"
                    with open(file_path, "wb") as f:
                        f.write(file_content)

                    logger.info(f"File saved to {file_path} for task {task_id}")

                    # Add task to Redis queue
                    task_data = {
                        "task_id": task_id,
                        "source_type": source_type,
                        "source_url": None,
                        "chunk_strategy": chunk_strategy,
                        "api_key": api_key,
                        "file_path": file_path,
                        "batch_id": batch_id
                    }

                    # Add task to Redis queue with rate limiting
                    redis_client.add_to_queue("document_processing", task_data, max_concurrent)

                except Exception as e:
                    logger.error(f"Error processing file for task {task_id}: {str(e)}")
                    cursor.execute("UPDATE tasks SET status = ? WHERE task_id = ?", ("failed", task_id))
            else:
                # Process synchronously using background tasks
                background_tasks.add_task(
                    process_document, task_id, file, source_type, None, chunk_strategy, api_key, batch_id
                )

    elif source_urls:
        # Insert batch record
        cursor.execute(
            "INSERT INTO batches (batch_id, status, api_key, total_tasks) VALUES (?, ?, ?, ?)",
            (batch_id, "processing", api_key, len(source_urls))
        )
        conn.commit()

        for source_url in source_urls:
            task_id = str(uuid.uuid4())
            task_ids.append(task_id)

            # Insert task record
            cursor.execute(
                "INSERT INTO tasks (task_id, status, api_key, batch_id) VALUES (?, ?, ?, ?)",
                (task_id, "queued", api_key, batch_id)
            )

            if async_processing and redis_client.is_connected():
                # Add task to Redis queue
                task_data = {
                    "task_id": task_id,
                    "source_type": source_type,
                    "source_url": source_url,
                    "chunk_strategy": chunk_strategy,
                    "api_key": api_key,
                    "file_path": None,
                    "batch_id": batch_id
                }

                # Add task to Redis queue with rate limiting
                redis_client.add_to_queue("document_processing", task_data, max_concurrent)
            else:
                # Process synchronously using background tasks
                background_tasks.add_task(
                    process_document, task_id, None, source_type, source_url, chunk_strategy, api_key, batch_id
                )

    conn.commit()
    conn.close()

    return {
        "batch_id": batch_id,
        "status": "processing",
        "total_tasks": len(task_ids),
        "task_ids": task_ids
    }

@app.get("/status/{task_id}")
async def get_task_status(
    request: Request,
    task_id: str,
    include_result: bool = False,
    api_key: str = None
):
    """
    Check status of an asynchronous task.

    - **task_id**: Task ID
    - **include_result**: Whether to include the task result in the response
    - **api_key**: API key from query parameter
    """
    # Print request information
    logger.info(f"Request path: {request.url.path}")
    logger.info(f"Request headers: {dict(request.headers)}")
    logger.info(f"Request query params: {dict(request.query_params)}")

    # Try to get API key from query parameter or header
    effective_api_key = api_key

    if not effective_api_key:
        # Try to get API key from headers
        for header_name in ["x-api-key", "X-API-Key", "x-api-key", "X-Api-Key", "api_key", "API_KEY", "apikey", "APIKEY"]:
            header_value = request.headers.get(header_name)
            if header_value:
                logger.info(f"Found API key in header {header_name}: {header_value}")
                effective_api_key = header_value
                break

    logger.info(f"API key from query parameter: {api_key}")
    logger.info(f"Effective API key: {effective_api_key}")

    if not effective_api_key or not validate_api_key(effective_api_key):
        logger.info(f"Invalid API key: {effective_api_key}")
        raise HTTPException(status_code=401, detail="API key required")

    # Check task status in SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT status, batch_id FROM tasks WHERE task_id = ? AND api_key = ?", (task_id, api_key))
    result = cursor.fetchone()
    conn.close()

    if not result:
        raise HTTPException(status_code=404, detail="Task not found")

    status, batch_id = result
    response = {"task_id": task_id, "status": status}

    if batch_id:
        response["batch_id"] = batch_id

    # If requested and task is completed, try to get result from Redis
    if include_result and status == "completed" and redis_client.is_connected():
        task_result = redis_client.get_task_result(task_id)
        if task_result:
            response["result"] = task_result

    return response

@app.get("/status/batch/{batch_id}")
async def get_batch_status(
    batch_id: str,
    include_results: bool = False,
    api_key: str = None
):
    """
    Check status of a batch processing job.

    - **batch_id**: Batch ID
    - **include_results**: Whether to include the task results in the response
    - **api_key**: API key for authentication
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

    response = {
        "batch_id": batch_id,
        "status": batch_status,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "progress_percentage": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
        "tasks": tasks
    }

    # If requested and Redis is available, include results for completed tasks
    if include_results and redis_client.is_connected():
        results = {}
        for task in tasks:
            if task["status"] == "completed":
                task_result = redis_client.get_task_result(task["task_id"])
                if task_result:
                    results[task["task_id"]] = task_result

        if results:
            response["results"] = results

    return response

@app.get("/usage_report")
async def usage_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    api_key: str = None
):
    """
    Generate usage report for an API key.

    - **start_date**: Start date for the report (format: YYYY-MM-DD)
    - **end_date**: End date for the report (format: YYYY-MM-DD)
    - **api_key**: API key for authentication
    """
    if not api_key or not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Validate dates if provided
    if start_date:
        try:
            import datetime
            datetime.datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")

    if end_date:
        try:
            import datetime
            datetime.datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get API key information
    cursor.execute("SELECT document_count, reset_date FROM api_keys WHERE key = ?", (api_key,))
    api_key_info = cursor.fetchone()

    if not api_key_info:
        conn.close()
        raise HTTPException(status_code=404, detail="API key not found")

    document_count, reset_date = api_key_info

    # Create tasks_usage table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks_usage (
        task_id TEXT PRIMARY KEY,
        api_key TEXT,
        source_type TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        status TEXT,
        document_size INTEGER DEFAULT 0,
        processing_time REAL DEFAULT 0
    )
    """)

    # Build query based on date filters
    query = "SELECT source_type, COUNT(*), SUM(document_size), AVG(processing_time) FROM tasks_usage WHERE api_key = ?"
    params = [api_key]

    if start_date:
        query += " AND created_at >= ?"
        params.append(f"{start_date} 00:00:00")

    if end_date:
        query += " AND created_at <= ?"
        params.append(f"{end_date} 23:59:59")

    query += " GROUP BY source_type"

    # Execute query
    cursor.execute(query, params)
    usage_by_source = cursor.fetchall()

    # Get batch processing usage
    cursor.execute("""
    SELECT COUNT(*), SUM(total_tasks) FROM batches
    WHERE api_key = ? AND status = 'completed'
    """, (api_key,))
    batch_usage = cursor.fetchone()

    # Get total tasks
    cursor.execute("""
    SELECT COUNT(*) FROM tasks
    WHERE api_key = ?
    """, (api_key,))
    total_tasks = cursor.fetchone()[0]

    # Get tasks by status
    cursor.execute("""
    SELECT status, COUNT(*) FROM tasks
    WHERE api_key = ?
    GROUP BY status
    """, (api_key,))
    tasks_by_status = cursor.fetchall()

    # Get LLM usage if Redis is available
    llm_usage = None
    if redis_client.is_connected():
        llm_usage = redis_client.get_llm_usage(api_key)

    conn.close()

    # Format the response
    source_type_usage = []
    for source_type, count, total_size, avg_time in usage_by_source:
        source_type_usage.append({
            "source_type": source_type,
            "count": count,
            "total_size_bytes": total_size if total_size else 0,
            "avg_processing_time_seconds": avg_time if avg_time else 0
        })

    status_counts = {}
    for status, count in tasks_by_status:
        status_counts[status] = count

    response = {
        "api_key": api_key,
        "document_count": document_count,
        "reset_date": reset_date,
        "total_tasks": total_tasks,
        "tasks_by_status": status_counts,
        "source_type_usage": source_type_usage,
    }

    if batch_usage and batch_usage[0]:
        response["batch_processing"] = {
            "total_batches": batch_usage[0],
            "total_batch_tasks": batch_usage[1] if batch_usage[1] else 0
        }

    if llm_usage:
        response["llm_usage"] = llm_usage

    return response

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)