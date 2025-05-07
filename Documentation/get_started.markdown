# Getting Started Guide for Document Parsing API

This guide details the step-by-step process to build a self-hosted, zero-cost document parsing API that processes all file types (e.g., PDF, DOCX, JPG) into LLM-ready JSON outputs, with optional Phi-4-multimodal Agentic AI, support for any LLM model, zero data retention, and enterprise features (three-way matching, advanced table parsing, chunking/deduplication, asynchronous processing). The API uses FastAPI, Unstructured.io, LlamaIndex, and open-source tools, with two Docker images (full and slim) for deployment.

## Prerequisites

- **Hardware**: Server with 8-16GB RAM (slim: 4-8GB), 10-20GB storage (slim: 5-10GB), 4+ CPU cores (slim: 2+).
- **Software**:
  - Docker (v20.10+)
  - Git (v2.30+)
  - Python 3.10
  - Cython (v3.0+)
  - GitHub account
- **Files**: Phi-4-multimodal model in GGUF format (~2.5-4GB, download from Microsoft Research or convert via llama.cpp).
- **Knowledge**: Basic Python, FastAPI, Docker, and command-line skills.

## Step-by-Step Implementation

### Step 1: Set Up Project Repository (Day 1-2)
- **Objective**: Create a GitHub repository for version control and documentation.
- **Tasks**:
  1. Create a new repository named `yourusername/your-api` on GitHub.
  2. Enable GitHub Pages for free documentation hosting.
  3. Initialize with a `README.md`:
     ```markdown
     # Document Parsing API
     A self-hosted API for parsing documents into LLM-ready JSON outputs with zero data retention.
     ```
  4. Clone the repository locally:
     ```bash
     git clone https://github.com/yourusername/your-api.git
     cd your-api
     ```
- **Output**: GitHub repository with basic `README.md`.

