#!/usr/bin/env python3
"""Test script to verify Redpanda connection and basic functionality."""

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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_redpanda_connection():
    """Test basic Redpanda connection and messaging."""
    try:
        # Create message broker
        message_broker = MessageBroker(
            bootstrap_servers=["localhost:9092"],
            security_protocol="PLAINTEXT"
        )
        
        logger.info("Starting message broker...")
        await message_broker.start()
        
        # Test health check
        is_healthy = await message_broker.health_check()
        logger.info(f"Message broker health check: {'✅ Healthy' if is_healthy else '❌ Unhealthy'}")
        
        if not is_healthy:
            logger.error("Message broker is not healthy. Please check Redpanda connection.")
            return False
        
        # Create a test topic
        test_topic = "test-topic"
        logger.info(f"Creating test topic: {test_topic}")
        await message_broker.create_topic(test_topic)
        
        # Create a test message
        test_message = AgentMessage(
            sender_id="test-sender",
            sender_name="Test Sender",
            sender_role="test",
            message_type=MessageType.TEXT,
            priority=MessagePriority.NORMAL,
            content="Hello, Redpanda! This is a test message.",
            topic=test_topic
        )
        
        # Publish the message
        logger.info("Publishing test message...")
        await message_broker.publish_message(test_message)
        logger.info("✅ Message published successfully!")
        
        # List topics
        topics = await message_broker.list_topics()
        logger.info(f"Available topics: {topics}")
        
        # Test message consumption
        received_messages = []
        
        async def message_handler(message: AgentMessage):
            received_messages.append(message)
            logger.info(f"📨 Received message: {message.content}")
        
        logger.info("Subscribing to test topic...")
        await message_broker.subscribe_to_topic(
            topic=test_topic,
            agent_id="test-consumer",
            handler=message_handler
        )
        
        # Wait a bit for message processing
        logger.info("Waiting for message processing...")
        await asyncio.sleep(2)
        
        # Publish another message to test consumption
        test_message2 = AgentMessage(
            sender_id="test-sender-2",
            sender_name="Test Sender 2",
            sender_role="test",
            message_type=MessageType.TEXT,
            priority=MessagePriority.HIGH,
            content="This is a high priority test message!",
            topic=test_topic
        )
        
        await message_broker.publish_message(test_message2)
        logger.info("Published high priority test message")
        
        # Wait for message processing
        await asyncio.sleep(2)
        
        logger.info(f"✅ Test completed! Received {len(received_messages)} messages")
        
        # Clean up
        await message_broker.stop()
        logger.info("Message broker stopped")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False


async def main():
    """Main test function."""
    logger.info("🚀 Starting Redpanda connection test...")
    
    success = await test_redpanda_connection()
    
    if success:
        logger.info("🎉 All tests passed! Redpanda is working correctly.")
        return 0
    else:
        logger.error("💥 Tests failed. Please check the logs above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
