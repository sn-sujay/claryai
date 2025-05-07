# ClaryAI User Guide

## Introduction

ClaryAI is a self-hosted API for parsing documents of all file types into structured, LLM-ready JSON outputs with zero data retention. It provides a comprehensive set of endpoints for document processing, querying, and analysis.

This guide provides detailed instructions on how to use ClaryAI, including examples for each endpoint and common use cases.

## Table of Contents

1. [Getting Started](#getting-started)
2. [API Authentication](#api-authentication)
3. [API Endpoints](#api-endpoints)
   - [Parse Documents](#parse-documents)
   - [Query Documents](#query-documents)
   - [Generate Schema](#generate-schema)
   - [Agent Tasks](#agent-tasks)
   - [Three-Way Matching](#three-way-matching)
   - [Check Task Status](#check-task-status)
   - [Analyze Images](#analyze-images)
4. [Data Sources](#data-sources)
5. [Asynchronous Processing](#asynchronous-processing)
6. [Error Handling](#error-handling)
7. [Performance Optimization](#performance-optimization)
8. [Security Considerations](#security-considerations)
9. [Troubleshooting](#troubleshooting)
10. [FAQ](#faq)

## Getting Started

### Installation

Follow the instructions in the [Getting Started Guide](get_started.markdown) to set up ClaryAI.

### Quick Start

Once ClaryAI is running, you can start using it with the following simple example:

```bash
# Parse a PDF document
curl -X POST "http://localhost:8000/parse" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample.pdf" \
  -F "api_key=your_api_key"
```

## API Authentication

All API endpoints require authentication using an API key. You can include the API key in one of two ways:

1. As a query parameter: `?api_key=your_api_key`
2. As a form field: `-F "api_key=your_api_key"`

API keys are managed in the SQLite database (`claryai.db`). You can add a new API key using the following SQL command:

```sql
INSERT INTO api_keys (key, document_count) VALUES ('your_api_key', 0);
```

## API Endpoints

### Parse Documents

The `/parse` endpoint is used to parse documents into structured JSON.

#### Request

```bash
curl -X POST "http://localhost:8000/parse" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample.pdf" \
  -F "api_key=your_api_key" \
  -F "chunk_strategy=paragraph" \
  -F "async_processing=false"
```

#### Parameters

- `file`: The document file to parse (required unless `source_url` is provided)
- `source_type`: Type of source (`file`, `sql`, `api`, `web`, `cloud`, `datasource`). Default: `file`
- `source_url`: URL or connection string for non-file sources
- `chunk_strategy`: Chunking strategy (`sentence`, `paragraph`, `fixed`). Default: `paragraph`
- `async_processing`: Whether to process the document asynchronously. Default: `false`
- `api_key`: Your API key (required)

#### Response

```json
{
  "elements": [
    {
      "type": "Title",
      "text": "Sample Document"
    },
    {
      "type": "NarrativeText",
      "text": "This is a sample paragraph."
    },
    {
      "type": "Table",
      "text": "| Name | Age | City |\n| ---- | --- | ---- |\n| John | 30 | New York |\n| Jane | 25 | San Francisco |",
      "data": {
        "headers": ["Name", "Age", "City"],
        "rows": [
          ["John", "30", "New York"],
          ["Jane", "25", "San Francisco"]
        ]
      }
    }
  ],
  "status": "parsed"
}
```

### Query Documents

The `/query` endpoint is used to query indexed documents.

#### Request

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the age of John?",
    "document_id": "doc123",
    "use_cache": true,
    "api_key": "your_api_key"
  }'
```

#### Parameters

- `query`: The query text (required)
- `document_id`: ID of the document to query (optional)
- `use_cache`: Whether to use cached responses. Default: `true`
- `api_key`: Your API key (required)

#### Response

```json
{
  "response": "John is 30 years old.",
  "source_documents": ["doc123"],
  "cached": false
}
```

### Generate Schema

The `/generate_schema` endpoint is used to generate a JSON schema based on document elements.

#### Request

```bash
curl -X POST "http://localhost:8000/generate_schema" \
  -H "Content-Type: application/json" \
  -d '{
    "schema_description": "Generate a schema for invoice data",
    "elements": {
      "elements": [
        {
          "type": "Title",
          "text": "Invoice #12345"
        },
        {
          "type": "NarrativeText",
          "text": "Date: 2023-05-01"
        },
        {
          "type": "Table",
          "text": "| Item | Quantity | Price | Total |\n| ---- | -------- | ----- | ----- |\n| Widget | 2 | $10.00 | $20.00 |\n| Gadget | 1 | $15.00 | $15.00 |",
          "data": {
            "headers": ["Item", "Quantity", "Price", "Total"],
            "rows": [
              ["Widget", "2", "$10.00", "$20.00"],
              ["Gadget", "1", "$15.00", "$15.00"]
            ]
          }
        },
        {
          "type": "NarrativeText",
          "text": "Total: $35.00"
        }
      ]
    },
    "api_key": "your_api_key"
  }'
```

#### Parameters

- `schema_description`: Description of the schema to generate (required)
- `elements`: Document elements (required)
- `api_key`: Your API key (required)

#### Response

```json
{
  "schema": {
    "type": "object",
    "properties": {
      "invoice_number": {
        "type": "string",
        "description": "Invoice number"
      },
      "date": {
        "type": "string",
        "format": "date",
        "description": "Invoice date"
      },
      "items": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "item": {
              "type": "string",
              "description": "Item name"
            },
            "quantity": {
              "type": "integer",
              "description": "Quantity of items"
            },
            "price": {
              "type": "string",
              "description": "Price per item"
            },
            "total": {
              "type": "string",
              "description": "Total price for the item"
            }
          }
        }
      },
      "total": {
        "type": "string",
        "description": "Total invoice amount"
      }
    }
  }
}
```

### Agent Tasks

The `/agent` endpoint is used to perform agentic tasks on documents.

#### Request

```bash
curl -X POST "http://localhost:8000/agent" \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Extract the total amount from the invoice",
    "elements": {
      "elements": [
        {
          "type": "Title",
          "text": "Invoice #12345"
        },
        {
          "type": "NarrativeText",
          "text": "Date: 2023-05-01"
        },
        {
          "type": "Table",
          "text": "| Item | Quantity | Price | Total |\n| ---- | -------- | ----- | ----- |\n| Widget | 2 | $10.00 | $20.00 |\n| Gadget | 1 | $15.00 | $15.00 |",
          "data": {
            "headers": ["Item", "Quantity", "Price", "Total"],
            "rows": [
              ["Widget", "2", "$10.00", "$20.00"],
              ["Gadget", "1", "$15.00", "$15.00"]
            ]
          }
        },
        {
          "type": "NarrativeText",
          "text": "Total: $35.00"
        }
      ]
    },
    "api_key": "your_api_key"
  }'
```

#### Parameters

- `task_description`: Description of the task to perform (required)
- `elements`: Document elements (required)
- `api_key`: Your API key (required)

#### Response

```json
{
  "result": {
    "total_amount": "$35.00"
  }
}
```

### Three-Way Matching

The `/match` endpoint is used to perform three-way matching on multiple documents.

#### Request

```bash
curl -X POST "http://localhost:8000/match" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@invoice.pdf" \
  -F "files=@po.pdf" \
  -F "files=@grn.pdf" \
  -F "api_key=your_api_key"
```

#### Parameters

- `files`: List of uploaded files (required unless task IDs are provided)
- `invoice_task_id`: Task ID for invoice (optional)
- `po_task_id`: Task ID for purchase order (optional)
- `grn_task_id`: Task ID for goods receipt note (optional)
- `api_key`: Your API key (required)

#### Response

```json
{
  "status": "complete_match",
  "matches": {
    "document_numbers": {
      "invoice": "INV-12345",
      "po": "PO-12345",
      "grn": "GRN-12345",
      "match": true
    },
    "dates": {
      "invoice": "2023-05-01",
      "po": "2023-04-15",
      "grn": "2023-04-30",
      "match": true
    },
    "amounts": {
      "invoice": "$35.00",
      "po": "$35.00",
      "grn": "$35.00",
      "match": true
    },
    "line_items": [
      {
        "item": "Widget",
        "quantity": {
          "invoice": 2,
          "po": 2,
          "grn": 2,
          "match": true
        },
        "price": {
          "invoice": "$10.00",
          "po": "$10.00",
          "match": true
        }
      },
      {
        "item": "Gadget",
        "quantity": {
          "invoice": 1,
          "po": 1,
          "grn": 1,
          "match": true
        },
        "price": {
          "invoice": "$15.00",
          "po": "$15.00",
          "match": true
        }
      }
    ]
  }
}
```

### Check Task Status

The `/status/{task_id}` endpoint is used to check the status of an asynchronous task.

#### Request

```bash
curl -X GET "http://localhost:8000/status/task_12345?api_key=your_api_key&include_result=true"
```

#### Parameters

- `task_id`: ID of the task to check (required, in path)
- `include_result`: Whether to include the task result. Default: `false`
- `api_key`: Your API key (required)

#### Response

```json
{
  "task_id": "task_12345",
  "status": "completed",
  "result": {
    "elements": [
      {
        "type": "Title",
        "text": "Sample Document"
      },
      {
        "type": "NarrativeText",
        "text": "This is a sample paragraph."
      }
    ],
    "status": "parsed"
  }
}
```

### Analyze Images

The `/analyze_image` endpoint is used to analyze images using Phi-4-multimodal.

#### Request

```bash
curl -X POST "http://localhost:8000/analyze_image" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@image.jpg" \
  -F "api_key=your_api_key" \
  -F "extract_text=true" \
  -F "detect_objects=true"
```

#### Parameters

- `file`: The image file to analyze (required)
- `extract_text`: Whether to extract text from the image. Default: `false`
- `detect_objects`: Whether to detect objects in the image. Default: `false`
- `api_key`: Your API key (required)

#### Response

```json
{
  "analysis": {
    "description": "The image shows a document with text and a table.",
    "extracted_text": "Sample Document\n\nThis is a sample paragraph.\n\nName | Age | City\n---- | --- | ----\nJohn | 30 | New York\nJane | 25 | San Francisco",
    "detected_objects": [
      {
        "object": "document",
        "confidence": 0.95
      },
      {
        "object": "table",
        "confidence": 0.87
      }
    ]
  }
}
```

## Data Sources

ClaryAI supports various data sources:

### Files

Supported file types include:
- PDF
- DOCX, DOC
- XLSX, XLS
- PPTX, PPT
- JPG, PNG, GIF
- TXT, MD
- HTML

### SQL

Connect to SQL databases using connection strings:

```
source_type=sql&source_url=postgresql://username:password@host:port/database
source_type=sql&source_url=mysql://username:password@host:port/database
source_type=sql&source_url=sqlite:///path/to/database.db
```

### APIs

Connect to REST APIs:

```
source_type=api&source_url=https://api.example.com/data
```

### Web

Parse web pages:

```
source_type=web&source_url=https://example.com
```

### Cloud Storage

Connect to cloud storage services:

```
source_type=cloud&source_url=cloud://googledrive:token123@file_id
source_type=cloud&source_url=cloud://s3:access_key:secret_key@bucket/key
source_type=cloud&source_url=cloud://dropbox:token456@file_path
source_type=cloud&source_url=cloud://azure:connection_string@container/blob
source_type=cloud&source_url=cloud://box:access_token@file_id
```

### Data Sources

Connect to various data sources:

```
source_type=datasource&source_url=datasource://notion:token123@page_id
source_type=datasource&source_url=datasource://github:token456@owner/repo/path
source_type=datasource&source_url=datasource://mongodb:username:password@host:port/database/collection
source_type=datasource&source_url=datasource://slack:token789@channel_id
source_type=datasource&source_url=datasource://confluence:username:password@host/page_id
source_type=datasource&source_url=datasource://couchbase:connection_string@bucket/scope/collection/document_id
source_type=datasource&source_url=datasource://elasticsearch:username:password@hosts/index/document_id
```

## Asynchronous Processing

For large documents, use asynchronous processing:

1. Submit the document with `async_processing=true`
2. Receive a task ID in the response
3. Check the task status using the `/status/{task_id}` endpoint
4. Retrieve the result when processing is complete with `/status/{task_id}?include_result=true`

## Error Handling

ClaryAI uses standard HTTP status codes for error handling:

- `200 OK`: Request successful
- `202 Accepted`: Asynchronous task accepted
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Invalid or missing API key
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

Error responses include a detail message:

```json
{
  "detail": "Error message"
}
```

## Performance Optimization

To optimize performance:

1. Use asynchronous processing for large documents
2. Use chunking strategies appropriate for your use case
3. Use caching for queries with `use_cache=true`
4. Use the slim Docker image for deployment without LLM features

## Security Considerations

ClaryAI is designed with security in mind:

1. Zero data retention: All temporary files are deleted after processing
2. API key authentication for all endpoints
3. SSL termination with Nginx for secure communication
4. Docker isolation for secure deployment

## Troubleshooting

Common issues and solutions:

1. **API key errors**: Ensure your API key is valid and included in the request
2. **File parsing errors**: Check that the file format is supported
3. **LLM errors**: Ensure the LLM is properly configured
4. **Redis errors**: Check that Redis is running and accessible
5. **Performance issues**: Use asynchronous processing for large documents

## FAQ

### General Questions

**Q: Is my data stored by ClaryAI?**
A: No, ClaryAI has zero data retention. All temporary files are deleted after processing.

**Q: Can I use ClaryAI offline?**
A: Yes, ClaryAI can be used offline with the Docker image.

**Q: Does ClaryAI support custom LLMs?**
A: Yes, you can configure ClaryAI to use custom LLMs by setting the `LLM_ENDPOINT` environment variable.

### Technical Questions

**Q: How do I add a new API key?**
A: Use the SQLite database to add a new API key: `INSERT INTO api_keys (key, document_count) VALUES ('your_api_key', 0);`

**Q: How do I monitor ClaryAI?**
A: ClaryAI logs to stdout/stderr, which can be captured by Docker or redirected to a log file.

**Q: How do I scale ClaryAI?**
A: Use Docker Compose to scale the worker containers for increased throughput.
