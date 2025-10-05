"""Tests for message schemas."""

import pytest
from datetime import datetime
from uuid import uuid4

from agentic_redpanda.schemas.message import AgentMessage, MessageType, MessagePriority, TopicInfo


class TestAgentMessage:
    """Test cases for AgentMessage."""
    
    def test_create_message(self):
        """Test creating a basic message."""
        message = AgentMessage(
            sender_id="test-agent",
            sender_name="Test Agent",
            sender_role="test",
            message_type=MessageType.TEXT,
            content="Hello, world!",
            topic="test-topic"
        )
        
        assert message.sender_id == "test-agent"
        assert message.sender_name == "Test Agent"
        assert message.sender_role == "test"
        assert message.message_type == MessageType.TEXT
        assert message.content == "Hello, world!"
        assert message.topic == "test-topic"
        assert message.priority == MessagePriority.NORMAL
        assert message.retry_count == 0
        assert message.max_retries == 3
    
    def test_message_serialization(self):
        """Test message serialization and deserialization."""
        message = AgentMessage(
            sender_id="test-agent",
            sender_name="Test Agent",
            sender_role="test",
            message_type=MessageType.TEXT,
            content="Hello, world!",
            topic="test-topic"
        )
        
        # Test to_dict
        message_dict = message.to_dict()
        assert isinstance(message_dict, dict)
        assert message_dict["sender_id"] == "test-agent"
        assert message_dict["content"] == "Hello, world!"
        
        # Test from_dict
        restored_message = AgentMessage.from_dict(message_dict)
        assert restored_message.sender_id == message.sender_id
        assert restored_message.content == message.content
        assert restored_message.message_type == message.message_type
    
    def test_message_validation(self):
        """Test message validation."""
        # Test empty content validation
        with pytest.raises(ValueError, match="Message content cannot be empty"):
            AgentMessage(
                sender_id="test-agent",
                sender_name="Test Agent",
                sender_role="test",
                message_type=MessageType.TEXT,
                content="",
                topic="test-topic"
            )
        
        # Test empty sender_id validation
        with pytest.raises(ValueError, match="Required fields cannot be empty"):
            AgentMessage(
                sender_id="",
                sender_name="Test Agent",
                sender_role="test",
                message_type=MessageType.TEXT,
                content="Hello",
                topic="test-topic"
            )
    
    def test_message_expiry(self):
        """Test message expiry functionality."""
        message = AgentMessage(
            sender_id="test-agent",
            sender_name="Test Agent",
            sender_role="test",
            message_type=MessageType.TEXT,
            content="Hello, world!",
            topic="test-topic",
            ttl=1  # 1 second TTL
        )
        
        # Should not be expired immediately
        assert not message.is_expired()
        
        # Test retry functionality
        assert message.should_retry()
        assert message.retry_count == 0
        
        # Increment retry
        retry_message = message.increment_retry()
        assert retry_message.retry_count == 1
        assert retry_message.should_retry()
        
        # Test max retries
        max_retry_message = AgentMessage(
            sender_id="test-agent",
            sender_name="Test Agent",
            sender_role="test",
            message_type=MessageType.TEXT,
            content="Hello, world!",
            topic="test-topic",
            retry_count=3,
            max_retries=3
        )
        assert not max_retry_message.should_retry()


class TestTopicInfo:
    """Test cases for TopicInfo."""
    
    def test_create_topic(self):
        """Test creating a topic."""
        topic = TopicInfo(
            name="test-topic",
            description="A test topic",
            created_by="test-agent"
        )
        
        assert topic.name == "test-topic"
        assert topic.description == "A test topic"
        assert topic.created_by == "test-agent"
        assert topic.message_count == 0
        assert topic.subscribers == []
        assert not topic.is_private
    
    def test_topic_subscribers(self):
        """Test topic subscriber management."""
        topic = TopicInfo(
            name="test-topic",
            created_by="test-agent"
        )
        
        # Add subscribers
        topic.add_subscriber("agent-1")
        topic.add_subscriber("agent-2")
        assert len(topic.subscribers) == 2
        assert "agent-1" in topic.subscribers
        assert "agent-2" in topic.subscribers
        
        # Add duplicate subscriber (should not add)
        topic.add_subscriber("agent-1")
        assert len(topic.subscribers) == 2
        
        # Remove subscriber
        topic.remove_subscriber("agent-1")
        assert len(topic.subscribers) == 1
        assert "agent-1" not in topic.subscribers
        assert "agent-2" in topic.subscribers
