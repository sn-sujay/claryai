# ClaryAI Tutorials

This document provides step-by-step tutorials for common use cases with ClaryAI.

## Table of Contents

1. [Parsing Documents](#parsing-documents)
2. [Processing Invoices](#processing-invoices)
3. [Three-Way Matching](#three-way-matching)
4. [Working with Cloud Storage](#working-with-cloud-storage)
5. [Using LlamaIndex Integration](#using-llamaindex-integration)
6. [Image Analysis with Phi-4-multimodal](#image-analysis-with-phi-4-multimodal)
7. [Building a Document Processing Pipeline](#building-a-document-processing-pipeline)

## Parsing Documents

This tutorial demonstrates how to parse various document types with ClaryAI.

### Prerequisites

- ClaryAI running locally or on a server
- Valid API key
- Sample documents (PDF, DOCX, etc.)

### Step 1: Parse a PDF Document

```bash
curl -X POST "http://localhost:8000/parse" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample.pdf" \
  -F "api_key=your_api_key"
```

### Step 2: Parse a Word Document

```bash
curl -X POST "http://localhost:8000/parse" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample.docx" \
  -F "api_key=your_api_key"
```

### Step 3: Parse a Web Page

```bash
curl -X POST "http://localhost:8000/parse" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "source_type=web&source_url=https://example.com&api_key=your_api_key"
```

### Step 4: Apply Chunking

```bash
curl -X POST "http://localhost:8000/parse" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample.pdf" \
  -F "chunk_strategy=paragraph" \
  -F "api_key=your_api_key"
```

### Step 5: Process Asynchronously

```bash
curl -X POST "http://localhost:8000/parse" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@large_document.pdf" \
  -F "async_processing=true" \
  -F "api_key=your_api_key"
```

Response:

```json
{
  "task_id": "task_12345",
  "status": "processing"
}
```

### Step 6: Check Task Status

```bash
curl -X GET "http://localhost:8000/status/task_12345?api_key=your_api_key"
```

Response:

```json
{
  "task_id": "task_12345",
  "status": "completed"
}
```

### Step 7: Get Task Result

```bash
curl -X GET "http://localhost:8000/status/task_12345?include_result=true&api_key=your_api_key"
```

## Processing Invoices

This tutorial demonstrates how to process invoices with ClaryAI.

### Prerequisites

- ClaryAI running locally or on a server
- Valid API key
- Sample invoice (PDF, DOCX, etc.)

### Step 1: Parse the Invoice

```bash
curl -X POST "http://localhost:8000/parse" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@invoice.pdf" \
  -F "api_key=your_api_key"
```

### Step 2: Generate a Schema for the Invoice

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

### Step 3: Extract Information from the Invoice

```bash
curl -X POST "http://localhost:8000/agent" \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Extract the invoice number, date, items, and total amount",
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

## Three-Way Matching

This tutorial demonstrates how to perform three-way matching with ClaryAI.

### Prerequisites

- ClaryAI running locally or on a server
- Valid API key
- Sample invoice, purchase order, and goods receipt note

### Step 1: Upload the Documents

```bash
curl -X POST "http://localhost:8000/match" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@invoice.pdf" \
  -F "files=@po.pdf" \
  -F "files=@grn.pdf" \
  -F "api_key=your_api_key"
```

### Step 2: Analyze the Matching Results

The response will indicate whether the documents match and provide details about any discrepancies.

## Working with Cloud Storage

This tutorial demonstrates how to work with cloud storage in ClaryAI.

### Prerequisites

- ClaryAI running locally or on a server
- Valid API key
- Access to cloud storage (Google Drive, S3, Dropbox, etc.)

### Step 1: Parse a Document from Google Drive

```bash
curl -X POST "http://localhost:8000/parse" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "source_type=cloud&source_url=cloud://googledrive:{\"access_token\":\"your_token\"}/file_id&api_key=your_api_key"
```

### Step 2: Parse a Document from S3

```bash
curl -X POST "http://localhost:8000/parse" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "source_type=cloud&source_url=cloud://s3:{\"aws_access_key_id\":\"your_key\",\"aws_secret_access_key\":\"your_secret\"}/bucket/key&api_key=your_api_key"
```

### Step 3: Parse a Document from Dropbox

```bash
curl -X POST "http://localhost:8000/parse" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "source_type=cloud&source_url=cloud://dropbox:{\"access_token\":\"your_token\"}/path/to/file&api_key=your_api_key"
```

## Using LlamaIndex Integration

This tutorial demonstrates how to use the LlamaIndex integration in ClaryAI.

### Prerequisites

- ClaryAI running locally or on a server
- Valid API key
- Sample documents

### Step 1: Parse and Index a Document

```bash
curl -X POST "http://localhost:8000/parse" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf" \
  -F "index_document=true" \
  -F "document_id=doc123" \
  -F "api_key=your_api_key"
```

### Step 2: Query the Indexed Document

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the main topic of the document?",
    "document_id": "doc123",
    "api_key": "your_api_key"
  }'
```

## Image Analysis with Phi-4-multimodal

This tutorial demonstrates how to analyze images with Phi-4-multimodal in ClaryAI.

### Prerequisites

- ClaryAI running locally or on a server with Phi-4-multimodal
- Valid API key
- Sample images

### Step 1: Analyze an Image

```bash
curl -X POST "http://localhost:8000/analyze_image" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@image.jpg" \
  -F "api_key=your_api_key"
```

### Step 2: Extract Text from an Image

```bash
curl -X POST "http://localhost:8000/analyze_image" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@image.jpg" \
  -F "extract_text=true" \
  -F "api_key=your_api_key"
```

### Step 3: Detect Objects in an Image

```bash
curl -X POST "http://localhost:8000/analyze_image" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@image.jpg" \
  -F "detect_objects=true" \
  -F "api_key=your_api_key"
```

## Building a Document Processing Pipeline

This tutorial demonstrates how to build a document processing pipeline with ClaryAI.

### Prerequisites

- ClaryAI running locally or on a server
- Valid API key
- Sample documents

### Step 1: Parse Documents Asynchronously

```bash
curl -X POST "http://localhost:8000/parse" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document1.pdf" \
  -F "async_processing=true" \
  -F "api_key=your_api_key"
```

Response:

```json
{
  "task_id": "task_1",
  "status": "processing"
}
```

### Step 2: Check Task Status

```bash
curl -X GET "http://localhost:8000/status/task_1?api_key=your_api_key"
```

### Step 3: Get Task Result

```bash
curl -X GET "http://localhost:8000/status/task_1?include_result=true&api_key=your_api_key"
```

### Step 4: Process the Result with an Agent

```bash
curl -X POST "http://localhost:8000/agent" \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Summarize the document",
    "elements": {
      "elements": [
        {
          "type": "Title",
          "text": "Sample Document"
        },
        {
          "type": "NarrativeText",
          "text": "This is a sample paragraph."
        }
      ]
    },
    "api_key": "your_api_key"
  }'
```

### Step 5: Generate a Schema

```bash
curl -X POST "http://localhost:8000/generate_schema" \
  -H "Content-Type: application/json" \
  -d '{
    "schema_description": "Generate a schema for the document",
    "elements": {
      "elements": [
        {
          "type": "Title",
          "text": "Sample Document"
        },
        {
          "type": "NarrativeText",
          "text": "This is a sample paragraph."
        }
      ]
    },
    "api_key": "your_api_key"
  }'
```

### Step 6: Match Documents

```bash
curl -X POST "http://localhost:8000/match" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@invoice.pdf" \
  -F "files=@po.pdf" \
  -F "files=@grn.pdf" \
  -F "api_key=your_api_key"
```

By following these tutorials, you can build a complete document processing pipeline with ClaryAI.
