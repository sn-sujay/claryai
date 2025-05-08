"""
Phi model integration module for ClaryAI.

This module provides direct integration with Phi models from Microsoft via Hugging Face.
Originally designed for Phi-4-multimodal, but can work with other Phi models like Phi-2.
"""

import os
import logging
import json
import base64
from typing import Optional, Dict, Any, List, Union
from io import BytesIO
from pathlib import Path
import tempfile

# Set up logging
logger = logging.getLogger("claryai.phi4_integration")

# Try to import required libraries
try:
    import torch
    from PIL import Image
    from transformers import AutoModelForCausalLM, AutoTokenizer, AutoProcessor
    from transformers.generation import GenerationConfig
    IMPORTS_SUCCESSFUL = True
except ImportError as e:
    logger.warning(f"Failed to import required libraries for Phi-4-multimodal: {str(e)}")
    IMPORTS_SUCCESSFUL = False

# Model configuration
DEFAULT_MODEL = "microsoft/phi-2"  # Using Phi-2 as a fallback since Phi-4-multimodal requires authentication
DEVICE = "cuda" if torch.cuda.is_available() else "cpu" if IMPORTS_SUCCESSFUL else None
MAX_LENGTH = 4096
MAX_NEW_TOKENS = 1024

# Prompt templates
PROMPT_TEMPLATES = {
    "document_analysis": """
You are an AI assistant that analyzes documents. Please analyze the following document content:

{document_content}

Provide a detailed analysis including:
1. Key information extracted from the document
2. Document type identification
3. Important entities mentioned
4. Any tables or structured data found
5. Summary of the main points

Your analysis:
""",
    "table_extraction": """
You are an AI assistant that extracts and analyzes tables from documents. Please analyze the following table:

{table_content}

Provide a detailed analysis including:
1. What kind of data this table contains
2. Key insights from the table
3. Any patterns or trends you notice
4. Summary of the most important information

Your analysis:
""",
    "document_qa": """
You are an AI assistant that answers questions about documents. Use the following document content to answer the question.

Document content:
{document_content}

Question: {question}

Your answer:
""",
    "image_analysis": """
You are an AI assistant that analyzes images. Please analyze the following image and provide a detailed description.

[IMAGE]

Your analysis:
"""
}

