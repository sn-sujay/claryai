# Getting Started Guide for ClaryAI

This guide details the step-by-step process to build a self-hosted, zero-cost document parsing API that processes all file types (e.g., PDF, DOCX, JPG) into LLM-ready JSON outputs, with optional Phi-4-multimodal Agentic AI, support for any LLM model, zero data retention, and enterprise features (three-way matching, advanced table parsing, chunking/deduplication, asynchronous processing). The API uses FastAPI, Unstructured.io, LlamaIndex, and open-source tools, with two Docker images (full and slim) for deployment.

## Prerequisites

- **Hardware**: Server with 8-16GB RAM (slim: 4-8GB), 10-20GB storage (slim: 5-10GB), 4+ CPU cores (slim: 2+).
- **Software**:
  - Docker (v20.10+)
  - Docker Compose (v2.0+)
  - Git (v2.30+)
  - Python 3.10
  - Cython (v3.0+)
  - GitHub account
- **Files**: Phi-4-multimodal model in GGUF format (~2.5-4GB, download from Microsoft Research or convert via llama.cpp).
- **Knowledge**: Basic Python, FastAPI, Docker, and command-line skills.

## Step-by-Step Implementation

### Step 1: Set Up Project Repository

- **Objective**: Create a GitHub repository for version control and documentation.
- **Tasks**:
  1. Create a new repository named `yourusername/claryai` on GitHub.
  2. Enable GitHub Pages for free documentation hosting.
  3. Initialize with a `README.md`:
     ```markdown
     # ClaryAI
     A self-hosted API for parsing documents into LLM-ready JSON outputs with zero data retention.
     ```
  4. Clone the repository locally:
     ```bash
     git clone https://github.com/yourusername/claryai.git
     cd claryai
     ```
- **Output**: GitHub repository with basic `README.md`.

### Step 2: Implement FastAPI Application

