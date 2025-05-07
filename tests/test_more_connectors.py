"""
Tests for more data source connectors.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add the parent directory to the path so we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Add the src directory to the path so modules can import each other
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.more_connectors import (
    AzureBlobConnector,
    BoxConnector,
    CouchbaseConnector,
    ElasticsearchConnector
)


class TestMoreConnectors(unittest.TestCase):
    """Tests for more data source connectors."""
    
    @patch('src.more_connectors.BlobServiceClient')
    def test_azure_blob_connector(self, mock_client):
        """Test Azure Blob Storage connector."""
        # Set up mocks
        mock_azure = MagicMock()
        mock_client.from_connection_string.return_value = mock_azure
        mock_container = MagicMock()
        mock_azure.get_container_client.return_value = mock_container
        mock_blob = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob.download_blob.return_value.readall.return_value = b"test content"
        
        # Create the connector
        connector = AzureBlobConnector("connection_string")
        
        # Test downloading a blob
        content = connector.download_blob("container", "blob")
        
        # Check the result
        self.assertEqual(content, b"test content")
        
        # Check that the methods were called
        mock_client.from_connection_string.assert_called_once_with("connection_string")
        mock_azure.get_container_client.assert_called_once_with("container")
        mock_container.get_blob_client.assert_called_once_with("blob")
        mock_blob.download_blob.assert_called_once()
    
    @patch('src.more_connectors.Client')
    def test_box_connector(self, mock_client):
        """Test Box connector."""
        # Set up mocks
        mock_box = MagicMock()
        mock_client.return_value = mock_box
        mock_file = MagicMock()
        mock_box.file.return_value = mock_file
        mock_file.get.return_value.content = b"test content"
        
        # Create the connector
        connector = BoxConnector("access_token")
        
        # Test downloading a file
        content = connector.download_file("file_id")
        
        # Check the result
        self.assertEqual(content, b"test content")
        
        # Check that the methods were called
        mock_client.assert_called_once_with(access_token="access_token")
        mock_box.file.assert_called_once_with("file_id")
        mock_file.get.assert_called_once()
    
    @patch('src.more_connectors.Cluster')
    def test_couchbase_connector(self, mock_cluster):
        """Test Couchbase connector."""
        # Set up mocks
        mock_cb = MagicMock()
        mock_cluster.connect.return_value = mock_cb
        mock_bucket = MagicMock()
        mock_cb.bucket.return_value = mock_bucket
        mock_scope = MagicMock()
        mock_bucket.scope.return_value = mock_scope
        mock_collection = MagicMock()
        mock_scope.collection.return_value = mock_collection
        mock_collection.get.return_value.content_as[dict] = {"data": "test"}
        
        # Create the connector
        connector = CouchbaseConnector("connection_string", "username", "password")
        
        # Test getting a document
        document = connector.get_document("bucket", "scope", "collection", "document_id")
        
        # Check the result
        self.assertEqual(document, {"data": "test"})
        
        # Check that the methods were called
        mock_cluster.connect.assert_called_once_with(
            "connection_string",
            username="username",
            password="password"
        )
        mock_cb.bucket.assert_called_once_with("bucket")
        mock_bucket.scope.assert_called_once_with("scope")
        mock_scope.collection.assert_called_once_with("collection")
        mock_collection.get.assert_called_once_with("document_id")
    
    @patch('src.more_connectors.Elasticsearch')
    def test_elasticsearch_connector(self, mock_es):
        """Test Elasticsearch connector."""
        # Set up mocks
        mock_client = MagicMock()
        mock_es.return_value = mock_client
        mock_client.get.return_value = {
            "_source": {"data": "test"}
        }
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"data": "test1"}},
                    {"_source": {"data": "test2"}}
                ]
            }
        }
        
        # Create the connector
        connector = ElasticsearchConnector("hosts", "username", "password")
        
        # Test getting a document
        document = connector.get_document("index", "document_id")
        
        # Check the result
        self.assertEqual(document, {"data": "test"})
        
        # Check that the methods were called
        mock_es.assert_called_once_with(
            hosts="hosts",
            http_auth=("username", "password")
        )
        mock_client.get.assert_called_once_with(
            index="index",
            id="document_id"
        )
        
        # Test searching for documents
        documents = connector.search_documents("index", {"query": {"match_all": {}}})
        
        # Check the result
        self.assertEqual(documents, [{"data": "test1"}, {"data": "test2"}])
        
        # Check that the methods were called
        mock_client.search.assert_called_once_with(
            index="index",
            body={"query": {"match_all": {}}}
        )


if __name__ == '__main__':
    unittest.main()
