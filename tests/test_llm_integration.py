"""
Tests for LLM integration.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add the parent directory to the path so we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Add the src directory to the path so modules can import each other
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.llm_integration import (
    LLMIntegration,
    LLMProvider,
    get_llm_integration,
    PROMPT_TEMPLATES
)


class TestLLMIntegration(unittest.TestCase):
    """Tests for the LLMIntegration class."""

    @patch('src.llm_integration.LLMIntegration._initialize_llm')
    def test_init(self, mock_initialize):
        """Test initialization."""
        # Create the integration
        integration = LLMIntegration(
            provider=LLMProvider.OLLAMA.value,
            model="phi-4-multimodal",
            endpoint="",
            api_key=""
        )

        # Check the attributes
        self.assertEqual(integration.provider, LLMProvider.OLLAMA.value)
        self.assertEqual(integration.model, "phi-4-multimodal")
        self.assertEqual(integration.endpoint, "")
        self.assertEqual(integration.api_key, "")

        # Check that _initialize_llm was called
        mock_initialize.assert_called_once()

    @patch('langchain_community.llms.Ollama')
    def test_initialize_ollama(self, mock_ollama):
        """Test initializing Ollama."""
        # Set up the mock
        mock_ollama_instance = MagicMock()
        mock_ollama.return_value = mock_ollama_instance

        # Create the integration
        with patch('src.llm_integration.LLMIntegration._initialize_llm'):
            integration = LLMIntegration(
                provider=LLMProvider.OLLAMA.value,
                model="phi-4-multimodal"
            )

        # Mock the import
        with patch('src.llm_integration.import_optional', return_value=mock_ollama):
            # Call the method
            integration._initialize_llm()

        # Check the result
        mock_ollama.assert_called_once_with(model="phi-4-multimodal")
        self.assertEqual(integration.llm, mock_ollama_instance)

    @patch('langchain_openai.ChatOpenAI')
    def test_initialize_openai(self, mock_openai):
        """Test initializing OpenAI."""
        # Set up the mock
        mock_openai_instance = MagicMock()
        mock_openai.return_value = mock_openai_instance

        # Create the integration
        with patch('src.llm_integration.LLMIntegration._initialize_llm'):
            integration = LLMIntegration(
                provider=LLMProvider.OPENAI.value,
                endpoint="https://api.openai.com/v1",
                api_key="sk-123"
            )

        # Mock the import
        with patch('src.llm_integration.import_optional', return_value=mock_openai):
            # Call the method
            integration._initialize_llm()

        # Check the result
        mock_openai.assert_called_once_with(api_key="sk-123", base_url="https://api.openai.com/v1")
        self.assertEqual(integration.llm, mock_openai_instance)

    @patch('langchain_community.llms.HuggingFaceEndpoint')
    def test_initialize_huggingface(self, mock_hf):
        """Test initializing HuggingFace."""
        # Set up the mock
        mock_hf_instance = MagicMock()
        mock_hf.return_value = mock_hf_instance

        # Create the integration
        with patch('src.llm_integration.LLMIntegration._initialize_llm'):
            integration = LLMIntegration(
                provider=LLMProvider.HUGGINGFACE.value,
                endpoint="https://api-inference.huggingface.co/models/microsoft/phi-4-multimodal"
            )

        # Mock the import
        with patch('src.llm_integration.import_optional', return_value=mock_hf):
            # Call the method
            integration._initialize_llm()

        # Check the result
        mock_hf.assert_called_once_with(endpoint_url="https://api-inference.huggingface.co/models/microsoft/phi-4-multimodal")
        self.assertEqual(integration.llm, mock_hf_instance)

    def test_invoke(self):
        """Test invoking the LLM."""
        # Create the integration
        with patch('src.llm_integration.LLMIntegration._initialize_llm'):
            integration = LLMIntegration()

        # Set up the mock
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = "Test response"
        integration.llm = mock_llm

        # Call the method
        result = integration.invoke("Test prompt")

        # Check the result
        self.assertEqual(result, "Test response")
        mock_llm.invoke.assert_called_once_with("Test prompt")

    def test_analyze_document(self):
        """Test analyzing a document."""
        # Create the integration
        with patch('src.llm_integration.LLMIntegration._initialize_llm'):
            integration = LLMIntegration()

        # Set up the mock
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = '{"analysis": "Test analysis"}'
        integration.llm = mock_llm

        # Call the method
        result = integration.analyze_document([{"type": "Text", "text": "Test document"}])

        # Check the result
        self.assertEqual(result, {"analysis": "Test analysis"})
        mock_llm.invoke.assert_called_once()

    def test_extract_table(self):
        """Test extracting a table."""
        # Create the integration
        with patch('src.llm_integration.LLMIntegration._initialize_llm'):
            integration = LLMIntegration()

        # Set up the mock
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = '{"headers": ["A", "B"], "rows": [[1, 2], [3, 4]]}'
        integration.llm = mock_llm

        # Call the method
        result = integration.extract_table("A | B\n1 | 2\n3 | 4")

        # Check the result
        self.assertEqual(result, {"headers": ["A", "B"], "rows": [[1, 2], [3, 4]]})
        mock_llm.invoke.assert_called_once()

    def test_generate_schema(self):
        """Test generating a schema."""
        # Create the integration
        with patch('src.llm_integration.LLMIntegration._initialize_llm'):
            integration = LLMIntegration()

        # Set up the mock
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = '{"type": "object", "properties": {"name": {"type": "string"}}}'
        integration.llm = mock_llm

        # Call the method
        result = integration.generate_schema("Generate a schema for a person", [{"type": "Text", "text": "Name: John"}])

        # Check the result
        self.assertEqual(result, {"type": "object", "properties": {"name": {"type": "string"}}})
        mock_llm.invoke.assert_called_once()

    @patch('builtins.open', unittest.mock.mock_open(read_data=b'test image data'))
    @patch('base64.b64encode')
    def test_analyze_image(self, mock_b64encode):
        """Test analyzing an image."""
        # Set up the mock
        mock_b64encode.return_value = b'dGVzdCBpbWFnZSBkYXRh'

        # Create the integration
        with patch('src.llm_integration.LLMIntegration._initialize_llm'):
            integration = LLMIntegration(model="phi-4-multimodal")

        # Set up the mock
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = "Image analysis result"
        integration.llm = mock_llm

        # Call the method
        result = integration.analyze_image("test.jpg")

        # Check the result
        self.assertEqual(result, "Image analysis result")
        mock_llm.invoke.assert_called_once()
        mock_b64encode.assert_called_once_with(b'test image data')


class TestGetLLMIntegration(unittest.TestCase):
    """Tests for the get_llm_integration function."""

    @patch('src.llm_integration.LLM_ENABLED', True)
    @patch('src.llm_integration.LLMIntegration')
    def test_get_llm_integration(self, mock_integration):
        """Test getting the LLM integration."""
        # Set up the mock
        mock_integration_instance = MagicMock()
        mock_integration.return_value = mock_integration_instance

        # Reset the singleton
        import src.llm_integration
        src.llm_integration.llm_integration = None

        # Call the function
        result = get_llm_integration()

        # Check the result
        self.assertEqual(result, mock_integration_instance)
        mock_integration.assert_called_once()

    @patch('src.llm_integration.LLM_ENABLED', False)
    def test_get_llm_integration_disabled(self):
        """Test getting the LLM integration when disabled."""
        # Reset the singleton
        import src.llm_integration
        src.llm_integration.llm_integration = None

        # Call the function
        result = get_llm_integration()

        # Check the result
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
