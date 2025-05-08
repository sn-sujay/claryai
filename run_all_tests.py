#!/usr/bin/env python3
"""
Master test script for ClaryAI API.

This script runs all the test scripts:
1. Comprehensive test (different file types, sizes, multi-batch processing)
2. Real-world document test (invoices, POs, GRNs, tables)
3. LLM integration test (querying, schema generation, agentic tasks)

Usage:
    python run_all_tests.py [--api-url API_URL] [--api-key API_KEY]
"""

import os
import sys
import json
import time
import argparse
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("claryai.master_test")

# Default configuration
DEFAULT_API_URL = "http://localhost:8080"
DEFAULT_API_KEY = "123e4567-e89b-12d3-a456-426614174000"

def run_test_script(script_name: str, api_url: str, api_key: str) -> bool:
    """Run a test script and return whether it succeeded."""
    logger.info(f"Running {script_name}...")
    
    try:
        result = subprocess.run(
            [sys.executable, script_name, "--api-url", api_url, "--api-key", api_key],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            logger.info(f"{script_name} completed successfully")
            logger.info(result.stdout)
            return True
        else:
            logger.error(f"{script_name} failed with return code {result.returncode}")
            logger.error(result.stderr)
            return False
    except Exception as e:
        logger.error(f"Error running {script_name}: {str(e)}")
        return False

def check_api_availability(api_url: str) -> bool:
    """Check if the API is available."""
    import requests
    
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            logger.info(f"API is available at {api_url}")
            return True
        else:
            logger.error(f"API returned status code {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error connecting to API: {str(e)}")
        return False

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Master test script for ClaryAI API")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="API URL")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="API key")
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()
    
    # Check if the API is available
    if not check_api_availability(args.api_url):
        logger.error("API is not available. Exiting.")
        sys.exit(1)
    
    # Run the test scripts
    test_scripts = [
        "comprehensive_test.py",
        "real_world_test.py",
        "llm_integration_test.py"
    ]
    
    results = {}
    all_passed = True
    
    for script in test_scripts:
        if not os.path.exists(script):
            logger.error(f"Test script {script} not found")
            all_passed = False
            continue
        
        success = run_test_script(script, args.api_url, args.api_key)
        results[script] = success
        
        if not success:
            all_passed = False
    
    # Print summary
    logger.info("=" * 80)
    logger.info("MASTER TEST SUMMARY")
    logger.info("=" * 80)
    
    for script, success in results.items():
        status = "PASSED" if success else "FAILED"
        logger.info(f"{script}: {status}")
    
    logger.info("=" * 80)
    logger.info(f"Overall result: {'PASSED' if all_passed else 'FAILED'}")
    logger.info("=" * 80)
    
    # Exit with appropriate status code
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()