- **Objective**: Develop the core FastAPI app with endpoints for parsing, querying, schema generation, three-way matching, and async task status.
- **Tasks**:
  1. Create a project directory structure:
     ```bash
     mkdir -p src
     touch src/main.py src/main_cy.pyx
     ```
  2. Install Python dependencies:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     pip install fastapi uvicorn unstructured[all-docs] llama-index langchain langchain-openai langchain-community chromadb cython requests beautifulsoup4 redis pandas
     ```
  3. Implement `src/main.py` with the FastAPI app:
     - Endpoints: `/parse`, `/query`, `/generate_schema`, `/agent`, `/match`, `/status`.
     - Features: Unstructured.io for parsing, LlamaIndex for RAG, langchain for LLM flexibility, Redis for async processing and caching, TableTransformer for table parsing, zero data retention.
  4. Compile `main.py` to Cython for dependency hiding:
     ```bash
     cp src/main.py src/main_cy.pyx
     cythonize -i src/main_cy.pyx
     ```
  5. Test locally:
     ```bash
     uvicorn src.main:app --host 0.0.0.0 --port 8000
     ```
     - Test `/parse` with a sample PDF:
       ```bash
       curl -X POST "http://localhost:8000/parse?api_key=123e4567-e89b-12d3-a456-426614174000" -F "file=@sample.pdf"
       ```
- **Output**: Functional FastAPI app with all endpoints, ready for Dockerization.

### Step 3: Implement Table Parsing

- **Objective**: Create a custom table parser for extracting structured data from tables.
- **Tasks**:
  1. Create a table parser module:
     ```bash
     touch src/table_parser.py
     ```
  2. Implement the TableTransformer class:
     ```python
     class TableTransformer:
         def __init__(self):
             pass
             
         def parse_text_table(self, text):
             # Parse text tables
             # ...
             
         def parse_html_table(self, html):
             # Parse HTML tables
             # ...
             
         def transform(self, df):
             # Transform pandas DataFrame
             # ...
     ```
  3. Update `main.py` to use the TableTransformer.
  4. Test table parsing with sample tables:
     ```bash
     curl -X POST "http://localhost:8000/parse?api_key=123e4567-e89b-12d3-a456-426614174000" -F "file=@sample_table.txt"
     ```
- **Output**: Enhanced table parsing capabilities.

### Step 4: Implement Redis Integration

- **Objective**: Add Redis for caching and asynchronous processing.
- **Tasks**:
  1. Create Redis client module:
     ```bash
     touch src/redis_client.py
     ```
  2. Implement the RedisClient class:
     ```python
     class RedisClient:
         def __init__(self):
             # Initialize Redis connection
             # ...
             
         def store_task_result(self, task_id, result, expiry=3600):
             # Store task result in Redis
             # ...
             
         def get_task_result(self, task_id):
             # Get task result from Redis
             # ...
             
         def cache_llm_response(self, prompt, response, expiry=86400):
             # Cache LLM response
             # ...
             
         def get_cached_llm_response(self, prompt):
             # Get cached LLM response
             # ...
             
         def add_to_queue(self, queue_name, item):
             # Add item to queue
             # ...
             
         def get_from_queue(self, queue_name):
             # Get item from queue
             # ...
     ```
  3. Update `main.py` to use the RedisClient.
  4. Test Redis integration:
     ```bash
     docker run -d -p 6379:6379 redis
     curl -X POST "http://localhost:8000/query?api_key=123e4567-e89b-12d3-a456-426614174000&use_cache=true" -d '{"query": "What is in this document?"}'
     ```
- **Output**: Redis integration for caching and queuing.

### Step 5: Implement Worker for Asynchronous Processing

- **Objective**: Create a worker for processing documents asynchronously.
- **Tasks**:
  1. Create worker module:
     ```bash
     touch src/worker.py
     ```
  2. Implement the worker:
     ```python
     def main():
         # Main worker function
         while True:
             # Get task from queue
             task = redis_client.get_from_queue("document_processing")
             if task:
                 # Process task
                 process_document_task(task)
             else:
                 # Sleep if no tasks
                 time.sleep(1)
     ```
  3. Create Docker Compose file:
     ```yaml
     version: '3.8'
     services:
       claryai:
         # API server
       worker:
         # Worker for async processing
       redis:
         # Redis for caching and queuing
       redis-commander:
         # Redis UI for monitoring
     ```
  4. Test asynchronous processing:
     ```bash
     curl -X POST "http://localhost:8000/parse?api_key=123e4567-e89b-12d3-a456-426614174000&async_processing=true" -F "file=@large.pdf"
     ```
- **Output**: Asynchronous processing with worker.

### Step 6: Implement Three-Way Matching

- **Objective**: Add three-way matching for invoices, purchase orders, and goods receipt notes.
- **Tasks**:
  1. Create sample files for testing:
     ```bash
     echo "INVOICE..." > sample_invoice.txt
     echo "PURCHASE ORDER..." > sample_po.txt
     echo "GOODS RECEIPT NOTE..." > sample_grn.txt
     ```
  2. Implement the `/match` endpoint:
     ```python
     @app.post("/match")
     async def three_way_match(
         files: List[UploadFile] = File(None),
         invoice_task_id: Optional[str] = None,
         po_task_id: Optional[str] = None,
         grn_task_id: Optional[str] = None,
         api_key: str = None
     ):
         # Implementation...
     ```
  3. Test three-way matching:
     ```bash
     curl -X POST "http://localhost:8000/match?api_key=123e4567-e89b-12d3-a456-426614174000" -F "files=@sample_invoice.txt" -F "files=@sample_po.txt" -F "files=@sample_grn.txt"
     ```
- **Output**: Three-way matching functionality.

### Step 7: Dockerize the Application

- **Objective**: Create Docker images for the application.
- **Tasks**:
  1. Create Dockerfile for the API server:
     ```dockerfile
     FROM python:3.10-slim
     WORKDIR /app
     RUN apt-get update && apt-get install -y tesseract-ocr
     RUN pip install --no-cache-dir unstructured[all-docs] llama-index fastapi uvicorn cython requests beautifulsoup4 pandas redis sqlalchemy
     COPY src/main.py .
     COPY src/table_parser.py .
     COPY src/redis_client.py .
     RUN cp main.py main_cy.pyx && cythonize -i main_cy.pyx
     USER appuser
     EXPOSE 8000
     CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
     ```
  2. Create Dockerfile for the worker:
     ```dockerfile
     FROM python:3.10-slim
     WORKDIR /app
     RUN apt-get update && apt-get install -y tesseract-ocr
     RUN pip install --no-cache-dir unstructured[all-docs] llama-index fastapi uvicorn requests beautifulsoup4 pandas redis sqlalchemy
     COPY src/worker.py .
     COPY src/table_parser.py .
     COPY src/redis_client.py .
     USER appuser
     CMD ["python", "worker.py"]
     ```
  3. Update Docker Compose file:
     ```yaml
     version: '3.8'
     services:
       claryai:
         build:
           context: .
           dockerfile: Dockerfile
         ports:
           - "8080:8000"
         environment:
           - REDIS_HOST=redis
       worker:
         build:
           context: .
           dockerfile: Dockerfile.worker
         environment:
           - REDIS_HOST=redis
       redis:
         image: redis:alpine
       redis-commander:
         image: rediscommander/redis-commander:latest
         ports:
           - "8081:8081"
     ```
  4. Build and run with Docker Compose:
     ```bash
     docker-compose up -d
     ```
- **Output**: Dockerized application with API server, worker, Redis, and Redis Commander.

### Step 8: Test and Document

- **Objective**: Test the application and update documentation.
- **Tasks**:
  1. Test all endpoints:
     - `/parse` with async processing
     - `/query` with caching
     - `/match` with three-way matching
     - `/status` with result inclusion
  2. Update README.md with new features.
  3. Create a test script:
     ```python
     #!/usr/bin/env python3
     import requests
     
     # Test async processing
     response = requests.post(
         "http://localhost:8080/parse",
         params={"api_key": "123e4567-e89b-12d3-a456-426614174000", "async_processing": "true"},
         files={"file": open("sample.pdf", "rb")}
     )
     print(response.json())
     ```
  4. Document the API endpoints and features.
- **Output**: Tested application with comprehensive documentation.

## Cost Breakdown
- **Development**: $0 (open-source tools: FastAPI, Unstructured.io, LlamaIndex, Redis).
- **Hosting**: $0 (GitHub Pages, Docker Hub, GitHub Actions).
- **Client Costs**: $0 if using existing hardware; ~$30-100/month for cloud (e.g., AWS t3.large).

## Notes
- Ensure **zero data retention** by verifying temporary files are deleted (`os.unlink(tmp_path)`) and SQLite stores only metadata.
- Test custom LLM integration with `LLM_ENDPOINT` (e.g., OpenAI, Hugging Face).
- Monitor resource usage (full image: 8-16GB RAM; slim: 4-8GB RAM) during testing.
