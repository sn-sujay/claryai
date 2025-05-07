"""
Cloud storage connectors for ClaryAI.

This module provides connectors for various cloud storage services:
- Google Drive
- Amazon S3
- Dropbox
"""

import os
import tempfile
import logging
from typing import Optional, Dict, Any, List

# Google Drive imports
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Amazon S3 imports
import boto3
from botocore.exceptions import ClientError

# Dropbox imports
import dropbox
from dropbox.exceptions import ApiError, AuthError

# Set up logging
logger = logging.getLogger(__name__)

class CloudStorageConnector:
    """Base class for cloud storage connectors."""
    
    def __init__(self):
        """Initialize the cloud storage connector."""
        pass
    
    def download_file(self, file_id: str, credentials: Dict[str, Any]) -> Optional[str]:
        """
        Download a file from cloud storage.
        
        Args:
            file_id: The ID of the file to download.
            credentials: The credentials to use for authentication.
            
        Returns:
            The path to the downloaded file, or None if the download failed.
        """
        raise NotImplementedError("Subclasses must implement download_file")
    
    def list_files(self, folder_id: Optional[str], credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        List files in a folder.
        
        Args:
            folder_id: The ID of the folder to list files from.
            credentials: The credentials to use for authentication.
            
        Returns:
            A list of file metadata.
        """
        raise NotImplementedError("Subclasses must implement list_files")


class GoogleDriveConnector(CloudStorageConnector):
    """Connector for Google Drive."""
    
    def __init__(self):
        """Initialize the Google Drive connector."""
        super().__init__()
    
    def authenticate(self, credentials: Dict[str, Any]) -> Optional[Credentials]:
        """
        Authenticate with Google Drive.
        
        Args:
            credentials: The credentials to use for authentication.
            
        Returns:
            The authenticated credentials, or None if authentication failed.
        """
        try:
            # Check if we have token
            if 'token' in credentials:
                return Credentials.from_authorized_user_info(credentials)
            
            # Otherwise, use client_id and client_secret to get a new token
            if 'client_id' in credentials and 'client_secret' in credentials:
                flow = InstalledAppFlow.from_client_config(
                    {
                        "installed": {
                            "client_id": credentials['client_id'],
                            "client_secret": credentials['client_secret'],
                            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token"
                        }
                    },
                    ['https://www.googleapis.com/auth/drive.readonly']
                )
                creds = flow.run_local_server(port=0)
                return creds
            
            return None
        except Exception as e:
            logger.error(f"Google Drive authentication failed: {str(e)}")
            return None
    
    def download_file(self, file_id: str, credentials: Dict[str, Any]) -> Optional[str]:
        """
        Download a file from Google Drive.
        
        Args:
            file_id: The ID of the file to download.
            credentials: The credentials to use for authentication.
            
        Returns:
            The path to the downloaded file, or None if the download failed.
        """
        try:
            creds = self.authenticate(credentials)
            if not creds:
                logger.error("Google Drive authentication failed")
                return None
            
            # Build the Drive API client
            service = build('drive', 'v3', credentials=creds)
            
            # Get file metadata to determine the file name
            file_metadata = service.files().get(fileId=file_id).execute()
            file_name = file_metadata.get('name', 'unknown_file')
            
            # Create a temporary file
            fd, temp_path = tempfile.mkstemp(suffix='_' + file_name)
            os.close(fd)
            
            # Download the file
            request = service.files().get_media(fileId=file_id)
            with open(temp_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    logger.info(f"Download {int(status.progress() * 100)}%")
            
            return temp_path
        except Exception as e:
            logger.error(f"Google Drive download failed: {str(e)}")
            return None
    
    def list_files(self, folder_id: Optional[str], credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        List files in a Google Drive folder.
        
        Args:
            folder_id: The ID of the folder to list files from.
            credentials: The credentials to use for authentication.
            
        Returns:
            A list of file metadata.
        """
        try:
            creds = self.authenticate(credentials)
            if not creds:
                logger.error("Google Drive authentication failed")
                return []
            
            # Build the Drive API client
            service = build('drive', 'v3', credentials=creds)
            
            # Prepare the query
            query = ""
            if folder_id:
                query = f"'{folder_id}' in parents"
            
            # List files
            results = service.files().list(
                q=query,
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType, size, createdTime)"
            ).execute()
            
            return results.get('files', [])
        except Exception as e:
            logger.error(f"Google Drive list files failed: {str(e)}")
            return []


