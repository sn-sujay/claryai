"""
Additional data source connectors for ClaryAI.

This module provides connectors for various data sources from Unstructured.io:
- Azure
- Box
- Couchbase
- Databricks Volumes
- Elasticsearch
- Google Cloud Storage
- Jira
- Kafka
- OneDrive
- Outlook
- PostgreSQL
- Salesforce
- SharePoint
- Snowflake
- Zendesk
"""

import os
import tempfile
import logging
import json
import requests
from typing import Optional, Dict, Any, List, Union
from urllib.parse import urlparse

# Set up logging
logger = logging.getLogger(__name__)

# Optional imports - these will be imported only when needed
# to avoid requiring all dependencies for all connectors
OPTIONAL_IMPORTS = {
    "azure.storage.blob": None,
    "boxsdk": None,
    "couchbase": None,
    "elasticsearch": None,
    "google.cloud.storage": None,
    "jira": None,
    "kafka": None,
    "msal": None,  # For Microsoft services (OneDrive, SharePoint, Outlook)
    "psycopg2": None,
    "simple_salesforce": None,
    "snowflake.connector": None,
    "zenpy": None
}

def import_optional(module_name):
    """Import an optional module."""
    if module_name not in OPTIONAL_IMPORTS:
        logger.warning(f"Unknown optional module: {module_name}")
        return None

    if OPTIONAL_IMPORTS[module_name] is None:
        try:
            OPTIONAL_IMPORTS[module_name] = __import__(module_name)
        except ImportError:
            logger.warning(f"Optional module {module_name} not available")
            return None
    return OPTIONAL_IMPORTS[module_name]


