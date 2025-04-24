"""
API client implementations for OpenServ and Runtime services.
"""

import httpx
from typing import Any, Dict, Optional, List
from .config import APIConfig
from .exceptions import APIError, AuthenticationError
import logging
import json
from datetime import datetime

# Configure logging to show INFO and above
logging.basicConfig(level=logging.INFO)

# Set httpx logger to debug level
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class BaseClient:
    """Base class for API clients."""
    def __init__(self, config: APIConfig):
        self.config = config
        # Create client without base_url, will be set by subclasses
        self.client = httpx.AsyncClient(
            headers={
                'Content-Type': 'application/json',
                'x-openserv-key': config.api_key
            },
            timeout=30.0  # Set a reasonable default timeout
        )
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def get(self, path: str, params: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        """Make a GET request to the API."""
        return await self._request('GET', path, params=params)
        
    async def post(self, path: str, json_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Make a POST request to the API."""
        return await self._request('POST', path, json_data=json_data)
        
    async def put(self, path: str, json_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Make a PUT request to the API."""
        return await self._request('PUT', path, json_data=json_data)
    
    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make an HTTP request and handle common error cases."""
        logger = logging.getLogger(__name__)
        try:
            # Pre-serialize JSON with our custom encoder
            content = None
            headers = {}
            
            # Handle file uploads with multipart/form-data
            if files is not None:
                logger.debug(f"Sending {method} request to {path} with files")
                # For multipart form data, let httpx handle the content
                response = await self.client.request(
                    method,
                    path,
                    params=params,
                    files=files,
                    data=json_data,  # For file uploads, json_data is sent as form fields
                )
            else:
                # Normal JSON request
                if json_data is not None:
                    content = json.dumps(json_data, cls=DateTimeEncoder).encode('utf-8')
                    headers['Content-Type'] = 'application/json'
                    logger.debug(f"Sending {method} request to {path} with data size: {len(content)} bytes")
                else:
                    logger.debug(f"Sending {method} request to {path} without data")

                response = await self.client.request(
                    method,
                    path,
                    content=content,
                    params=params,
                    headers=headers,
                )
            
            logger.info(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {response.headers}")
            
            # Early return for 204 No Content
            if response.status_code == 204:
                logger.info("Received 204 No Content response")
                return {"success": True}
                
            logger.debug(f"Response content size: {len(response.content)} bytes")
            
            # Log the actual content for debugging, but limit length
            if len(response.content) < 1000:
                logger.debug(f"Response content: {response.content}")
            else:
                logger.debug(f"Response content (truncated): {response.content[:1000]}...")
            
            response.raise_for_status()
            
            # Handle different content types
            content_type = response.headers.get('content-type', '')
            logger.debug(f"Response content type: {content_type}")
            
            if 'application/json' in content_type:
                if response.content:
                    json_response = response.json()
                    if isinstance(json_response, dict):
                        logger.debug(f"JSON response keys: {list(json_response.keys())}")
                    return json_response
                return {"success": True}
            elif 'text/html' in content_type or 'text/plain' in content_type:
                return {'content': response.text, 'success': True}
            else:
                # Special handling for empty or unspecified content types
                if path.endswith('/execute') and response.status_code == 200:
                    logger.info("Task execution request successful with status 200")
                    # Return a successful response even if there's no content
                    return {'success': True, 'status': 'Task execution initiated'}
                
                # For chat message endpoints that might return no content-type
                if 'message' in path and response.status_code == 200:
                    logger.info("Chat message request successful with status 200")
                    if not response.content:
                        # Empty response but successful status
                        return {'success': True}
                    else:
                        # Try to parse as JSON if there's content
                        try:
                            return response.json()
                        except json.JSONDecodeError:
                            # Return text content if not JSON
                            return {'content': response.text, 'success': True}
                
                logger.warning(f"Unhandled content type: {content_type}")
                # Try to parse as JSON anyway if there's content
                if response.content:
                    try:
                        json_response = response.json()
                        logger.info("Successfully parsed response as JSON despite missing content-type")
                        return json_response
                    except json.JSONDecodeError:
                        logger.warning("Could not parse response as JSON")
                        return {'content': response.text, 'success': True}
                return {'success': True}
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key")
            
            # Try to get error details from response
            error_details = None
            try:
                if e.response.content:
                    error_details = e.response.json()
            except json.JSONDecodeError:
                # If response is not JSON, use text content
                error_details = {'error': e.response.text} if e.response.text else None
                
            logger.error(f"HTTP error {e.response.status_code}: {error_details}")
            raise APIError(
                str(e),
                status_code=e.response.status_code,
                response=error_details
            )
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise APIError(f"Request failed: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            raise APIError(f"Invalid JSON response: {str(e)}")

class OpenServClient(BaseClient):
    """Client for the OpenServ Platform API."""
    def __init__(self, config: APIConfig):
        super().__init__(config)
        # Make sure the base URL doesn't end with a slash
        self.client.base_url = httpx.URL(config.platform_url.rstrip('/'))
        logger.info(f"Platform client initialized with base URL: {config.platform_url}")
    
    async def get_files(self, workspace_id: int) -> Dict[str, Any]:
        """Get files from a workspace."""
        return await self._request('GET', f'/workspaces/{workspace_id}/files')
    
    async def upload_file(
        self,
        workspace_id: int,
        path: str,
        file_content: Any,
        task_ids: Optional[List[int]] = None,
        skip_summarizer: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Upload a file to a workspace."""
        # Create files dictionary for multipart upload
        files = {'file': ('file', file_content)}
        
        # Create form data (not JSON)
        data = {'path': path}
        
        # Add optional parameters if they are provided
        if task_ids is not None:
            if isinstance(task_ids, list):
                data['taskIds'] = json.dumps(task_ids)
            else:
                data['taskIds'] = str(task_ids)
                
        if skip_summarizer is not None:
            data['skipSummarizer'] = str(skip_summarizer).lower()
            
        # Use form data instead of JSON for file uploads
        return await self._request(
            'POST',
            f'/workspaces/{workspace_id}/files',
            json_data=data,  # This will be sent as form fields with files
            files=files
        )

class RuntimeClient(BaseClient):
    """Client for the OpenServ Runtime API."""
    def __init__(self, config: APIConfig):
        super().__init__(config)
        # Make sure the base URL doesn't end with a slash
        # and append /runtime to match TypeScript SDK
        self.client.base_url = httpx.URL(f"{config.runtime_url.rstrip('/')}/runtime")
        
        # Log base URL for debugging
        logger.info(f"Runtime client initialized with base URL: {self.client.base_url}")
        if config.api_key and len(config.api_key) > 8:
            masked_key = f"{config.api_key[:4]}...{config.api_key[-4:]}"
            logger.info(f"Using API key starting with: {masked_key}")
        else:
            logger.warning("API key is missing or too short")
    
    async def execute_task(
        self,
        workspace_id: int,
        task_id: int,
        tools: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a task on the runtime."""
        logger.info(f"Executing task {task_id} for workspace {workspace_id}")
        logger.info(f"Tools provided: {', '.join([t.get('name', 'unknown') for t in tools])}")
        logger.info(f"Number of messages: {len(messages)}")
        
        # Construct the payload in the format expected by the runtime
        # Match exactly the TypeScript SDK payload format
        payload = {
            'tools': tools,
            'messages': messages,
            'action': action,
            'workspace_id': workspace_id,
            'task_id': task_id
        }
        
        # Log request details at debug level
        logger.debug(f"Execute task payload: {json.dumps(payload, cls=DateTimeEncoder)}")
        
        try:
            # Note: Path is now just /execute since /runtime is part of the base URL
            response = await self.post('/execute', json_data=payload)
            logger.info(f"Task execution successful for task {task_id}")
            return {'success': True, 'data': response}
        except AuthenticationError as auth_err:
            # Handle authentication errors specifically
            logger.error(f"Authentication error: {str(auth_err)}")
            return {'success': False, 'error': str(auth_err)}
        except APIError as api_err:
            # Handle API errors with more detail
            logger.error(f"API error executing task: {str(api_err)}")
            error_detail = {
                'message': str(api_err),
                'status_code': getattr(api_err, 'status_code', None),
                'response': getattr(api_err, 'response', None)
            }
            return {'success': False, 'error': error_detail}
        except Exception as e:
            # Handle other unexpected errors
            logger.exception(f"Unexpected error executing task: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def handle_chat(
        self,
        tools: List[Dict[str, Any]],
        messages: List[Dict[str, str]],
        action: Dict[str, Any],
        single_use: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Handle a chat request."""
        # Format the payload consistently with execute_task
        payload = {
            "tools": tools,
            "messages": messages,
            "action": action
        }
        
        if single_use:
            payload["single_use"] = True
        
        logger.info(f"Sending chat request with {len(messages)} messages and {len(tools)} tools")
        logger.debug(f"Chat request payload: {json.dumps(payload, cls=DateTimeEncoder)}")
        
        try:
            # Note: Path is now just /chat since /runtime is part of the base URL
            response = await self.post('/chat', json_data=payload)
            logger.info("Chat request successful")
            
            # Check if we have a response - this is optional since the runtime might handle sending the response directly
            if response:
                logger.debug(f"Chat response data: {response}")
                return {'success': True, 'data': response}
            else:
                # This is still a success case, just no response data
                return {'success': True}
        except AuthenticationError as auth_err:
            # Handle authentication errors specifically
            logger.error(f"Authentication error in chat request: {str(auth_err)}")
            return {'success': False, 'error': str(auth_err)}
        except APIError as api_err:
            # Handle API errors with more detail
            logger.error(f"API error in chat request: {str(api_err)}")
            error_detail = {
                'message': str(api_err),
                'status_code': getattr(api_err, 'status_code', None),
                'response': getattr(api_err, 'response', None)
            }
            return {'success': False, 'error': error_detail}
        except Exception as e:
            logger.exception(f"Chat request failed: {str(e)}")
            return {'success': False, 'error': str(e)} 