#!/usr/bin/env python3
"""
Comprehensive test script for ClaryAI API.

This script tests:
1. Different file types (TXT, CSV, JSON, etc.)
2. Different file sizes (small, medium, large)
3. Multi-batch processing
4. Asynchronous processing

Usage:
    python comprehensive_test.py [--api-url API_URL] [--api-key API_KEY]
"""

import os
import sys
import json
import time
import random
import string
import argparse
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import logging
import concurrent.futures

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("claryai.test")

# Default configuration
DEFAULT_API_URL = "http://localhost:8080"  # Main API server
BATCH_API_URL = "http://localhost:8082"  # Batch test server
DEFAULT_API_KEY = "123e4567-e89b-12d3-a456-426614174000"

# Test file directory
TEST_FILES_DIR = Path("test_files/multi_batch")
if not TEST_FILES_DIR.exists():
    TEST_FILES_DIR.mkdir(parents=True, exist_ok=True)

class ComprehensiveTest:
    """Comprehensive test class for ClaryAI."""

    def __init__(self, api_url: str, api_key: str):
        """Initialize the test class."""
        self.api_url = api_url
        self.api_key = api_key
        self.test_files = {}
        self.results = {
            "single_file": {},
            "multi_batch": {},
            "async_processing": {}
        }
        self.success_count = 0
        self.failure_count = 0
        self.total_tests = 0

    def create_test_files(self):
        """Create test files of different types and sizes."""
        logger.info("Creating test files...")

        # File sizes
        sizes = {
            "small": 1024,  # 1KB
            "medium": 1024 * 10,  # 10KB
            "large": 1024 * 100,  # 100KB
        }

        # Create text files
        for size in sizes:
            file_path = self.create_text_file(size, sizes[size])
            self.test_files[f"txt_{size}"] = file_path

        # Create CSV files
        for size in sizes:
            file_path = self.create_csv_file(size, sizes[size])
            self.test_files[f"csv_{size}"] = file_path

        # Create JSON files
        for size in sizes:
            file_path = self.create_json_file(size, sizes[size])
            self.test_files[f"json_{size}"] = file_path

        # Create HTML files
        for size in sizes:
            file_path = self.create_html_file(size, sizes[size])
            self.test_files[f"html_{size}"] = file_path

        logger.info(f"Created {len(self.test_files)} test files")
        return self.test_files

    def create_text_file(self, size_name: str, size: int) -> str:
        """Create a text file of the specified size."""
        file_path = TEST_FILES_DIR / f"test_{size_name}.txt"

        with open(file_path, "w") as f:
            # Generate random text
            for _ in range(size // 100):
                f.write(''.join(random.choices(string.ascii_letters + string.digits + ' \n', k=100)))

        return str(file_path)

    def create_csv_file(self, size_name: str, size: int) -> str:
        """Create a CSV file of the specified size."""
        file_path = TEST_FILES_DIR / f"test_{size_name}.csv"

        with open(file_path, "w") as f:
            # Write header
            f.write("id,name,value,description\n")

            # Write rows
            rows_count = size // 100
            for i in range(rows_count):
                name = f"item_{i}"
                value = random.random() * 100
                description = ''.join(random.choices(string.ascii_uppercase, k=20))
                f.write(f"{i},{name},{value},{description}\n")

        return str(file_path)

    def create_json_file(self, size_name: str, size: int) -> str:
        """Create a JSON file of the specified size."""
        file_path = TEST_FILES_DIR / f"test_{size_name}.json"

        # Create a JSON structure
        data = {"items": []}
        items_count = size // 200  # Each item will be about 200 bytes

        for i in range(items_count):
            item = {
                "id": i,
                "name": f"item_{i}",
                "value": random.random() * 100,
                "description": ''.join(random.choices(string.ascii_uppercase, k=20)),
                "attributes": {
                    "color": random.choice(["red", "green", "blue", "yellow"]),
                    "size": random.choice(["small", "medium", "large"]),
                    "weight": random.random() * 10
                }
            }
            data["items"].append(item)

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

        return str(file_path)

    def create_html_file(self, size_name: str, size: int) -> str:
        """Create an HTML file of the specified size."""
        file_path = TEST_FILES_DIR / f"test_{size_name}.html"

        with open(file_path, "w") as f:
            f.write("<!DOCTYPE html>\n<html>\n<head>\n<title>Test HTML</title>\n</head>\n<body>\n")

            # Generate paragraphs
            paragraphs_count = size // 200
            for i in range(paragraphs_count):
                f.write(f"<h2>Section {i}</h2>\n")
                f.write(f"<p>{''.join(random.choices(string.ascii_letters + string.digits + ' ', k=150))}</p>\n")

            # Generate a table
            f.write("<table border='1'>\n<tr><th>ID</th><th>Name</th><th>Value</th></tr>\n")
            for i in range(10):
                f.write(f"<tr><td>{i}</td><td>Item {i}</td><td>{random.random() * 100:.2f}</td></tr>\n")
            f.write("</table>\n")

            f.write("</body>\n</html>")

        return str(file_path)

    def test_single_file(self, file_key: str) -> Dict[str, Any]:
        """Test parsing a single file."""
        file_path = self.test_files[file_key]
        file_type = file_key.split('_')[0]
        file_size = file_key.split('_')[1]

        logger.info(f"Testing single file: {file_path} (type: {file_type}, size: {file_size})")

        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                response = requests.post(
                    f"{self.api_url}/parse",
                    files=files,
                    params={"api_key": self.api_key, "source_type": "file"}
                )

            if response.status_code == 200:
                task_id = response.json().get("task_id")
                status = self.check_task_status(task_id)
                self.success_count += 1
                return {
                    "file_key": file_key,
                    "file_path": file_path,
                    "status_code": response.status_code,
                    "task_id": task_id,
                    "task_status": status,
                    "success": True
                }
            else:
                self.failure_count += 1
                return {
                    "file_key": file_key,
                    "file_path": file_path,
                    "status_code": response.status_code,
                    "error": response.text,
                    "success": False
                }
        except Exception as e:
            self.failure_count += 1
            return {
                "file_key": file_key,
                "file_path": file_path,
                "error": str(e),
                "success": False
            }

    def check_task_status(self, task_id: str, max_retries: int = 10) -> Dict[str, Any]:
        """Check the status of a task."""
        for i in range(max_retries):
            try:
                response = requests.get(
                    f"{self.api_url}/status/{task_id}",
                    params={"api_key": self.api_key}
                )

                if response.status_code == 200:
                    status = response.json()
                    if status.get("status") in ["completed", "failed"]:
                        return status

                # Wait before retrying
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error checking task status: {str(e)}")

        return {"status": "unknown", "error": "Max retries reached"}

    def test_multi_batch(self, file_keys: List[str]) -> Dict[str, Any]:
        """Test processing multiple files in a batch."""
        file_paths = [self.test_files[key] for key in file_keys]

        logger.info(f"Testing multi-batch processing with {len(file_paths)} files")

        try:
            files = []
            for file_path in file_paths:
                with open(file_path, "rb") as f:
                    files.append(("files", (os.path.basename(file_path), f.read())))

            # Use the batch test server
            response = requests.post(
                f"{BATCH_API_URL}/batch",
                files=files,
                params={
                    "api_key": self.api_key,
                    "source_type": "file",
                    "async_processing": "true",
                    "max_concurrent": "3"
                }
            )

            if response.status_code == 200:
                batch_id = response.json().get("batch_id")
                task_ids = response.json().get("task_ids", [])

                # Check status of each task
                task_statuses = {}
                for task_id in task_ids:
                    # Use the batch test server for status checks
                    status_response = requests.get(f"{BATCH_API_URL}/status/{task_id}")
                    if status_response.status_code == 200:
                        task_statuses[task_id] = status_response.json()
                    else:
                        task_statuses[task_id] = {"status": "unknown", "error": "Failed to get status"}

                # Check batch status
                batch_status_response = requests.get(f"{BATCH_API_URL}/status/batch/{batch_id}")
                batch_status = {}
                if batch_status_response.status_code == 200:
                    batch_status = batch_status_response.json()

                self.success_count += 1
                return {
                    "file_keys": file_keys,
                    "status_code": response.status_code,
                    "batch_id": batch_id,
                    "task_ids": task_ids,
                    "task_statuses": task_statuses,
                    "batch_status": batch_status,
                    "success": True
                }
            else:
                self.failure_count += 1
                return {
                    "file_keys": file_keys,
                    "status_code": response.status_code,
                    "error": response.text,
                    "success": False
                }
        except Exception as e:
            self.failure_count += 1
            return {
                "file_keys": file_keys,
                "error": str(e),
                "success": False
            }

    def test_async_processing(self, file_key: str) -> Dict[str, Any]:
        """Test asynchronous processing of a file."""
        file_path = self.test_files[file_key]

        logger.info(f"Testing async processing: {file_path}")

        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                response = requests.post(
                    f"{self.api_url}/parse",
                    files=files,
                    params={
                        "api_key": self.api_key,
                        "source_type": "file",
                        "async_processing": "true"
                    }
                )

            if response.status_code == 200:
                task_id = response.json().get("task_id")
                status = self.check_task_status(task_id)
                self.success_count += 1
                return {
                    "file_key": file_key,
                    "file_path": file_path,
                    "status_code": response.status_code,
                    "task_id": task_id,
                    "task_status": status,
                    "success": True
                }
            else:
                self.failure_count += 1
                return {
                    "file_key": file_key,
                    "file_path": file_path,
                    "status_code": response.status_code,
                    "error": response.text,
                    "success": False
                }
        except Exception as e:
            self.failure_count += 1
            return {
                "file_key": file_key,
                "file_path": file_path,
                "error": str(e),
                "success": False
            }

    def run_all_tests(self):
        """Run all tests."""
        logger.info("Starting comprehensive tests...")

        # Create test files
        self.create_test_files()

        # Test single file processing for each file
        logger.info("Testing single file processing...")
        for file_key in self.test_files:
            self.total_tests += 1
            result = self.test_single_file(file_key)
            self.results["single_file"][file_key] = result

        # Test multi-batch processing with different combinations
        logger.info("Testing multi-batch processing...")

        # Test with files of the same type but different sizes
        for file_type in ["txt", "csv", "json", "html"]:
            self.total_tests += 1
            file_keys = [f"{file_type}_{size}" for size in ["small", "medium", "large"]]
            result = self.test_multi_batch(file_keys)
            self.results["multi_batch"][f"same_type_{file_type}"] = result

        # Test with files of the same size but different types
        for size in ["small", "medium", "large"]:
            self.total_tests += 1
            file_keys = [f"{file_type}_{size}" for file_type in ["txt", "csv", "json", "html"]]
            result = self.test_multi_batch(file_keys)
            self.results["multi_batch"][f"same_size_{size}"] = result

        # Test with mixed files
        self.total_tests += 1
        mixed_file_keys = ["txt_small", "csv_medium", "json_large", "html_small"]
        result = self.test_multi_batch(mixed_file_keys)
        self.results["multi_batch"]["mixed"] = result

        # Test async processing
        logger.info("Testing async processing...")
        for file_key in ["txt_large", "csv_large", "json_large", "html_large"]:
            self.total_tests += 1
            result = self.test_async_processing(file_key)
            self.results["async_processing"][file_key] = result

        # Print summary
        self.print_summary()

        return self.results

    def print_summary(self):
        """Print a summary of the test results."""
        logger.info("=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total tests: {self.total_tests}")
        logger.info(f"Successful tests: {self.success_count}")
        logger.info(f"Failed tests: {self.failure_count}")
        logger.info(f"Success rate: {(self.success_count / self.total_tests) * 100:.2f}%")
        logger.info("=" * 80)

        # Print details of failed tests
        if self.failure_count > 0:
            logger.info("FAILED TESTS:")
            for category, results in self.results.items():
                for key, result in results.items():
                    if not result.get("success", False):
                        logger.info(f"- {category} / {key}: {result.get('error', 'Unknown error')}")

        logger.info("=" * 80)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Comprehensive test script for ClaryAI API")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="API URL")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="API key")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    test = ComprehensiveTest(args.api_url, args.api_key)
    results = test.run_all_tests()

    # Save results to file
    with open("test_results.json", "w") as f:
        json.dump(results, f, indent=2)
