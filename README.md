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
3. Run the deployment script: `./deploy.sh`

This will:
- Build and push Docker images to Docker Hub
- Start the ClaryAI API server on port 8000
- Start Redis for caching and queuing on port 6379
- Set up Nginx for SSL termination and load balancing
- Configure worker for asynchronous processing

For development, you can use:
```bash
# Start the full stack with LLM
docker-compose up -d

# Start the slim version without LLM
docker-compose --profile slim up -d

# Start with development tools (Redis Commander)
docker-compose --profile dev up -d
```

### Using Docker (Manual)

1. Pull image: `docker pull claryai/claryai:latest` (full version with LLM)
2. Pull image: `docker pull claryai/claryai:slim` (slim version without LLM)
3. Run slim: `docker run -d -p 8000:8000 -e USE_LLM=false claryai/claryai:slim`
4. Run full: `docker run -d -p 8000:8000 -e USE_LLM=true -e LLM_MODEL=phi-4-multimodal claryai/claryai:latest`
5. Custom LLM: `docker run -e USE_LLM=true -e LLM_ENDPOINT=http://localhost:9000 -e OPENAI_API_KEY=sk-...`
6. Offline: Save (`docker save claryai/claryai > claryai.tar`), load (`docker load -i claryai.tar`).

### Production Deployment

For production deployment, follow these steps:

1. Set up a server with Docker and Docker Compose installed
2. Clone the repository: `git clone https://github.com/sn-sujay/claryai.git`
3. Navigate to the directory: `cd claryai`
4. Update the Nginx configuration in `nginx/conf.d/claryai.conf` with your domain
5. Generate SSL certificates for your domain:
   ```bash
   # Using Let's Encrypt (recommended)
   certbot certonly --webroot -w /var/www/html -d yourdomain.com

   # Copy certificates to nginx/ssl
   cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/claryai.crt
   cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/claryai.key
   ```
6. Update environment variables in `docker-compose.yml` with secure API keys
7. Run the deployment script: `./deploy.sh`
8. Set up monitoring and backups for production use

## Endpoints

- **POST /parse**: Parse file (any type) or data source with chunking (e.g., `chunk_strategy=sentence`). Returns JSON (e.g., `{"elements": [{"type": "Table", "text": "Row1,Col1"}]}`). Supports asynchronous processing with `async_processing=true`.
- **POST /query**: Query indexed documents (LLM required). Supports response caching with `use_cache=true`.
- **POST /generate_schema**: Generate custom JSON schema (LLM required).
- **POST /agent**: Perform agentic tasks (LLM required).
- **POST /match**: Three-way matching for invoices, POs, GRNs. Supports both file uploads and task IDs.
- **GET /status/{task_id}**: Check async task status. Supports including results with `include_result=true`.
- **POST /analyze_image**: Analyze images using Phi-4-multimodal. Supports text extraction and object detection.

## Asynchronous Processing

ClaryAI supports asynchronous processing for large documents:

1. Submit a document with `async_processing=true` to the `/parse` endpoint
2. Receive a task ID in the response: `{"task_id": "uuid", "status": "processing"}`
3. Check the status using `/status/{task_id}` endpoint
4. Retrieve the result when processing is complete with `/status/{task_id}?include_result=true`

The asynchronous processing system uses Redis for queuing and a dedicated worker process for handling document processing tasks. This architecture allows the API to handle large documents without blocking the main thread, improving overall performance and scalability.

## Data Sources

- **Files**: PDF, DOCX, JPG, PNG, PPTX, TXT, etc.
- **SQL**: PostgreSQL, MySQL, SQLite.
- **APIs**: REST endpoints.
- **Web**: HTML pages.
- **Cloud Storage**: Google Drive, S3, Dropbox, Azure Blob Storage, Box.
- **Data Sources**: Notion, GitHub, MongoDB, Slack, Confluence, Couchbase, Elasticsearch.

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
