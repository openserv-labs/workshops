"""
Main Agent implementation for the OpenServ Agent library.
"""

import logging
from typing import Optional, List, Dict, Any, TypeVar, Generic, Callable, Awaitable, cast, Union
import openai
import asyncio
import signal
from pydantic import BaseModel
import json
import inspect
import os

# Configure logging to show INFO and above
logging.basicConfig(level=logging.INFO)

from .config import Config
from .client import OpenServClient, RuntimeClient, DateTimeEncoder
from .server import AgentServer
from .capability import Capability
from .exceptions import ConfigurationError, RuntimeError
from .types import (
    AgentOptions,
    DoTaskAction,
    RespondChatMessageAction,
    ProcessParams,
    ChatMessage,
    AgentAction,
    TaskStatus,
    GetTaskDetailParams,
    GetAgentsParams,
    GetTasksParams,
    CreateTaskParams,
    AddLogToTaskParams,
    RequestHumanAssistanceParams,
    UpdateTaskStatusParams,
    IntegrationCallRequest,
    ProxyConfiguration,
    GetSecretsParams,
    GetSecretValueParams
)

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class Agent:
    """
    Main Agent class that orchestrates the OpenServ Agent functionality.
    
    This class handles:
    - Configuration and initialization
    - Tool/capability management
    - API communication
    - Task and chat message processing
    - Server management
    """
    
    def __init__(self, options: AgentOptions) -> None:
        """Initialize the Agent with the given options."""
        logger.info("Initializing Agent with options: %s", options.model_dump())
        
        # Create configuration
        self.config = Config.from_env(system_prompt=options.system_prompt)
        if options.api_key:
            self.config.api.api_key = options.api_key
        if options.openai_api_key:
            self.config.openai.api_key = options.openai_api_key
        if options.port:
            self.config.server.port = options.port
        if options.model:
            self.config.openai.model = options.model
            logger.info(f"Using custom OpenAI model: {options.model}")
            
        # Validate configuration - fail early
        if not self.config.api.api_key:
            api_key_error = ConfigurationError('OpenServ API key is required')
            if options.on_error:
                options.on_error(api_key_error, {"context": "Missing API key during initialization"})
            raise api_key_error
        
        # Initialize components
        self.tools: List[Capability[BaseModel]] = []
        self._openai: Optional[openai.OpenAI] = None
        self.api_client = OpenServClient(self.config.api)
        self.runtime_client = RuntimeClient(self.config.api)
        
        # Store error handler if provided
        self.on_error = options.on_error
        
        # Set up server with common security and performance features
        self.server = AgentServer(self.config.server)
        self.server.set_agent(self)
        
    @property
    def openai_client(self) -> openai.OpenAI:
        """Get or create the OpenAI client instance."""
        if not self._openai:
            if not self.config.openai.api_key:
                raise ConfigurationError('OpenAI API key is required')
            self._openai = openai.OpenAI(api_key=self.config.openai.api_key)
        return self._openai

    @property
    def openai_tools(self) -> List[Dict[str, Any]]:
        """Convert tools to OpenAI function format."""
        return [{
            'type': 'function',
            'function': {
                'name': tool.name,
                'description': tool.description,
                'parameters': tool.schema.model_json_schema()
            }
        } for tool in self.tools]

    def add_capability(self, capability: Capability[T]) -> 'Agent':
        """Add a single capability to the agent."""
        if any(t.name == capability.name for t in self.tools):
            raise ValueError(f'Tool with name "{capability.name}" already exists')
        self.tools.append(capability)
        return self

    def add_capabilities(self, capabilities: List[Capability[T]]) -> 'Agent':
        """Add multiple capabilities to the agent."""
        for capability in capabilities:
            self.add_capability(capability)
        return self

    async def process(self, params: ProcessParams) -> Dict[str, Any]:
        """Process a conversation with OpenAI."""
        logger.info("Starting process with %d messages", len(params.messages))
        try:
            current_messages = params.messages.copy()
            # Get the tool loop limit from env or default to 10 to match TS SDK
            max_iterations = int(os.environ.get("OPENSERV_TOOL_LOOP_LIMIT", "10"))
            iteration_count = 0
            final_response = None
            tool_outputs = []

            while iteration_count < max_iterations:
                logger.info("Process iteration %d/%d", iteration_count + 1, max_iterations)
                iteration_count += 1
                
                # Debug the tools being sent to OpenAI
                if self.tools:
                    tool_names = [tool.name for tool in self.tools]
                    logger.info(f"Sending {len(self.tools)} tools to OpenAI: {tool_names}")
                else:
                    logger.info("No tools available to send to OpenAI")
                
                # Log the model being used
                logger.info(f"Using OpenAI model: {self.config.openai.model}")
                
                try:
                    # Create the completion with tools if available
                    completion_args = {
                        'model': self.config.openai.model,
                        'messages': current_messages,
                    }
                    
                    if self.tools:
                        completion_args['tools'] = self.openai_tools
                        
                    # Add tool_outputs if there are any
                    if tool_outputs:
                        completion_args['tool_choice'] = 'auto'
                        
                    completion = self.openai_client.chat.completions.create(**completion_args)
                except Exception as e:
                    logger.error(f"OpenAI API error: {str(e)}")
                    if self.on_error:
                        self.on_error(e, {"context": "OpenAI API call failure in process method"})
                    return {
                        "error": str(e),
                        "messages": current_messages,
                        "completed": False
                    }

                if not completion.choices or not completion.choices[0].message:
                    error = RuntimeError('No response from OpenAI')
                    if self.on_error:
                        self.on_error(error, {"context": "Empty response from OpenAI"})
                    raise error

                last_message = completion.choices[0].message
                
                # Create a properly formatted message to add to the conversation history
                assistant_message = {
                    'role': 'assistant',
                    'content': last_message.content or '',
                }
                
                # Add tool_calls if present
                if last_message.tool_calls:
                    assistant_message['tool_calls'] = last_message.tool_calls
                
                # Add the assistant's message to the conversation
                current_messages.append(assistant_message)
                
                # If no tool calls, we have our final response
                if not last_message.tool_calls:
                    logger.info("No tool calls requested, returning completion")
                    final_response = last_message.content
                    break

                logger.info(f"OpenAI requested {len(last_message.tool_calls)} tool calls")
                
                # Process all tool calls in the response
                tool_outputs = []
                for tool_call in last_message.tool_calls:
                    if not tool_call.function or not tool_call.function.name:
                        logger.warning("Tool call missing function name")
                        continue

                    tool_name = tool_call.function.name
                    function_args = tool_call.function.arguments
                    tool_call_id = tool_call.id
                    
                    logger.info(f"Processing tool call: {tool_name}")
                    
                    # Find the corresponding tool
                    tool = next((t for t in self.tools if t.name == tool_name), None)
                    if not tool:
                        error_msg = f"Tool not found: {tool_name}"
                        logger.warning(error_msg)
                        tool_outputs.append({
                            "tool_call_id": tool_call_id,
                            "role": "tool",
                            "content": f"Error: {error_msg}",
                        })
                        continue
                    
                    # Parse tool arguments
                    try:
                        if isinstance(function_args, str):
                            try:
                                args = json.loads(function_args)
                            except json.JSONDecodeError:
                                args = function_args
                        else:
                            args = function_args
                            
                        logger.info(f"Tool arguments: {args}")
                    except Exception as e:
                        error_msg = f"Failed to parse tool arguments: {str(e)}"
                        logger.error(error_msg)
                        tool_outputs.append({
                            "tool_call_id": tool_call_id,
                            "role": "tool",
                            "content": f"Error: {error_msg}",
                        })
                        continue
                    
                    # Execute the tool
                    try:
                        result = await tool.run({"args": args}, current_messages)
                        logger.info(f"Tool result: {result[:100]}...")
                        
                        tool_outputs.append({
                            "tool_call_id": tool_call_id,
                            "role": "tool",
                            "content": result,
                        })
                    except Exception as e:
                        error_msg = f"Error executing tool: {str(e)}"
                        logger.error(error_msg)
                        if self.on_error:
                            self.on_error(e, {"context": f"Tool execution failure: {tool_name}"})
                        tool_outputs.append({
                            "tool_call_id": tool_call_id,
                            "role": "tool",
                            "content": f"Error: {error_msg}",
                        })
                
                # Add tool responses to messages
                for tool_output in tool_outputs:
                    current_messages.append(tool_output)
            
            # Check if we exited the loop due to max iterations
            if iteration_count >= max_iterations and not final_response:
                logger.warning(f"Reached maximum iterations ({max_iterations}) without a final response")
                final_response = "Maximum number of tool calls reached without a conclusion. Please try again with a simpler request."
            
            return {
                "messages": current_messages,
                "content": final_response,
                "completed": True
            }
        except Exception as e:
            logger.exception("Error in process method")
            if self.on_error:
                self.on_error(e, {"context": "Process method failure"})
            return {
                "error": str(e),
                "messages": params.messages,
                "completed": False
            }

    async def handle_root_route(self, body: Dict[str, Any]) -> None:
        """Handle the root route for task execution and chat message responses."""
        logger.info("Handling root route request with body type: %s", body.get('type'))
        try:
            if body.get('type') == 'do-task':
                logger.info("Processing do-task action")
                action = DoTaskAction.model_validate(body)
                
                # To ensure consistent behavior with TypeScript, use create_task 
                # but add better error reporting
                task = asyncio.create_task(self.do_task(action))
                
                # Add a done callback to log any errors
                def on_task_done(t):
                    try:
                        # This will re-raise any exception that occurred in do_task
                        t.result()
                    except Exception as e:
                        logger.error(f"Task {action.task.id} failed: {str(e)}")
                        if self.on_error:
                            try:
                                self.on_error(e)
                            except Exception as callback_error:
                                logger.error(f"Error in error callback: {str(callback_error)}")
                
                task.add_done_callback(on_task_done)
                
            elif body.get('type') == 'respond-chat-message':
                logger.info("Processing respond-chat-message action")
                action = RespondChatMessageAction.model_validate(body)
                
                # Fire and forget - don't await
                chat_task = asyncio.create_task(self.respond_to_chat(action))
                
                # Add a done callback to log any errors
                def on_chat_done(t):
                    try:
                        # This will re-raise any exception that occurred in respond_to_chat
                        t.result()
                    except Exception as e:
                        logger.error(f"Chat response failed: {str(e)}")
                        if self.on_error:
                            try:
                                self.on_error(e)
                            except Exception as callback_error:
                                logger.error(f"Error in error callback: {str(callback_error)}")
                
                chat_task.add_done_callback(on_chat_done)
                
            else:
                raise ValueError(f'Invalid action type: {body.get("type")}')
        except Exception as error:
            logger.error("Root route handler failed: %s", str(error), exc_info=True)
            if self.on_error:
                try:
                    self.on_error(error)
                except Exception as callback_error:
                    logger.error(f"Error in error callback: {str(callback_error)}")
            raise

    async def handle_tool_route(self, tool_name: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Handle execution of a specific tool/capability."""
        try:
            # Find the requested tool by name
            tool = next((t for t in self.tools if t.name == tool_name), None)
            if not tool:
                logger.warning(f'Tool "{tool_name}" not found')
                return {'error': f'Tool "{tool_name}" not found'}

            # Parse and validate the args with the tool's schema
            args_data = body.get('args', {})
            logger.info(f"Executing tool '{tool_name}' with args: {args_data}")
            
            try:
                # Create a pydantic model instance to pass to the tool
                args = tool.schema(**args_data)
            except Exception as validation_error:
                logger.error(f"Validation error for tool '{tool_name}': {str(validation_error)}")
                return {'error': f"Invalid arguments: {str(validation_error)}"}
            
            # Ensure messages are in the correct format (if provided)
            messages = body.get('messages', [])
            # Convert any message IDs to maintain their original types (don't force string conversion)
            formatted_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    formatted_msg = dict(msg)
                    formatted_messages.append(formatted_msg)
                else:
                    # If it's already a model instance, convert to dict 
                    formatted_messages.append(msg.dict() if hasattr(msg, 'dict') else msg)
            
            # Get the action if it exists
            action = body.get('action')
            
            # Create a dict to pass to the tool run method
            params = {"args": args, "action": action}
            
            # Execute the tool
            result = await tool.run(params, formatted_messages)
            logger.info(f"Tool '{tool_name}' execution result: {result}")
            
            # Return the result in the format expected by the runtime
            return {'result': result}
        except Exception as error:
            logger.error(f"Tool route handler failed for '{tool_name}': {str(error)}", exc_info=True)
            return {'error': str(error)}

    def start(self) -> None:
        """
        Start the server and set up signal handlers.
        This method is the main entry point for running an agent.
        
        Returns:
            None
        """
        logger.info("Starting agent")
        
        # Set up signal handlers for graceful shutdown
        def handle_signal(sig: int, frame) -> None:
            logger.info(f"Received signal {sig}, shutting down")
            
            # Create event loop for shutdown if not already in one
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Schedule shutdown in the current loop
                    loop.create_task(self.stop())
                else:
                    # Create a new loop for shutdown
                    asyncio.run(self.stop())
            except Exception as e:
                logger.error(f"Error during shutdown: {str(e)}")
                # Force exit if graceful shutdown fails
                import sys
                sys.exit(1)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        
        try:
            # Start the server - this is a blocking call
            self.server.start()
        except Exception as e:
            logger.error(f"Error starting server: {str(e)}")
            if self.on_error:
                self.on_error(e, {"context": "Server startup failure"})
            raise

    async def stop(self) -> None:
        """Stop the agent and clean up resources."""
        logger.info("Stopping server and closing clients...")
        
        try:
            await self.server.shutdown()
        except Exception as e:
            logger.error("Error during server shutdown: %s", e)
            
        try:
            await self.api_client.close()
            await self.runtime_client.close()
        except Exception as e:
            logger.error("Error during client cleanup: %s", e)

    async def do_task(self, action: DoTaskAction) -> None:
        """Handle a task execution request."""
        logger.info(f"Handling task: {action.task.id} - '{action.task.description}'")
        
        messages = [
            {'role': 'system', 'content': self.config.system_prompt}
        ]

        if action.task.description:
            messages.append({
                'role': 'user',
                'content': action.task.description
            })
            
        logger.info(f"Task messages: {messages}")
        logger.info(f"Available tools: {[tool.name for tool in self.tools]}")

        try:
            # Convert tools to JSON schema format
            tools = [self._convert_tool_to_json_schema(t) for t in self.tools]
            
            # Log request details in a more readable format
            logger.info(f"Executing task {action.task.id} for workspace {action.workspace.id}")
            
            # Send request to runtime
            response = await self.runtime_client.execute_task(
                workspace_id=action.workspace.id,
                task_id=action.task.id,
                tools=tools,
                messages=messages,
                action=action.model_dump()
            )
            logger.info(f"Runtime response: {response}")
            
            # Check if the execution was successful
            if not response.get('success', False):
                error_msg = response.get('error', 'Unknown error')
                logger.error(f"Task execution failed: {error_msg}")
                
                # Try to mark the task as errored
                try:
                    await self.mark_task_as_errored(
                        workspace_id=action.workspace.id, 
                        task_id=action.task.id, 
                        error=str(error_msg)
                    )
                except Exception as mark_error:
                    logger.error(f"Failed to mark task as errored: {str(mark_error)}")
            
        except Exception as error:
            logger.error(f"Task execution failed: {str(error)}", exc_info=True)
            # Try to mark the task as errored if we have an exception
            try:
                await self.mark_task_as_errored(
                    workspace_id=action.workspace.id, 
                    task_id=action.task.id, 
                    error=str(error)
                )
            except Exception as mark_error:
                logger.error(f"Failed to mark task as errored: {str(mark_error)}")

    async def respond_to_chat(self, action: RespondChatMessageAction) -> None:
        """Handle a chat message response request."""
        # Create message list with system prompt
        messages = [
            {'role': 'system', 'content': self.config.system_prompt}
        ]

        # Add all chat messages, preserving original ID types
        if action.messages:
            for msg in action.messages:
                messages.append({
                    'role': 'user' if msg.author == 'user' else 'assistant',
                    'content': msg.message,
                    # Keep ID as original type (int), don't convert to string
                    'id': msg.id,
                    'createdAt': msg.createdAt.isoformat() if hasattr(msg.createdAt, 'isoformat') else msg.createdAt
                })

        try:
            # Process the chat locally if we have tools, to match the TypeScript SDK behavior
            if self.tools:
                logger.info(f"Processing chat locally with {len(self.tools)} tools")
                
                # Use the process method to handle the chat with tools
                process_result = await self.process(ProcessParams(messages=messages))
                
                if process_result.get("completed", False) and process_result.get("content"):
                    # Send the final response back to the user
                    response_message = process_result["content"]
                    logger.info(f"Sending chat response: {response_message[:100]}...")
                    
                    await self.send_chat_message(
                        workspace_id=action.workspace.id,
                        agent_id=action.me.id,
                        message=response_message
                    )
                    return
                elif process_result.get("error"):
                    # Log the error but continue to try the runtime as fallback
                    logger.error(f"Local chat processing failed: {process_result['error']}")
            
            # If local processing failed or we have no tools, use the runtime
            logger.info("Sending chat to runtime with %d messages", len(messages))
            response = await self.runtime_client.handle_chat(
                tools=[self._convert_tool_to_json_schema(t) for t in self.tools],
                messages=messages,
                action=action.model_dump(),
                single_use=True
            )
            
            if not response.get('success', False):
                logger.error(f"Runtime chat processing failed: {response.get('error', 'Unknown error')}")
            
        except Exception as error:
            logger.error("Chat response failed: %s", str(error), exc_info=True)
            # Don't re-raise the error to match TypeScript behavior

    @staticmethod
    def _convert_tool_to_json_schema(tool: Capability[BaseModel]) -> Dict[str, Any]:
        """
        Convert a tool to JSON schema format.
        
        This method converts a Capability object into the format expected by the OpenAI API
        and the OpenServ runtime.
        
        Args:
            tool: The capability to convert
            
        Returns:
            A dictionary with name, description, and JSON schema for the tool
        """
        schema = tool.schema.model_json_schema()
        
        # Ensure required fields are present
        if 'type' not in schema:
            schema['type'] = 'object'
            
        # Log the schema for debugging
        logger.debug(f"JSON schema for tool {tool.name}: {json.dumps(schema)}")
            
        return {
            'name': tool.name,
            'description': tool.description,
            'schema': schema
        }

    # Helper method to safely extract data from API responses
    def _extract_response_data(self, response: Any, default_value: Any = None) -> Any:
        """
        Safely extract data from API responses.
        
        This method handles different response formats:
        - Responses with a 'data' key
        - Direct response objects
        - Empty responses
        
        Args:
            response: The API response
            default_value: Default value to return if response is None
            
        Returns:
            The extracted data or the whole response if no 'data' key exists
        """
        if response is None:
            return default_value
            
        if isinstance(response, dict) and "data" in response:
            return response["data"]
            
        return response

    async def get_files(self, workspace_id: int) -> Dict[str, Any]:
        """Get files in a workspace."""
        response = await self.api_client.get(f"/workspaces/{workspace_id}/files")
        return self._extract_response_data(response, {})

    async def get_secrets(self, params: GetSecretsParams) -> Dict[str, Any]:
        """Get all secrets for an agent in a workspace."""
        response = await self.api_client.get(f"/workspaces/{params.workspace_id}/agent-secrets")
        return self._extract_response_data(response, {})

    async def get_secret_value(self, params: GetSecretValueParams) -> str:
        """Get the value of a secret for an agent in a workspace."""
        response = await self.api_client.get(f"/workspaces/{params.workspace_id}/agent-secrets/{params.secret_id}/value")
        return self._extract_response_data(response, "")

    async def upload_file(self, workspace_id: int, path: str, file: Union[str, bytes], task_ids: Optional[List[int]] = None, skip_summarizer: bool = False) -> Dict[str, Any]:
        """Upload a file to a workspace."""
        # Delegate to the OpenServClient which has the proper implementation
        response = await self.api_client.upload_file(
            workspace_id=workspace_id,
            path=path,
            file_content=file,
            task_ids=task_ids,
            skip_summarizer=skip_summarizer
        )
        return self._extract_response_data(response, {})

    async def get_tasks(self, workspace_id: int) -> Dict[str, Any]:
        """Get tasks in a workspace."""
        response = await self.api_client.get(f"/workspaces/{workspace_id}/tasks")
        return self._extract_response_data(response, [])

    async def mark_task_as_errored(self, workspace_id: int, task_id: int, error: str) -> Dict[str, Any]:
        """Mark a task as errored."""
        response = await self.api_client.post(f"/workspaces/{workspace_id}/tasks/{task_id}/error", {
            "error": error
        })
        return self._extract_response_data(response, {"success": True})

    async def complete_task(self, workspace_id: int, task_id: int, output: str) -> Dict[str, Any]:
        """Complete a task."""
        logger.info(f"Marking task {task_id} as complete with output length: {len(output)}")
        response = await self.api_client.put(f"/workspaces/{workspace_id}/tasks/{task_id}/complete", {
            "output": output
        })
        logger.info(f"Task completion response: {response}")
        return self._extract_response_data(response, {"success": True})

    async def send_chat_message(self, workspace_id: int, agent_id: int, message: str) -> Dict[str, Any]:
        """Send a chat message."""
        try:
            response = await self.api_client.post(f"/workspaces/{workspace_id}/agent-chat/{agent_id}/message", {
                "message": message
            })
            return self._extract_response_data(response, {"success": True})
        except Exception as e:
            logger.error(f"Error sending chat message: {str(e)}")
            return {"error": str(e), "success": False}

    async def request_human_assistance(self, workspace_id: int, task_id: int, type: str, question: str) -> Dict[str, Any]:
        """Request human assistance."""
        response = await self.api_client.post(f"/workspaces/{workspace_id}/tasks/{task_id}/human-assistance", {
            "type": type,
            "question": question
        })
        return self._extract_response_data(response, {"success": True})

    async def get_task_detail(self, params: GetTaskDetailParams) -> Dict[str, Any]:
        """Gets detailed information about a specific task."""
        response = await self.api_client.get(f"/workspaces/{params.workspace_id}/tasks/{params.task_id}/detail")
        return self._extract_response_data(response, {})

    async def get_agents(self, params: GetAgentsParams) -> Dict[str, Any]:
        """Gets a list of agents in a workspace."""
        response = await self.api_client.get(f"/workspaces/{params.workspace_id}/agents")
        return self._extract_response_data(response, [])

    async def get_tasks_with_params(self, params: GetTasksParams) -> Dict[str, Any]:
        """Gets a list of tasks in a workspace."""
        response = await self.api_client.get(f"/workspaces/{params.workspace_id}/tasks")
        return self._extract_response_data(response, [])

    async def create_task(self, params: CreateTaskParams) -> Dict[str, Any]:
        """Creates a new task in a workspace."""
        response = await self.api_client.post(f"/workspaces/{params.workspace_id}/tasks", {
            "assignee": params.assignee,
            "description": params.description,
            "body": params.body,
            "input": params.input,
            "expectedOutput": params.expected_output,
            "dependencies": params.dependencies
        })
        return self._extract_response_data(response, {})

    async def add_log_to_task(self, params: AddLogToTaskParams) -> Dict[str, Any]:
        """Adds a log entry to a task."""
        response = await self.api_client.post(
            f"/workspaces/{params.workspace_id}/tasks/{params.task_id}/log",
            {
                "severity": params.severity,
                "type": params.type,
                "body": params.body
            }
        )
        return self._extract_response_data(response, {"success": True})

    async def request_human_assistance_with_params(self, params: RequestHumanAssistanceParams) -> Dict[str, Any]:
        """Requests human assistance for a task."""
        response = await self.api_client.post(
            f"/workspaces/{params.workspace_id}/tasks/{params.task_id}/human-assistance",
            {
                "type": params.type,
                "question": params.question,
                "agentDump": params.agent_dump
            }
        )
        return self._extract_response_data(response, {"success": True})

    async def update_task_status(self, params: UpdateTaskStatusParams) -> Dict[str, Any]:
        """Updates the status of a task."""
        response = await self.api_client.put(
            f"/workspaces/{params.workspace_id}/tasks/{params.task_id}/status",
            {
                "status": params.status
            }
        )
        return self._extract_response_data(response, {"success": True})

    async def call_integration(self, integration: IntegrationCallRequest) -> Dict[str, Any]:
        """
        Calls an integration endpoint through the OpenServ platform.
        This method allows agents to interact with external services and APIs that are integrated with OpenServ.
        """
        # The API documentation doesn't show an /integration endpoint, let's try with proper pluralization
        response = await self.api_client.post(
            f"/workspaces/{integration.workspace_id}/integrations/{integration.integration_id}/proxy",
            integration.details.model_dump()
        )
        return self._extract_response_data(response, {})

    async def send_message(self, message: str) -> Dict[str, Any]:
        """
        Convenience method to send a message in the current chat context.
        This is used in respond_to_chat implementations to reply to users.
        
        Args:
            message: The message content to send
            
        Returns:
            The response data from the API
        """
        # Check if we're currently processing a chat message
        # This is determined by looking at the call stack - respond_to_chat should be in the call stack
        call_stack = inspect.stack()
        called_from_respond_to_chat = any('respond_to_chat' in frame.function for frame in call_stack)
        
        if not called_from_respond_to_chat:
            logger.warning("send_message called outside of respond_to_chat context")
            return {"error": "send_message should be called from within respond_to_chat", "success": False}
            
        # Find the current action in the call stack
        action = None
        for frame in call_stack:
            if frame.function == 'respond_to_chat':
                # Look for the 'action' parameter in local variables
                if 'action' in frame.frame.f_locals:
                    action = frame.frame.f_locals['action']
                    break
                    
        if not action or not isinstance(action, RespondChatMessageAction):
            logger.error("Failed to find valid action in respond_to_chat context")
            return {"error": "No valid action found", "success": False}
            
        # Now we have the action, we can send the message
        if not action.me or not action.workspace:
            logger.error("Missing required action fields (me or workspace)")
            return {"error": "Missing required action fields", "success": False}
            
        try:
            response = await self.send_chat_message(
                workspace_id=action.workspace.id,
                agent_id=action.me.id,
                message=message
            )
            return response
        except Exception as e:
            logger.error(f"Error in send_message: {str(e)}")
            return {"error": str(e), "success": False}

    async def _execute_capability(self, name, params):
        """Execute a capability if it exists."""
        try:
            if name not in self.tools:
                return {"success": False, "error": f"Capability {name} not found"}
            
            capability = next((t for t in self.tools if t.name == name), None)
            
            # Validate params against schema if provided
            if capability.schema:
                try:
                    # Handle both Pydantic v1 and v2
                    if hasattr(capability.schema, 'model_validate'):
                        # Pydantic v2
                        validated_args = capability.schema.model_validate(params.get("args", {}))
                    else:
                        # Pydantic v1
                        validated_args = capability.schema(**params.get("args", {}))
                    
                    # Update params with validated args
                    params["args"] = validated_args
                except Exception as e:
                    return {"success": False, "error": f"Invalid arguments: {str(e)}"}
            
            try:
                # Execute capability
                result = await capability.run(params, params.get("messages", []))
                return {"success": True, "result": result}
            except TypeError as e:
                # Handle case where OpenAI Python client returns a non-awaitable
                if "can't be used in 'await' expression" in str(e):
                    self.logger.warning(f"Capability {name} returned non-awaitable result, running synchronously")
                    # Try to run without await since it might be a non-awaitable call
                    result = capability.run(params, params.get("messages", []))
                    return {"success": True, "result": result}
                else:
                    raise
            
        except Exception as e:
            self.logger.error(f"Error executing capability {name}: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            if self.on_error:
                self.on_error(e, {"capability": name, "params": params})
            return {"success": False, "error": str(e)}
