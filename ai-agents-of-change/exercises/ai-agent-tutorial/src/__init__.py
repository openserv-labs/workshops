"""
OpenServ Agent library.
"""

import logging
import os

from .types import (
    AgentOptions,
    ProcessParams,
    AgentAction,
    DoTaskAction,
    RespondChatMessageAction,
    ChatMessage,
    TaskStatus,
    IntegrationCallRequest,
    ProxyConfiguration
)
from .agent import Agent
from .capability import Capability
from .exceptions import (
    OpenServError,
    ConfigurationError,
    APIError,
    AuthenticationError,
    ToolError,
    ValidationError,
    RuntimeError
)

# Configure logging - use environment variable or default to INFO
log_level = os.environ.get("OPENSERV_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info(f"OpenServ Agent SDK initialized with log level: {log_level}")

__all__ = [
    'Agent',
    'AgentOptions',
    'Capability',
    'ProcessParams',
    'AgentAction',
    'DoTaskAction',
    'RespondChatMessageAction',
    'ChatMessage',
    'TaskStatus',
    'IntegrationCallRequest',
    'ProxyConfiguration',
    'OpenServError',
    'ConfigurationError',
    'APIError',
    'AuthenticationError',
    'ToolError',
    'ValidationError',
    'RuntimeError'
]

__version__ = '0.1.0' 
