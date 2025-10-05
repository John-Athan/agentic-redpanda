#!/usr/bin/env python3
"""Simple demo of Agentic Redpanda working with Redpanda."""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agentic_redpanda.core import MessageBroker
from agentic_redpanda.schemas.message import AgentMessage, MessageType, MessagePriority

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def demo():
    """Simple demo of the system working."""
    logger.info("🚀 Starting Agentic Redpanda Demo")
    
    # Create message broker
    message_broker = MessageBroker(
        bootstrap_servers=["localhost:19092"],
        security_protocol="PLAINTEXT"
    )
    
    try:
        # Start message broker
        await message_broker.start()
        logger.info("✅ Connected to Redpanda successfully!")
        
        # Create a demo topic
        topic = "demo-topic"
        await message_broker.create_topic(topic)
        logger.info(f"✅ Created topic: {topic}")
        
        # Create and send a message
        message = AgentMessage(
            sender_id="demo-agent",
            sender_name="Demo Agent",
            sender_role="demo",
            message_type=MessageType.TEXT,
            priority=MessagePriority.HIGH,
            content="Hello from Agentic Redpanda! 🎉",
            topic=topic
        )
        
        await message_broker.publish_message(message)
        logger.info("✅ Message published successfully!")
        
        # List topics
        topics = await message_broker.list_topics()
        logger.info(f"✅ Available topics: {topics}")
        
        logger.info("🎉 Demo completed successfully!")
        logger.info("The Agentic Redpanda system is working with Redpanda!")
        
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        return False
    finally:
        await message_broker.stop()
        logger.info("🔌 Disconnected from Redpanda")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(demo())
    sys.exit(0 if success else 1)