### Step 2: Implement FastAPI Application (Day 3-7)
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
     pip install fastapi uvicorn unstructured[all-docs] llama-index langchain langchain-openai langchain-community chromadb cython requests beautifulsoup4 celery redis transformers
     ```
  3. Implement `src/main.py` with the FastAPI app (use the provided code from Artifact ID: `0b15eaab-655b-40fd-b24d-6344dd7395b4`, updated below to include new features):
     - Endpoints: `/parse`, `/query`, `/generate_schema`, `/agent`, `/match`, `/status`.
     - Features: Unstructured.io for parsing, LlamaIndex for RAG, langchain for LLM flexibility, Celery/Redis for async processing, TableTransformer for table parsing, zero data retention.
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

### Step 3: Prepare Phi-4-Multimodal Model (Day 8-10)
- **Objective**: Convert and configure Phi-4-multimodal for use with Ollama in the full Docker image.
- **Tasks**:
  1. Install llama.cpp for GGUF conversion:
     ```bash
     git clone https://github.com/ggerganov/llama.cpp
     cd llama.cpp
     make
     ```
  2. Convert Phi-4-multimodal to GGUF (replace `/path/to/phi-4-multimodal` with the model path):
     ```bash
     python convert.py --outfile phi-4-multimodal.gguf /path/to/phi-4-multimodal
     ```
  3. Create a `Modelfile` for Ollama:
     ```bash
     echo "FROM ./phi-4-multimodal.gguf" > Modelfile
     ```
  4. Test Ollama locally:
     ```bash
     docker run -v $(pwd):/models -p 11434:11434 ollama/ollama
     ollama create phi-4-multimodal -f /models/Modelfile
     ollama run phi-4-multimodal
     ```
- **Output**: Phi-4-multimodal GGUF model and Modelfile ready for Docker integration.

### Step 4: Build Docker Images (Day 11-14)
- **Objective**: Create two Docker images (full and slim) for deployment.
- **Tasks**:
  1. Create `Dockerfile` for the full image:
     ```dockerfile
     FROM python:3.10-slim
     WORKDIR /app
     RUN apt-get update && apt-get install -y tesseract-ocr libtesseract-dev poppler-utils sqlite3 gcc && rm -rf /var/lib/apt/lists/*
     RUN pip install --no-cache-dir fastapi uvicorn unstructured[all-docs] llama-index langchain langchain-openai langchain-community chromadb cython requests beautifulsoup4 celery redis transformers
     RUN useradd -m appuser
     COPY src/main.py src/main_cy.c src/main_cy.cpython-*.so .
     COPY phi-4-multimodal.gguf Modelfile .
     RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
     RUN curl -fsSL https://ollama.com/install.sh | sh
     RUN ollama serve & sleep 5 && ollama create phi-4-multimodal -f Modelfile
     USER appuser
     EXPOSE 8000
     CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
     ```
  2. Create `Dockerfile.slim` for the slim image:
     ```dockerfile
     FROM python:3.10-slim
     WORKDIR /app
     RUN apt-get update && apt-get install -y tesseract-ocr libtesseract-dev poppler-utils sqlite3 gcc && rm -rf /var/lib/apt/lists/*
     RUN pip install --no-cache-dir unstructured[all-docs] llama-index fastapi uvicorn cython requests beautifulsoup4
     RUN useradd -m appuser
     COPY src/main.py src/main_cy.c src/main_cy.cpython-*.so .
     USER appuser
     EXPOSE 8000
     CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
     ```
  3. Build and test images:
     ```bash
     docker build -t yourusername/your-api:latest -f Dockerfile .
     docker build -t yourusername/your-api:slim -f Dockerfile.slim .
     docker run -d -p 8000:8000 -e USE_LLM=false yourusername/your-api:slim
     docker run -d -p 8000:8000 -e USE_LLM=true -e LLM_MODEL=phi-4-multimodal yourusername/your-api:latest
     ```
  4. Push to Docker Hub:
     ```bash
     docker push yourusername/your-api:latest
     docker push yourusername/your-api:slim
     ```
- **Output**: Two Docker images (full: ~4-4.5GB, slim: ~2GB) hosted on Docker Hub.

### Step 5: Integrate Data Source Connectors (Day 15-21)
- **Objective**: Enable parsing from diverse sources (files, SQL, APIs, web, cloud).
- **Tasks**:
  1. Implement `parse_document` in `main.py` to handle `source_type` (file, sql, api, web, cloud):
     - File: Use Unstructured.io (`partition`).
     - SQL: Use LlamaIndex’s `SQLDatabaseReader`.
     - API: Use `requests.get`.
     - Web: Use LlamaIndex’s `BeautifulSoupWebReader`.
     - Cloud: Use external libraries (e.g., `boto3` for S3, `google-cloud-storage` for Google Drive).
  2. Test connectors:
     - File: `curl -X POST -F "file=@sample.pdf" "http://localhost:8000/parse?api_key=123e4567-e89b-12d3-a456-426614174000"`
     - SQL: `curl -X POST "http://localhost:8000/parse?api_key=123e4567-e89b-12d3-a456-426614174000&source_type=sql&source_url=sqlite:///test.db"`
     - Web: `curl -X POST "http://localhost:8000/parse?api_key=123e4567-e89b-12d3-a456-426614174000&source_type=web&source_url=https://example.com"`
- **Output**: Fully functional `/parse` endpoint supporting all data sources.

### Step 6: Enhance Parsing and Processing Features (Day 22-28)
- **Objective**: Add advanced table parsing, chunking/deduplication, three-way matching, and asynchronous processing.
- **Tasks**:
  1. **Table Parsing**:
     - Install TableTransformer:
       ```bash
       pip install transformers
       ```
     - Update `parse_document` to use TableTransformer for tables:
       ```python
       from transformers import TableTransformerForObjectDetection
       table_model = TableTransformerForObjectDetection.from_pretrained("microsoft/table-transformer-detection")
       ```
     - Refine table outputs with Phi-4-multimodal:
       ```python
       prompt = f"Reorganize this table JSON to match human reading order: {table_json}"
       ```
  2. **Chunking/Deduplication**:
     - Add `chunk_strategy` to `/parse` (sentence, paragraph, fixed).
     - Implement deduplication using LlamaIndex’s vector store:
       ```python
       from llama_index.core import VectorStoreIndex
       index = VectorStoreIndex.from_documents(documents, similarity_threshold=0.9)
       ```
  3. **Three-Way Matching**:
     - Implement `/match` endpoint (already in `main.py`).
     - Test with sample invoice, PO, GRN files:
       ```bash
       curl -X POST "http://localhost:8000/match?api_key=123e4567-e89b-12d3-a456-426614174000" -F "files=@invoice.pdf" -F "files=@po.pdf" -F "files=@grn.pdf"
       ```
  4. **Asynchronous Processing**:
     - Install Redis locally:
       ```bash
       docker run -d -p 6379:6379 redis
       ```
     - Configure Celery in `main.py` (already included).
     - Test async `/parse`:
       ```bash
       curl -X POST "http://localhost:8000/parse?api_key=123e4567-e89b-12d3-a456-426614174000" -F "file=@large.pdf"
       ```
- **Output**: Enhanced API with enterprise-grade features.

### Step 7: Test Implementation (Day 29-35)
- **Objective**: Ensure all features work as expected.
- **Tasks**:
  1. Set up GitHub Actions for automated testing:
     ```yaml
     name: CI
     on: [push]
     jobs:
       test:
         runs-on: ubuntu-latest
         steps:
           - uses: actions/checkout@v3
           - name: Set up Python
             uses: actions/setup-python@v4
             with:
               python-version: '3.10'
           - name: Install dependencies
             run: pip install -r requirements.txt
           - name: Run tests
             run: pytest tests/
     ```
  2. Create `tests/test_api.py`:
     ```python
     import requests
     def test_parse():
         files = {"file": open("sample.pdf", "rb")}
         response = requests.post("http://localhost:8000/parse?api_key=123e4567-e89b-12d3-a456-426614174000", files=files)
         assert response.status_code == 200
         assert "elements" in response.json()
     ```
  3. Test all endpoints and features (parsing, RAG, schema generation, matching, async tasks, zero data retention).
- **Output**: Verified API functionality via automated tests.

### Step 8: Document and Deploy (Day 36-42)
- **Objective**: Finalize documentation and distribute the API.
- **Tasks**:
  1. Update `README.md` (as per project plan):
     ```markdown
     # Document Parsing API
     A self-hosted API for parsing documents into LLM-ready JSON outputs with zero data retention.

     ## Setup
     1. Pull image: `docker pull yourusername/your-api:slim` or `yourusername/your-api:latest`
     2. Run slim: `docker run -d -p 8000:8000 -e USE_LLM=false yourusername/your-api:slim`
     3. Run full: `docker run -d -p 8000:8000 -e USE_LLM=true -e LLM_MODEL=phi-4-multimodal yourusername/your-api:latest`
     4. Custom LLM: `docker run -e USE_LLM=true -e LLM_ENDPOINT=http://localhost:9000 -e OPENAI_API_KEY=sk-...`
     5. Offline: Save (`docker save yourusername/your-api > your-api.tar`), load (`docker load -i your-api.tar`).

     ## Endpoints
     - **POST /parse**: Parse file (any type) or data source with chunking (e.g., `chunk_strategy=sentence`). Returns JSON (e.g., `{"elements": [{"type": "Table", "text": "Row1,Col1"}]}`).
     - **POST /query**: Query indexed documents (LLM required).
     - **POST /generate_schema**: Generate custom JSON schema (LLM required).
     - **POST /agent**: Perform agentic tasks (LLM required).
     - **POST /match**: Three-way matching for invoices, POs, GRNs (LLM required).
     - **GET /status/{task_id}**: Check async task status.

     ## Data Sources
     - Files: PDF, DOCX, JPG, PNG, PPTX, TXT, etc.
     - SQL: PostgreSQL, MySQL, SQLite.
     - APIs: REST endpoints.
     - Web: HTML pages.
     - Cloud: Google Drive, S3, Dropbox.
     ```
  2. Publish documentation on GitHub Pages.
  3. Push final images to Docker Hub.
  4. Set up GitHub Issues for client support.
- **Output**: Deployed API with comprehensive documentation.

## Post-Implementation
- **Feedback and Optimization** (Week 6):
  - Gather client feedback via GitHub Issues.
  - Fix bugs and optimize performance (e.g., reduce Docker image size, improve parsing speed).
- **Future Enhancements**:
  - Add connectors (e.g., OneDrive, Notion).
  - Implement caching for faster parsing.
  - Support batch processing.
  - Add `/usage_report` endpoint.

## Cost Breakdown
- **Development**: $0 (open-source tools: FastAPI, Unstructured.io, LlamaIndex, langchain, Celery, Redis, TableTransformer).
- **Hosting**: $0 (GitHub Pages, Docker Hub, GitHub Actions).
- **Client Costs**: $0 if using existing hardware; ~$30-100/month for cloud (e.g., AWS t3.large).

## Notes
- Ensure **zero data retention** by verifying temporary files are deleted (`os.unlink(tmp_path)`) and SQLite stores only metadata.
- Test custom LLM integration with `LLM_ENDPOINT` (e.g., OpenAI, Hugging Face).
- Monitor resource usage (full image: 8-16GB RAM; slim: 4-8GB RAM) during testing.