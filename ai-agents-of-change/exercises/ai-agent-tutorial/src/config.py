"""
Configuration management for the OpenServ Agent library.
"""

import os
from typing import Optional
from pydantic import BaseModel, Field

class APIConfig(BaseModel):
    """API configuration settings."""
    platform_url: str = Field(
        default_factory=lambda: os.getenv('OPENSERV_API_URL', 'https://api.openserv.ai')
    )
    runtime_url: str = Field(
        default_factory=lambda: os.getenv('OPENSERV_RUNTIME_URL', 'https://agents.openserv.ai')
    )
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv('OPENSERV_API_KEY'))

class ServerConfig(BaseModel):
    """Server configuration settings."""
    port: int = Field(
        default_factory=lambda: int(os.getenv('PORT', '7378'))
    )
    host: str = Field(default='0.0.0.0')
    log_level: str = Field(default='debug')
    reload: bool = Field(default=False)

class OpenAIConfig(BaseModel):
    """OpenAI configuration settings."""
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv('OPENAI_API_KEY'))
    model: str = Field(default='gpt-4o')

class Config(BaseModel):
    """Main configuration class combining all settings."""
    api: APIConfig = Field(default_factory=APIConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    system_prompt: str

    @classmethod
    def from_env(cls, system_prompt: str) -> 'Config':
        """Create a configuration instance from environment variables."""
        return cls(system_prompt=system_prompt)

    def validate_api_key(self) -> None:
        """Validate that required API keys are present."""
        from .exceptions import ConfigurationError
        
        if not self.api.api_key:
            raise ConfigurationError('OpenServ API key is required')
        
        if not self.openai.api_key:
            raise ConfigurationError('OpenAI API key is required') 
