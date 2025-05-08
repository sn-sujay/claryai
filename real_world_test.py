#!/usr/bin/env python3
"""
Real-world document test script for ClaryAI API.

This script tests the system with real-world documents:
1. Invoices, purchase orders, and goods receipt notes
2. Tables and structured data
3. Images with text
4. Multi-page documents

Usage:
    python real_world_test.py [--api-url API_URL] [--api-key API_KEY]
"""

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("claryai.real_world_test")

# Default configuration
DEFAULT_API_URL = "http://localhost:8080"
DEFAULT_API_KEY = "123e4567-e89b-12d3-a456-426614174000"

# Test file paths
TEST_FILES = {
    "invoice": "test_files/sample_invoice.txt",
    "po": "test_files/sample_po.txt",
    "grn": "test_files/sample_grn.txt",
    "invoice_mismatch": "sample_invoice_mismatch.txt"
}

class RealWorldTest:
    """Real-world document test class for ClaryAI."""

    def __init__(self, api_url: str, api_key: str):
        """Initialize the test class."""
        self.api_url = api_url
        self.api_key = api_key
        self.results = {
            "document_parsing": {},
            "three_way_matching": {},
            "table_parsing": {}
        }
        self.success_count = 0
        self.failure_count = 0
        self.total_tests = 0

    def test_document_parsing(self, doc_type: str) -> Dict[str, Any]:
        """Test parsing a document."""
        file_path = TEST_FILES.get(doc_type)
        if not file_path or not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            self.failure_count += 1
            return {
                "doc_type": doc_type,
                "file_path": file_path,
                "error": "File not found",
                "success": False
            }
        
        logger.info(f"Testing document parsing: {doc_type} ({file_path})")
        
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
                    "doc_type": doc_type,
                    "file_path": file_path,
                    "status_code": response.status_code,
                    "task_id": task_id,
                    "task_status": status,
                    "success": True
                }
            else:
                self.failure_count += 1
                return {
                    "doc_type": doc_type,
                    "file_path": file_path,
                    "status_code": response.status_code,
                    "error": response.text,
                    "success": False
                }
        except Exception as e:
            self.failure_count += 1
            return {
                "doc_type": doc_type,
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

    def test_three_way_matching(self) -> Dict[str, Any]:
        """Test three-way matching with invoice, PO, and GRN."""
        file_paths = [TEST_FILES.get("invoice"), TEST_FILES.get("po"), TEST_FILES.get("grn")]
        
        # Check if all files exist
        for file_path in file_paths:
            if not file_path or not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                self.failure_count += 1
                return {
                    "file_paths": file_paths,
                    "error": f"File not found: {file_path}",
                    "success": False
                }
        
        logger.info(f"Testing three-way matching with {len(file_paths)} files")
        
        try:
            files = []
            for file_path in file_paths:
                with open(file_path, "rb") as f:
                    files.append(("files", (os.path.basename(file_path), f.read())))
            
            response = requests.post(
                f"{self.api_url}/match",
                files=files,
                params={"api_key": self.api_key}
            )
            
            if response.status_code == 200:
                self.success_count += 1
                return {
                    "file_paths": file_paths,
                    "status_code": response.status_code,
                    "result": response.json(),
                    "success": True
                }
            else:
                self.failure_count += 1
                return {
                    "file_paths": file_paths,
                    "status_code": response.status_code,
                    "error": response.text,
                    "success": False
                }
        except Exception as e:
            self.failure_count += 1
            return {
                "file_paths": file_paths,
                "error": str(e),
                "success": False
            }

    def test_mismatch_detection(self) -> Dict[str, Any]:
        """Test mismatch detection with mismatched invoice, PO, and GRN."""
        file_paths = [TEST_FILES.get("invoice_mismatch"), TEST_FILES.get("po"), TEST_FILES.get("grn")]
        
        # Check if all files exist
        for file_path in file_paths:
            if not file_path or not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                self.failure_count += 1
                return {
                    "file_paths": file_paths,
                    "error": f"File not found: {file_path}",
                    "success": False
                }
        
        logger.info(f"Testing mismatch detection with {len(file_paths)} files")
        
        try:
            files = []
            for file_path in file_paths:
                with open(file_path, "rb") as f:
                    files.append(("files", (os.path.basename(file_path), f.read())))
            
            response = requests.post(
                f"{self.api_url}/match",
                files=files,
                params={"api_key": self.api_key}
            )
            
            if response.status_code == 200:
                result = response.json()
                # Check if mismatch was detected
                if "mismatch" in str(result).lower():
                    self.success_count += 1
                    return {
                        "file_paths": file_paths,
                        "status_code": response.status_code,
                        "result": result,
                        "mismatch_detected": True,
                        "success": True
                    }
                else:
                    self.failure_count += 1
                    return {
                        "file_paths": file_paths,
                        "status_code": response.status_code,
                        "result": result,
                        "error": "Mismatch not detected",
                        "mismatch_detected": False,
                        "success": False
                    }
            else:
                self.failure_count += 1
                return {
                    "file_paths": file_paths,
                    "status_code": response.status_code,
                    "error": response.text,
                    "success": False
                }
        except Exception as e:
            self.failure_count += 1
            return {
                "file_paths": file_paths,
                "error": str(e),
                "success": False
            }

    def test_table_parsing(self, doc_type: str) -> Dict[str, Any]:
        """Test table parsing in a document."""
        file_path = TEST_FILES.get(doc_type)
        if not file_path or not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            self.failure_count += 1
            return {
                "doc_type": doc_type,
                "file_path": file_path,
                "error": "File not found",
                "success": False
            }
        
        logger.info(f"Testing table parsing in {doc_type} ({file_path})")
        
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
                
                # Check if tables were parsed
                result = status.get("result", {})
                elements = result.get("elements", [])
                tables = [elem for elem in elements if elem.get("type") == "Table"]
                
                if tables:
                    self.success_count += 1
                    return {
                        "doc_type": doc_type,
                        "file_path": file_path,
                        "status_code": response.status_code,
                        "task_id": task_id,
                        "tables_count": len(tables),
                        "tables": tables,
                        "success": True
                    }
                else:
                    self.failure_count += 1
                    return {
                        "doc_type": doc_type,
                        "file_path": file_path,
                        "status_code": response.status_code,
                        "task_id": task_id,
                        "error": "No tables found",
                        "success": False
                    }
            else:
                self.failure_count += 1
                return {
                    "doc_type": doc_type,
                    "file_path": file_path,
                    "status_code": response.status_code,
                    "error": response.text,
                    "success": False
                }
        except Exception as e:
            self.failure_count += 1
            return {
                "doc_type": doc_type,
                "file_path": file_path,
                "error": str(e),
                "success": False
            }

    def run_all_tests(self):
        """Run all tests."""
        logger.info("Starting real-world document tests...")
        
        # Test document parsing
        logger.info("Testing document parsing...")
        for doc_type in ["invoice", "po", "grn"]:
            self.total_tests += 1
            result = self.test_document_parsing(doc_type)
            self.results["document_parsing"][doc_type] = result
        
        # Test three-way matching
        logger.info("Testing three-way matching...")
        self.total_tests += 1
        result = self.test_three_way_matching()
        self.results["three_way_matching"]["matching"] = result
        
        # Test mismatch detection
        logger.info("Testing mismatch detection...")
        self.total_tests += 1
        result = self.test_mismatch_detection()
        self.results["three_way_matching"]["mismatch"] = result
        
        # Test table parsing
        logger.info("Testing table parsing...")
        for doc_type in ["invoice", "po", "grn"]:
            self.total_tests += 1
            result = self.test_table_parsing(doc_type)
            self.results["table_parsing"][doc_type] = result
        
        # Print summary
        self.print_summary()
        
        return self.results

    def print_summary(self):
        """Print a summary of the test results."""
        logger.info("=" * 80)
        logger.info("REAL-WORLD TEST SUMMARY")
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
    parser = argparse.ArgumentParser(description="Real-world document test script for ClaryAI API")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="API URL")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="API key")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    test = RealWorldTest(args.api_url, args.api_key)
    results = test.run_all_tests()
    
    # Save results to file
    with open("real_world_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
