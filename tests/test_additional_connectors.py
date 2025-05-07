"""
Tests for additional data source connectors.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add the parent directory to the path so we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Add the src directory to the path so modules can import each other
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.additional_connectors import (
    BaseConnector,
    NotionConnector,
    MongoDBConnector,
    GitHubConnector,
    SlackConnector,
    get_connector
)


class TestBaseConnector(unittest.TestCase):
    """Tests for the BaseConnector class."""

    def test_base_class_methods(self):
        """Test that the base class methods raise NotImplementedError."""
        connector = BaseConnector()

        with self.assertRaises(NotImplementedError):
            connector.download_data("source_id", {})

        with self.assertRaises(NotImplementedError):
            connector.list_sources("parent_id", {})


class TestNotionConnector(unittest.TestCase):
    """Tests for the NotionConnector class."""

    @patch('src.additional_connectors.requests.get')
    def test_download_data(self, mock_get):
        """Test downloading data from Notion."""
        # Set up the mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {"plain_text": "Test paragraph"}
                        ]
                    }
                },
                {
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [
                            {"plain_text": "Test heading"}
                        ]
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        # Create the connector
        connector = NotionConnector()

        # Call the method
        with patch('builtins.open', unittest.mock.mock_open()) as mock_open:
            result = connector.download_data("page_id", {"token": "mock_token"})

        # Check the result
        self.assertIsNotNone(result)
        mock_get.assert_called_once_with(
            "https://api.notion.com/v1/blocks/page_id/children",
            headers={
                "Authorization": "Bearer mock_token",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
        )
        mock_open.assert_called_once()
        mock_open().write.assert_called_once()

    @patch('src.additional_connectors.requests.post')
    def test_list_sources(self, mock_post):
        """Test listing pages in Notion."""
        # Set up the mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "page_id_1",
                    "properties": {
                        "title": {
                            "type": "title",
                            "title": [
                                {"plain_text": "Test Page 1"}
                            ]
                        }
                    },
                    "last_edited_time": "2023-01-01T00:00:00.000Z"
                },
                {
                    "id": "page_id_2",
                    "properties": {
                        "title": {
                            "type": "title",
                            "title": [
                                {"plain_text": "Test Page 2"}
                            ]
                        }
                    },
                    "last_edited_time": "2023-01-02T00:00:00.000Z"
                }
            ]
        }
        mock_post.return_value = mock_response

        # Create the connector
        connector = NotionConnector()

        # Call the method
        result = connector.list_sources(None, {"token": "mock_token"})

        # Check the result
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "page_id_1")
        self.assertEqual(result[0]["title"], "Test Page 1")
        self.assertEqual(result[1]["id"], "page_id_2")
        self.assertEqual(result[1]["title"], "Test Page 2")
        mock_post.assert_called_once_with(
            "https://api.notion.com/v1/search",
            headers={
                "Authorization": "Bearer mock_token",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            },
            json={"filter": {"value": "page", "property": "object"}}
        )


class TestMongoDBConnector(unittest.TestCase):
    """Tests for the MongoDBConnector class."""

    @patch('src.additional_connectors.import_optional')
    @patch('tempfile.mkstemp')
    @patch('os.close')
    def test_download_data(self, mock_close, mock_mkstemp, mock_import):
        """Test downloading data from MongoDB."""
        # Set up the mocks
        mock_mkstemp.return_value = (123, "/tmp/mock_file")

        mock_pymongo = MagicMock()
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_object_id = MagicMock()

        # Create a mock ObjectId class
        class MockObjectId:
            pass

        mock_pymongo.ObjectId = MockObjectId
        mock_pymongo.MongoClient.return_value = mock_client
        mock_client.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection

        # Set up the mock documents
        doc1 = {"_id": mock_object_id, "name": "Test 1"}
        doc2 = {"_id": "id2", "name": "Test 2"}
        mock_collection.find.return_value = [doc1, doc2]

        # Set up the import_optional mock
        mock_import.return_value = mock_pymongo

        # Create the connector
        connector = MongoDBConnector()

        # Call the method
        with patch('builtins.open', unittest.mock.mock_open()) as mock_open:
            with patch('json.dump') as mock_dump:
                result = connector.download_data("database.collection", {"connection_string": "mongodb://localhost"})

        # Check the result
        self.assertEqual(result, "/tmp/mock_file")
        mock_pymongo.MongoClient.assert_called_once_with("mongodb://localhost")
        mock_client.__getitem__.assert_called_once_with("database")
        mock_db.__getitem__.assert_called_once_with("collection")
        mock_collection.find.assert_called_once_with({})
        mock_open.assert_called_once_with("/tmp/mock_file", "w", encoding="utf-8")
        mock_dump.assert_called_once()


class TestGetConnector(unittest.TestCase):
    """Tests for the get_connector function."""

    def test_get_notion_connector(self):
        """Test getting a Notion connector."""
        connector = get_connector("notion")
        self.assertIsInstance(connector, NotionConnector)

    def test_get_mongodb_connector(self):
        """Test getting a MongoDB connector."""
        connector = get_connector("mongodb")
        self.assertIsInstance(connector, MongoDBConnector)

    def test_get_github_connector(self):
        """Test getting a GitHub connector."""
        connector = get_connector("github")
        self.assertIsInstance(connector, GitHubConnector)

    def test_get_slack_connector(self):
        """Test getting a Slack connector."""
        connector = get_connector("slack")
        self.assertIsInstance(connector, SlackConnector)

    def test_get_unsupported_connector(self):
        """Test getting an unsupported connector."""
        connector = get_connector("unsupported")
        self.assertIsNone(connector)


if __name__ == '__main__':
    unittest.main()
