"""
LLM integration module for ClaryAI.

This module provides integration with various LLMs, including Phi-4-multimodal.
"""

import os
import logging
import json
import base64
from typing import Optional, Dict, Any, List, Union
from enum import Enum
import tempfile
from pathlib import Path

# Set up logging
logger = logging.getLogger(__name__)

# Optional imports - these will be imported only when needed
OPTIONAL_IMPORTS = {
    "langchain_community.llms.Ollama": None,
    "langchain_openai.ChatOpenAI": None,
    "langchain_community.llms.HuggingFaceEndpoint": None
}

def import_optional(module_path):
    """Import an optional module."""
    if module_path not in OPTIONAL_IMPORTS:
        logger.warning(f"Unknown optional module: {module_path}")
        return None

    if OPTIONAL_IMPORTS[module_path] is None:
        try:
            parts = module_path.split(".")
            module_name = ".".join(parts[:-1])
            class_name = parts[-1]
            module = __import__(module_name, fromlist=[class_name])
            OPTIONAL_IMPORTS[module_path] = getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            logger.warning(f"Optional module {module_path} not available: {str(e)}")
            return None
    return OPTIONAL_IMPORTS[module_path]

# LLM configuration
LLM_ENABLED = os.getenv("USE_LLM", "false").lower() == "true"
LLM_MODEL = os.getenv("LLM_MODEL", "phi-4-multimodal")
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# Prompt templates
PROMPT_TEMPLATES = {
    "document_analysis": """
    Analyze the following document elements and provide a structured summary:

    {document_elements}

    Provide a summary that includes:
    1. Document type
    2. Key information
    3. Main topics or themes
    4. Any important dates, numbers, or entities
    """,

    "table_extraction": """
    Extract and structure the following table:

    {table_text}

    Return the result as a JSON object with headers and rows.
    """,

    "three_way_matching": """
    Perform three-way matching on the following documents:

    INVOICE:
    {invoice_data}

    PURCHASE ORDER:
    {po_data}

    GOODS RECEIPT NOTE:
    {grn_data}

    Identify matches and discrepancies in:
    1. Document numbers
    2. Dates
    3. Amounts
    4. Line items
    5. Quantities

    Return the result as a JSON object.
    """,

    "schema_generation": """
    Generate a JSON schema based on this description:

    {schema_description}

    Use these document elements as reference:

    {document_elements}

    Return a valid JSON schema.
    """,

    "image_analysis": """
    Analyze the following image and provide a detailed description:

    [IMAGE]

    Describe:
    1. What is shown in the image
    2. Any text visible in the image
    3. Key objects or people
    4. Any relevant details for document processing
    """
}


class LLMProvider(Enum):
    """Enum for LLM providers."""
    OLLAMA = "ollama"
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"
    CUSTOM = "custom"


