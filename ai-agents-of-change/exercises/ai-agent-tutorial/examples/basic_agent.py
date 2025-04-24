"""
📚 Basic Agent Example for OpenServ Python SDK 📚

A simple educational example showing core OpenServ SDK concepts.
"""

from src import Agent, Capability, AgentOptions
from pydantic import BaseModel
from typing import Dict, Any, List
import os
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging, a debugger for Python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Define argument models
class GreetArgs(BaseModel):
    name: str

class FarewellArgs(BaseModel):
    name: str

class HelpArgs(BaseModel):  # Define an empty schema for the help command
    pass

# Define async functions for capabilities
async def greet_run(data, messages):
    # data.args contains the validated GreetArgs instance
    args = data["args"]
    return f"Hello, {args.name}! How can I help you today?"

async def farewell_run(data, messages):
    # data.args contains the validated FarewellArgs instance
    args = data["args"]
    return f"Goodbye, {args.name}! Have a great day!"

async def help_run(data, messages):
    return "Available commands: greet, farewell, help"

# Initialize the agent
def create_agent() -> Agent:
    """Create and configure the agent."""
    system_prompt_path = Path(__file__).parent.joinpath('system.md')
    
    if not system_prompt_path.exists():
        raise FileNotFoundError("system.md not found")
    
    # Get API keys from environment
    api_key = os.getenv('OPENSERV_API_KEY')
    
    # Validate API keys
    if not api_key:
        raise ValueError("OPENSERV_API_KEY environment variable is required")
    
    # Create standard agent with iteration limit matching TS SDK
    agent = Agent(
        AgentOptions(
            system_prompt=system_prompt_path.read_text(),
            api_key=api_key,
        )
    )
    
    # Create and add capabilities
    greet_capability = Capability(
        name="greet",
        description="Greet a user by name",
        schema=GreetArgs,
        run=greet_run
    )

    farewell_capability = Capability(
        name="farewell",
        description="Say goodbye to a user",
        schema=FarewellArgs,
        run=farewell_run
    )

    help_capability = Capability(
        name="help",
        description="Show available commands",
        schema=HelpArgs,
        run=help_run
    )

    # Add capabilities to agent
    agent.add_capabilities([
        greet_capability,
        farewell_capability,
        help_capability
    ])

    return agent

if __name__ == '__main__':
    # Configure more selective logging
    for logger_name in ['httpx', 'urllib3']:
        logging.getLogger(logger_name).setLevel(logging.ERROR)
    
    try:
        agent = create_agent()
        agent.start()
    except Exception as e:
        logging.error(f"Failed to start agent: {str(e)}")
        import sys
        sys.exit(1)