class BaseConnector:
    """Base class for all data source connectors."""

    def __init__(self):
        """Initialize the connector."""
        pass

    def download_data(self, source_id: str, credentials: Dict[str, Any]) -> Optional[str]:
        """
        Download data from the source.

        Args:
            source_id: The ID of the source to download.
            credentials: The credentials to use for authentication.

        Returns:
            The path to the downloaded file, or None if the download failed.
        """
        raise NotImplementedError("Subclasses must implement download_data")

    def list_sources(self, parent_id: Optional[str], credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        List sources in a parent container.

        Args:
            parent_id: The ID of the parent container to list sources from.
            credentials: The credentials to use for authentication.

        Returns:
            A list of source metadata.
        """
        raise NotImplementedError("Subclasses must implement list_sources")


class AzureConnector(BaseConnector):
    """Connector for Azure Blob Storage."""

    def __init__(self):
        """Initialize the Azure connector."""
        super().__init__()

    def download_data(self, source_id: str, credentials: Dict[str, Any]) -> Optional[str]:
        """
        Download data from Azure Blob Storage.

        Args:
            source_id: The ID of the blob to download in format "container/blob_name".
            credentials: The credentials to use for authentication.
                Must contain 'connection_string' key.

        Returns:
            The path to the downloaded file, or None if the download failed.
        """
        try:
            azure = import_optional("azure.storage.blob")
            if azure is None:
                logger.error("azure-storage-blob module not available")
                return None

            if 'connection_string' not in credentials:
                logger.error("Azure connection string is required")
                return None

            connection_string = credentials['connection_string']

            # Parse the source_id
            parts = source_id.split('/', 1)
            if len(parts) != 2:
                logger.error(f"Invalid Azure source ID format: {source_id}")
                return None

            container_name, blob_name = parts

            # Create a temporary file
            file_name = os.path.basename(blob_name)
            fd, temp_path = tempfile.mkstemp(suffix=f"_{file_name}")
            os.close(fd)

            # Download the blob
            blob_service_client = azure.BlobServiceClient.from_connection_string(connection_string)
            container_client = blob_service_client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)

            with open(temp_path, "wb") as f:
                f.write(blob_client.download_blob().readall())

            return temp_path
        except Exception as e:
            logger.error(f"Azure download failed: {str(e)}")
            return None

    def list_sources(self, parent_id: Optional[str], credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        List blobs in an Azure container.

        Args:
            parent_id: The name of the container to list blobs from.
            credentials: The credentials to use for authentication.
                Must contain 'connection_string' key.

        Returns:
            A list of blob metadata.
        """
        try:
            azure = import_optional("azure.storage.blob")
            if azure is None:
                logger.error("azure-storage-blob module not available")
                return []

            if 'connection_string' not in credentials:
                logger.error("Azure connection string is required")
                return []

            connection_string = credentials['connection_string']

            # Connect to Azure
            blob_service_client = azure.BlobServiceClient.from_connection_string(connection_string)

            if parent_id:
                # List blobs in the specified container
                container_client = blob_service_client.get_container_client(parent_id)
                blobs = container_client.list_blobs()

                result = []
                for blob in blobs:
                    result.append({
                        "id": f"{parent_id}/{blob.name}",
                        "name": blob.name,
                        "size": blob.size,
                        "last_modified": blob.last_modified
                    })

                return result
            else:
                # List all containers
                containers = blob_service_client.list_containers()

                result = []
                for container in containers:
                    result.append({
                        "id": container.name,
                        "name": container.name,
                        "type": "container"
                    })

                return result
        except Exception as e:
            logger.error(f"Azure list blobs failed: {str(e)}")
            return []


class CouchbaseConnector(BaseConnector):
    """Connector for Couchbase."""

    def __init__(self):
        """Initialize the Couchbase connector."""
        super().__init__()

    def download_data(self, source_id: str, credentials: Dict[str, Any]) -> Optional[str]:
        """
        Download data from Couchbase.

        Args:
            source_id: The ID of the document or query to download in format "bucket.scope.collection:document_id" or "bucket.scope.collection:query".
            credentials: The credentials to use for authentication.
                Must contain 'connection_string', 'username', and 'password' keys.

        Returns:
            The path to the downloaded file, or None if the download failed.
        """
        try:
            couchbase = import_optional("couchbase")
            if couchbase is None:
                logger.error("couchbase module not available")
                return None

            if not all(k in credentials for k in ['connection_string', 'username', 'password']):
                logger.error("Couchbase credentials must contain connection_string, username, and password")
                return None

            connection_string = credentials['connection_string']
            username = credentials['username']
            password = credentials['password']

            # Parse the source_id
            parts = source_id.split(':', 1)
            if len(parts) != 2:
                logger.error(f"Invalid Couchbase source ID format: {source_id}")
                return None

            collection_path, document_id_or_query = parts
            collection_parts = collection_path.split('.')
            if len(collection_parts) != 3:
                logger.error(f"Invalid Couchbase collection path format: {collection_path}")
                return None

            bucket_name, scope_name, collection_name = collection_parts

            # Create a temporary file
            fd, temp_path = tempfile.mkstemp(suffix='_couchbase.json')
            os.close(fd)

            # Connect to Couchbase
            from couchbase.cluster import Cluster, ClusterOptions
            from couchbase.auth import PasswordAuthenticator

            auth = PasswordAuthenticator(username, password)
            cluster = Cluster(connection_string, ClusterOptions(auth))

            # Get the bucket, scope, and collection
            bucket = cluster.bucket(bucket_name)
            scope = bucket.scope(scope_name)
            collection = scope.collection(collection_name)

            # Check if it's a document ID or a query
            if document_id_or_query.startswith("SELECT "):
                # It's a query
                query_result = cluster.query(document_id_or_query)
                result = list(query_result)
            else:
                # It's a document ID
                result = collection.get(document_id_or_query).content_as
                result = [result]  # Make it a list for consistent handling

            # Write to file
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)

            return temp_path
        except Exception as e:
            logger.error(f"Couchbase download failed: {str(e)}")
            return None

    def list_sources(self, parent_id: Optional[str], credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        List buckets, scopes, collections, or documents in Couchbase.

        Args:
            parent_id: The ID of the parent container to list sources from in format "bucket" or "bucket.scope" or "bucket.scope.collection".
            credentials: The credentials to use for authentication.
                Must contain 'connection_string', 'username', and 'password' keys.

        Returns:
            A list of source metadata.
        """
        try:
            couchbase = import_optional("couchbase")
            if couchbase is None:
                logger.error("couchbase module not available")
                return []

            if not all(k in credentials for k in ['connection_string', 'username', 'password']):
                logger.error("Couchbase credentials must contain connection_string, username, and password")
                return []

            connection_string = credentials['connection_string']
            username = credentials['username']
            password = credentials['password']

            # Connect to Couchbase
            from couchbase.cluster import Cluster, ClusterOptions
            from couchbase.auth import PasswordAuthenticator

            auth = PasswordAuthenticator(username, password)
            cluster = Cluster(connection_string, ClusterOptions(auth))

            if not parent_id:
                # List buckets
                buckets = cluster.buckets().get_all_buckets()

                result = []
                for bucket_name in buckets:
                    result.append({
                        "id": bucket_name,
                        "name": bucket_name,
                        "type": "bucket"
                    })

                return result
            elif '.' not in parent_id:
                # List scopes in a bucket
                bucket = cluster.bucket(parent_id)
                scopes = bucket.collections().get_all_scopes()

                result = []
                for scope in scopes:
                    result.append({
                        "id": f"{parent_id}.{scope.name}",
                        "name": scope.name,
                        "type": "scope"
                    })

                return result
            elif parent_id.count('.') == 1:
                # List collections in a scope
                bucket_name, scope_name = parent_id.split('.')
                bucket = cluster.bucket(bucket_name)
                scopes = bucket.collections().get_all_scopes()

                result = []
                for scope in scopes:
                    if scope.name == scope_name:
                        for collection in scope.collections:
                            result.append({
                                "id": f"{parent_id}.{collection.name}",
                                "name": collection.name,
                                "type": "collection"
                            })

                return result
            else:
                # List documents in a collection (limited to first 100)
                bucket_name, scope_name, collection_name = parent_id.split('.')

                query = f"SELECT META().id FROM `{bucket_name}`.`{scope_name}`.`{collection_name}` LIMIT 100"
                query_result = cluster.query(query)

                result = []
                for row in query_result:
                    doc_id = row['id']
                    result.append({
                        "id": f"{parent_id}:{doc_id}",
                        "name": doc_id,
                        "type": "document"
                    })

                return result
        except Exception as e:
            logger.error(f"Couchbase list sources failed: {str(e)}")
            return []


class ElasticsearchConnector(BaseConnector):
    """Connector for Elasticsearch."""

    def __init__(self):
        """Initialize the Elasticsearch connector."""
        super().__init__()

    def download_data(self, source_id: str, credentials: Dict[str, Any]) -> Optional[str]:
        """
        Download data from Elasticsearch.

        Args:
            source_id: The ID of the index and document to download in format "index:document_id" or "index:query".
            credentials: The credentials to use for authentication.
                Must contain 'hosts' key and optionally 'username' and 'password' keys.

        Returns:
            The path to the downloaded file, or None if the download failed.
        """
        try:
            elasticsearch = import_optional("elasticsearch")
            if elasticsearch is None:
                logger.error("elasticsearch module not available")
                return None

            if 'hosts' not in credentials:
                logger.error("Elasticsearch hosts is required")
                return None

            hosts = credentials['hosts']
            username = credentials.get('username')
            password = credentials.get('password')

            # Parse the source_id
            parts = source_id.split(':', 1)
            if len(parts) != 2:
                logger.error(f"Invalid Elasticsearch source ID format: {source_id}")
                return None

            index_name, document_id_or_query = parts

            # Create a temporary file
            fd, temp_path = tempfile.mkstemp(suffix='_elasticsearch.json')
            os.close(fd)

            # Connect to Elasticsearch
            es_args = {"hosts": hosts}
            if username and password:
                es_args["basic_auth"] = (username, password)

            es = elasticsearch.Elasticsearch(**es_args)

            # Check if it's a document ID or a query
            if document_id_or_query.startswith("{"):
                # It's a query
                query = json.loads(document_id_or_query)
                result = es.search(index=index_name, body=query)
                documents = result.get('hits', {}).get('hits', [])
            else:
                # It's a document ID
                result = es.get(index=index_name, id=document_id_or_query)
                documents = [result]

            # Write to file
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(documents, f, indent=2)

            return temp_path
        except Exception as e:
            logger.error(f"Elasticsearch download failed: {str(e)}")
            return None

    def list_sources(self, parent_id: Optional[str], credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        List indices or documents in Elasticsearch.

        Args:
            parent_id: The name of the index to list documents from.
            credentials: The credentials to use for authentication.
                Must contain 'hosts' key and optionally 'username' and 'password' keys.

        Returns:
            A list of index or document metadata.
        """
        try:
            elasticsearch = import_optional("elasticsearch")
            if elasticsearch is None:
                logger.error("elasticsearch module not available")
                return []

            if 'hosts' not in credentials:
                logger.error("Elasticsearch hosts is required")
                return []

            hosts = credentials['hosts']
            username = credentials.get('username')
            password = credentials.get('password')

            # Connect to Elasticsearch
            es_args = {"hosts": hosts}
            if username and password:
                es_args["basic_auth"] = (username, password)

            es = elasticsearch.Elasticsearch(**es_args)

            if not parent_id:
                # List indices
                indices = es.indices.get_alias(index="*")

                result = []
                for index_name in indices:
                    result.append({
                        "id": index_name,
                        "name": index_name,
                        "type": "index"
                    })

                return result
            else:
                # List documents in the index (limited to first 100)
                query = {"query": {"match_all": {}}, "size": 100}
                search_result = es.search(index=parent_id, body=query)

                result = []
                for hit in search_result.get('hits', {}).get('hits', []):
                    doc_id = hit.get('_id')
                    result.append({
                        "id": f"{parent_id}:{doc_id}",
                        "name": doc_id,
                        "type": "document",
                        "score": hit.get('_score')
                    })

                return result
        except Exception as e:
            logger.error(f"Elasticsearch list sources failed: {str(e)}")
            return []


# Factory function to get the appropriate connector
def get_connector(provider: str) -> Optional[BaseConnector]:
    """
    Get a data source connector for the specified provider.

    Args:
        provider: The data source provider (azure, box, couchbase, elasticsearch, etc.).

    Returns:
        The appropriate connector, or None if the provider is not supported.
    """
    provider = provider.lower()

    if provider == "azure":
        return AzureConnector()
    elif provider == "couchbase":
        return CouchbaseConnector()
    elif provider == "elasticsearch":
        return ElasticsearchConnector()
    elif provider == "box":
        return BoxConnector()
    else:
        logger.error(f"Unsupported data source provider: {provider}")
        return None


class BoxConnector(BaseConnector):
    """Connector for Box."""

    def __init__(self):
        """Initialize the Box connector."""
        super().__init__()

    def download_data(self, source_id: str, credentials: Dict[str, Any]) -> Optional[str]:
        """
        Download data from Box.

        Args:
            source_id: The ID of the file to download.
            credentials: The credentials to use for authentication.
                Must contain 'client_id', 'client_secret', and 'access_token' keys.

        Returns:
            The path to the downloaded file, or None if the download failed.
        """
        try:
            boxsdk = import_optional("boxsdk")
            if boxsdk is None:
                logger.error("boxsdk module not available")
                return None

            if not all(k in credentials for k in ['client_id', 'client_secret', 'access_token']):
                logger.error("Box credentials must contain client_id, client_secret, and access_token")
                return None

            client_id = credentials['client_id']
            client_secret = credentials['client_secret']
            access_token = credentials['access_token']

            # Create a temporary file
            fd, temp_path = tempfile.mkstemp()
            os.close(fd)

            # Connect to Box
            oauth = boxsdk.OAuth2(
                client_id=client_id,
                client_secret=client_secret,
                access_token=access_token
            )
            client = boxsdk.Client(oauth)

            # Download the file
            file_obj = client.file(source_id).get()
            with open(temp_path, 'wb') as f:
                file_obj.download_to(f)

            return temp_path
        except Exception as e:
            logger.error(f"Box download failed: {str(e)}")
            return None

    def list_sources(self, parent_id: Optional[str], credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        List files in a Box folder.

        Args:
            parent_id: The ID of the folder to list files from.
            credentials: The credentials to use for authentication.
                Must contain 'client_id', 'client_secret', and 'access_token' keys.

        Returns:
            A list of file metadata.
        """
        try:
            boxsdk = import_optional("boxsdk")
            if boxsdk is None:
                logger.error("boxsdk module not available")
                return []

            if not all(k in credentials for k in ['client_id', 'client_secret', 'access_token']):
                logger.error("Box credentials must contain client_id, client_secret, and access_token")
                return []

            client_id = credentials['client_id']
            client_secret = credentials['client_secret']
            access_token = credentials['access_token']

            # Connect to Box
            oauth = boxsdk.OAuth2(
                client_id=client_id,
                client_secret=client_secret,
                access_token=access_token
            )
            client = boxsdk.Client(oauth)

            # Use root folder if not specified
            folder_id = parent_id or '0'

            # List items
            items = client.folder(folder_id).get_items()

            result = []
            for item in items:
                result.append({
                    "id": item.id,
                    "name": item.name,
                    "type": item.type
                })

            return result
        except Exception as e:
            logger.error(f"Box list files failed: {str(e)}")
            return []