class S3Connector(CloudStorageConnector):
    """Connector for Amazon S3."""
    
    def __init__(self):
        """Initialize the S3 connector."""
        super().__init__()
    
    def authenticate(self, credentials: Dict[str, Any]) -> Optional[boto3.session.Session]:
        """
        Authenticate with Amazon S3.
        
        Args:
            credentials: The credentials to use for authentication.
            
        Returns:
            The authenticated session, or None if authentication failed.
        """
        try:
            # Check if we have access key and secret key
            if 'aws_access_key_id' in credentials and 'aws_secret_access_key' in credentials:
                session = boto3.session.Session(
                    aws_access_key_id=credentials['aws_access_key_id'],
                    aws_secret_access_key=credentials['aws_secret_access_key'],
                    region_name=credentials.get('region_name', 'us-east-1')
                )
                return session
            
            # Otherwise, use default credentials
            return boto3.session.Session()
        except Exception as e:
            logger.error(f"S3 authentication failed: {str(e)}")
            return None
    
    def download_file(self, file_id: str, credentials: Dict[str, Any]) -> Optional[str]:
        """
        Download a file from Amazon S3.
        
        Args:
            file_id: The ID of the file to download (bucket/key).
            credentials: The credentials to use for authentication.
            
        Returns:
            The path to the downloaded file, or None if the download failed.
        """
        try:
            session = self.authenticate(credentials)
            if not session:
                logger.error("S3 authentication failed")
                return None
            
            # Parse the file ID (bucket/key)
            parts = file_id.split('/', 1)
            if len(parts) != 2:
                logger.error(f"Invalid S3 file ID: {file_id}")
                return None
            
            bucket, key = parts
            
            # Get the file name from the key
            file_name = os.path.basename(key)
            
            # Create a temporary file
            fd, temp_path = tempfile.mkstemp(suffix='_' + file_name)
            os.close(fd)
            
            # Download the file
            s3 = session.client('s3')
            s3.download_file(bucket, key, temp_path)
            
            return temp_path
        except Exception as e:
            logger.error(f"S3 download failed: {str(e)}")
            return None
    
    def list_files(self, folder_id: Optional[str], credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        List files in an S3 bucket/prefix.
        
        Args:
            folder_id: The ID of the folder to list files from (bucket/prefix).
            credentials: The credentials to use for authentication.
            
        Returns:
            A list of file metadata.
        """
        try:
            session = self.authenticate(credentials)
            if not session:
                logger.error("S3 authentication failed")
                return []
            
            # Parse the folder ID (bucket/prefix)
            if not folder_id:
                logger.error("S3 folder ID is required")
                return []
            
            parts = folder_id.split('/', 1)
            bucket = parts[0]
            prefix = parts[1] if len(parts) > 1 else ""
            
            # List files
            s3 = session.client('s3')
            paginator = s3.get_paginator('list_objects_v2')
            
            files = []
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        files.append({
                            'id': f"{bucket}/{obj['Key']}",
                            'name': os.path.basename(obj['Key']),
                            'size': obj['Size'],
                            'lastModified': obj['LastModified']
                        })
            
            return files
        except Exception as e:
            logger.error(f"S3 list files failed: {str(e)}")
            return []


class DropboxConnector(CloudStorageConnector):
    """Connector for Dropbox."""
    
    def __init__(self):
        """Initialize the Dropbox connector."""
        super().__init__()
    
    def authenticate(self, credentials: Dict[str, Any]) -> Optional[dropbox.Dropbox]:
        """
        Authenticate with Dropbox.
        
        Args:
            credentials: The credentials to use for authentication.
            
        Returns:
            The authenticated Dropbox client, or None if authentication failed.
        """
        try:
            # Check if we have access token
            if 'access_token' in credentials:
                dbx = dropbox.Dropbox(credentials['access_token'])
                # Test the connection
                dbx.users_get_current_account()
                return dbx
            
            return None
        except AuthError as e:
            logger.error(f"Dropbox authentication failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Dropbox authentication failed: {str(e)}")
            return None
    
    def download_file(self, file_id: str, credentials: Dict[str, Any]) -> Optional[str]:
        """
        Download a file from Dropbox.
        
        Args:
            file_id: The ID of the file to download (path).
            credentials: The credentials to use for authentication.
            
        Returns:
            The path to the downloaded file, or None if the download failed.
        """
        try:
            dbx = self.authenticate(credentials)
            if not dbx:
                logger.error("Dropbox authentication failed")
                return None
            
            # Get the file name from the path
            file_name = os.path.basename(file_id)
            
            # Create a temporary file
            fd, temp_path = tempfile.mkstemp(suffix='_' + file_name)
            os.close(fd)
            
            # Download the file
            with open(temp_path, 'wb') as f:
                metadata, res = dbx.files_download(file_id)
                f.write(res.content)
            
            return temp_path
        except ApiError as e:
            logger.error(f"Dropbox download failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Dropbox download failed: {str(e)}")
            return None
    
    def list_files(self, folder_id: Optional[str], credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        List files in a Dropbox folder.
        
        Args:
            folder_id: The ID of the folder to list files from (path).
            credentials: The credentials to use for authentication.
            
        Returns:
            A list of file metadata.
        """
        try:
            dbx = self.authenticate(credentials)
            if not dbx:
                logger.error("Dropbox authentication failed")
                return []
            
            # Use root folder if not specified
            path = folder_id or ""
            
            # List files
            result = dbx.files_list_folder(path)
            
            files = []
            for entry in result.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    files.append({
                        'id': entry.path_display,
                        'name': entry.name,
                        'size': entry.size,
                        'lastModified': entry.client_modified
                    })
            
            return files
        except ApiError as e:
            logger.error(f"Dropbox list files failed: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Dropbox list files failed: {str(e)}")
            return []


# Factory function to get the appropriate connector
def get_connector(provider: str) -> Optional[CloudStorageConnector]:
    """
    Get a cloud storage connector for the specified provider.
    
    Args:
        provider: The cloud storage provider (google_drive, s3, dropbox).
        
    Returns:
        The appropriate connector, or None if the provider is not supported.
    """
    if provider == "google_drive":
        return GoogleDriveConnector()
    elif provider == "s3":
        return S3Connector()
    elif provider == "dropbox":
        return DropboxConnector()
    else:
        logger.error(f"Unsupported cloud storage provider: {provider}")
        return None
