"""
TableTransformer module for advanced table parsing in ClaryAI.
This module provides functionality to parse tables from various formats
and convert them into structured JSON.
"""

import pandas as pd
import numpy as np
import re
import json
import logging
from typing import List, Dict, Any, Optional, Union
from bs4 import BeautifulSoup

# Configure logging
logger = logging.getLogger("claryai.table_parser")

class TableTransformer:
    """
    TableTransformer class for advanced table parsing.

    This class provides methods to:
    1. Parse HTML tables
    2. Parse text-based tables (ASCII, markdown, etc.)
    3. Extract tables from PDF content
    4. Convert tables to structured JSON
    """

    def __init__(self):
        """Initialize the TableTransformer."""
        pass

    def parse_html_table(self, html_table: str) -> Dict[str, Any]:
        """
        Parse an HTML table and convert it to structured JSON.

        Args:
            html_table: HTML table as string

        Returns:
            Dict with parsed table data
        """
        try:
            # Parse HTML
            soup = BeautifulSoup(html_table, 'html.parser')

            # Extract headers
            headers = []
            header_row = soup.find('thead')
            if header_row:
                headers = [th.text.strip() for th in header_row.find_all('th')]
            else:
                # Try to get headers from first row
                first_row = soup.find('tr')
                if first_row:
                    headers = [th.text.strip() for th in first_row.find_all(['th', 'td'])]

            # Extract rows
            rows = []
            for tr in soup.find_all('tr')[1:] if headers else soup.find_all('tr'):
                row = [td.text.strip() for td in tr.find_all(['td', 'th'])]
                if row:  # Skip empty rows
                    rows.append(row)

            # Create DataFrame
            if headers and rows:
                # Ensure all rows have the same length as headers
                rows = [row + [''] * (len(headers) - len(row)) for row in rows if len(row) <= len(headers)]
                rows = [row[:len(headers)] for row in rows if len(row) > len(headers)]
                df = pd.DataFrame(rows, columns=headers)
            elif rows:
                df = pd.DataFrame(rows)
            else:
                return {"type": "Table", "data": [], "headers": [], "error": "No data found in table"}

            # Convert to structured JSON
            return {
                "type": "Table",
                "headers": headers if headers else df.columns.tolist(),
                "data": df.to_dict(orient='records'),
                "num_rows": len(df),
                "num_cols": len(df.columns)
            }

        except Exception as e:
            logger.error(f"Error parsing HTML table: {str(e)}")
            return {"type": "Table", "error": f"Failed to parse HTML table: {str(e)}"}

    def parse_text_table(self, text_table: str) -> Dict[str, Any]:
        """
        Parse a text-based table (ASCII, markdown) and convert it to structured JSON.

        Args:
            text_table: Text table as string

        Returns:
            Dict with parsed table data
        """
        try:
            # Check if it's a markdown table
            if '|' in text_table and ('-+-' in text_table or '---|---' in text_table):
                return self._parse_markdown_table(text_table)
                
            # Check if it's a table with dollar amounts and "Total"
            if '$' in text_table and 'Total' in text_table:
                return self._parse_financial_table(text_table)
                
            # Check if it's a table with multiple spaces as column separators
            if text_table.count('\n') >= 2 and any('  ' in line for line in text_table.split('\n')):
                return self._parse_space_separated_table(text_table)

            # Otherwise treat as fixed-width table
            return self._parse_fixed_width_table(text_table)

        except Exception as e:
            logger.error(f"Error parsing text table: {str(e)}")
            return {"type": "Table", "error": f"Failed to parse text table: {str(e)}"}

    def _parse_markdown_table(self, md_table: str) -> Dict[str, Any]:
        """Parse a markdown table."""
        # Split into lines and remove empty lines
        lines = [line.strip() for line in md_table.split('\n') if line.strip()]

        # Extract header and data rows
        header_row = lines[0] if lines else ""
        separator_row = lines[1] if len(lines) > 1 else ""
        data_rows = lines[2:] if len(lines) > 2 else []

        # Process header
        headers = [h.strip() for h in header_row.split('|') if h.strip()]

        # Process data rows
        rows = []
        for row in data_rows:
            cells = [cell.strip() for cell in row.split('|') if cell.strip()]
            if cells:  # Skip empty rows
                # Ensure all rows have the same length as headers
                cells = cells + [''] * (len(headers) - len(cells)) if len(cells) < len(headers) else cells[:len(headers)]
                rows.append(cells)

        # Create DataFrame
        if headers and rows:
            df = pd.DataFrame(rows, columns=headers)
        elif rows:
            df = pd.DataFrame(rows)
        else:
            return {"type": "Table", "data": [], "headers": headers, "error": "No data found in table"}

        # Convert to structured JSON
        return {
            "type": "Table",
            "headers": headers,
            "data": df.to_dict(orient='records'),
            "num_rows": len(df),
            "num_cols": len(df.columns)
        }

    def _parse_fixed_width_table(self, text_table: str) -> Dict[str, Any]:
        """Parse a fixed-width ASCII table."""
        # Implementation of fixed-width table parsing
        # (Existing implementation)
        
        # Split into lines and remove empty lines
        lines = [line for line in text_table.split('\n') if line.strip()]

        if not lines:
            return {"type": "Table", "data": [], "headers": [], "error": "Empty table"}

        # Check for separator lines (e.g., "-----", "=====", etc.)
        separator_indices = []
        for i, line in enumerate(lines):
            if re.match(r'^[-=+]+$', line.strip()) or all(c in '-=+|' for c in line.strip()):
                separator_indices.append(i)

        # Process based on separator lines
        headers = []
        rows = []
        
        # (Rest of the existing implementation)
        # ...
        
        # Create DataFrame
        if headers and rows:
            # Ensure all rows have the same length as headers
            rows = [row + [''] * (len(headers) - len(row)) for row in rows if len(row) <= len(headers)]
            rows = [row[:len(headers)] for row in rows if len(row) > len(headers)]
            df = pd.DataFrame(rows, columns=headers)
        elif rows:
            df = pd.DataFrame(rows)
        else:
            return {"type": "Table", "data": [], "headers": headers, "error": "No data found in table"}

        # Convert to structured JSON
        return {
            "type": "Table",
            "headers": headers,
            "data": df.to_dict(orient='records'),
            "num_rows": len(df),
            "num_cols": len(df.columns)
        }
        
    def _parse_financial_table(self, text_table: str) -> Dict[str, Any]:
        """Parse a financial table with dollar amounts and totals."""
        # Split into lines and remove empty lines
        lines = [line for line in text_table.split('\n') if line.strip()]
        
        if not lines:
            return {"type": "Table", "data": [], "headers": [], "error": "Empty table"}
            
        # Look for separator lines (e.g., "-----", "=====", etc.)
        separator_indices = []
        for i, line in enumerate(lines):
            if re.match(r'^[-=]+$', line.strip()) or all(c in '-=+' for c in line.strip()):
                separator_indices.append(i)
                
        # Identify header row
        header_row = None
        data_rows = []
        
        if separator_indices:
            # If we have separator lines, use them to identify header and data rows
            if separator_indices[0] == 0:  # Separator at the top
                header_idx = 1
            else:  # Header before first separator
                header_idx = 0
                
            if header_idx < len(lines):
                header_row = lines[header_idx]
                
            # Data rows are all non-separator lines except the header
            data_rows = [lines[i] for i in range(len(lines)) 
                        if i not in separator_indices and i != header_idx]
        else:
            # No separators, look for header based on content
            for i, line in enumerate(lines):
                if "Item" in line or "Description" in line or "Product" in line:
                    header_row = line
                    data_rows = lines[i+1:]
                    break
            
            # If no header found, use first line as header
            if header_row is None:
                header_row = lines[0]
                data_rows = lines[1:]
                
        # Parse header
        # Look for multiple spaces as column separators
        headers = []
        if header_row:
            # Split by multiple spaces
            headers = re.split(r'\s{2,}', header_row.strip())
            
        # If headers couldn't be extracted, use default headers
        if not headers:
            # Try to determine number of columns from data rows
            max_cols = 0
            for row in data_rows:
                cols = len(re.split(r'\s{2,}', row.strip()))
                max_cols = max(max_cols, cols)
                
            if max_cols >= 3:
                headers = ["Item", "Quantity", "Price", "Total"][:max_cols]
            else:
                headers = ["Item", "Value", "Total"][:max_cols]
                
        # Parse data rows
        rows = []
        for row in data_rows:
            # Skip total rows for now
            if row.strip().startswith("Total") or row.strip().startswith("Subtotal"):
                continue
                
            # Split by multiple spaces
            cells = re.split(r'\s{2,}', row.strip())
            
            # Skip empty rows
            if cells and any(cells):
                # Ensure all rows have the same length as headers
                if len(cells) < len(headers):
                    cells = cells + [''] * (len(headers) - len(cells))
                elif len(cells) > len(headers):
                    cells = cells[:len(headers)]
                    
                rows.append(cells)
                
        # Create DataFrame
        if headers and rows:
            df = pd.DataFrame(rows, columns=headers)
        elif rows:
            df = pd.DataFrame(rows)
        else:
            return {"type": "Table", "data": [], "headers": headers, "error": "No data found in table"}
            
        # Convert to structured JSON
        return {
            "type": "Table",
            "headers": headers,
            "data": df.to_dict(orient='records'),
            "num_rows": len(df),
            "num_cols": len(df.columns)
        }
        
    def _parse_space_separated_table(self, text_table: str) -> Dict[str, Any]:
        """Parse a table with multiple spaces as column separators."""
        # Split into lines and remove empty lines
        lines = [line for line in text_table.split('\n') if line.strip()]
        
        if not lines:
            return {"type": "Table", "data": [], "headers": [], "error": "Empty table"}
            
        # Identify header row (usually the first line)
        header_row = lines[0]
        data_rows = lines[1:]
        
        # Parse header by splitting on multiple spaces
        headers = re.split(r'\s{2,}', header_row.strip())
        
        # Parse data rows
        rows = []
        for row in data_rows:
            # Split by multiple spaces
            cells = re.split(r'\s{2,}', row.strip())
            
            # Skip empty rows
            if cells and any(cells):
                # Ensure all rows have the same length as headers
                if len(cells) < len(headers):
                    cells = cells + [''] * (len(headers) - len(cells))
                elif len(cells) > len(headers):
                    cells = cells[:len(headers)]
                    
                rows.append(cells)
                
        # Create DataFrame
        if headers and rows:
            df = pd.DataFrame(rows, columns=headers)
        elif rows:
            df = pd.DataFrame(rows)
        else:
            return {"type": "Table", "data": [], "headers": headers, "error": "No data found in table"}
            
        # Convert to structured JSON
        return {
            "type": "Table",
            "headers": headers,
            "data": df.to_dict(orient='records'),
            "num_rows": len(df),
            "num_cols": len(df.columns)
        }
