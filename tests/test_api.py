"""
Tests for ClaryAI API endpoints
"""

import os
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import the FastAPI app
import sys
# Add the parent directory to the path so we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Add the src directory to the path so modules can import each other
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import src.main
from src.main import app

# Create test client
client = TestClient(app)

# Mock API key for testing
TEST_API_KEY = "test-api-key-123"

# Mock the validate_api_key function to always return True for tests
@pytest.fixture(autouse=True)
def mock_validate_api_key():
    with patch('src.main.validate_api_key', return_value=True):
        yield

# Mock the update_document_count function to do nothing
@pytest.fixture(autouse=True)
def mock_update_document_count():
    with patch('src.main.update_document_count'):
        yield

# Test root endpoint
def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "ClaryAI"
    assert "endpoints" in data
    assert "/parse" in data["endpoints"]

# Test parse endpoint with file
def test_parse_with_file():
    # Mock the parse_document function
    with patch('src.main.parse_document', return_value={"elements": [{"type": "Text", "text": "Sample text"}], "status": "parsed"}):
        # Create a sample file for testing
        with open("sample.txt", "w") as f:
            f.write("Sample text for testing")

        # Test the endpoint
        with open("sample.txt", "rb") as f:
            response = client.post(
                "/parse",
                files={"file": ("sample.txt", f, "text/plain")},
                params={"api_key": TEST_API_KEY}
            )

        # Clean up
        os.remove("sample.txt")

        # Assert response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "parsed"
        assert len(data["elements"]) > 0

# Test parse endpoint with web source
def test_parse_with_web_source():
    # Mock the parse_document function and database operations
    with patch('src.main.parse_document', return_value={"elements": [{"type": "Title", "text": "Example Domain"}], "status": "parsed"}), \
         patch('src.main.sqlite3.connect') as mock_connect:

        # Configure the mock cursor
        mock_cursor = MagicMock()
        mock_connect.return_value.cursor.return_value = mock_cursor

        # Test the endpoint
        response = client.post(
            "/parse",
            params={
                "api_key": TEST_API_KEY,
                "source_type": "web",
                "source_url": "https://example.com"
            }
        )

        assert response.status_code == 200
        data = response.json()
        # For async processing, the response will have task_id and status
        assert "task_id" in data
        assert data["status"] == "processing"

# Test query endpoint
def test_query():
    # Mock the LLM and USE_LLM
    with patch('src.main.USE_LLM', True), \
         patch.object(src.main, 'llm', create=True) as mock_llm:

        # Configure the mock
        mock_llm.invoke.return_value = "This is a response from the LLM"

        # Test the endpoint
        response = client.post(
            "/query",
            params={
                "query": "What is in this document?",
                "api_key": TEST_API_KEY
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert data["response"] == "This is a response from the LLM"

# Test generate_schema endpoint
def test_generate_schema():
    # Mock the LLM, USE_LLM, and parse_document
    with patch('src.main.USE_LLM', True), \
         patch.object(src.main, 'llm', create=True) as mock_llm, \
         patch('src.main.parse_document', return_value={"elements": [{"type": "Text", "text": "Invoice #123, Total: $500"}], "status": "parsed"}):

        # Configure the mock
        mock_llm.invoke.return_value = json.dumps({"invoice_number": "123", "total_amount": "$500"})

        # Test the endpoint
        response = client.post(
            "/generate_schema",
            params={
                "schema_description": "Extract invoice number and total amount",
                "api_key": TEST_API_KEY
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "schema" in data
        assert data["schema"]["invoice_number"] == "123"
        assert data["schema"]["total_amount"] == "$500"

# Test agent endpoint
def test_agent():
    # Mock the LLM, USE_LLM, and parse_document
    with patch('src.main.USE_LLM', True), \
         patch.object(src.main, 'llm', create=True) as mock_llm, \
         patch('src.main.parse_document', return_value={"elements": [{"type": "Text", "text": "Sample text"}], "status": "parsed"}):

        # Configure the mock
        mock_llm.invoke.return_value = json.dumps({"result": "Task completed", "actions": ["Extracted text", "Analyzed content"]})

        # Test the endpoint
        response = client.post(
            "/agent",
            params={
                "task_description": "Extract and analyze text",
                "api_key": TEST_API_KEY
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "actions" in data
        assert len(data["actions"]) == 2

# Test match endpoint
def test_match():
    # Mock the LLM, USE_LLM, and parse_document
    with patch('src.main.USE_LLM', True), \
         patch.object(src.main, 'llm', create=True) as mock_llm, \
         patch('src.main.parse_document', return_value={"elements": [{"type": "Text", "text": "Sample text"}], "status": "parsed"}), \
         patch('src.main.identify_document_type', side_effect=["invoice", "po", "grn"]), \
         patch('src.main.extract_document_info', return_value={"type": "invoice", "invoice_number": "123", "po_number": "456"}):

        # Configure the mock
        mock_llm.invoke.return_value = json.dumps({"match_result": "Documents match", "confidence": 0.95})

        # Create sample files for testing
        with open("invoice.txt", "w") as f:
            f.write("Invoice #123, Total: $500")
        with open("po.txt", "w") as f:
            f.write("PO #456, Total: $500")
        with open("grn.txt", "w") as f:
            f.write("GRN #789, Received: 10 items")

        # Test the endpoint
        with open("invoice.txt", "rb") as f1, open("po.txt", "rb") as f2, open("grn.txt", "rb") as f3:
            response = client.post(
                "/match",
                files=[
                    ("files", ("invoice.txt", f1, "text/plain")),
                    ("files", ("po.txt", f2, "text/plain")),
                    ("files", ("grn.txt", f3, "text/plain"))
                ],
                params={"api_key": TEST_API_KEY}
            )

        # Clean up
        os.remove("invoice.txt")
        os.remove("po.txt")
        os.remove("grn.txt")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "documents" in data
        assert "invoice" in data["documents"]
        assert "po" in data["documents"]
        assert "grn" in data["documents"]

# Test status endpoint
def test_status():
    # Mock the database query
    with patch('src.main.sqlite3.connect') as mock_connect:
        # Configure the mock
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("completed",)
        mock_connect.return_value.cursor.return_value = mock_cursor

        # Test the endpoint
        response = client.get(
            "/status/test-task-id",
            params={"api_key": TEST_API_KEY}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "test-task-id"
        assert data["status"] == "completed"

# Run the tests
if __name__ == "__main__":
    pytest.main(["-v", "test_api.py"])
