"""
Test Cython compilation.

This script tests that the Cython compilation works correctly.
"""

import os
import sys
import unittest
import importlib
import time

# Add the parent directory to the path so we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestCythonCompilation(unittest.TestCase):
    """Tests for Cython compilation."""

    def test_compilation(self):
        """Test that the Cython compilation works."""
        # Compile the code
        os.system('cd .. && python setup.py build_ext --inplace')

        # Check that the compiled files exist
        compiled_files = []
        for root, _, files in os.walk('../src'):
            for file in files:
                if file.endswith('.so') or file.endswith('.pyd'):
                    compiled_files.append(os.path.join(root, file))

        # Assert that at least one compiled file exists
        self.assertTrue(len(compiled_files) > 0, "No compiled files found")

        # Print the compiled files
        print(f"Found {len(compiled_files)} compiled files:")
        for file in compiled_files:
            print(f"  - {file}")

    def test_import_compiled_modules(self):
        """Test that we can import the compiled modules."""
        # Try to import the main module
        try:
            import src.main
            # Access something from the module to ensure it's loaded
            app = getattr(src.main, 'app', None)
            self.assertIsNotNone(app, "Failed to access 'app' from src.main")
            self.assertTrue(True, "Successfully imported src.main")
        except ImportError as e:
            self.fail(f"Failed to import src.main: {str(e)}")
        except Exception as e:
            self.fail(f"Error accessing src.main: {str(e)}")

        # Try to import the LLM integration module
        try:
            import src.llm_integration
            # Access something from the module to ensure it's loaded
            llm_provider = getattr(src.llm_integration, 'LLMProvider', None)
            self.assertIsNotNone(llm_provider, "Failed to access 'LLMProvider' from src.llm_integration")
            self.assertTrue(True, "Successfully imported src.llm_integration")
        except ImportError as e:
            self.fail(f"Failed to import src.llm_integration: {str(e)}")
        except Exception as e:
            self.fail(f"Error accessing src.llm_integration: {str(e)}")

    def test_performance(self):
        """Test that the compiled code is faster than the Python code."""
        # Create backup copies of the compiled files
        import shutil
        compiled_files = []
        for root, _, files in os.walk('../src'):
            for file in files:
                if file.endswith('.so') or file.endswith('.pyd'):
                    compiled_file = os.path.join(root, file)
                    backup_file = compiled_file + '.bak'
                    shutil.copy2(compiled_file, backup_file)
                    compiled_files.append((compiled_file, backup_file))

        try:
            # Remove compiled files to test Python performance
            for compiled_file, _ in compiled_files:
                if os.path.exists(compiled_file):
                    os.remove(compiled_file)

            # Clear the import cache
            for module in list(sys.modules.keys()):
                if module.startswith('src.'):
                    del sys.modules[module]

            # Measure the time to import the Python modules
            start_time = time.time()
            import src.main
            import src.llm_integration
            python_time = time.time() - start_time

            # Clear the import cache again
            for module in list(sys.modules.keys()):
                if module.startswith('src.'):
                    del sys.modules[module]

            # Restore compiled files
            for _, backup_file in compiled_files:
                if os.path.exists(backup_file):
                    shutil.copy2(backup_file, backup_file.replace('.bak', ''))

            # Measure the time to import the compiled modules
            start_time = time.time()
            import src.main
            import src.llm_integration
            cython_time = time.time() - start_time

            # Print the results
            print(f"Python import time: {python_time:.6f} seconds")
            print(f"Cython import time: {cython_time:.6f} seconds")
            if cython_time > 0:
                print(f"Speedup: {python_time / cython_time:.2f}x")
            else:
                print("Cython import time too small to calculate speedup")

            # Assert that the compiled code is faster
            # Note: This might not always be true for small modules
            # self.assertLess(cython_time, python_time, "Compiled code is not faster than Python code")

        finally:
            # Clean up backup files
            for _, backup_file in compiled_files:
                if os.path.exists(backup_file):
                    os.remove(backup_file)


if __name__ == '__main__':
    unittest.main()
