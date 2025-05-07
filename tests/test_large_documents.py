"""
Tests for large document processing.
"""

import os
import sys
import unittest
import tempfile
import time
import logging
import json
import random
import string
from pathlib import Path

# Add the parent directory to the path so we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Add the src directory to the path so modules can import each other
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestLargeDocuments(unittest.TestCase):
    """Tests for large document processing."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for test files
        self.test_dir = Path('test_files')
        self.test_dir.mkdir(exist_ok=True)
        
        # Create test files of different sizes
        self.create_test_files()
    
    def tearDown(self):
        """Clean up the test environment."""
        # Remove test files
        for file_path in self.test_files:
            if os.path.exists(file_path):
                os.unlink(file_path)
        
        # Remove the test directory
        if self.test_dir.exists() and not any(self.test_dir.iterdir()):
            self.test_dir.rmdir()
    
    def create_test_files(self):
        """Create test files of different sizes."""
        self.test_files = []
        
        # Create a small text file (10 KB)
        small_file = self.test_dir / 'small.txt'
        with open(small_file, 'w') as f:
            f.write(''.join(random.choices(string.ascii_letters + string.digits + ' \n', k=10 * 1024)))
        self.test_files.append(small_file)
        
        # Create a medium text file (1 MB)
        medium_file = self.test_dir / 'medium.txt'
        with open(medium_file, 'w') as f:
            f.write(''.join(random.choices(string.ascii_letters + string.digits + ' \n', k=1024 * 1024)))
        self.test_files.append(medium_file)
        
        # Create a large text file (10 MB)
        large_file = self.test_dir / 'large.txt'
        with open(large_file, 'w') as f:
            f.write(''.join(random.choices(string.ascii_letters + string.digits + ' \n', k=10 * 1024 * 1024)))
        self.test_files.append(large_file)
        
        logger.info(f"Created test files: {', '.join(str(f) for f in self.test_files)}")
    
    def test_parse_small_file(self):
        """Test parsing a small file."""
        from src.main import parse_file
        
        # Parse the small file
        start_time = time.time()
        elements = parse_file(self.test_files[0])
        end_time = time.time()
        
        # Check the results
        self.assertIsNotNone(elements)
        self.assertGreater(len(elements), 0)
        
        # Log the performance
        duration = end_time - start_time
        logger.info(f"Parsed small file in {duration:.2f} seconds")
        
        # Assert that the parsing is reasonably fast
        self.assertLess(duration, 1.0, "Parsing small file took too long")
    
    def test_parse_medium_file(self):
        """Test parsing a medium file."""
        from src.main import parse_file
        
        # Parse the medium file
        start_time = time.time()
        elements = parse_file(self.test_files[1])
        end_time = time.time()
        
        # Check the results
        self.assertIsNotNone(elements)
        self.assertGreater(len(elements), 0)
        
        # Log the performance
        duration = end_time - start_time
        logger.info(f"Parsed medium file in {duration:.2f} seconds")
        
        # Assert that the parsing is reasonably fast
        self.assertLess(duration, 5.0, "Parsing medium file took too long")
    
    def test_parse_large_file(self):
        """Test parsing a large file."""
        from src.main import parse_file
        
        # Parse the large file
        start_time = time.time()
        elements = parse_file(self.test_files[2])
        end_time = time.time()
        
        # Check the results
        self.assertIsNotNone(elements)
        self.assertGreater(len(elements), 0)
        
        # Log the performance
        duration = end_time - start_time
        logger.info(f"Parsed large file in {duration:.2f} seconds")
        
        # Assert that the parsing is reasonably fast
        self.assertLess(duration, 30.0, "Parsing large file took too long")
    
    def test_async_parse_large_file(self):
        """Test asynchronous parsing of a large file."""
        from src.main import app
        from fastapi.testclient import TestClient
        
        # Create a test client
        client = TestClient(app)
        
        # Submit the large file for asynchronous parsing
        with open(self.test_files[2], 'rb') as f:
            start_time = time.time()
            response = client.post(
                "/parse",
                files={"file": ("large.txt", f, "text/plain")},
                data={"async_processing": "true"},
                headers={"X-API-Key": "test"}
            )
            end_time = time.time()
        
        # Check the response
        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertIn("task_id", data)
        self.assertEqual(data["status"], "processing")
        
        # Log the performance
        duration = end_time - start_time
        logger.info(f"Submitted large file for async parsing in {duration:.2f} seconds")
        
        # Assert that the submission is reasonably fast
        self.assertLess(duration, 1.0, "Submitting large file took too long")
        
        # Check the status of the task
        task_id = data["task_id"]
        max_wait = 60  # Maximum wait time in seconds
        wait_interval = 2  # Wait interval in seconds
        total_wait = 0
        
        while total_wait < max_wait:
            response = client.get(f"/status/{task_id}", headers={"X-API-Key": "test"})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            if data["status"] == "completed":
                logger.info(f"Async parsing completed in {total_wait} seconds")
                break
            
            time.sleep(wait_interval)
            total_wait += wait_interval
        
        # Check that the task completed
        self.assertEqual(data["status"], "completed")
        
        # Get the result
        response = client.get(
            f"/status/{task_id}?include_result=true",
            headers={"X-API-Key": "test"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check the result
        self.assertIn("result", data)
        self.assertIn("elements", data["result"])
        self.assertGreater(len(data["result"]["elements"]), 0)


if __name__ == '__main__':
    unittest.main()
