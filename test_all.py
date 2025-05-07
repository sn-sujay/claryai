#!/usr/bin/env python3
"""
Comprehensive test script for ClaryAI API.
Tests all core functionality including:
- Synchronous document processing
- Asynchronous document processing
- Three-way matching
- Status checking and result retrieval
"""

import os
import sys
import json
import time
import requests
import argparse
from typing import Dict, Any, Optional, List

# Configuration
API_BASE_URL = "http://localhost:8080"
API_KEY = "123e4567-e89b-12d3-a456-426614174000"
TEST_FILES = {
    "invoice": "sample_invoice.txt",
    "po": "sample_po.txt",
    "grn": "sample_grn.txt",
    "invoice_mismatch": "sample_invoice_mismatch.txt"
}

# ANSI color codes for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{BOLD}{YELLOW}{'=' * 80}{RESET}")
    print(f"{BOLD}{YELLOW}  {text}{RESET}")
    print(f"{BOLD}{YELLOW}{'=' * 80}{RESET}\n")

def print_success(text: str) -> None:
    """Print a success message."""
    print(f"{GREEN}✓ {text}{RESET}")

def print_error(text: str) -> None:
    """Print an error message."""
    print(f"{RED}✗ {text}{RESET}")

def print_info(text: str) -> None:
    """Print an info message."""
    print(f"{YELLOW}ℹ {text}{RESET}")

def check_api_health() -> bool:
    """Check if the API is healthy."""
    try:
        response = requests.get(f"{API_BASE_URL}/")
        if response.status_code == 200:
            print_success("API is healthy")
            return True
        else:
            print_error(f"API returned status code {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Failed to connect to API: {str(e)}")
        return False

def test_sync_processing(file_path: str) -> bool:
    """Test synchronous document processing."""
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            response = requests.post(
                f"{API_BASE_URL}/parse",
                params={"api_key": API_KEY},
                files=files
            )

        if response.status_code == 200:
            result = response.json()
            if "elements" in result and "status" in result and result["status"] == "parsed":
                print_success(f"Synchronous processing successful for {file_path}")
                return True
            else:
                print_error(f"Unexpected response format: {result}")
                return False
        else:
            print_error(f"API returned status code {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print_error(f"Failed to test synchronous processing: {str(e)}")
        return False

def test_async_processing(file_path: str) -> Dict[str, Any]:
    """Test asynchronous document processing."""
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            response = requests.post(
                f"{API_BASE_URL}/parse",
                params={"api_key": API_KEY, "async_processing": "true"},
                files=files
            )

        if response.status_code == 200:
            result = response.json()
            if "task_id" in result and "status" in result and result["status"] == "processing":
                print_success(f"Asynchronous processing initiated for {file_path}")
                return result
            else:
                print_error(f"Unexpected response format: {result}")
                return {}
        else:
            print_error(f"API returned status code {response.status_code}: {response.text}")
            return {}
    except Exception as e:
        print_error(f"Failed to test asynchronous processing: {str(e)}")
        return {}

def test_status_check(task_id: str, include_result: bool = False) -> Dict[str, Any]:
    """Test status checking and result retrieval."""
    try:
        params = {"api_key": API_KEY}
        if include_result:
            params["include_result"] = "true"

        response = requests.get(
            f"{API_BASE_URL}/status/{task_id}",
            params=params
        )

        if response.status_code == 200:
            result = response.json()
            if "task_id" in result and "status" in result:
                status = result["status"]
                if status == "completed":
                    print_success(f"Task {task_id} completed successfully")
                    if include_result and "result" in result:
                        print_success("Result retrieved successfully")
                    elif include_result:
                        print_error("Result not included in response")
                else:
                    print_info(f"Task {task_id} status: {status}")
                return result
            else:
                print_error(f"Unexpected response format: {result}")
                return {}
        else:
            print_error(f"API returned status code {response.status_code}: {response.text}")
            return {}
    except Exception as e:
        print_error(f"Failed to check status: {str(e)}")
        return {}

def test_three_way_match(match_files: List[str], expected_match: bool = True) -> bool:
    """Test three-way matching."""
    try:
        files = []
        for file_path in match_files:
            files.append(("files", open(file_path, "rb")))

        response = requests.post(
            f"{API_BASE_URL}/match",
            params={"api_key": API_KEY},
            files=files
        )

        # Close all file handles
        for _, file_handle in files:
            file_handle.close()

        if response.status_code == 200:
            result = response.json()
            if "status" in result:
                match_status = result["status"]
                is_match = match_status == "complete_match"

                if is_match == expected_match:
                    print_success(f"Three-way match result as expected: {match_status}")
                    return True
                else:
                    print_error(f"Unexpected match result: {match_status}, expected match: {expected_match}")
                    return False
            else:
                print_error(f"Unexpected response format: {result}")
                return False
        else:
            print_error(f"API returned status code {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print_error(f"Failed to test three-way matching: {str(e)}")
        return False

def wait_for_task_completion(task_id: str, max_wait_seconds: int = 60) -> Dict[str, Any]:
    """Wait for a task to complete and return the result."""
    print_info(f"Waiting for task {task_id} to complete (max {max_wait_seconds} seconds)...")

    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        result = test_status_check(task_id)
        if result.get("status") == "completed":
            return test_status_check(task_id, include_result=True)
        time.sleep(2)

    print_error(f"Task {task_id} did not complete within {max_wait_seconds} seconds")
    return {}

def run_all_tests() -> None:
    """Run all tests."""
    print_header("ClaryAI API Test Suite")

    # Check API health
    if not check_api_health():
        print_error("API health check failed. Aborting tests.")
        return

    # Test synchronous processing
    print_header("Testing Synchronous Processing")
    sync_success = test_sync_processing(TEST_FILES["invoice"])

    # Test asynchronous processing
    print_header("Testing Asynchronous Processing")
    async_result = test_async_processing(TEST_FILES["po"])
    if async_result:
        task_id = async_result.get("task_id")
        if task_id:
            result = wait_for_task_completion(task_id)
            async_success = "result" in result
        else:
            async_success = False
    else:
        async_success = False

    # Test three-way matching
    print_header("Testing Three-Way Matching")
    match_files = [TEST_FILES["invoice"], TEST_FILES["po"], TEST_FILES["grn"]]
    match_success = test_three_way_match(match_files, expected_match=True)

    # Test three-way matching with mismatch
    print_header("Testing Three-Way Matching (Mismatch)")
    mismatch_files = [TEST_FILES["invoice_mismatch"], TEST_FILES["po"], TEST_FILES["grn"]]
    mismatch_success = test_three_way_match(mismatch_files, expected_match=False)

    # Print summary
    print_header("Test Summary")
    if sync_success:
        print_success("Synchronous Processing: PASSED")
    else:
        print_error("Synchronous Processing: FAILED")

    if async_success:
        print_success("Asynchronous Processing: PASSED")
    else:
        print_error("Asynchronous Processing: FAILED")

    if match_success:
        print_success("Three-Way Matching: PASSED")
    else:
        print_error("Three-Way Matching: FAILED")

    if mismatch_success:
        print_success("Three-Way Matching (Mismatch): PASSED")
    else:
        print_error("Three-Way Matching (Mismatch): FAILED")

    overall_success = sync_success and async_success and match_success and mismatch_success
    if overall_success:
        print_success("\nAll tests PASSED!")
    else:
        print_error("\nSome tests FAILED!")

if __name__ == "__main__":
    run_all_tests()
