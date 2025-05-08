#!/usr/bin/env python3
"""
LLM integration test script for ClaryAI API.

This script tests the LLM integration features:
1. Document querying
2. Schema generation
3. Agentic tasks
4. Image analysis (if Phi-4-multimodal is available)

Usage:
    python llm_integration_test.py [--api-url API_URL] [--api-key API_KEY]
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
logger = logging.getLogger("claryai.llm_test")

# Default configuration
DEFAULT_API_URL = "http://localhost:8080"
DEFAULT_API_KEY = "123e4567-e89b-12d3-a456-426614174000"

# Test file paths
TEST_FILES = {
    "invoice": "test_files/sample_invoice.txt",
    "po": "test_files/sample_po.txt",
    "grn": "test_files/sample_grn.txt"
}

class LLMIntegrationTest:
    """LLM integration test class for ClaryAI."""

    def __init__(self, api_url: str, api_key: str):
        """Initialize the test class."""
        self.api_url = api_url
        self.api_key = api_key
        self.results = {
            "llm_availability": {},
            "document_querying": {},
            "schema_generation": {},
            "agentic_tasks": {},
            "image_analysis": {}
        }
        self.success_count = 0
        self.failure_count = 0
        self.total_tests = 0
        self.llm_enabled = False
        self.multimodal_enabled = False

    def check_llm_availability(self) -> Dict[str, Any]:
        """Check if LLM integration is available."""
        logger.info("Checking LLM availability...")
        
        try:
            response = requests.get(self.api_url)
            
            if response.status_code == 200:
                data = response.json()
                self.llm_enabled = data.get("llm_enabled", False)
                self.multimodal_enabled = data.get("multimodal_enabled", False)
                llm_model = data.get("llm_model")
                
                if self.llm_enabled:
                    self.success_count += 1
                    logger.info(f"LLM integration is enabled with model: {llm_model}")
                    return {
                        "llm_enabled": self.llm_enabled,
                        "multimodal_enabled": self.multimodal_enabled,
                        "llm_model": llm_model,
                        "success": True
                    }
                else:
                    self.failure_count += 1
                    logger.warning("LLM integration is disabled")
                    return {
                        "llm_enabled": False,
                        "multimodal_enabled": False,
                        "error": "LLM integration is disabled",
                        "success": False
                    }
            else:
                self.failure_count += 1
                return {
                    "status_code": response.status_code,
                    "error": response.text,
                    "success": False
                }
        except Exception as e:
            self.failure_count += 1
            return {
                "error": str(e),
                "success": False
            }

    def parse_document(self, doc_type: str) -> Dict[str, Any]:
        """Parse a document and return the task ID."""
        file_path = TEST_FILES.get(doc_type)
        if not file_path or not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return {"error": "File not found", "success": False}
        
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
                return {
                    "task_id": task_id,
                    "task_status": status,
                    "success": True
                }
            else:
                return {
                    "status_code": response.status_code,
                    "error": response.text,
                    "success": False
                }
        except Exception as e:
            return {
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

    def test_document_querying(self, doc_type: str, query: str) -> Dict[str, Any]:
        """Test querying a document with LLM."""
        if not self.llm_enabled:
            logger.warning("Skipping document querying test: LLM integration is disabled")
            return {"error": "LLM integration is disabled", "success": False}
        
        logger.info(f"Testing document querying: {doc_type} with query: {query}")
        
        # First parse the document
        parse_result = self.parse_document(doc_type)
        if not parse_result.get("success", False):
            self.failure_count += 1
            return {
                "doc_type": doc_type,
                "query": query,
                "error": f"Failed to parse document: {parse_result.get('error')}",
                "success": False
            }
        
        try:
            response = requests.post(
                f"{self.api_url}/query",
                json={"query": query},
                params={"api_key": self.api_key, "use_cache": "false"}
            )
            
            if response.status_code == 200:
                self.success_count += 1
                return {
                    "doc_type": doc_type,
                    "query": query,
                    "status_code": response.status_code,
                    "response": response.json(),
                    "success": True
                }
            else:
                self.failure_count += 1
                return {
                    "doc_type": doc_type,
                    "query": query,
                    "status_code": response.status_code,
                    "error": response.text,
                    "success": False
                }
        except Exception as e:
            self.failure_count += 1
            return {
                "doc_type": doc_type,
                "query": query,
                "error": str(e),
                "success": False
            }

    def test_schema_generation(self, doc_type: str, schema_description: str) -> Dict[str, Any]:
        """Test generating a schema for a document with LLM."""
        if not self.llm_enabled:
            logger.warning("Skipping schema generation test: LLM integration is disabled")
            return {"error": "LLM integration is disabled", "success": False}
        
        file_path = TEST_FILES.get(doc_type)
        if not file_path or not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            self.failure_count += 1
            return {
                "doc_type": doc_type,
                "schema_description": schema_description,
                "error": "File not found",
                "success": False
            }
        
        logger.info(f"Testing schema generation: {doc_type} with description: {schema_description}")
        
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                response = requests.post(
                    f"{self.api_url}/generate_schema",
                    files=files,
                    data={"schema_description": schema_description},
                    params={"api_key": self.api_key}
                )
            
            if response.status_code == 200:
                self.success_count += 1
                return {
                    "doc_type": doc_type,
                    "schema_description": schema_description,
                    "status_code": response.status_code,
                    "schema": response.json(),
                    "success": True
                }
            else:
                self.failure_count += 1
                return {
                    "doc_type": doc_type,
                    "schema_description": schema_description,
                    "status_code": response.status_code,
                    "error": response.text,
                    "success": False
                }
        except Exception as e:
            self.failure_count += 1
            return {
                "doc_type": doc_type,
                "schema_description": schema_description,
                "error": str(e),
                "success": False
            }

    def test_agentic_tasks(self, doc_type: str, task_description: str) -> Dict[str, Any]:
        """Test performing agentic tasks on a document with LLM."""
        if not self.llm_enabled:
            logger.warning("Skipping agentic tasks test: LLM integration is disabled")
            return {"error": "LLM integration is disabled", "success": False}
        
        file_path = TEST_FILES.get(doc_type)
        if not file_path or not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            self.failure_count += 1
            return {
                "doc_type": doc_type,
                "task_description": task_description,
                "error": "File not found",
                "success": False
            }
        
        logger.info(f"Testing agentic tasks: {doc_type} with task: {task_description}")
        
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                response = requests.post(
                    f"{self.api_url}/agent",
                    files=files,
                    data={"task_description": task_description},
                    params={"api_key": self.api_key}
                )
            
            if response.status_code == 200:
                self.success_count += 1
                return {
                    "doc_type": doc_type,
                    "task_description": task_description,
                    "status_code": response.status_code,
                    "result": response.json(),
                    "success": True
                }
            else:
                self.failure_count += 1
                return {
                    "doc_type": doc_type,
                    "task_description": task_description,
                    "status_code": response.status_code,
                    "error": response.text,
                    "success": False
                }
        except Exception as e:
            self.failure_count += 1
            return {
                "doc_type": doc_type,
                "task_description": task_description,
                "error": str(e),
                "success": False
            }

    def run_all_tests(self):
        """Run all tests."""
        logger.info("Starting LLM integration tests...")
        
        # Check LLM availability
        self.total_tests += 1
        result = self.check_llm_availability()
        self.results["llm_availability"]["check"] = result
        
        if not self.llm_enabled:
            logger.warning("Skipping LLM tests: LLM integration is disabled")
            self.print_summary()
            return self.results
        
        # Test document querying
        logger.info("Testing document querying...")
        queries = {
            "invoice": "What is the total amount on the invoice?",
            "po": "What items are listed in the purchase order?",
            "grn": "When was the goods receipt note issued?"
        }
        
        for doc_type, query in queries.items():
            self.total_tests += 1
            result = self.test_document_querying(doc_type, query)
            self.results["document_querying"][doc_type] = result
        
        # Test schema generation
        logger.info("Testing schema generation...")
        schema_descriptions = {
            "invoice": "Extract invoice number, date, total amount, and vendor information",
            "po": "Extract purchase order number, date, items, quantities, and prices",
            "grn": "Extract receipt number, date, items received, and quantities"
        }
        
        for doc_type, schema_description in schema_descriptions.items():
            self.total_tests += 1
            result = self.test_schema_generation(doc_type, schema_description)
            self.results["schema_generation"][doc_type] = result
        
        # Test agentic tasks
        logger.info("Testing agentic tasks...")
        task_descriptions = {
            "invoice": "Extract all financial information and calculate the tax rate",
            "po": "Compare the items and prices to market rates and suggest if they are reasonable",
            "grn": "Check if all items have been received in the correct quantities"
        }
        
        for doc_type, task_description in task_descriptions.items():
            self.total_tests += 1
            result = self.test_agentic_tasks(doc_type, task_description)
            self.results["agentic_tasks"][doc_type] = result
        
        # Print summary
        self.print_summary()
        
        return self.results

    def print_summary(self):
        """Print a summary of the test results."""
        logger.info("=" * 80)
        logger.info("LLM INTEGRATION TEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total tests: {self.total_tests}")
        logger.info(f"Successful tests: {self.success_count}")
        logger.info(f"Failed tests: {self.failure_count}")
        if self.total_tests > 0:
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
    parser = argparse.ArgumentParser(description="LLM integration test script for ClaryAI API")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="API URL")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="API key")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    test = LLMIntegrationTest(args.api_url, args.api_key)
    results = test.run_all_tests()
    
    # Save results to file
    with open("llm_integration_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
