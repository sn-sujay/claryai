# Document Parsing API Comprehensive Project Plan

## 1. Project Overview

### 1.1 Idea

Develop a **self-hosted, zero-cost API** to parse documents of **all file types** (e.g., PDF, DOCX, JPG, PNG, PPTX, TXT) into **structured, LLM-ready JSON outputs** for enterprise use cases (e.g., financial reports, data extraction). The API uses **Unstructured.io** for document parsing, **LlamaIndex** for retrieval-augmented generation (RAG), and **Phi-4-multimodal** (Microsoft, pre-installed, optional) as an **Agentic AI** for autonomous text refinement, multimodal querying, and **custom JSON schema generation**. It supports **any LLM model** via a generic interface, **offline operation**, **dependency hiding** via Cython, **extensive data source connectors**, **zero data retention**, **three-way matching**, **advanced table parsing**, **chunking/deduplication**, and **asynchronous processing**, with **two Docker images** (with/without Phi-4-multimodal), all at **no cost** to you.

### 1.2 Objectives

- **Functionality**: Parse documents into structured JSON; enable Agentic AI for refinement, RAG, schema generation, and three-way matching.
- **Output**: JSON-only (e.g., `{"elements": [{"type": "Title", "text": "Report"}]}`), with custom schemas (e.g., `{"invoice_number": "INV123", "total_amount": "$1000"}`).
- **File Types**: All types (PDF, DOCX, JPG, PNG, PPTX, TXT, etc.) via Unstructured.io.
- **Data Sources**: Unstructured.io and LlamaIndex connectors (files, APIs, databases) with interconnected processing.
- **LLM Flexibility**: Support any LLM model via `langchain` adapters, with Phi-4-multimodal pre-installed.
- **Agentic AI**: Use Phi-4-multimodal for autonomous tasks (e.g., error correction, schema design, matching).
- **Cost**: $0 for development/hosting (open-source tools, Docker Hub, GitHub Pages); clients provide hardware ($30-100/month cloud if not self-hosted).
- **Security**: Offline, self-hosted, hidden dependencies, secure API key validation.
- **Privacy**: Phi-4-multimodal (U.S.-developed) ensures minimal concerns; no data leaves client infrastructure.
- **Zero Data Retention**: No document data stored post-processing; temporary files deleted immediately.

## 2. Technical Implementation

### 2.1 Architecture

- **Framework**: FastAPI for RESTful endpoints (`/parse`, `/query`, `/generate_schema`, `/agent`, `/match`, `/status`).
- **Parsing**: Unstructured.io for OCR/layout analysis, enhanced with TableTransformer for advanced table parsing.
- **Indexing/Querying**: LlamaIndex for RAG with configurable chunking and deduplication, using ChromaDB as the vector store.
- **LLM**: Phi-4-multimodal (pre-installed via Ollama, optional) as Agentic AI; generic LLM interface via `langchain` for any model (e.g., Hugging Face, OpenAI, custom).
- **Usage Tracking**: SQLite for API key validation and document limits (e.g., 1,000/month).
- **Asynchronous Processing**: Celery with Redis for large documents and batch requests.
- **Deployment**: Two Docker images (full: with Phi-4-multimodal; slim: without), self-hosted, offline-capable.
- **Security**: Cython compilation to hide dependencies; log filtering to obscure model names.

### 2.2 Key Components

- **Endpoints**:
  - **POST `/parse`**:
    - **Input**: File (any type), API key (UUID), `source_type` (file, sql, api, web, cloud), `source_url` (optional), `chunk_strategy` (sentence, paragraph, fixed).
    - **Output**: JSON with structured elements (e.g., `{"elements": [{"type": "Table", "text": "Row1,Col1"}], "status": "parsed"}`).
    - **With LLM**: Agentic AI refines outputs, applies chunking/deduplication, indexes for RAG (e.g., `{"status": "indexed"}`).
  - **POST `/query`**:
    - **Input**: Query string (e.g., “Summarize the table”), API key.
    - **Output**: JSON response (e.g., `{"response": "Revenue is $1M"}`).
    - **Availability**: Only if `USE_LLM=true`.
  - **POST `/generate_schema`**:
    - **Input**: File/parsed elements, schema description (e.g., “Extract invoice number and total amount”), API key.
    - **Output**: Custom JSON schema (e.g., `{"schema": {"invoice_number": "INV123", "total_amount": "$1000"}}`).
    - **Availability**: Only if `USE_LLM=true`.
  - **POST `/agent`**:
    - **Input**: Task description (e.g., “Parse, refine, generate schema”), file/source, API key.
    - **Output**: JSON with refined elements, schema, and query plan (e.g., `{"elements": [...], "schema": {...}, "query_plan": "..."}`).
    - **Availability**: Only if `USE_LLM=true`.
  - **POST `/match`**:
    - **Input**: Multiple files (e.g., invoice, PO, GRN), API key.
    - **Output**: JSON with match results and actions (e.g., `{"mismatch": "Invoice #123 differs from PO", "action": "Email supplier"}`).
    - **Availability**: Only if `USE_LLM=true`.
  - **GET `/status/{task_id}`**:
    - **Input**: Task ID from async processing, API key.
    - **Output**: JSON with task status (e.g., `{"task_id": "abc123", "status": "completed"}`).
