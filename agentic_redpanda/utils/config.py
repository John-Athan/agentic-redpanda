"""Configuration management for Agentic Redpanda."""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class MessageBrokerConfig(BaseModel):
    """Configuration for the message broker."""
    
    bootstrap_servers: List[str] = Field(default=["localhost:9092"], description="Redpanda/Kafka bootstrap servers")
    security_protocol: str = Field(default="PLAINTEXT", description="Security protocol")
    sasl_mechanism: Optional[str] = Field(None, description="SASL mechanism")
    sasl_username: Optional[str] = Field(None, description="SASL username")
    sasl_password: Optional[str] = Field(None, description="SASL password")
    auto_offset_reset: str = Field(default="latest", description="Auto offset reset policy")
    enable_auto_commit: bool = Field(default=True, description="Enable auto commit")


class LLMProviderConfig(BaseModel):
    """Configuration for LLM providers."""
    
    provider_type: str = Field(..., description="Type of LLM provider")
    model: str = Field(..., description="Model name")
    api_key: Optional[str] = Field(None, description="API key")
    base_url: Optional[str] = Field(None, description="Base URL for the provider")
    max_tokens: int = Field(default=1000, description="Maximum tokens")
    temperature: float = Field(default=0.7, description="Temperature")
    top_p: float = Field(default=1.0, description="Top-p parameter")
    frequency_penalty: float = Field(default=0.0, description="Frequency penalty")
    presence_penalty: float = Field(default=0.0, description="Presence penalty")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    additional_config: Dict[str, Any] = Field(default_factory=dict, description="Additional provider-specific config")


class AgentConfig(BaseModel):
    """Configuration for individual agents."""
    
    agent_id: str = Field(..., description="Unique agent identifier")
    agent_name: str = Field(..., description="Human-readable agent name")
    role: str = Field(..., description="Agent role or type")
    llm_provider: LLMProviderConfig = Field(..., description="LLM provider configuration")
    topics: List[str] = Field(default_factory=list, description="Topics to subscribe to")
    additional_config: Dict[str, Any] = Field(default_factory=dict, description="Additional agent-specific config")


class Config(BaseModel):
    """Main configuration class."""
    
    message_broker: MessageBrokerConfig = Field(default_factory=MessageBrokerConfig, description="Message broker configuration")
    agents: List[AgentConfig] = Field(default_factory=list, description="Agent configurations")
    logging: Dict[str, Any] = Field(default_factory=dict, description="Logging configuration")
    monitoring: Dict[str, Any] = Field(default_factory=dict, description="Monitoring configuration")
    
    class Config:
        env_prefix = "AGENTIC_REDPANDA_"


def load_config(config_path: Union[str, Path]) -> Config:
    """Load configuration from a YAML file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Config object
    """
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    return Config(**config_data)


def load_config_from_env() -> Config:
    """Load configuration from environment variables.
    
    Returns:
        Config object
    """
    config_data = {}
    
    # Message broker config
    message_broker_config = {}
    if os.getenv("AGENTIC_REDPANDA_BOOTSTRAP_SERVERS"):
        message_broker_config["bootstrap_servers"] = os.getenv("AGENTIC_REDPANDA_BOOTSTRAP_SERVERS").split(",")
    if os.getenv("AGENTIC_REDPANDA_SECURITY_PROTOCOL"):
        message_broker_config["security_protocol"] = os.getenv("AGENTIC_REDPANDA_SECURITY_PROTOCOL")
    if os.getenv("AGENTIC_REDPANDA_SASL_MECHANISM"):
        message_broker_config["sasl_mechanism"] = os.getenv("AGENTIC_REDPANDA_SASL_MECHANISM")
    if os.getenv("AGENTIC_REDPANDA_SASL_USERNAME"):
        message_broker_config["sasl_username"] = os.getenv("AGENTIC_REDPANDA_SASL_USERNAME")
    if os.getenv("AGENTIC_REDPANDA_SASL_PASSWORD"):
        message_broker_config["sasl_password"] = os.getenv("AGENTIC_REDPANDA_SASL_PASSWORD")
    
    config_data["message_broker"] = message_broker_config
    
    # Agent config (single agent from env)
    if os.getenv("AGENTIC_REDPANDA_AGENT_ID"):
        agent_config = {
            "agent_id": os.getenv("AGENTIC_REDPANDA_AGENT_ID"),
            "agent_name": os.getenv("AGENTIC_REDPANDA_AGENT_NAME", "Agent"),
            "role": os.getenv("AGENTIC_REDPANDA_AGENT_ROLE", "general"),
            "llm_provider": {
                "provider_type": os.getenv("AGENTIC_REDPANDA_LLM_PROVIDER", "openai"),
                "model": os.getenv("AGENTIC_REDPANDA_LLM_MODEL", "gpt-3.5-turbo"),
                "api_key": os.getenv("AGENTIC_REDPANDA_LLM_API_KEY"),
                "max_tokens": int(os.getenv("AGENTIC_REDPANDA_LLM_MAX_TOKENS", "1000")),
                "temperature": float(os.getenv("AGENTIC_REDPANDA_LLM_TEMPERATURE", "0.7")),
            }
        }
        
        if os.getenv("AGENTIC_REDPANDA_TOPICS"):
            agent_config["topics"] = os.getenv("AGENTIC_REDPANDA_TOPICS").split(",")
        
        config_data["agents"] = [agent_config]
    
    return Config(**config_data)


def create_default_config(config_path: Union[str, Path]) -> None:
    """Create a default configuration file.
    
    Args:
        config_path: Path where to create the configuration file
    """
    config_path = Path(config_path)
    
    default_config = {
        "message_broker": {
            "bootstrap_servers": ["localhost:9092"],
            "security_protocol": "PLAINTEXT"
        },
        "agents": [
            {
                "agent_id": "agent-1",
                "agent_name": "Assistant",
                "role": "general",
                "llm_provider": {
                    "provider_type": "openai",
                    "model": "gpt-3.5-turbo",
                    "api_key": "your-api-key-here",
                    "max_tokens": 1000,
                    "temperature": 0.7
                },
                "topics": ["general", "random"]
            }
        ],
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    }
    
    with open(config_path, 'w') as f:
        yaml.dump(default_config, f, default_flow_style=False, indent=2)
    
    print(f"Created default configuration file: {config_path}")