class LLMIntegration:
    """LLM integration class."""

    def __init__(self, provider: str = None, model: str = None, endpoint: str = None, api_key: str = None):
        """
        Initialize the LLM integration.

        Args:
            provider: LLM provider (ollama, openai, huggingface, custom)
            model: LLM model name
            endpoint: LLM endpoint URL
            api_key: LLM API key
        """
        self.provider = provider or (
            LLMProvider.OPENAI.value if "openai" in LLM_ENDPOINT else
            LLMProvider.HUGGINGFACE.value if LLM_ENDPOINT else
            LLMProvider.OLLAMA.value
        )
        self.model = model or LLM_MODEL
        self.endpoint = endpoint or LLM_ENDPOINT
        self.api_key = api_key or LLM_API_KEY
        self.llm = None

        # Initialize LLM
        self._initialize_llm()

    def _initialize_llm(self):
        """Initialize the LLM based on provider."""
        try:
            if self.provider == LLMProvider.OLLAMA.value:
                # Import required modules
                import subprocess
                import time
                import requests

                # Check if Ollama is running
                try:
                    response = requests.get("http://localhost:11434/api/version")
                    if response.status_code != 200:
                        # Start Ollama if not running
                        logger.info("Starting Ollama server...")
                        subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        # Wait for Ollama to start
                        for _ in range(10):
                            try:
                                response = requests.get("http://localhost:11434/api/version")
                                if response.status_code == 200:
                                    logger.info("Ollama server started successfully")
                                    break
                            except:
                                pass
                            time.sleep(1)
                except:
                    # Start Ollama if not running
                    logger.info("Starting Ollama server...")
                    subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    # Wait for Ollama to start
                    time.sleep(5)

                # Check if the model is available
                try:
                    response = requests.get(f"http://localhost:11434/api/show?name={self.model}")
                    if response.status_code != 200:
                        # Pull the model if not available
                        logger.info(f"Pulling {self.model} model...")
                        subprocess.run(["ollama", "pull", self.model], check=True)
                except:
                    # Pull the model if not available
                    logger.info(f"Pulling {self.model} model...")
                    subprocess.run(["ollama", "pull", self.model], check=True)

                # Initialize the LLM
                Ollama = import_optional("langchain_community.llms.Ollama")
                if not Ollama:
                    raise ImportError("Failed to import Ollama")

                # Initialize with specific parameters for better performance
                self.llm = Ollama(
                    model=self.model,
                    num_ctx=8192,  # Large context window
                    num_predict=2048,  # Reasonable output length
                    temperature=0.7,  # Balanced creativity
                    top_k=40,  # Diverse token selection
                    top_p=0.9,  # Nucleus sampling
                    repeat_penalty=1.1  # Avoid repetition
                )
                logger.info(f"Initialized Ollama LLM with model: {self.model}")

            elif self.provider == LLMProvider.OPENAI.value:
                ChatOpenAI = import_optional("langchain_openai.ChatOpenAI")
                if not ChatOpenAI:
                    raise ImportError("Failed to import ChatOpenAI")
                self.llm = ChatOpenAI(
                    api_key=self.api_key,
                    base_url=self.endpoint,
                    temperature=0.7,
                    max_tokens=2048
                )
                logger.info(f"Initialized OpenAI LLM with endpoint: {self.endpoint}")

            elif self.provider == LLMProvider.HUGGINGFACE.value:
                HuggingFaceEndpoint = import_optional("langchain_community.llms.HuggingFaceEndpoint")
                if not HuggingFaceEndpoint:
                    raise ImportError("Failed to import HuggingFaceEndpoint")
                self.llm = HuggingFaceEndpoint(
                    endpoint_url=self.endpoint,
                    huggingfacehub_api_token=self.api_key,
                    task="text-generation",
                    max_new_tokens=2048,
                    temperature=0.7
                )
                logger.info(f"Initialized HuggingFace LLM with endpoint: {self.endpoint}")

            elif self.provider == LLMProvider.CUSTOM.value:
                # Custom implementation for direct API calls
                self.llm = self._create_custom_llm()
                logger.info(f"Initialized custom LLM with endpoint: {self.endpoint}")

            else:
                logger.error(f"Unsupported LLM provider: {self.provider}")
                raise ValueError(f"Unsupported LLM provider: {self.provider}")

        except ImportError as e:
            logger.error(f"Failed to import LLM dependencies: {str(e)}")
            raise ImportError(f"Failed to import LLM dependencies: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to initialize LLM: {str(e)}")
            raise RuntimeError(f"Failed to initialize LLM: {str(e)}")

    def _create_custom_llm(self):
        """Create a custom LLM implementation."""
        # This is a placeholder for a custom LLM implementation
        # that doesn't use LangChain
        from langchain_core.language_models.llms import LLM

        class CustomLLM(LLM):
            """Custom LLM implementation."""

            def _call(self, prompt, **kwargs):
                """Call the LLM with the prompt."""
                # Implement custom API call here
                import requests

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }

                data = {
                    "model": self.model,
                    "prompt": prompt,
                    "max_tokens": kwargs.get("max_tokens", 1024),
                    "temperature": kwargs.get("temperature", 0.7)
                }

                response = requests.post(self.endpoint, headers=headers, json=data)

                if response.status_code != 200:
                    raise RuntimeError(f"LLM API call failed: {response.text}")

                return response.json()["choices"][0]["text"]

            @property
            def _llm_type(self):
                """Return the LLM type."""
                return "custom"

        return CustomLLM()

    def invoke(self, prompt: str, **kwargs) -> str:
        """
        Invoke the LLM with a prompt.

        Args:
            prompt: The prompt to send to the LLM
            **kwargs: Additional arguments to pass to the LLM

        Returns:
            The LLM response
        """
        try:
            if not self.llm:
                raise RuntimeError("LLM not initialized")

            response = self.llm.invoke(prompt, **kwargs)
            return str(response)

        except Exception as e:
            logger.error(f"LLM invocation failed: {str(e)}")
            raise RuntimeError(f"LLM invocation failed: {str(e)}")

    def analyze_document(self, document_elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze a document using the LLM.

        Args:
            document_elements: List of document elements

        Returns:
            Analysis results
        """
        prompt = PROMPT_TEMPLATES["document_analysis"].format(
            document_elements=json.dumps(document_elements, indent=2)
        )

        response = self.invoke(prompt)

        try:
            # Try to parse as JSON
            return json.loads(response)
        except json.JSONDecodeError:
            # Return as text if not valid JSON
            return {"analysis": response}

    def extract_table(self, table_text: str) -> Dict[str, Any]:
        """
        Extract a table using the LLM.

        Args:
            table_text: Table text

        Returns:
            Extracted table
        """
        prompt = PROMPT_TEMPLATES["table_extraction"].format(
            table_text=table_text
        )

        response = self.invoke(prompt)

        try:
            # Try to parse as JSON
            return json.loads(response)
        except json.JSONDecodeError:
            # Return as text if not valid JSON
            return {"table": response}

    def generate_schema(self, schema_description: str, document_elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a JSON schema using the LLM.

        Args:
            schema_description: Schema description
            document_elements: List of document elements

        Returns:
            Generated schema
        """
        prompt = PROMPT_TEMPLATES["schema_generation"].format(
            schema_description=schema_description,
            document_elements=json.dumps(document_elements, indent=2)
        )

        response = self.invoke(prompt)

        try:
            # Try to parse as JSON
            return json.loads(response)
        except json.JSONDecodeError:
            # Return as text if not valid JSON
            return {"schema": response}

    def analyze_image(self, image_path: str) -> str:
        """
        Analyze an image using the LLM.

        Args:
            image_path: Path to the image

        Returns:
            Image analysis
        """
        # Only supported for Phi-4-multimodal
        if self.model != "phi-4-multimodal":
            raise ValueError(f"Image analysis not supported for model: {self.model}")

        # Import required modules
        import os
        from PIL import Image
        import tempfile

        # Check if the image exists
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Process the image
        try:
            # Open the image with PIL
            img = Image.open(image_path)

            # Resize if too large (Phi-4-multimodal has limits)
            max_size = 1024
            if img.width > max_size or img.height > max_size:
                # Maintain aspect ratio
                if img.width > img.height:
                    new_width = max_size
                    new_height = int(img.height * (max_size / img.width))
                else:
                    new_height = max_size
                    new_width = int(img.width * (max_size / img.height))

                # Resize the image
                img = img.resize((new_width, new_height), Image.LANCZOS)

                # Save to a temporary file
                temp_path = tempfile.mktemp(suffix=".jpg")
                img.save(temp_path, format="JPEG", quality=85)
                image_path = temp_path

            # Read the image and convert to base64
            with open(image_path, "rb") as f:
                image_data = f.read()
                image_base64 = base64.b64encode(image_data).decode("utf-8")

            # Determine image format
            img_format = image_path.split(".")[-1].lower()
            if img_format not in ["jpg", "jpeg", "png", "gif", "webp"]:
                img_format = "jpeg"  # Default to JPEG

            # Create a prompt with the image
            prompt = PROMPT_TEMPLATES["image_analysis"].replace(
                "[IMAGE]",
                f"data:image/{img_format};base64,{image_base64}"
            )

            # Invoke the LLM
            response = self.invoke(prompt)

            # Clean up temporary file if created
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)

            return response

        except Exception as e:
            logger.error(f"Image analysis failed: {str(e)}")
            raise RuntimeError(f"Image analysis failed: {str(e)}")


# Create a singleton instance
llm_integration = None

def get_llm_integration() -> LLMIntegration:
    """
    Get the LLM integration instance.

    Returns:
        LLM integration instance
    """
    global llm_integration

    if llm_integration is None and LLM_ENABLED:
        llm_integration = LLMIntegration()

    return llm_integration
