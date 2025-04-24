"""
FastAPI server implementation for the OpenServ Agent.
"""

import json
import logging
import os
import hmac
import hashlib
import base64
from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from typing import Optional, Dict, Any, Callable, List
import uvicorn
import asyncio
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time

from .config import ServerConfig
from .exceptions import ToolError

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, 
        app: ASGIApp, 
        requests_per_minute: int = 60,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_timestamps: Dict[str, List[float]] = {}
        
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Clean up old timestamps
        if client_ip in self.request_timestamps:
            self.request_timestamps[client_ip] = [
                ts for ts in self.request_timestamps[client_ip]
                if current_time - ts < 60  # Keep only timestamps from the last minute
            ]
        else:
            self.request_timestamps[client_ip] = []
            
        # Check rate limit
        if len(self.request_timestamps[client_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later."
            )
            
        # Add current timestamp
        self.request_timestamps[client_ip].append(current_time)
        
        # Process the request
        response = await call_next(request)
        return response

async def verify_auth_token(
    request: Request,
    authorization: Optional[str] = Header(None)
) -> None:
    """Verify the authorization token for API requests."""
    auth_token = os.environ.get("OPENSERV_AUTH_TOKEN")
    
    # If no auth token is set, skip validation
    if not auth_token:
        return
    
    # Check if token is provided in headers
    if not authorization:
        logger.warning("Missing authorization header")
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing authorization token"
        )
        
    # Simple token comparison (improve with secure methods in production)
    if authorization != f"Bearer {auth_token}":
        logger.warning("Invalid authorization token")
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid token"
        )

class AgentServer:
    """HTTP server for the Agent."""
    def __init__(self, config: ServerConfig):
        self.config = config
        self.app = FastAPI()
        self._agent = None
        self._server: Optional[uvicorn.Server] = None
        
        # Add security middleware
        self.add_middleware()
        
        # Set up routes
        @self.app.get("/health")
        async def health():
            """Health check endpoint."""
            return {"status": "up", "version": "1.0.0"}
        
        @self.app.post("/", dependencies=[Depends(verify_auth_token)])
        async def root(request: Request):
            """Root route for task execution and chat message responses."""
            if not self._agent:
                raise HTTPException(status_code=500, detail="Agent not initialized")
            
            try:
                body = await request.json()
                logger.info(f"Root route request received: {body.get('type', 'unknown')}")
                
                await self._agent.handle_root_route(body)
                return {"status": "OK", "message": "Request accepted for processing"}
            except Exception as e:
                logger.exception("Error handling root request: %s", str(e))
                raise HTTPException(
                    status_code=500,
                    detail=f"Error processing request: {str(e)}"
                )
            
        @self.app.post("/tools/{tool_name}", dependencies=[Depends(verify_auth_token)])
        async def tool(tool_name: str, request: Request):
            """Tool route for executing specific capabilities."""
            if not self._agent:
                raise HTTPException(status_code=500, detail="Agent not initialized")
                
            try:
                body = await request.json()
                logger.info(f"Tool request for {tool_name}")
                
                # Ensure body contains necessary parameters
                if 'args' not in body:
                    body['args'] = {}
                if 'messages' not in body:
                    body['messages'] = []
                
                result = await self._agent.handle_tool_route(tool_name, body)
                return result
            except Exception as e:
                logger.exception("Error handling tool request for %s: %s", tool_name, str(e))
                raise HTTPException(
                    status_code=500, 
                    detail=f"Error executing tool {tool_name}: {str(e)}"
                )
        
        @self.app.post("/task-complete", dependencies=[Depends(verify_auth_token)])
        async def task_complete(request: Request):
            """Endpoint to explicitly mark a task as complete."""
            if not self._agent:
                raise HTTPException(status_code=500, detail="Agent not initialized")
                
            try:
                body = await request.json()
                logger.info(f"Task completion request received")
                
                workspace_id = body.get('workspace_id')
                task_id = body.get('task_id')
                output = body.get('output', 'Task completed by agent')
                
                if not workspace_id or not task_id:
                    raise HTTPException(
                        status_code=400,
                        detail="Missing required parameters: workspace_id and task_id"
                    )
                
                result = await self._agent.complete_task(workspace_id, task_id, output)
                return {"status": "success", "message": f"Task {task_id} marked as complete", "result": result}
            except Exception as e:
                logger.exception("Error completing task: %s", str(e))
                raise HTTPException(
                    status_code=500,
                    detail=f"Error completing task: {str(e)}"
                )
    
    def add_middleware(self):
        """Add security and performance middleware to the FastAPI app."""
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # More restrictive in production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Add GZip compression
        self.app.add_middleware(GZipMiddleware, minimum_size=1000)
        
        # Add rate limiting
        self.app.add_middleware(RateLimitMiddleware, requests_per_minute=300)

    def set_agent(self, agent: Any) -> None:
        """Set the agent instance for request handling."""
        self._agent = agent

    def start(self) -> None:
        """Start the HTTP server."""
        logger.info("Agent server starting on port %s", self.config.port)
        
        config = uvicorn.Config(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info"
        )
        
        self._server = uvicorn.Server(config)
        logger.info("Server configuration complete, starting server")
        
        try:
            # Run the server
            self._server.run()
        except Exception as e:
            logger.error("Server error: %s", e)
            raise

    async def shutdown(self) -> None:
        """Gracefully shut down the server."""
        if self._server:
            logger.info("Shutting down server...")
            self._server.should_exit = True
            try:
                await self._server.shutdown()
            except Exception as e:
                logger.error("Error during server shutdown: %s", e) 
