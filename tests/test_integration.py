"""
Test the integration between unstructured.io, LlamaIndex, and Phi-4-multimodal.
"""

import os
import sys
import unittest
import tempfile
import logging
import json
from pathlib import Path

# Add the parent directory to the path so we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestIntegration(unittest.TestCase):
    """Test the integration between unstructured.io, LlamaIndex, and Phi-4-multimodal."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a test file
        self.test_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=False)
        with open(self.test_file.name, 'w') as f:
            f.write("This is a test document.\n")
            f.write("It contains multiple paragraphs.\n\n")
            f.write("This is the second paragraph.\n")
            f.write("It also contains multiple sentences.\n\n")
            f.write("Here is a table:\n")
            f.write("| Name | Age | City |\n")
            f.write("| ---- | --- | ---- |\n")
            f.write("| John | 30  | New York |\n")
            f.write("| Jane | 25  | San Francisco |\n")
    
    def tearDown(self):
        """Clean up the test environment."""
        # Remove the test file
        if os.path.exists(self.test_file.name):
            os.unlink(self.test_file.name)
    
    def test_unstructured_parsing(self):
        """Test parsing with unstructured.io."""
        try:
            from unstructured.partition.auto import partition
            
            # Parse the file
            elements = partition(self.test_file.name)
            
            # Check the results
            self.assertIsNotNone(elements)
            self.assertGreater(len(elements), 0)
            
            # Log the elements
            logger.info(f"Parsed {len(elements)} elements with unstructured.io")
            for i, element in enumerate(elements):
                logger.info(f"Element {i}: {type(element).__name__} - {str(element)[:50]}...")
            
            # Test passed
            logger.info("unstructured.io parsing test passed")
            return elements
        except ImportError:
            logger.error("unstructured.io not available")
            self.skipTest("unstructured.io not available")
        except Exception as e:
            logger.error(f"unstructured.io parsing failed: {str(e)}")
            self.fail(f"unstructured.io parsing failed: {str(e)}")
    
    def test_llamaindex_chunking(self):
        """Test chunking with LlamaIndex."""
        try:
            # First parse with unstructured.io
            elements = self.test_unstructured_parsing()
            if not elements:
                self.skipTest("unstructured.io parsing failed")
            
            # Import LlamaIndex
            from llama_index.core import Document
            from llama_index.core.node_parser import SentenceSplitter
            
            # Convert elements to text
            text = "\n\n".join([str(element) for element in elements])
            document = Document(text=text)
            
            # Apply chunking
            splitter = SentenceSplitter(chunk_size=512)
            nodes = splitter.get_nodes_from_documents([document])
            
            # Check the results
            self.assertIsNotNone(nodes)
            self.assertGreater(len(nodes), 0)
            
            # Log the nodes
            logger.info(f"Created {len(nodes)} nodes with LlamaIndex")
            for i, node in enumerate(nodes):
                logger.info(f"Node {i}: {node.text[:50]}...")
            
            # Test passed
            logger.info("LlamaIndex chunking test passed")
            return nodes
        except ImportError:
            logger.error("LlamaIndex not available")
            self.skipTest("LlamaIndex not available")
        except Exception as e:
            logger.error(f"LlamaIndex chunking failed: {str(e)}")
            self.fail(f"LlamaIndex chunking failed: {str(e)}")
    
    def test_phi4_integration(self):
        """Test integration with Phi-4-multimodal."""
        try:
            # First chunk with LlamaIndex
            nodes = self.test_llamaindex_chunking()
            if not nodes:
                self.skipTest("LlamaIndex chunking failed")
            
            # Import LLM integration
            from src.llm_integration import get_llm_integration
            
            # Get LLM integration
            llm = get_llm_integration()
            if not llm:
                logger.warning("LLM integration not available")
                self.skipTest("LLM integration not available")
            
            # Create a prompt
            prompt = f"Summarize this document: {nodes[0].text}"
            
            # Invoke the LLM
            response = llm.invoke(prompt)
            
            # Check the results
            self.assertIsNotNone(response)
            self.assertGreater(len(str(response)), 0)
            
            # Log the response
            logger.info(f"LLM response: {str(response)[:100]}...")
            
            # Test passed
            logger.info("Phi-4-multimodal integration test passed")
            return response
        except ImportError:
            logger.error("Phi-4-multimodal integration not available")
            self.skipTest("Phi-4-multimodal integration not available")
        except Exception as e:
            logger.error(f"Phi-4-multimodal integration failed: {str(e)}")
            self.fail(f"Phi-4-multimodal integration failed: {str(e)}")
    
    def test_full_integration(self):
        """Test the full integration pipeline."""
        try:
            # Run the Phi-4-multimodal integration test
            response = self.test_phi4_integration()
            if not response:
                self.skipTest("Phi-4-multimodal integration failed")
            
            # Test passed
            logger.info("Full integration pipeline test passed")
        except Exception as e:
            logger.error(f"Full integration pipeline failed: {str(e)}")
            self.fail(f"Full integration pipeline failed: {str(e)}")


if __name__ == '__main__':
    unittest.main()