- **Phi-4-Multimodal as Agentic AI**:
  - **Refinement**: Autonomously corrects OCR errors, structures tables, ensures reading order.
  - **RAG**: Plans and executes complex queries across text/images.
  - **Schema Generation**: Creates custom JSON schemas from natural language or templates.
  - **Three-Way Matching**: Compares documents for consistency and suggests actions.
  - **Optional**: Enabled via `USE_LLM=true`.
- **LLM Flexibility**:
  - Pre-installed: Phi-4-multimodal via Ollama.
  - Custom Models: `LLM_MODEL` (Ollama-compatible, e.g., `llama3.1`), `LLM_ENDPOINT` (external APIs), or `langchain` adapters for any model.
- **Data Source Connectors**:
  - **Unstructured.io**:
    - Local files: All types (PDF, DOCX, JPG, PNG, PPTX, TXT, HTML, CSV, etc.).
    - Integrations: Label Studio, LangChain, Weaviate (processing, not pulling).
  - **LlamaIndex**:
    - Files: PDF, DOCX, PNG, PPTX, TXT, JSON, CSV via `SimpleDirectoryReader`.
    - APIs: REST endpoints via custom readers.
    - Databases: SQL (PostgreSQL, MySQL, SQLite) via `SQLDatabaseReader`.
    - Cloud Storage: Google Drive, S3, Dropbox (via external libraries).
    - Web: HTML pages via `BeautifulSoupWebReader`.
    - Vector Stores: ChromaDB, Weaviate, Pinecone, Qdrant.
  - **Interconnected Processing**:
    - Flow: LlamaIndex pulls data (e.g., SQL, APIs) → Unstructured.io parses into JSON (if file-based) → LlamaIndex indexes with chunking/deduplication → LLM refines, generates schemas, or matches documents.
- **Output Format**:
  - JSON-only (e.g., `{"elements": [{"type": "Table", "text": "Row1,Col1"}]}`).
  - Custom schemas via `/generate_schema` or `/agent`.

### 2.3 Implementation Details

- **FastAPI App** (`main.py`):
  - Handles file uploads, data source pulling, parsing, indexing, querying, schema generation, three-way matching, and agentic tasks.
  - Validates API keys using SQLite (stores only metadata: API key, document count, reset date).
  - Processes all file types with Unstructured.io (`auto` strategy) and TableTransformer for tables.
  - Ensures **zero data retention** by deleting temporary files post-processing and storing no document content.
  - Supports asynchronous processing with Celery and Redis.
  - Supports any LLM via `langchain` adapters:

    ```python
    from langchain_core.language_models import BaseLanguageModel
    from langchain_openai import ChatOpenAI
    from langchain_community.llms import HuggingFaceEndpoint
    from celery import Celery
    app_celery = Celery('tasks', broker='redis://localhost:6379/0')
    if USE_LLM:
        if LLM_ENDPOINT:
            if "openai" in LLM_ENDPOINT:
                llm = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=LLM_ENDPOINT)
            else:
                llm = HuggingFaceEndpoint(endpoint_url=LLM_ENDPOINT)
        else:
            llm = Ollama(model=LLM_MODEL or "phi-4-multimodal", request_timeout=30.0)
    ```
  - Example for `/match`:

    ```python
    @app.post("/match")
    async def three_way_match(files: List[UploadFile] = File(None), api_key: str = None):
        if not USE_LLM:
            raise HTTPException(status_code=400, detail="LLM integration is disabled")
        if not api_key or not validate_api_key(api_key):
            raise HTTPException(status_code=401, detail="API key required")
        elements_list = [await parse_document(file) for file in files]
        prompt = f"Compare these documents for three-way matching (invoice, PO, GRN): {json.dumps(elements_list)}. Flag mismatches and suggest actions."
        response = await llm.acomplete(prompt) if hasattr(llm, 'acomplete') else llm.complete(prompt)
        return json.loads(str(response))
    ```
  - Example for async `/parse`:

    ```python
    from fastapi import BackgroundTasks
    @app.post("/parse")
    async def parse_document_endpoint(background_tasks: BackgroundTasks, file: UploadFile = File(None), api_key: str = None, source_type: str = "file", source_url: str = None, chunk_strategy: str = "paragraph"):
        if not api_key or not validate_api_key(api_key):
            raise HTTPException(status_code=401, detail="API key required")
        task_id = str(uuid.uuid4())
        background_tasks.add_task(process_document, task_id, file, source_type, source_url, chunk_strategy, api_key)
        return {"task_id": task_id, "status": "processing"}
    ```
