#!/usr/bin/env python3
"""
Comprehensive test suite for ClaryAI.

This script runs all tests for ClaryAI, including:
- Unit tests for individual components
- Integration tests for API endpoints
- Performance tests for large documents
- Edge case tests for unusual inputs
"""

import os
import sys
import unittest
import json
import time
import logging
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Add the parent directory to the path so we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_results.log')
    ]
)
logger = logging.getLogger(__name__)

# Import test modules
from tests.test_cython_compilation import TestCythonCompilation
from tests.test_llm_integration import TestLLMIntegration

# Import additional test modules if they exist
try:
    from tests.test_cloud_connectors import TestCloudConnectors
    has_cloud_connectors_tests = True
except ImportError:
    has_cloud_connectors_tests = False

try:
    from tests.test_additional_connectors import TestAdditionalConnectors
    has_additional_connectors_tests = True
except ImportError:
    has_additional_connectors_tests = False

try:
    from tests.test_more_connectors import TestMoreConnectors
    has_more_connectors_tests = True
except ImportError:
    has_more_connectors_tests = False


class TestPerformance(unittest.TestCase):
    """Performance tests for ClaryAI."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for test files
        self.test_dir = Path('test_files')
        self.test_dir.mkdir(exist_ok=True)
        
        # Create a large test file
        self.large_file = self.test_dir / 'large_file.txt'
        with open(self.large_file, 'w') as f:
            f.write('This is a test.\n' * 10000)
    
    def tearDown(self):
        """Clean up the test environment."""
        # Remove the test files
        if self.large_file.exists():
            self.large_file.unlink()
        
        # Remove the test directory
        if self.test_dir.exists():
            self.test_dir.rmdir()
    
    def test_parse_large_file(self):
        """Test parsing a large file."""
        from src.main import parse_file
        
        # Parse the large file
        start_time = time.time()
        elements = parse_file(self.large_file)
        end_time = time.time()
        
        # Check the results
        self.assertIsNotNone(elements)
        self.assertGreater(len(elements), 0)
        
        # Log the performance
        duration = end_time - start_time
        logger.info(f"Parsed large file in {duration:.2f} seconds")
        
        # Assert that the parsing is reasonably fast
        self.assertLess(duration, 10.0, "Parsing large file took too long")
    
    def test_concurrent_requests(self):
        """Test handling concurrent requests."""
        from src.main import parse_file
        
        # Create multiple small files
        num_files = 10
        files = []
        for i in range(num_files):
            file_path = self.test_dir / f'file_{i}.txt'
            with open(file_path, 'w') as f:
                f.write(f'This is test file {i}.\n' * 100)
            files.append(file_path)
        
        # Parse the files concurrently
        start_time = time.time()
        
        def parse_file_wrapper(file_path):
            return parse_file(file_path)
        
        with ThreadPoolExecutor(max_workers=num_files) as executor:
            results = list(executor.map(parse_file_wrapper, files))
        
        end_time = time.time()
        
        # Check the results
        for result in results:
            self.assertIsNotNone(result)
            self.assertGreater(len(result), 0)
        
        # Log the performance
        duration = end_time - start_time
        logger.info(f"Parsed {num_files} files concurrently in {duration:.2f} seconds")
        
        # Assert that the concurrent parsing is reasonably fast
        self.assertLess(duration, 20.0, "Concurrent parsing took too long")
        
        # Clean up the files
        for file_path in files:
            if file_path.exists():
                file_path.unlink()


class TestEdgeCases(unittest.TestCase):
    """Edge case tests for ClaryAI."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for test files
        self.test_dir = Path('test_files')
        self.test_dir.mkdir(exist_ok=True)
    
    def tearDown(self):
        """Clean up the test environment."""
        # Remove the test directory if it's empty
        if self.test_dir.exists() and not any(self.test_dir.iterdir()):
            self.test_dir.rmdir()
    
    def test_empty_file(self):
        """Test parsing an empty file."""
        from src.main import parse_file
        
        # Create an empty file
        empty_file = self.test_dir / 'empty.txt'
        with open(empty_file, 'w') as f:
            pass
        
        # Parse the empty file
        elements = parse_file(empty_file)
        
        # Check the results
        self.assertIsNotNone(elements)
        self.assertEqual(len(elements), 0)
        
        # Clean up
        empty_file.unlink()
    
    def test_binary_file(self):
        """Test parsing a binary file."""
        from src.main import parse_file
        
        # Create a binary file
        binary_file = self.test_dir / 'binary.bin'
        with open(binary_file, 'wb') as f:
            f.write(os.urandom(1024))
        
        # Parse the binary file
        elements = parse_file(binary_file)
        
        # Check the results
        self.assertIsNotNone(elements)
        
        # Clean up
        binary_file.unlink()
    
    def test_special_characters(self):
        """Test parsing a file with special characters."""
        from src.main import parse_file
        
        # Create a file with special characters
        special_file = self.test_dir / 'special.txt'
        with open(special_file, 'w', encoding='utf-8') as f:
            f.write('Special characters: áéíóúñÁÉÍÓÚÑ¿¡€£¥©®™\n')
            f.write('Symbols: !"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~\n')
            f.write('Emojis: 😀😁😂🤣😃😄😅😆😉😊\n')
        
        # Parse the file with special characters
        elements = parse_file(special_file)
        
        # Check the results
        self.assertIsNotNone(elements)
        self.assertGreater(len(elements), 0)
        
        # Clean up
        special_file.unlink()


