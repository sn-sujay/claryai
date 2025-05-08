#!/usr/bin/env python3
"""
Test script for the improved table parser.

This script tests the improved table parser with various table formats.
"""

import os
import sys
import json
from pathlib import Path

# Add src directory to path
sys.path.append('src')

try:
    from table_parser_improved import TableTransformer
except ImportError:
    try:
        from src.table_parser_improved import TableTransformer
    except ImportError:
        print("Error: Could not import TableTransformer from table_parser_improved")
        sys.exit(1)

# Test files
TEST_FILES_DIR = Path("test_files")
if not TEST_FILES_DIR.exists():
    print(f"Test files directory not found: {TEST_FILES_DIR}")
    sys.exit(1)

def test_table_parser():
    """Test the improved table parser with various table formats."""
    print("Testing improved table parser...")

    # Create TableTransformer instance
    table_transformer = TableTransformer()

    # Test with sample PO file
    sample_po_path = TEST_FILES_DIR / "sample_po.txt"
    if sample_po_path.exists():
        print(f"\nTesting with sample PO file: {sample_po_path}")
        with open(sample_po_path, "r") as f:
            content = f.read()

        # Find the table in the content
        table_text = ""
        capture = False
        for line in content.split('\n'):
            if "Item" in line and "Quantity" in line and "Unit Price" in line:
                table_text = line + "\n"
                capture = True
                continue

            if capture and line.strip():
                table_text += line + "\n"

            if capture and "Total:" in line:
                table_text += line + "\n"
                break

        if table_text:
            print("Found table text:")
            print(table_text)

            # Parse the table
            result = table_transformer.parse_text_table(table_text)
            print("\nParsed table result:")
            print(json.dumps(result, indent=2))
        else:
            print("No table found in sample PO file")

    # Test with sample invoice file
    sample_invoice_path = TEST_FILES_DIR / "sample_invoice.txt"
    if sample_invoice_path.exists():
        print(f"\nTesting with sample invoice file: {sample_invoice_path}")
        with open(sample_invoice_path, "r") as f:
            content = f.read()

        # Find the table in the content
        table_text = ""
        capture = False
        for line in content.split('\n'):
            if ("Description" in line or "Item" in line) and "Quantity" in line and ("Price" in line or "Amount" in line):
                table_text = line + "\n"
                capture = True
                continue

            if capture and line.strip():
                table_text += line + "\n"

            if capture and "Total:" in line:
                table_text += line + "\n"
                break

        # If no table found, use the entire content
        if not table_text:
            table_text = content

        if table_text:
            print("Found table text:")
            print(table_text)

            # Parse the table
            result = table_transformer.parse_text_table(table_text)
            print("\nParsed table result:")
            print(json.dumps(result, indent=2))
        else:
            print("No table found in sample invoice file")

    # Test with manually created table
    print("\nTesting with manually created table")
    manual_table = """
    Item                  Quantity    Unit Price    Total
    --------------------------------------------------------
    Widget A              10          $25.00        $250.00
    Widget B              5           $30.00        $150.00
    Service Package       1           $500.00       $500.00
    --------------------------------------------------------
    Subtotal:     $900.00
    Tax (10%):    $90.00
    Total:        $990.00
    """

    result = table_transformer.parse_text_table(manual_table)
    print("\nParsed table result:")
    print(json.dumps(result, indent=2))

    # Test with space-separated table
    print("\nTesting with space-separated table")
    space_table = """
    Item        Quantity    Price       Total
    Widget A    10          $25.00      $250.00
    Widget B    5           $30.00      $150.00
    Service     1           $500.00     $500.00
    """

    result = table_transformer.parse_text_table(space_table)
    print("\nParsed table result:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    test_table_parser()
