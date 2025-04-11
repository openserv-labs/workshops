import os
import aiohttp
import ssl
import certifi
import json
from typing import Dict, Any, Optional, Union
from dotenv import load_dotenv

load_dotenv()

api_root_url = os.getenv("API_BASE_URL", "https://api.openserv.ai").rstrip('/')
api_key = os.getenv("OPENSERV_API_KEY")

if not api_root_url:
    raise Exception("API_BASE_URL is not set")

if not api_key:
    raise Exception("OPENSERV_API_KEY is not set")

class APIClient:
    def __init__(self):
        self.base_url = api_root_url
        self.headers = {
            'x-openserv-key': api_key,
            'Content-Type': 'application/json'
        }
        self.session = None
        # Create SSL context with proper certificate verification
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())

    async def ensure_session(self):
        if self.session is None:
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            self.session = aiohttp.ClientSession(
                headers={'x-openserv-key': api_key},  # Set only the API key header by default
                connector=connector
            )
        return self.session

    async def parse_response(self, response):
        try:
            if response.status == 200:
                if response.content_type == 'application/json':
                    return await response.json()
                return await response.text()
            else:
                error_text = await response.text()
                raise Exception(f"Request failed with status {response.status}: {error_text}")
        except Exception as e:
            raise Exception(f"Failed to parse response: {str(e)}")

    async def upload_file(self, workspace_id: str, file_content: Union[str, bytes], 
                         filename: str, path: str = None, task_ids: list = None, 
                         content_type: str = 'text/plain', skip_summarizer: bool = True) -> Optional[Dict]:
        """
        Upload a file to the workspace.
        
        Args:
            workspace_id: The ID of the workspace
            file_content: The content of the file (string or bytes)
            filename: The name of the file
            path: Optional path where the file should be stored
            task_ids: Optional list of task IDs to associate with the file
            content_type: The content type of the file (default: text/plain)
            skip_summarizer: Whether to skip the summarizer (default: True)
        """
        if isinstance(file_content, str):
            file_content = file_content.encode('utf-8')

        form = aiohttp.FormData()
        form.add_field('file', file_content,
                      filename=filename,
                      content_type=content_type)
        
        if path:
            form.add_field('path', path)
        if task_ids:
            form.add_field('taskIds', ','.join(map(str, task_ids)))
        if skip_summarizer:
            form.add_field('skipSummarizer', 'true')

        return await self.post(f"/workspaces/{workspace_id}/file", form=form)

    async def post(self, path: str, data: Dict = None, form: aiohttp.FormData = None) -> Optional[Dict]:
        session = await self.ensure_session()
        try:
            if form:
                # For form data, only include the API key header
                async with session.post(f"{self.base_url}{path}", data=form) as response:
                    return await self.parse_response(response)
            else:
                # For JSON data, include Content-Type header
                headers = {**session.headers, 'Content-Type': 'application/json'}
                async with session.post(f"{self.base_url}{path}", json=data, headers=headers) as response:
                    return await self.parse_response(response)
        except Exception as e:
            raise Exception(f"POST request failed: {str(e)}")

    async def put(self, path: str, data: Dict = None) -> Optional[Dict]:
        session = await self.ensure_session()
        try:
            # For JSON data, include Content-Type header
            headers = {**session.headers, 'Content-Type': 'application/json'}
            async with session.put(f"{self.base_url}{path}", json=data, headers=headers) as response:
                return await self.parse_response(response)
        except Exception as e:
            raise Exception(f"PUT request failed: {str(e)}")

    async def close(self):
        if self.session:
            await self.session.close()

api_client = APIClient() 