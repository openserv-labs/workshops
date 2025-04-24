from typing import TypeVar, Protocol, Dict, Any, List, Awaitable, Union, Generic, cast
from pydantic import BaseModel
import inspect
import json
import logging
from .types import AgentAction, ChatMessage

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class CapabilityFunction(Protocol[T]):
    """Protocol defining the expected signature of a capability's run function."""
    def __call__(
        self,
        params: Dict[str, Union[T, AgentAction]],
        messages: List[Dict[str, Any]]
    ) -> Union[str, Awaitable[str]]: ...

class Capability(Generic[T]):
    """
    A capability that can be added to an agent.
    
    This is the Python equivalent of the TypeScript SDK's Capability class.
    It represents a function that can be exposed to an LLM as a tool.
    
    Attributes:
        name: The unique name of the capability
        description: A description of what the capability does
        schema: The Pydantic model class defining the capability's parameters
        run: The function that implements the capability's behavior
    """
    def __init__(
        self,
        name: str,
        description: str,
        schema: type[T],
        run: CapabilityFunction[T]
    ) -> None:
        """
        Initialize a new Capability instance.
        
        Args:
            name: The name of the capability
            description: A description of what the capability does
            schema: The Pydantic model class defining the capability's parameters
            run: The function that implements the capability's behavior
            
        Raises:
            TypeError: If schema is not a Pydantic model class
            ValueError: If run is not callable
        """
        if not issubclass(schema, BaseModel):
            raise TypeError("schema must be a Pydantic model class")
        if not callable(run):
            raise ValueError("run must be a callable")
            
        self.name = name
        self.description = description
        self.schema = schema
        
        # Ensure run is an async function
        if inspect.iscoroutinefunction(run):
            self._run = run
        else:
            # Convert sync function to async
            async def async_run(args, messages) -> str:
                return run(args, messages)
            self._run = async_run
            
    async def run(self, params: Dict[str, Any], messages: List[Any]) -> str:
        """
        Execute the capability with the given parameters.
        
        This method handles parsing arguments from OpenAI and passing them to the capability's run function.
        
        Args:
            params: A dictionary with the arguments for the capability
            messages: The conversation history
            
        Returns:
            The result of executing the capability
        """
        try:
            # Extract args and action
            args = params.get('args', {})
            action = params.get('action')
            
            # If args is a string (JSON), parse it
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON arguments: {e}")
                    return f"Error: Invalid JSON arguments: {str(e)}"
            
            # If args is already a Pydantic model instance of the right type, use it directly
            if isinstance(args, self.schema):
                validated_args = args
            else:
                # Otherwise validate args with the schema
                try:
                    validated_args = self.schema(**args)
                except Exception as e:
                    logger.error(f"Validation error for {self.name}: {str(e)}")
                    return f"Error: Invalid arguments: {str(e)}"
            
            # Ensure messages are properly formatted
            formatted_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    formatted_messages.append(msg)
                elif hasattr(msg, 'dict') or hasattr(msg, 'model_dump'):
                    # Handle both Pydantic v1 and v2 models
                    if hasattr(msg, 'model_dump'):
                        formatted_messages.append(msg.model_dump())
                    else:
                        formatted_messages.append(msg.dict())
                else:
                    formatted_messages.append(msg)
            
            # Prepare params with validated args
            run_params = {"args": validated_args, "action": action}
            
            # Execute the capability's run function
            result = await self._run(run_params, formatted_messages)
            
            # Ensure result is a string
            if not isinstance(result, str):
                logger.warning(f"Capability {self.name} returned non-string result, converting to string")
                if hasattr(result, 'model_dump'):
                    # Pydantic v2
                    result = json.dumps(result.model_dump())
                elif hasattr(result, 'dict'):
                    # Pydantic v1
                    result = json.dumps(result.dict())
                else:
                    # Other types
                    result = str(result)
                    
            return result
        except Exception as e:
            logger.exception(f"Error executing capability {self.name}")
            return f"Error executing {self.name}: {str(e)}"
