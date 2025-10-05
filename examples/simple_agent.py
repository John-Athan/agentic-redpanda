"""Simple example of an AI agent using Agentic Redpanda."""

import asyncio
import logging
from typing import Optional

from agentic_redpanda import Agent, MessageBroker, AgentMessage
from agentic_redpanda.providers import OpenAIProvider
from agentic_redpanda.schemas.message import MessageType
from agentic_redpanda.utils import setup_logging, load_config

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)


class SimpleAgent(Agent):
    """A simple example agent."""
    
    async def process_message(self, message: AgentMessage) -> Optional[str]:
        """Process incoming messages with custom logic."""
        logger.info(f"Processing message from {message.sender_name}: {message.content}")
        
        # Custom logic based on message type
        if message.message_type == MessageType.QUERY:
            # Handle queries with specific logic
            if "weather" in message.content.lower():
                return "I don't have access to weather data, but I can help with other questions!"
            elif "time" in message.content.lower():
                from datetime import datetime
                return f"The current time is {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Default: use LLM to generate response
        return await self._generate_response(message.content)


async def main():
    """Main function to run the example."""
    try:
        # Load configuration
        config = load_config("config/example.yaml")
        
        # Get first agent config
        agent_config = config.agents[0]
        
        # Create LLM provider
        llm_provider = OpenAIProvider(agent_config.llm_provider.dict())
        
        # Create message broker
        message_broker = MessageBroker(**config.message_broker.dict())
        
        # Create agent
        agent = SimpleAgent(
            agent_id=agent_config.agent_id,
            agent_name=agent_config.agent_name,
            role=agent_config.role,
            llm_provider=llm_provider,
            message_broker=message_broker,
            topics=agent_config.topics
        )
        
        # Start agent
        await agent.start()
        
        logger.info(f"Agent {agent.agent_name} is running. Press Ctrl+C to stop.")
        
        # Send a test message
        await agent.send_message(
            content="Hello! I'm a simple AI agent. How can I help you?",
            topic="general"
        )
        
        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        raise
    finally:
        # Clean up
        if 'agent' in locals():
            await agent.stop()
        if 'message_broker' in locals():
            await message_broker.stop()


if __name__ == "__main__":
    asyncio.run(main())
