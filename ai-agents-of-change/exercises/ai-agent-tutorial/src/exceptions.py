"""
Custom exceptions for the OpenServ Agent library.
"""

class OpenServError(Exception):
    """Base exception class for all OpenServ Agent errors."""
    pass

class ConfigurationError(OpenServError):
    """Raised when there's an error in the configuration."""
    pass

class APIError(OpenServError):
    """Raised when there's an error in API communication."""
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response

class AuthenticationError(APIError):
    """Raised when there's an authentication error."""
    pass

class ToolError(OpenServError):
    """Raised when there's an error in tool execution."""
    def __init__(self, tool_name: str, message: str, original_error: Exception = None):
        super().__init__(f"Error in tool '{tool_name}': {message}")
        self.tool_name = tool_name
        self.original_error = original_error

class ValidationError(OpenServError):
    """Raised when there's a validation error."""
    pass

class RuntimeError(OpenServError):
    """Raised when there's a runtime error."""
    pass 
