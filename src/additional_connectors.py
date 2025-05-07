"""
Additional data source connectors for ClaryAI.

This module provides connectors for various data sources beyond the basic cloud storage:
- Web-based services (Notion, Confluence, Jira, etc.)
- Database systems (MongoDB, PostgreSQL, Elasticsearch, etc.)
- Productivity tools (Slack, Discord, etc.)
- Email systems (Outlook, Gmail, etc.)
- Code repositories (GitHub, GitLab, etc.)

This implementation includes connectors for the most commonly used data sources
from both Unstructured.io and LlamaIndex.
"""

import os
import tempfile
import logging
import json
import requests
from typing import Optional, Dict, Any, List, Union
from urllib.parse import urlparse

# Optional imports - these will be imported only when needed
# to avoid requiring all dependencies for all connectors
OPTIONAL_IMPORTS = {
    "pymongo": None,
    "psycopg2": None,
    "elasticsearch": None,
    "slack_sdk": None,
    "github": None,
    "gitlab": None,
    "msal": None,  # For Microsoft services
    "googleapiclient": None
}

# Set up logging
logger = logging.getLogger(__name__)

def import_optional(module_name):
    """Import an optional module."""
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


class NotionConnector(BaseConnector):
    """Connector for Notion."""

    def __init__(self):
        """Initialize the Notion connector."""
        super().__init__()

    def download_data(self, source_id: str, credentials: Dict[str, Any]) -> Optional[str]:
        """
        Download data from Notion.

        Args:
            source_id: The ID of the page or database to download.
            credentials: The credentials to use for authentication.
                Must contain 'token' key with a Notion API token.

        Returns:
            The path to the downloaded file, or None if the download failed.
        """
        try:
            if 'token' not in credentials:
                logger.error("Notion token is required")
                return None

            token = credentials['token']

            # Create a temporary file
            fd, temp_path = tempfile.mkstemp(suffix='_notion.md')
            os.close(fd)

            # Download the page content
            headers = {
                "Authorization": f"Bearer {token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }

            # Get page content
            response = requests.get(
                f"https://api.notion.com/v1/blocks/{source_id}/children",
                headers=headers
            )

            if response.status_code != 200:
                logger.error(f"Failed to get Notion page content: {response.text}")
                return None

            # Extract text content
            blocks = response.json().get("results", [])
            content = self._extract_text_from_blocks(blocks)

            # Write to file
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)

            return temp_path
        except Exception as e:
            logger.error(f"Notion download failed: {str(e)}")
            return None

    def _extract_text_from_blocks(self, blocks: List[Dict[str, Any]]) -> str:
        """Extract text content from Notion blocks."""
        content = []

        for block in blocks:
            block_type = block.get("type")
            if not block_type:
                continue

            block_content = block.get(block_type, {})

            if block_type == "paragraph":
                text = self._extract_rich_text(block_content.get("rich_text", []))
                if text:
                    content.append(text)
            elif block_type == "heading_1":
                text = self._extract_rich_text(block_content.get("rich_text", []))
                if text:
                    content.append(f"# {text}")
            elif block_type == "heading_2":
                text = self._extract_rich_text(block_content.get("rich_text", []))
                if text:
                    content.append(f"## {text}")
            elif block_type == "heading_3":
                text = self._extract_rich_text(block_content.get("rich_text", []))
                if text:
                    content.append(f"### {text}")
            elif block_type == "bulleted_list_item":
                text = self._extract_rich_text(block_content.get("rich_text", []))
                if text:
                    content.append(f"- {text}")
            elif block_type == "numbered_list_item":
                text = self._extract_rich_text(block_content.get("rich_text", []))
                if text:
                    content.append(f"1. {text}")
            elif block_type == "to_do":
                text = self._extract_rich_text(block_content.get("rich_text", []))
                checked = block_content.get("checked", False)
                if text:
                    content.append(f"- {'[x]' if checked else '[ ]'} {text}")
            elif block_type == "code":
                text = self._extract_rich_text(block_content.get("rich_text", []))
                language = block_content.get("language", "")
                if text:
                    content.append(f"```{language}\n{text}\n```")
            elif block_type == "quote":
                text = self._extract_rich_text(block_content.get("rich_text", []))
                if text:
                    content.append(f"> {text}")
            elif block_type == "divider":
                content.append("---")
            elif block_type == "table":
                # Recursively get table rows
                table_id = block.get("id")
                # This would require another API call to get table rows
                content.append("[Table content]")

        return "\n\n".join(content)

    def _extract_rich_text(self, rich_text: List[Dict[str, Any]]) -> str:
        """Extract text from rich text objects."""
        return "".join([rt.get("plain_text", "") for rt in rich_text])

    def list_sources(self, parent_id: Optional[str], credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        List pages in a Notion workspace.

        Args:
            parent_id: Not used for Notion (lists all pages).
            credentials: The credentials to use for authentication.
                Must contain 'token' key with a Notion API token.

        Returns:
            A list of page metadata.
        """
        try:
            if 'token' not in credentials:
                logger.error("Notion token is required")
                return []

            token = credentials['token']

            # List pages
            headers = {
                "Authorization": f"Bearer {token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }

            response = requests.post(
                "https://api.notion.com/v1/search",
                headers=headers,
                json={"filter": {"value": "page", "property": "object"}}
            )

            if response.status_code != 200:
                logger.error(f"Failed to list Notion pages: {response.text}")
                return []

            results = response.json().get("results", [])

            pages = []
            for page in results:
                page_id = page.get("id")
                title = "Untitled"

                # Try to get the title from properties
                properties = page.get("properties", {})
                for prop in properties.values():
                    if prop.get("type") == "title":
                        title_parts = prop.get("title", [])
                        title = "".join([part.get("plain_text", "") for part in title_parts])
                        break

                pages.append({
                    "id": page_id,
                    "title": title,
                    "last_edited": page.get("last_edited_time")
                })

            return pages
        except Exception as e:
            logger.error(f"Notion list pages failed: {str(e)}")
            return []


class MongoDBConnector(BaseConnector):
    """Connector for MongoDB."""

    def __init__(self):
        """Initialize the MongoDB connector."""
        super().__init__()

    def download_data(self, source_id: str, credentials: Dict[str, Any]) -> Optional[str]:
        """
        Download data from MongoDB.

        Args:
            source_id: The ID of the collection to download in format "database.collection".
            credentials: The credentials to use for authentication.
                Must contain 'connection_string' key.

        Returns:
            The path to the downloaded file, or None if the download failed.
        """
        try:
            pymongo = import_optional("pymongo")
            if pymongo is None:
                logger.error("pymongo module not available")
                return None

            if 'connection_string' not in credentials:
                logger.error("MongoDB connection string is required")
                return None

            connection_string = credentials['connection_string']

            # Parse the source_id to get database and collection
            parts = source_id.split('.')
            if len(parts) != 2:
                logger.error(f"Invalid MongoDB source ID format: {source_id}")
                return None

            database_name, collection_name = parts

            # Create a temporary file
            fd, temp_path = tempfile.mkstemp(suffix='_mongodb.json')
            os.close(fd)

            # Connect to MongoDB
            client = pymongo.MongoClient(connection_string)
            db = client[database_name]
            collection = db[collection_name]

            # Get documents
            documents = list(collection.find({}))

            # Convert ObjectId to string for JSON serialization
            for doc in documents:
                if '_id' in doc and isinstance(doc['_id'], pymongo.ObjectId):
                    doc['_id'] = str(doc['_id'])

            # Write to file
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(documents, f, indent=2)

            client.close()
            return temp_path
        except Exception as e:
            logger.error(f"MongoDB download failed: {str(e)}")
            return None

    def list_sources(self, parent_id: Optional[str], credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        List collections in a MongoDB database.

        Args:
            parent_id: The name of the database to list collections from.
            credentials: The credentials to use for authentication.
                Must contain 'connection_string' key.

        Returns:
            A list of collection metadata.
        """
        try:
            pymongo = import_optional("pymongo")
            if pymongo is None:
                logger.error("pymongo module not available")
                return []

            if 'connection_string' not in credentials:
                logger.error("MongoDB connection string is required")
                return []

            connection_string = credentials['connection_string']

            # Connect to MongoDB
            client = pymongo.MongoClient(connection_string)

            if parent_id:
                # List collections in the specified database
                db = client[parent_id]
                collections = db.list_collection_names()

                result = []
                for collection_name in collections:
                    result.append({
                        "id": f"{parent_id}.{collection_name}",
                        "name": collection_name,
                        "type": "collection"
                    })

                client.close()
                return result
            else:
                # List all databases
                databases = client.list_database_names()

                result = []
                for db_name in databases:
                    if db_name not in ['admin', 'local', 'config']:  # Skip system databases
                        result.append({
                            "id": db_name,
                            "name": db_name,
                            "type": "database"
                        })

                client.close()
                return result
        except Exception as e:
            logger.error(f"MongoDB list collections failed: {str(e)}")
            return []


class GitHubConnector(BaseConnector):
    """Connector for GitHub repositories."""

    def __init__(self):
        """Initialize the GitHub connector."""
        super().__init__()

    def download_data(self, source_id: str, credentials: Dict[str, Any]) -> Optional[str]:
        """
        Download data from GitHub.

        Args:
            source_id: The ID of the repository or file to download in format "owner/repo" or "owner/repo/path/to/file".
            credentials: The credentials to use for authentication.
                Must contain 'token' key with a GitHub personal access token.

        Returns:
            The path to the downloaded file, or None if the download failed.
        """
        try:
            github = import_optional("github")
            if github is None:
                logger.error("PyGithub module not available")
                return None

            if 'token' not in credentials:
                logger.error("GitHub token is required")
                return None

            token = credentials['token']

            # Parse the source_id
            parts = source_id.split('/')
            if len(parts) < 2:
                logger.error(f"Invalid GitHub source ID format: {source_id}")
                return None

            owner = parts[0]
            repo_name = parts[1]
            file_path = '/'.join(parts[2:]) if len(parts) > 2 else None

            # Connect to GitHub
            g = github.Github(token)
            repo = g.get_repo(f"{owner}/{repo_name}")

            if file_path:
                # Download a specific file
                file_content = repo.get_contents(file_path)

                # Create a temporary file
                file_name = os.path.basename(file_path)
                fd, temp_path = tempfile.mkstemp(suffix=f"_{file_name}")
                os.close(fd)

                # Write to file
                with open(temp_path, 'wb') as f:
                    if isinstance(file_content, list):
                        # It's a directory, not a file
                        logger.error(f"Path is a directory, not a file: {file_path}")
                        return None

                    f.write(file_content.decoded_content)

                return temp_path
            else:
                # Download the entire repository
                # Create a temporary directory
                temp_dir = tempfile.mkdtemp(suffix=f"_{repo_name}")

                # Create a temporary file for the repository contents
                fd, temp_path = tempfile.mkstemp(suffix=f"_{repo_name}.md")
                os.close(fd)

                # Get repository information
                repo_info = f"# {repo.name}\n\n"
                repo_info += f"**Description:** {repo.description or 'No description'}\n\n"
                repo_info += f"**Owner:** {repo.owner.login}\n"
                repo_info += f"**Stars:** {repo.stargazers_count}\n"
                repo_info += f"**Forks:** {repo.forks_count}\n"
                repo_info += f"**Last Updated:** {repo.updated_at}\n\n"

                # Get README content if available
                try:
                    readme = repo.get_readme()
                    repo_info += "## README\n\n"
                    repo_info += readme.decoded_content.decode('utf-8')
                except github.GithubException:
                    repo_info += "No README found."

                # Write to file
                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.write(repo_info)

                return temp_path
        except Exception as e:
            logger.error(f"GitHub download failed: {str(e)}")
            return None

    def list_sources(self, parent_id: Optional[str], credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        List repositories or files in a GitHub repository.

        Args:
            parent_id: The ID of the repository to list files from in format "owner/repo/path".
            credentials: The credentials to use for authentication.
                Must contain 'token' key with a GitHub personal access token.

        Returns:
            A list of repository or file metadata.
        """
        try:
            github = import_optional("github")
            if github is None:
                logger.error("PyGithub module not available")
                return []

            if 'token' not in credentials:
                logger.error("GitHub token is required")
                return []

            token = credentials['token']

            # Connect to GitHub
            g = github.Github(token)

            if not parent_id:
                # List user's repositories
                user = g.get_user()
                repos = user.get_repos()

                result = []
                for repo in repos:
                    result.append({
                        "id": f"{repo.owner.login}/{repo.name}",
                        "name": repo.name,
                        "description": repo.description,
                        "type": "repository"
                    })

                return result
            else:
                # Parse the parent_id
                parts = parent_id.split('/')
                if len(parts) < 2:
                    logger.error(f"Invalid GitHub parent ID format: {parent_id}")
                    return []

                owner = parts[0]
                repo_name = parts[1]
                path = '/'.join(parts[2:]) if len(parts) > 2 else ""

                # Get repository
                repo = g.get_repo(f"{owner}/{repo_name}")

                # List files in the repository or directory
                contents = repo.get_contents(path)

                result = []
                for content in contents:
                    result.append({
                        "id": f"{owner}/{repo_name}/{content.path}",
                        "name": content.name,
                        "type": "file" if content.type == "file" else "directory"
                    })

                return result
        except Exception as e:
            logger.error(f"GitHub list sources failed: {str(e)}")
            return []


class SlackConnector(BaseConnector):
    """Connector for Slack."""

    def __init__(self):
        """Initialize the Slack connector."""
        super().__init__()

    def download_data(self, source_id: str, credentials: Dict[str, Any]) -> Optional[str]:
        """
        Download data from Slack.

        Args:
            source_id: The ID of the channel to download.
            credentials: The credentials to use for authentication.
                Must contain 'token' key with a Slack API token.

        Returns:
            The path to the downloaded file, or None if the download failed.
        """
        try:
            slack_sdk = import_optional("slack_sdk")
            if slack_sdk is None:
                logger.error("slack_sdk module not available")
                return None

            if 'token' not in credentials:
                logger.error("Slack token is required")
                return None

            token = credentials['token']

            # Create a temporary file
            fd, temp_path = tempfile.mkstemp(suffix='_slack.md')
            os.close(fd)

            # Connect to Slack
            client = slack_sdk.WebClient(token=token)

            # Get channel info
            channel_info = client.conversations_info(channel=source_id)
            channel_name = channel_info['channel']['name']

            # Get messages
            messages = []
            cursor = None

            while True:
                if cursor:
                    response = client.conversations_history(channel=source_id, cursor=cursor)
                else:
                    response = client.conversations_history(channel=source_id)

                messages.extend(response['messages'])

                if not response['has_more']:
                    break

                cursor = response['response_metadata']['next_cursor']

            # Format messages
            content = f"# Slack Channel: {channel_name}\n\n"

            for message in reversed(messages):  # Oldest first
                user_id = message.get('user', 'Unknown')
                text = message.get('text', '')
                ts = message.get('ts', '')

                # Convert timestamp to readable date
                from datetime import datetime
                date = datetime.fromtimestamp(float(ts)).strftime('%Y-%m-%d %H:%M:%S')

                # Get user info
                try:
                    user_info = client.users_info(user=user_id)
                    user_name = user_info['user']['real_name']
                except:
                    user_name = user_id

                content += f"**{user_name}** ({date}):\n{text}\n\n"

            # Write to file
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)

            return temp_path
        except Exception as e:
            logger.error(f"Slack download failed: {str(e)}")
            return None

    def list_sources(self, parent_id: Optional[str], credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        List channels in a Slack workspace.

        Args:
            parent_id: Not used for Slack.
            credentials: The credentials to use for authentication.
                Must contain 'token' key with a Slack API token.

        Returns:
            A list of channel metadata.
        """
        try:
            slack_sdk = import_optional("slack_sdk")
            if slack_sdk is None:
                logger.error("slack_sdk module not available")
                return []

            if 'token' not in credentials:
                logger.error("Slack token is required")
                return []

            token = credentials['token']

            # Connect to Slack
            client = slack_sdk.WebClient(token=token)

            # List channels
            channels = []
            cursor = None

            while True:
                if cursor:
                    response = client.conversations_list(cursor=cursor)
                else:
                    response = client.conversations_list()

                channels.extend(response['channels'])

                if not response.get('response_metadata', {}).get('next_cursor'):
                    break

                cursor = response['response_metadata']['next_cursor']

            result = []
            for channel in channels:
                result.append({
                    "id": channel['id'],
                    "name": channel['name'],
                    "is_private": channel.get('is_private', False),
                    "member_count": channel.get('num_members', 0)
                })

            return result
        except Exception as e:
            logger.error(f"Slack list channels failed: {str(e)}")
            return []


# Factory function to get the appropriate connector
def get_connector(provider: str) -> Optional[BaseConnector]:
    """
    Get a data source connector for the specified provider.

    Args:
        provider: The data source provider (notion, github, mongodb, slack, etc.).

    Returns:
        The appropriate connector, or None if the provider is not supported.
    """
    provider = provider.lower()

    if provider == "notion":
        return NotionConnector()
    elif provider == "github":
        return GitHubConnector()
    elif provider == "mongodb":
        return MongoDBConnector()
    elif provider == "slack":
        return SlackConnector()
    elif provider == "confluence":
        return ConfluenceConnector()
    else:
        logger.error(f"Unsupported data source provider: {provider}")
        return None


class ConfluenceConnector(BaseConnector):
    """Connector for Confluence."""

    def __init__(self):
        """Initialize the Confluence connector."""
        super().__init__()

    def download_data(self, source_id: str, credentials: Dict[str, Any]) -> Optional[str]:
        """
        Download data from Confluence.

        Args:
            source_id: The ID of the page to download.
            credentials: The credentials to use for authentication.
                Must contain 'username', 'api_token', and 'base_url' keys.

        Returns:
            The path to the downloaded file, or None if the download failed.
        """
        try:
            if not all(k in credentials for k in ['username', 'api_token', 'base_url']):
                logger.error("Confluence credentials must contain username, api_token, and base_url")
                return None

            username = credentials['username']
            api_token = credentials['api_token']
            base_url = credentials['base_url']

            # Create a temporary file
            fd, temp_path = tempfile.mkstemp(suffix='_confluence.md')
            os.close(fd)

            # Download the page content
            auth = (username, api_token)

            # Get page content
            response = requests.get(
                f"{base_url}/wiki/rest/api/content/{source_id}?expand=body.storage",
                auth=auth
            )

            if response.status_code != 200:
                logger.error(f"Failed to get Confluence page: {response.text}")
                return None

            # Extract content
            page_data = response.json()
            title = page_data.get("title", "Untitled")
            body = page_data.get("body", {}).get("storage", {}).get("value", "")

            # Convert HTML to Markdown (simplified)
            # In a real implementation, you would use a proper HTML to Markdown converter
            content = f"# {title}\n\n{body}"

            # Write to file
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)

            return temp_path
        except Exception as e:
            logger.error(f"Confluence download failed: {str(e)}")
            return None

    def list_sources(self, parent_id: Optional[str], credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        List pages in a Confluence space.

        Args:
            parent_id: The ID of the space to list pages from.
            credentials: The credentials to use for authentication.
                Must contain 'username', 'api_token', and 'base_url' keys.

        Returns:
            A list of page metadata.
        """
        try:
            if not all(k in credentials for k in ['username', 'api_token', 'base_url']):
                logger.error("Confluence credentials must contain username, api_token, and base_url")
                return []

            username = credentials['username']
            api_token = credentials['api_token']
            base_url = credentials['base_url']

            # List pages
            auth = (username, api_token)

            params = {}
            if parent_id:
                params["spaceKey"] = parent_id

            response = requests.get(
                f"{base_url}/wiki/rest/api/content",
                auth=auth,
                params=params
            )

            if response.status_code != 200:
                logger.error(f"Failed to list Confluence pages: {response.text}")
                return []

            results = response.json().get("results", [])

            pages = []
            for page in results:
                pages.append({
                    "id": page.get("id"),
                    "title": page.get("title"),
                    "space": page.get("space", {}).get("key"),
                    "last_updated": page.get("version", {}).get("when")
                })

            return pages
        except Exception as e:
            logger.error(f"Confluence list pages failed: {str(e)}")
            return []
