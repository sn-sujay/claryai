"""
Tests for cloud storage connectors.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add the parent directory to the path so we can import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Add the src directory to the path so modules can import each other
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.cloud_connectors import (
    CloudStorageConnector,
    GoogleDriveConnector,
    S3Connector,
    DropboxConnector,
    get_connector
)


class TestCloudStorageConnector(unittest.TestCase):
    """Tests for the CloudStorageConnector base class."""
    
    def test_base_class_methods(self):
        """Test that the base class methods raise NotImplementedError."""
        connector = CloudStorageConnector()
        
        with self.assertRaises(NotImplementedError):
            connector.download_file("file_id", {})
        
        with self.assertRaises(NotImplementedError):
            connector.list_files("folder_id", {})


class TestGoogleDriveConnector(unittest.TestCase):
    """Tests for the GoogleDriveConnector class."""
    
    @patch('src.cloud_connectors.Credentials')
    def test_authenticate_with_token(self, mock_credentials):
        """Test authentication with a token."""
        # Set up the mock
        mock_credentials.from_authorized_user_info.return_value = "mock_creds"
        
        # Create the connector
        connector = GoogleDriveConnector()
        
        # Call the method
        result = connector.authenticate({"token": "mock_token"})
        
        # Check the result
        self.assertEqual(result, "mock_creds")
        mock_credentials.from_authorized_user_info.assert_called_once_with({"token": "mock_token"})
    
    @patch('src.cloud_connectors.InstalledAppFlow')
    def test_authenticate_with_client_id(self, mock_flow):
        """Test authentication with client ID and secret."""
        # Set up the mock
        mock_flow_instance = MagicMock()
        mock_flow_instance.run_local_server.return_value = "mock_creds"
        mock_flow.from_client_config.return_value = mock_flow_instance
        
        # Create the connector
        connector = GoogleDriveConnector()
        
        # Call the method
        result = connector.authenticate({
            "client_id": "mock_client_id",
            "client_secret": "mock_client_secret"
        })
        
        # Check the result
        self.assertEqual(result, "mock_creds")
        mock_flow.from_client_config.assert_called_once()
        mock_flow_instance.run_local_server.assert_called_once_with(port=0)
    
    @patch('src.cloud_connectors.build')
    @patch('src.cloud_connectors.MediaIoBaseDownload')
    @patch('src.cloud_connectors.tempfile.mkstemp')
    @patch('src.cloud_connectors.os.close')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    def test_download_file(self, mock_open, mock_close, mock_mkstemp, mock_downloader, mock_build):
        """Test downloading a file from Google Drive."""
        # Set up the mocks
        mock_mkstemp.return_value = (123, "/tmp/mock_file")
        
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        mock_file_metadata = MagicMock()
        mock_file_metadata.execute.return_value = {"name": "test.txt"}
        mock_service.files.return_value.get.return_value = mock_file_metadata
        
        mock_request = MagicMock()
        mock_service.files.return_value.get_media.return_value = mock_request
        
        mock_downloader_instance = MagicMock()
        mock_downloader_instance.next_chunk.side_effect = [(MagicMock(progress=lambda: 0.5), False), (MagicMock(progress=lambda: 1.0), True)]
        mock_downloader.return_value = mock_downloader_instance
        
        # Create the connector
        connector = GoogleDriveConnector()
        
        # Mock the authenticate method
        connector.authenticate = MagicMock(return_value="mock_creds")
        
        # Call the method
        result = connector.download_file("file_id", {"token": "mock_token"})
        
        # Check the result
        self.assertEqual(result, "/tmp/mock_file")
        connector.authenticate.assert_called_once_with({"token": "mock_token"})
        mock_build.assert_called_once_with('drive', 'v3', credentials="mock_creds")
        mock_service.files.return_value.get.assert_called_once_with(fileId="file_id")
        mock_service.files.return_value.get_media.assert_called_once_with(fileId="file_id")
        mock_downloader.assert_called_once()
        self.assertEqual(mock_downloader_instance.next_chunk.call_count, 2)


class TestS3Connector(unittest.TestCase):
    """Tests for the S3Connector class."""
    
    @patch('src.cloud_connectors.boto3.session.Session')
    def test_authenticate_with_keys(self, mock_session):
        """Test authentication with access key and secret key."""
        # Set up the mock
        mock_session.return_value = "mock_session"
        
        # Create the connector
        connector = S3Connector()
        
        # Call the method
        result = connector.authenticate({
            "aws_access_key_id": "mock_key",
            "aws_secret_access_key": "mock_secret"
        })
        
        # Check the result
        self.assertEqual(result, "mock_session")
        mock_session.assert_called_once_with(
            aws_access_key_id="mock_key",
            aws_secret_access_key="mock_secret",
            region_name="us-east-1"
        )
    
    @patch('src.cloud_connectors.boto3.session.Session')
    def test_authenticate_with_default(self, mock_session):
        """Test authentication with default credentials."""
        # Set up the mock
        mock_session.return_value = "mock_session"
        
        # Create the connector
        connector = S3Connector()
        
        # Call the method
        result = connector.authenticate({})
        
        # Check the result
        self.assertEqual(result, "mock_session")
        mock_session.assert_called_once_with()
    
    @patch('src.cloud_connectors.tempfile.mkstemp')
    @patch('src.cloud_connectors.os.close')
    def test_download_file(self, mock_close, mock_mkstemp):
        """Test downloading a file from S3."""
        # Set up the mocks
        mock_mkstemp.return_value = (123, "/tmp/mock_file")
        
        mock_session = MagicMock()
        mock_s3 = MagicMock()
        mock_session.client.return_value = mock_s3
        
        # Create the connector
        connector = S3Connector()
        
        # Mock the authenticate method
        connector.authenticate = MagicMock(return_value=mock_session)
        
        # Call the method
        result = connector.download_file("bucket/key/file.txt", {"aws_access_key_id": "mock_key"})
        
        # Check the result
        self.assertEqual(result, "/tmp/mock_file")
        connector.authenticate.assert_called_once_with({"aws_access_key_id": "mock_key"})
        mock_session.client.assert_called_once_with('s3')
        mock_s3.download_file.assert_called_once_with("bucket", "key/file.txt", "/tmp/mock_file")


class TestDropboxConnector(unittest.TestCase):
    """Tests for the DropboxConnector class."""
    
    @patch('src.cloud_connectors.dropbox.Dropbox')
    def test_authenticate(self, mock_dropbox):
        """Test authentication with an access token."""
        # Set up the mock
        mock_dbx = MagicMock()
        mock_dropbox.return_value = mock_dbx
        
        # Create the connector
        connector = DropboxConnector()
        
        # Call the method
        result = connector.authenticate({"access_token": "mock_token"})
        
        # Check the result
        self.assertEqual(result, mock_dbx)
        mock_dropbox.assert_called_once_with("mock_token")
        mock_dbx.users_get_current_account.assert_called_once()
    
    @patch('src.cloud_connectors.tempfile.mkstemp')
    @patch('src.cloud_connectors.os.close')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    def test_download_file(self, mock_open, mock_close, mock_mkstemp):
        """Test downloading a file from Dropbox."""
        # Set up the mocks
        mock_mkstemp.return_value = (123, "/tmp/mock_file")
        
        mock_dbx = MagicMock()
        mock_metadata = MagicMock()
        mock_res = MagicMock()
        mock_res.content = b"file content"
        mock_dbx.files_download.return_value = (mock_metadata, mock_res)
        
        # Create the connector
        connector = DropboxConnector()
        
        # Mock the authenticate method
        connector.authenticate = MagicMock(return_value=mock_dbx)
        
        # Call the method
        result = connector.download_file("/path/to/file.txt", {"access_token": "mock_token"})
        
        # Check the result
        self.assertEqual(result, "/tmp/mock_file")
        connector.authenticate.assert_called_once_with({"access_token": "mock_token"})
        mock_dbx.files_download.assert_called_once_with("/path/to/file.txt")
        mock_open.assert_called_once_with("/tmp/mock_file", "wb")
        mock_open().write.assert_called_once_with(b"file content")


class TestGetConnector(unittest.TestCase):
    """Tests for the get_connector function."""
    
    def test_get_google_drive_connector(self):
        """Test getting a Google Drive connector."""
        connector = get_connector("google_drive")
        self.assertIsInstance(connector, GoogleDriveConnector)
    
    def test_get_s3_connector(self):
        """Test getting an S3 connector."""
        connector = get_connector("s3")
        self.assertIsInstance(connector, S3Connector)
    
    def test_get_dropbox_connector(self):
        """Test getting a Dropbox connector."""
        connector = get_connector("dropbox")
        self.assertIsInstance(connector, DropboxConnector)
    
    def test_get_unsupported_connector(self):
        """Test getting an unsupported connector."""
        connector = get_connector("unsupported")
        self.assertIsNone(connector)


if __name__ == '__main__':
    unittest.main()