class PhiModelIntegration:
    """
    Phi model integration class for ClaryAI.

    This class provides methods to:
    1. Load and initialize Phi models from Microsoft
    2. Generate text based on prompts
    3. Process multimodal inputs (text + images) if supported
    4. Analyze documents using the model
    """

    def __init__(self, model_name: str = DEFAULT_MODEL):
        """
        Initialize the Phi Model Integration.

        Args:
            model_name: Name of the model to use (default: microsoft/phi-2)
        """
        if not IMPORTS_SUCCESSFUL:
            raise ImportError("Required libraries for Phi models are not installed")

        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self.processor = None
        self.is_multimodal = "multimodal" in model_name.lower()

        # Initialize the model
        self._initialize_model()

    def _initialize_model(self):
        """Initialize the Phi model."""
        try:
            logger.info(f"Initializing Phi model: {self.model_name}")

            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)

            # Load model with appropriate configuration
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
                device_map="auto" if DEVICE == "cuda" else None,
                trust_remote_code=True
            )

            # Set generation config
            self.model.generation_config = GenerationConfig.from_pretrained(
                self.model_name,
                trust_remote_code=True
            )

            # Load processor for multimodal models
            if self.is_multimodal:
                try:
                    self.processor = AutoProcessor.from_pretrained(self.model_name)
                    logger.info("Multimodal processor initialized")
                except Exception as e:
                    logger.warning(f"Failed to load multimodal processor: {str(e)}")
                    self.is_multimodal = False

            logger.info(f"Phi model initialized successfully on {DEVICE}")
        except Exception as e:
            logger.error(f"Error initializing Phi model: {str(e)}")
            raise

    def generate_text(self, prompt: str, max_new_tokens: int = MAX_NEW_TOKENS) -> str:
        """
        Generate text based on a prompt.

        Args:
            prompt: Input prompt
            max_new_tokens: Maximum number of tokens to generate

        Returns:
            Generated text
        """
        try:
            logger.info("Generating text with Phi-4-multimodal")

            # Tokenize input
            inputs = self.tokenizer(prompt, return_tensors="pt")

            # Move inputs to the appropriate device
            if DEVICE == "cuda":
                inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

            # Generate text
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9
                )

            # Decode the generated text
            generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

            # Extract only the generated part (remove the prompt)
            generated_text = generated_text[len(prompt):]

            logger.info("Text generation completed")
            return generated_text.strip()
        except Exception as e:
            logger.error(f"Error generating text: {str(e)}")
            return f"Error generating text: {str(e)}"

    def process_image_and_text(self, image_data: bytes, prompt: str, max_new_tokens: int = MAX_NEW_TOKENS) -> str:
        """
        Process an image and text prompt.

        Args:
            image_data: Image data as bytes
            prompt: Text prompt
            max_new_tokens: Maximum number of tokens to generate

        Returns:
            Generated text
        """
        if not self.is_multimodal or self.processor is None:
            logger.error("Model is not multimodal or processor is not initialized")
            return "Error: Model is not multimodal or processor is not initialized. This model cannot process images."

        try:
            logger.info("Processing image and text with multimodal Phi model")

            # Load image
            image = Image.open(BytesIO(image_data)).convert("RGB")

            # Process inputs
            inputs = self.processor(
                text=prompt,
                images=image,
                return_tensors="pt"
            )

            # Move inputs to the appropriate device
            if DEVICE == "cuda":
                inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

            # Generate text
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9
                )

            # Decode the generated text
            generated_text = self.processor.decode(outputs[0], skip_special_tokens=True)

            # Extract only the generated part (remove the prompt)
            if prompt in generated_text:
                generated_text = generated_text[len(prompt):]

            logger.info("Multimodal processing completed")
            return generated_text.strip()
        except Exception as e:
            logger.error(f"Error processing image and text: {str(e)}")
            return f"Error processing image and text: {str(e)}"

    def analyze_document(self, document_content: str, template: str = "document_analysis") -> str:
        """
        Analyze a document using the model.

        Args:
            document_content: Document content to analyze
            template: Prompt template to use

        Returns:
            Analysis result
        """
        try:
            logger.info(f"Analyzing document using template: {template}")

            # Get the prompt template
            prompt_template = PROMPT_TEMPLATES.get(template, PROMPT_TEMPLATES["document_analysis"])

            # Format the prompt
            prompt = prompt_template.format(document_content=document_content)

            # Generate text
            analysis = self.generate_text(prompt)

            logger.info("Document analysis completed")
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing document: {str(e)}")
            return f"Error analyzing document: {str(e)}"

    def analyze_image(self, image_data: bytes) -> str:
        """
        Analyze an image.

        Args:
            image_data: Image data as bytes

        Returns:
            Analysis result
        """
        if not self.is_multimodal:
            logger.error("Model is not multimodal, cannot analyze images")
            return "Error: Model is not multimodal, cannot analyze images. Please use a multimodal model like Phi-4-multimodal."

        try:
            logger.info("Analyzing image with Phi model")

            # Get the prompt template
            prompt_template = PROMPT_TEMPLATES["image_analysis"]

            # Process image and text
            analysis = self.process_image_and_text(image_data, prompt_template)

            logger.info("Image analysis completed")
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing image: {str(e)}")
            return f"Error analyzing image: {str(e)}"

    def analyze_image_from_path(self, image_path: str) -> str:
        """
        Analyze an image from a file path.

        Args:
            image_path: Path to the image file

        Returns:
            Analysis result
        """
        try:
            logger.info(f"Analyzing image from path: {image_path}")

            # Read the image file
            with open(image_path, "rb") as f:
                image_data = f.read()

            # Analyze the image
            return self.analyze_image(image_data)
        except Exception as e:
            logger.error(f"Error analyzing image from path: {str(e)}")
            return f"Error analyzing image from path: {str(e)}"

# Singleton instance
_phi4_instance = None

def get_phi_model_integration(model_name: str = DEFAULT_MODEL) -> PhiModelIntegration:
    """
    Get the Phi model integration instance.

    Args:
        model_name: Name of the model to use

    Returns:
        Phi model integration instance
    """
    global _phi4_instance

    if _phi4_instance is None:
        try:
            _phi4_instance = PhiModelIntegration(model_name)
        except Exception as e:
            logger.error(f"Failed to initialize Phi model integration: {str(e)}")
            return None

    return _phi4_instance

# Alias for backward compatibility
get_phi4_integration = get_phi_model_integration
