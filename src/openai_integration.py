"""
OpenAI integration module for ClaryAI.

This module provides integration with OpenAI models.
"""

import os
import logging
import json
import base64
from typing import Optional, Dict, Any, List, Union
from io import BytesIO
from pathlib import Path
import tempfile
import requests

# Set up logging
logger = logging.getLogger("claryai.openai_integration")

# OpenAI configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = "gpt-4o"
MAX_TOKENS = 1024

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

class OpenAIIntegration:
    """
    OpenAI integration class for ClaryAI.
    
    This class provides methods to:
    1. Generate text based on prompts
    2. Process multimodal inputs (text + images)
    3. Analyze documents using OpenAI models
    """
    
    def __init__(self, model_name: str = DEFAULT_MODEL, api_key: str = None):
        """
        Initialize the OpenAI Integration.
        
        Args:
            model_name: Name of the model to use (default: gpt-4o)
            api_key: OpenAI API key (default: from environment variable)
        """
        self.model_name = model_name
        self.api_key = api_key or OPENAI_API_KEY
        
        if not self.api_key:
            logger.warning("OpenAI API key not provided")
        
        self.is_multimodal = "gpt-4" in model_name.lower() and ("vision" in model_name.lower() or "o" in model_name.lower())
    
    def generate_text(self, prompt: str, max_tokens: int = MAX_TOKENS) -> str:
        """
        Generate text based on a prompt.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            Generated text
        """
        try:
            logger.info("Generating text with OpenAI")
            
            if not self.api_key:
                return "Error: OpenAI API key not provided"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.7
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                logger.error(f"OpenAI API error: {response.text}")
                return f"Error: OpenAI API returned status code {response.status_code}"
            
            result = response.json()
            generated_text = result["choices"][0]["message"]["content"]
            
            logger.info("Text generation completed")
            return generated_text.strip()
        except Exception as e:
            logger.error(f"Error generating text: {str(e)}")
            return f"Error generating text: {str(e)}"
    
    def process_image_and_text(self, image_data: bytes, prompt: str, max_tokens: int = MAX_TOKENS) -> str:
        """
        Process an image and text prompt.
        
        Args:
            image_data: Image data as bytes
            prompt: Text prompt
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            Generated text
        """
        if not self.is_multimodal:
            logger.error("Model is not multimodal, cannot process images")
            return "Error: Model is not multimodal, cannot process images"
        
        try:
            logger.info("Processing image and text with OpenAI")
            
            if not self.api_key:
                return "Error: OpenAI API key not provided"
            
            # Convert image to base64
            image_base64 = base64.b64encode(image_data).decode("utf-8")
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": max_tokens,
                "temperature": 0.7
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                logger.error(f"OpenAI API error: {response.text}")
                return f"Error: OpenAI API returned status code {response.status_code}"
            
            result = response.json()
            generated_text = result["choices"][0]["message"]["content"]
            
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
            return "Error: Model is not multimodal, cannot analyze images"
        
        try:
            logger.info("Analyzing image with OpenAI")
            
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
_openai_instance = None

def get_openai_integration(model_name: str = DEFAULT_MODEL, api_key: str = None) -> OpenAIIntegration:
    """
    Get the OpenAI integration instance.
    
    Args:
        model_name: Name of the model to use
        api_key: OpenAI API key
        
    Returns:
        OpenAI integration instance
    """
    global _openai_instance
    
    if _openai_instance is None:
        try:
            _openai_instance = OpenAIIntegration(model_name, api_key)
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI integration: {str(e)}")
            return None
    
    return _openai_instance
