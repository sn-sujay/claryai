# ClaryAI

A self-hosted API for parsing documents of all file types into structured, LLM-ready JSON outputs with zero data retention.

## Overview

ClaryAI is a comprehensive document parsing solution that uses Unstructured.io for document parsing, LlamaIndex for retrieval-augmented generation (RAG), and optional Phi-4-multimodal as an Agentic AI for autonomous text refinement, multimodal querying, and custom JSON schema generation.

## Features

- Parse documents of all file types (PDF, DOCX, JPG, PNG, PPTX, TXT, etc.)
- Generate structured JSON outputs for enterprise use cases
- Support for any LLM model via a generic interface
- Zero data retention with immediate deletion of temporary files
- Advanced features including three-way matching, table parsing, chunking/deduplication
- Robust asynchronous processing with Redis-based queuing and worker system
- LLM response caching for improved performance
- Three-way matching for invoices, purchase orders, and goods receipt notes
- Comprehensive error handling and logging
- Available in two Docker images (with/without Phi-4-multimodal)

## Setup

### Using Docker Compose (Recommended)

1. Clone the repository: `git clone https://github.com/sn-sujay/claryai.git`
2. Navigate to the directory: `cd claryai`
3. Run the Docker Compose setup: `./run.sh`

This will start:
- ClaryAI API server on port 8080
- Redis for caching and queuing on port 6379
- Redis Commander UI on port 8081
- Worker for asynchronous processing

### Using Docker (Manual)

1. Pull image: `docker pull sn-sujay/claryai:slim` or `sn-sujay/claryai:latest`
2. Run slim: `docker run -d -p 8000:8000 -e USE_LLM=false sn-sujay/claryai:slim`
3. Run full: `docker run -d -p 8000:8000 -e USE_LLM=true -e LLM_MODEL=phi-4-multimodal sn-sujay/claryai:latest`
4. Custom LLM: `docker run -e USE_LLM=true -e LLM_ENDPOINT=http://localhost:9000 -e OPENAI_API_KEY=sk-...`
5. Offline: Save (`docker save sn-sujay/claryai > claryai.tar`), load (`docker load -i claryai.tar`).

## Endpoints

- **POST /parse**: Parse file (any type) or data source with chunking (e.g., `chunk_strategy=sentence`). Returns JSON (e.g., `{"elements": [{"type": "Table", "text": "Row1,Col1"}]}`). Supports asynchronous processing with `async_processing=true`.
- **POST /query**: Query indexed documents (LLM required). Supports response caching with `use_cache=true`.
- **POST /generate_schema**: Generate custom JSON schema (LLM required).
- **POST /agent**: Perform agentic tasks (LLM required).
- **POST /match**: Three-way matching for invoices, POs, GRNs. Supports both file uploads and task IDs.
- **GET /status/{task_id}**: Check async task status. Supports including results with `include_result=true`.

## Asynchronous Processing

ClaryAI supports asynchronous processing for large documents:

1. Submit a document with `async_processing=true` to the `/parse` endpoint
2. Receive a task ID in the response: `{"task_id": "uuid", "status": "processing"}`
3. Check the status using `/status/{task_id}` endpoint
4. Retrieve the result when processing is complete with `/status/{task_id}?include_result=true`

The asynchronous processing system uses Redis for queuing and a dedicated worker process for handling document processing tasks. This architecture allows the API to handle large documents without blocking the main thread, improving overall performance and scalability.

## Data Sources

- Files: PDF, DOCX, JPG, PNG, PPTX, TXT, etc.
- SQL: PostgreSQL, MySQL, SQLite.
- APIs: REST endpoints.
- Web: HTML pages.
- Cloud: Google Drive, S3, Dropbox.

## Getting Started

See the [Getting Started Guide](Documentation/get_started.markdown) for detailed instructions on setting up and using ClaryAI.

## Testing

ClaryAI includes a comprehensive test suite to verify all functionality:

```bash
# Run the full test suite
python test_all.py

# Test specific functionality
python test_async.py sample_invoice.txt --async
```

## Project Plan

For a comprehensive overview of the project, see the [Project Plan](Documentation/project_plan.markdown).

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
