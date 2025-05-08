#!/usr/bin/env python3
"""
Test script for Phi model integration.

This script tests the Phi model integration with various inputs.
Originally designed for Phi-4-multimodal, but can work with other Phi models like Phi-2.
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_phi4_integration")

# Add src directory to path
sys.path.append('src')

def test_text_generation(phi_model):
    """Test text generation with Phi model."""
    logger.info("Testing text generation...")

    prompt = "Explain the concept of document parsing in simple terms."

    logger.info(f"Prompt: {prompt}")

    response = phi_model.generate_text(prompt)

    logger.info(f"Response: {response}")

    return response

def test_document_analysis(phi_model):
    """Test document analysis with Phi model."""
    logger.info("Testing document analysis...")

    document_content = """
    INVOICE

    Invoice Number: INV-2023-001
    Date: May 1, 2023

    Bill To:
    Acme Corporation
    123 Main Street
    Anytown, CA 12345

    Item        Quantity    Unit Price    Total
    Widget A    10          $25.00        $250.00
    Widget B    5           $30.00        $150.00
    Service     1           $500.00       $500.00

    Subtotal: $900.00
    Tax (10%): $90.00
    Total: $990.00

    Payment Terms: Net 30
    Due Date: June 1, 2023
    """

    logger.info("Analyzing document...")

    analysis = phi_model.analyze_document(document_content)

    logger.info(f"Analysis: {analysis}")

    return analysis

def test_image_analysis(phi_model, image_path):
    """Test image analysis with Phi model."""
    logger.info("Testing image analysis...")

    if not os.path.exists(image_path):
        logger.error(f"Image not found: {image_path}")
        return "Image not found"

    logger.info(f"Analyzing image: {image_path}")

    analysis = phi_model.analyze_image_from_path(image_path)

    logger.info(f"Analysis: {analysis}")

    return analysis

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test Phi model integration")
    parser.add_argument("--image", type=str, help="Path to an image file for testing image analysis")
    parser.add_argument("--test", type=str, choices=["text", "document", "image", "all"], default="all", help="Test to run")
    args = parser.parse_args()

    try:
        # Import Phi model integration
        from phi4_integration import get_phi_model_integration

        # Get Phi model integration instance
        phi_model = get_phi_model_integration()

        if phi_model is None:
            logger.error("Failed to initialize Phi model integration")
            return 1

        # Run tests
        if args.test == "text" or args.test == "all":
            test_text_generation(phi_model)

        if args.test == "document" or args.test == "all":
            test_document_analysis(phi_model)

        if (args.test == "image" or args.test == "all") and args.image:
            test_image_analysis(phi_model, args.image)
        elif args.test == "image" and not args.image:
            logger.error("Image path not provided for image analysis test")
            return 1

        logger.info("All tests completed successfully")
        return 0

    except ImportError as e:
        logger.error(f"Failed to import Phi-4-multimodal integration: {str(e)}")
        return 1

    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