def run_all_tests():
    """Run all tests."""
    # Create a test suite
    test_suite = unittest.TestSuite()
    
    # Add the test cases
    test_suite.addTest(unittest.makeSuite(TestCythonCompilation))
    test_suite.addTest(unittest.makeSuite(TestLLMIntegration))
    test_suite.addTest(unittest.makeSuite(TestPerformance))
    test_suite.addTest(unittest.makeSuite(TestEdgeCases))
    
    # Add additional test cases if available
    if has_cloud_connectors_tests:
        test_suite.addTest(unittest.makeSuite(TestCloudConnectors))
    
    if has_additional_connectors_tests:
        test_suite.addTest(unittest.makeSuite(TestAdditionalConnectors))
    
    if has_more_connectors_tests:
        test_suite.addTest(unittest.makeSuite(TestMoreConnectors))
    
    # Run the tests
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # Return the result
    return result


if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run ClaryAI tests')
    parser.add_argument('--performance', action='store_true', help='Run performance tests only')
    parser.add_argument('--edge-cases', action='store_true', help='Run edge case tests only')
    parser.add_argument('--cython', action='store_true', help='Run Cython compilation tests only')
    parser.add_argument('--llm', action='store_true', help='Run LLM integration tests only')
    parser.add_argument('--connectors', action='store_true', help='Run connector tests only')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    args = parser.parse_args()
    
    # Run the specified tests
    if args.performance:
        unittest.main(argv=['first-arg-is-ignored', 'TestPerformance'])
    elif args.edge_cases:
        unittest.main(argv=['first-arg-is-ignored', 'TestEdgeCases'])
    elif args.cython:
        unittest.main(argv=['first-arg-is-ignored', 'TestCythonCompilation'])
    elif args.llm:
        unittest.main(argv=['first-arg-is-ignored', 'TestLLMIntegration'])
    elif args.connectors:
        if has_cloud_connectors_tests or has_additional_connectors_tests or has_more_connectors_tests:
            test_suite = unittest.TestSuite()
            if has_cloud_connectors_tests:
                test_suite.addTest(unittest.makeSuite(TestCloudConnectors))
            if has_additional_connectors_tests:
                test_suite.addTest(unittest.makeSuite(TestAdditionalConnectors))
            if has_more_connectors_tests:
                test_suite.addTest(unittest.makeSuite(TestMoreConnectors))
            unittest.TextTestRunner(verbosity=2).run(test_suite)
        else:
            print("No connector tests available")
    elif args.all or not any([args.performance, args.edge_cases, args.cython, args.llm, args.connectors]):
        result = run_all_tests()
        sys.exit(0 if result.wasSuccessful() else 1)
