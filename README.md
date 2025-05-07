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
- Asynchronous processing for large documents
- Available in two Docker images (with/without Phi-4-multimodal)

## Setup

1. Pull image: `docker pull yourusername/claryai:slim` or `yourusername/claryai:latest`
2. Run slim: `docker run -d -p 8000:8000 -e USE_LLM=false yourusername/claryai:slim`
3. Run full: `docker run -d -p 8000:8000 -e USE_LLM=true -e LLM_MODEL=phi-4-multimodal yourusername/claryai:latest`
4. Custom LLM: `docker run -e USE_LLM=true -e LLM_ENDPOINT=http://localhost:9000 -e OPENAI_API_KEY=sk-...`
5. Offline: Save (`docker save yourusername/claryai > claryai.tar`), load (`docker load -i claryai.tar`).

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

## Getting Started

See the [Getting Started Guide](Documentation/get_started.markdown) for detailed instructions on setting up and using ClaryAI.

## Project Plan

For a comprehensive overview of the project, see the [Project Plan](Documentation/project_plan.markdown).
