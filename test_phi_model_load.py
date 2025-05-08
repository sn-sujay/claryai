#!/usr/bin/env python3
"""
Simple test script to load the Phi model.

This script tests loading the Phi model from Hugging Face.
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_phi_model_load")

# Add src directory to path
sys.path.append('src')

def main():
    """Main function."""
    try:
        # Import required libraries
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        
        # Model name
        model_name = "microsoft/phi-2"
        
        logger.info(f"Loading tokenizer for {model_name}...")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        logger.info(f"Loading model {model_name}...")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float32,
            trust_remote_code=True
        )
        
        logger.info("Model loaded successfully")
        
        # Test simple generation
        prompt = "Explain the concept of document parsing in simple terms."
        logger.info(f"Testing generation with prompt: {prompt}")
        
        inputs = tokenizer(prompt, return_tensors="pt")
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=100,
                do_sample=True,
                temperature=0.7,
                top_p=0.9
            )
        
        generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        logger.info(f"Generated text: {generated_text}")
        
        return 0
    
    except ImportError as e:
        logger.error(f"Failed to import required libraries: {str(e)}")
        return 1
    
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
