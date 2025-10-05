"""
Agentic Redpanda - A distributed AI agent communication system.

This package provides a framework for AI agents to communicate through
Redpanda topics in a channel-based organization similar to Slack.
"""

__version__ = "0.1.0"
__author__ = "Agentic Redpanda Team"

from .core.agent import Agent
from .core.message_broker import MessageBroker
from .schemas.message import AgentMessage

__all__ = ["Agent", "MessageBroker", "AgentMessage"]
