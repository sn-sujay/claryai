# ClaryAI API User Guide

This guide provides detailed information on how to use the ClaryAI API, including sample API calls for each endpoint.

## Table of Contents

1. [Introduction](#introduction)
2. [Authentication](#authentication)
3. [API Endpoints](#api-endpoints)
   - [Root Endpoint](#root-endpoint)
   - [Parse Endpoint](#parse-endpoint)
   - [Query Endpoint](#query-endpoint)
   - [Generate Schema Endpoint](#generate-schema-endpoint)
   - [Agent Endpoint](#agent-endpoint)
   - [Match Endpoint](#match-endpoint)
   - [Status Endpoint](#status-endpoint)
4. [Chunking Strategies](#chunking-strategies)
5. [Asynchronous Processing](#asynchronous-processing)
6. [Error Handling](#error-handling)

## Introduction

ClaryAI is a self-hosted API for parsing documents into LLM-ready JSON outputs with zero data retention. It supports various document types, including PDFs, Word documents, images, and text files, and can extract structured data from tables, forms, and unstructured text.

## Authentication

All API endpoints require an API key for authentication. The API key should be included as a query parameter in all requests.

```
api_key=123e4567-e89b-12d3-a456-426614174000
```

## API Endpoints

### Root Endpoint

The root endpoint provides information about the API.

**Request:**

```
GET http://localhost:8080/
```

**Response:**

```json
{
  "name": "ClaryAI",
  "description": "A self-hosted API for parsing documents into LLM-ready JSON outputs with zero data retention.",
  "version": "0.1.0",
  "endpoints": [
    "/parse", "/query", "/generate_schema", "/agent", "/match", "/status/{task_id}"
  ],
  "llm_enabled": false
}
```

### Parse Endpoint

The parse endpoint is used to parse documents from various sources into structured JSON.

**Parameters:**

- `file`: Uploaded file (for file source_type)
- `api_key`: API key for authentication
- `source_type`: Type of source (file, sql, api, web, cloud)
- `source_url`: URL or connection string for non-file sources
- `chunk_strategy`: Chunking strategy (sentence, paragraph, fixed)
- `async_processing`: Whether to process document asynchronously using Redis queue

**Example 1: Parse a file**

```bash
curl -X POST "http://localhost:8080/parse?api_key=123e4567-e89b-12d3-a456-426614174000" \
  -F "file=@sample_invoice.txt"
```

**Example 2: Parse a web page**

```bash
curl -X POST "http://localhost:8080/parse?api_key=123e4567-e89b-12d3-a456-426614174000&source_type=web&source_url=https://example.com"
```

**Example 3: Parse a file from Google Drive**

```bash
curl -X POST "http://localhost:8080/parse?api_key=123e4567-e89b-12d3-a456-426614174000&source_type=cloud&source_url=google_drive://{\"access_token\":\"your_access_token\"}/file_id"
```

**Example 4: Parse a file from Amazon S3**

```bash
curl -X POST "http://localhost:8080/parse?api_key=123e4567-e89b-12d3-a456-426614174000&source_type=cloud&source_url=s3://{\"aws_access_key_id\":\"your_key\",\"aws_secret_access_key\":\"your_secret\"}/bucket/key"
```

**Example 5: Parse a file from Dropbox**

```bash
curl -X POST "http://localhost:8080/parse?api_key=123e4567-e89b-12d3-a456-426614174000&source_type=cloud&source_url=dropbox://{\"access_token\":\"your_access_token\"}/path/to/file"
```

**Example 6: Parse data from Notion**

```bash
curl -X POST "http://localhost:8080/parse?api_key=123e4567-e89b-12d3-a456-426614174000&source_type=datasource&source_url=notion://{\"token\":\"your_notion_token\"}/page_id"
```

**Example 7: Parse data from GitHub**

```bash
curl -X POST "http://localhost:8080/parse?api_key=123e4567-e89b-12d3-a456-426614174000&source_type=datasource&source_url=github://{\"token\":\"your_github_token\"}/owner/repo/path/to/file"
```

**Example 8: Parse data from MongoDB**

```bash
curl -X POST "http://localhost:8080/parse?api_key=123e4567-e89b-12d3-a456-426614174000&source_type=datasource&source_url=mongodb://{\"connection_string\":\"mongodb://username:password@host:port\"}/database.collection"
```

**Example 9: Parse data from Slack**

```bash
curl -X POST "http://localhost:8080/parse?api_key=123e4567-e89b-12d3-a456-426614174000&source_type=datasource&source_url=slack://{\"token\":\"your_slack_token\"}/channel_id"
```

**Example 10: Parse data from Azure Blob Storage**

```bash
curl -X POST "http://localhost:8080/parse?api_key=123e4567-e89b-12d3-a456-426614174000&source_type=datasource&source_url=azure://{\"connection_string\":\"your_connection_string\"}/container/blob_name"
```

**Example 11: Parse data from Box**

```bash
curl -X POST "http://localhost:8080/parse?api_key=123e4567-e89b-12d3-a456-426614174000&source_type=datasource&source_url=box://{\"client_id\":\"your_client_id\",\"client_secret\":\"your_client_secret\",\"access_token\":\"your_access_token\"}/file_id"
```

**Example 12: Parse data from Couchbase**

```bash
curl -X POST "http://localhost:8080/parse?api_key=123e4567-e89b-12d3-a456-426614174000&source_type=datasource&source_url=couchbase://{\"connection_string\":\"couchbase://localhost\",\"username\":\"user\",\"password\":\"pass\"}/bucket.scope.collection:document_id"
```

**Example 13: Parse data from Elasticsearch**

```bash
curl -X POST "http://localhost:8080/parse?api_key=123e4567-e89b-12d3-a456-426614174000&source_type=datasource&source_url=elasticsearch://{\"hosts\":\"http://localhost:9200\"}/index:document_id"
```

**Example 14: Parse a file with a specific chunking strategy**

```bash
curl -X POST "http://localhost:8080/parse?api_key=123e4567-e89b-12d3-a456-426614174000&chunk_strategy=sentence" \
  -F "file=@large_document.txt"
```

**Example 15: Parse a file asynchronously**

```bash
curl -X POST "http://localhost:8080/parse?api_key=123e4567-e89b-12d3-a456-426614174000&async=true" \
  -F "file=@large_document.txt"
```

### Query Endpoint

The query endpoint is used to query parsed documents using LLM. Note that this endpoint requires LLM integration to be enabled.

**Parameters:**

- `query`: Query string
- `api_key`: API key for authentication
- `use_cache`: Whether to use cached responses

**Example:**

```bash
curl -X POST "http://localhost:8080/query?api_key=123e4567-e89b-12d3-a456-426614174000&query=What%20is%20the%20total%20profit%20for%20Q4%20across%20all%20departments%3F"
```

### Generate Schema Endpoint

The generate schema endpoint is used to generate custom JSON schemas from documents. Note that this endpoint requires LLM integration to be enabled.

**Parameters:**

- `schema_description`: Description of the schema to generate
- `file`: Uploaded file
- `api_key`: API key for authentication

**Example:**

```bash
curl -X POST "http://localhost:8080/generate_schema?api_key=123e4567-e89b-12d3-a456-426614174000&schema_description=Extract%20invoice%20details%20including%20invoice%20number%2C%20date%2C%20vendor%2C%20and%20line%20items" \
  -F "file=@sample_invoice.txt"
```

### Agent Endpoint

The agent endpoint is used to perform agentic tasks on documents. Note that this endpoint requires LLM integration to be enabled.

**Parameters:**

- `task_description`: Description of the task to perform
- `file`: Uploaded file
- `api_key`: API key for authentication

**Example:**

```bash
curl -X POST "http://localhost:8080/agent?api_key=123e4567-e89b-12d3-a456-426614174000&task_description=Summarize%20the%20document%20and%20extract%20key%20financial%20metrics" \
  -F "file=@financial_report.txt"
```

### Match Endpoint

The match endpoint is used to perform three-way matching on multiple documents (e.g., invoice, PO, GRN).

**Parameters:**

- `files`: List of uploaded files
- `invoice_task_id`: Task ID for invoice document (alternative to files)
- `po_task_id`: Task ID for purchase order document (alternative to files)
- `grn_task_id`: Task ID for goods receipt note document (alternative to files)
- `api_key`: API key for authentication

**Example:**

```bash
curl -X POST "http://localhost:8080/match?api_key=123e4567-e89b-12d3-a456-426614174000" \
  -F "files=@sample_invoice.txt" \
  -F "files=@sample_po.txt" \
  -F "files=@sample_grn.txt"
```

### Status Endpoint

The status endpoint is used to check the status of asynchronous tasks.

**Parameters:**

- `task_id`: Task ID
- `api_key`: API key for authentication

**Example:**

```bash
curl -X GET "http://localhost:8080/status/550e8400-e29b-41d4-a716-446655440000?api_key=123e4567-e89b-12d3-a456-426614174000"
```

## Chunking Strategies

ClaryAI supports three chunking strategies:

1. **Sentence-based chunking**: Splits the document into chunks based on sentence boundaries. This is useful for fine-grained analysis but may lose context across sentences.

2. **Paragraph-based chunking**: Splits the document into chunks based on paragraph boundaries. This preserves the context within paragraphs but may create chunks of varying sizes.

3. **Fixed-size chunking**: Splits the document into chunks of approximately equal size, regardless of content boundaries. This ensures consistent chunk sizes but may split sentences or paragraphs.

## Asynchronous Processing

For large documents, ClaryAI supports asynchronous processing using Redis. When a document is processed asynchronously, the API returns a task ID that can be used to check the status of the task using the status endpoint.

## Error Handling

The API returns standard HTTP status codes to indicate the success or failure of a request. In case of an error, the API returns a JSON object with a `detail` field containing a description of the error.

**Example:**

```json
{
  "detail": "API key required"
}
```
