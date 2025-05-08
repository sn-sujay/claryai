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
            if '|' in text_table and '-+-' in text_table or '---|---' in text_table:
                return self._parse_markdown_table(text_table)

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
        # Split into lines and remove empty lines
        lines = [line for line in text_table.split('\n') if line.strip()]

        if not lines:
            return {"type": "Table", "data": [], "headers": [], "error": "Empty table"}

        # Check for separator lines (e.g., "-----", "=====", etc.)
        separator_indices = []
        for i, line in enumerate(lines):
            if re.match(r'^[-=+]+$', line.strip()) or all(c in '-=+|' for c in line.strip()):
                separator_indices.append(i)

        # If we found separator lines, use them to determine the table structure
        if separator_indices:
            # Determine header and data rows based on separator positions
            if separator_indices[0] == 0:  # Separator at the top
                header_idx = 1
            else:  # Header before first separator
                header_idx = 0

            # Get header row
            header_row = lines[header_idx]

            # Skip separator lines for data rows
            data_rows = [lines[i] for i in range(len(lines)) if i not in separator_indices and i != header_idx]

            # Try to detect column boundaries based on the separator line
            separator_line = lines[separator_indices[0]]

            # Find column boundaries based on spaces in the separator line
            boundaries = []
            in_separator = False
            for i, char in enumerate(separator_line):
                if char in '-=+' and not in_separator:
                    boundaries.append(i)
                    in_separator = True
                elif char == ' ' and in_separator:
                    in_separator = False

            # Extract headers
            headers = []
            if boundaries:
                # Extract headers based on boundaries
                prev_boundary = 0
                for boundary in boundaries:
                    if boundary > prev_boundary:
                        headers.append(header_row[prev_boundary:boundary].strip())
                    prev_boundary = boundary
                if prev_boundary < len(header_row):
                    headers.append(header_row[prev_boundary:].strip())
            else:
                # Fallback: split by whitespace
                headers = [h for h in header_row.split() if h]

            # Extract data rows
            rows = []
            for line in data_rows:
                if boundaries:
                    # Extract cells based on boundaries
                    row = []
                    prev_boundary = 0
                    for boundary in boundaries:
                        if boundary > prev_boundary and boundary <= len(line):
                            row.append(line[prev_boundary:boundary].strip())
                        prev_boundary = boundary
                    if prev_boundary < len(line):
                        row.append(line[prev_boundary:].strip())
                    if row:  # Skip empty rows
                        rows.append(row)
                else:
                    # Fallback: split by whitespace
                    row = [cell for cell in line.split() if cell]
                    if row:  # Skip empty rows
                        rows.append(row)
        else:
            # No separator lines found, try to detect column boundaries based on spaces
            def find_boundaries(line):
                boundaries = []
                in_word = False
                for i, char in enumerate(line):
                    if char != ' ' and not in_word:
                        boundaries.append(i)
                        in_word = True
                    elif char == ' ' and in_word:
                        in_word = False
                return boundaries

            # Use the first line to detect boundaries
            boundaries = find_boundaries(lines[0])

            # Extract headers and data
            headers = []
            if boundaries:
                # Extract headers from first line
                prev_boundary = 0
                for boundary in boundaries:
                    headers.append(lines[0][prev_boundary:boundary].strip())
                    prev_boundary = boundary
                headers.append(lines[0][prev_boundary:].strip())
            else:
                # Fallback: split by whitespace
                headers = lines[0].split()

            # Extract data rows
            rows = []
            for line in lines[1:]:
                if boundaries:
                    # Extract cells based on boundaries
                    row = []
                    prev_boundary = 0
                    for boundary in boundaries:
                        row.append(line[prev_boundary:boundary].strip())
                        prev_boundary = boundary
                    row.append(line[prev_boundary:].strip())
                    rows.append(row)
                else:
                    # Fallback: split by whitespace
                    rows.append(line.split())

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