- **Zero Data Retention**:
  - Temporary files deleted immediately after processing (`os.unlink(tmp_path)`).
  - SQLite stores only usage metadata (no document content).
  - No persistent storage of parsed data, query results, or matching outputs.
- **Docker Images**:
  - **Full Image**:
    - Base: `python:3.10-slim`.
    - Installs Unstructured.io, LlamaIndex, FastAPI, Ollama, Phi-4-multimodal (GGUF, ~2.5-4GB), langchain, Celery, Redis, TableTransformer.
    - Size: ~4-4.5GB compressed, ~10-12GB uncompressed.
  - **Slim Image**:
    - Excludes Ollama, Phi-4-multimodal, Celery, Redis, TableTransformer.
    - Size: ~2GB compressed, ~5GB uncompressed.
- **Cython Compilation**:
  - Compiles `main.py` to `main_cy.c`:

    ```bash
    cythonize -i main_cy.pyx
    ```
  - Filters logs:

    ```python
    logging.getLogger().addFilter(lambda record: "phi-4-multimodal" not in record.msg.lower())
    ```

### 2.4 Resource Requirements

- **Slim Image**: 4-8GB RAM, 5-10GB storage, 2+ CPU cores.
- **Full Image**: 8-16GB RAM, 10-20GB storage, 4+ CPU cores.

## 3. Client Flow

- **Setup**:
  - Pull image: `docker pull yourusername/your-api:slim` or `yourusername/your-api:latest`.
  - Run slim: `docker run -d -p 8000:8000 -e USE_LLM=false yourusername/your-api:slim`.
  - Run full: `docker run -d -p 8000:8000 -e USE_LLM=true -e LLM_MODEL=phi-4-multimodal yourusername/your-api:latest`.
  - Custom LLM: `docker run -e USE_LLM=true -e LLM_ENDPOINT=http://localhost:9000 -e OPENAI_API_KEY=sk-...`.
  - Offline: Save/load image (`docker save`, `docker load`).
- **Usage**:
  - **Parse Documents**: POST to `/parse` with file or data source (e.g., `source_type=sql`, `source_url=sqlite:///db`, `chunk_strategy=sentence`).
  - **Query Documents** (full image): POST to `/query` (e.g., “Summarize the table”).
  - **Generate Schema** (full image): POST to `/generate_schema` (e.g., “Extract invoice number and total amount”).
  - **Agentic Tasks** (full image): POST to `/agent` (e.g., “Parse, refine, generate schema”).
  - **Three-Way Matching** (full image): POST to `/match` with multiple files (e.g., invoice, PO, GRN).
  - **Check Status**: GET `/status/{task_id}` for async tasks.
- **Customization**:
  - Use any LLM: Set `LLM_MODEL` or `LLM_ENDPOINT` with credentials (e.g., `OPENAI_API_KEY`).
  - Configure chunking: Set `chunk_strategy` for RAG optimization.

## 4. Technical Infrastructure

- **Open-Source/Free Tools**:
  - FastAPI (MIT), Unstructured.io (Apache 2.0), LlamaIndex (MIT), Phi-4-multimodal (MIT, assumed), Ollama (MIT), langchain (MIT), ChromaDB (Apache 2.0), SQLite (Public Domain), Tesseract (Apache 2.0), Cython (Apache 2.0), Celery (BSD), Redis (BSD), TableTransformer (Apache 2.0), Docker (Apache 2.0), GitHub ($0), Docker Hub ($0), GitHub Actions ($0), Let’s Encrypt ($0).

## 5. Execution Plan

### 5.1 Getting Started Guide

#### Prerequisites

- **Hardware**: Server with 8-16GB RAM (slim: 4-8GB), 10-20GB storage (slim: 5-10GB), 4+ CPU cores (slim: 2+).
- **Software**: Docker, Git, Python 3.10, Cython, GitHub account.
- **Files**: Phi-4-multimodal model (GGUF, ~2.5-4GB).

#### Steps

1. **Create GitHub Repository**:
   - Initialize `yourusername/your-api`.
   - Enable GitHub Pages ($0).
   - Add `README.md`.
2. **Implement FastAPI App**:
   - Use provided `main.py` (artifact ID: `0b15eaab-655b-40fd-b24d-6344dd7395b4`):
     - Supports `/parse`, `/query`, `/generate_schema`, `/agent`, `/match`, `/status`.
     - Includes three-way matching, table parsing, chunking/deduplication, async processing.
     - Ensures zero data retention.
   - Compile to Cython:

     ```bash
     cythonize -i main_cy.pyx
     ```
3. **Prepare Phi-4-Multimodal**:
   - Convert to GGUF:

     ```bash
     git clone https://github.com/ggerganov/llama.cpp
     cd llama.cpp
     python convert.py --outfile phi-4-multimodal.gguf /path/to/phi-4-multimodal
     ```
   - Create `Modelfile`:

     ```plaintext
     FROM ./phi-4-multimodal.gguf
     ```
4. **Build Docker Images**:
   - **Full Image**:
     - Installs langchain, Ollama, Phi-4-multimodal, Celery, Redis, TableTransformer.
     - Build/push:

       ```bash
       docker build -t yourusername/your-api:latest .
       docker push yourusername/your-api:latest
       ```
   - **Slim Image**:

     ```dockerfile
     FROM python:3.10-slim
     WORKDIR /app
     RUN apt-get update && apt-get install -y tesseract-ocr libtesseract-dev poppler-utils sqlite3 gcc && rm -rf /var/lib/apt/lists/*
     RUN pip install --no-cache-dir unstructured[all-docs] llama-index fastapi uvicorn cython requests beautifulsoup4
     RUN useradd -m appuser
     COPY main.py main_cy.c main_cy.cpython-*.so .
     USER appuser
     EXPOSE 8000
     CMD ["python", "main.py"]
     ```
     - Build/push:

       ```bash
       docker build -t yourusername/your-api:slim .
       docker push yourusername/your-api:slim
       ```
5. **Integrate Data Source Connectors**:
   - Implement `/parse` with `source_type` (file, sql, api, web, cloud).
   - Test connectors (e.g., SQLite, REST API, Google Drive).
6. **Document Setup**:
   - Update `README.md`:

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
7. **Test Implementation**:
   - Use GitHub Actions ($0) to test:
     - Parsing, connectors, agentic tasks, three-way matching, chunking, async processing, zero data retention.
   - Sample test script:

     ```python
     import requests
     files = {"file": open("sample.pdf", "rb")}
     response = requests.post("http://localhost:8000/parse?api_key=123e4567-e89b-12d3-a456-426614174000&chunk_strategy=sentence", files=files)
     print(response.json())
     response = requests.post("http://localhost:8000/match?api_key=123e4567-e89b-12d3-a456-426614174000", files=[("files", open("invoice.pdf", "rb")), ("files", open("po.pdf", "rb"))])
     print(response.json())
     ```
8. **Deploy and Distribute**:
   - Push images to Docker Hub.
   - Host documentation on GitHub Pages ($0).
   - Support clients via GitHub issues.

### 5.2 Execution Timeline

- **Week 1**: Set up repository, implement FastAPI app with new endpoints, compile with Cython.
- **Week 2**: Prepare Phi-4-multimodal, integrate TableTransformer, build/test slim and full Docker images.
- **Week 3**: Integrate and test connectors, chunking, deduplication, async processing, three-way matching.
- **Week 4**: Test parsing, RAG, schema generation, agentic behavior, zero data retention; set up GitHub Actions.
- **Week 5**: Write `README.md`, publish documentation, push images to Docker Hub.
- **Week 6**: Gather client feedback, fix bugs, optimize performance.

## 6. Cost Breakdown

- **Development**: $0 (open-source tools, existing hardware).
- **Hosting**: $0 (GitHub Pages, Docker Hub, GitHub Actions).
- **Client Costs**: $0 if using existing hardware; ~$30-100/month for cloud (e.g., AWS t3.large).

## 7. Risks and Mitigations

- **Parsing Accuracy**: Unstructured.io + TableTransformer may struggle with complex tables.
  - **Mitigation**: Use Phi-4-multimodal’s agentic capabilities; support custom LLMs.
- **LLM Compatibility**: Some models may require specific configurations.
  - **Mitigation**: Use `langchain` adapters, document setup.
- **Docker Image Size**: Full image (~4-4.5GB) may challenge low-bandwidth clients.
  - **Mitigation**: Provide slim image (~2GB).
- **Hardware Needs**: Full image requires 8-16GB RAM.
  - **Mitigation**: Slim image supports 4-8GB RAM.

## 8. Future Enhancements

- Add LlamaIndex connectors (e.g., OneDrive, Notion).
- Implement caching for faster parsing.
- Support batch processing.
- Add `/usage_report` endpoint.

## 9. Conclusion

This plan delivers a **self-hosted API** for parsing **all file types** into **LLM-ready JSON**, with **Phi-4-multimodal** as an **Agentic AI**, support for **any LLM model** via `langchain`, **zero data retention**, and **Pulse-inspired features** (three-way matching, advanced table parsing, chunking, async processing). Using **open-source tools**, **two Docker images**, and **extensive data source connectors**, it ensures flexibility, security, and zero cost. The 6-week plan enables rapid deployment, positioning your API as a robust, enterprise-ready solution competitive with hosted alternatives like Pulse.