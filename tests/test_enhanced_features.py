"""Tests for enhanced agent features."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from agentic_redpanda.core import (
    SubscriptionManager, SubscriptionType, SubscriptionFilter,
    MessageRouter, RoutingRuleType, TopicValidator, TopicType,
    ErrorHandler, RetryConfig, RetryStrategy, ConversationManager
)
from agentic_redpanda.schemas.message import AgentMessage, MessageType, MessagePriority


class TestSubscriptionManager:
    """Test cases for SubscriptionManager."""
    
    @pytest.fixture
    def subscription_manager(self):
        return SubscriptionManager()
    
    @pytest.fixture
    def sample_message(self):
        return AgentMessage(
            sender_id="test-agent",
            sender_name="Test Agent",
            sender_role="test",
            message_type=MessageType.TEXT,
            content="Hello, world!",
            topic="test-topic"
        )
    
    async def test_subscribe_agent_to_topic(self, subscription_manager):
        """Test subscribing an agent to a topic."""
        subscription = await subscription_manager.subscribe_agent_to_topic(
            agent_id="agent-1",
            topic="test-topic",
            subscription_type=SubscriptionType.ALL_MESSAGES
        )
        
        assert subscription.agent_id == "agent-1"
        assert subscription.topic == "test-topic"
        assert subscription.subscription_type == SubscriptionType.ALL_MESSAGES
    
    async def test_message_routing(self, subscription_manager, sample_message):
        """Test message routing to subscribers."""
        # Subscribe agent
        await subscription_manager.subscribe_agent_to_topic(
            agent_id="agent-1",
            topic="test-topic"
        )
        
        # Route message
        matching_subscriptions = await subscription_manager.route_message(sample_message)
        
        assert len(matching_subscriptions) == 1
        assert matching_subscriptions[0].agent_id == "agent-1"
    
    async def test_content_filtering(self, subscription_manager):
        """Test content-based filtering."""
        # Create filter for specific keywords
        filter_criteria = SubscriptionFilter(
            content_keywords=["urgent", "important"]
        )
        
        # Subscribe with filter
        await subscription_manager.subscribe_agent_to_topic(
            agent_id="agent-1",
            topic="test-topic",
            filter_criteria=filter_criteria
        )
        
        # Test message with keyword
        urgent_message = AgentMessage(
            sender_id="sender-1",
            sender_name="Sender",
            sender_role="user",
            message_type=MessageType.TEXT,
            content="This is an urgent message!",
            topic="test-topic"
        )
        
        matching = await subscription_manager.route_message(urgent_message)
        assert len(matching) == 1
        
        # Test message without keyword
        normal_message = AgentMessage(
            sender_id="sender-1",
            sender_name="Sender",
            sender_role="user",
            message_type=MessageType.TEXT,
            content="This is a normal message",
            topic="test-topic"
        )
        
        matching = await subscription_manager.route_message(normal_message)
        assert len(matching) == 0


class TestMessageRouter:
    """Test cases for MessageRouter."""
    
    @pytest.fixture
    def message_router(self):
        return MessageRouter()
    
    @pytest.fixture
    def sample_message(self):
        return AgentMessage(
            sender_id="test-agent",
            sender_name="Test Agent",
            sender_role="test",
            message_type=MessageType.TEXT,
            content="Hello, world!",
            topic="test-topic"
        )
    
    async def test_add_routing_rule(self, message_router):
        """Test adding routing rules."""
        rule = await message_router.add_routing_rule(
            rule_id="test-rule",
            rule_type=RoutingRuleType.CONTENT_KEYWORD,
            condition=["urgent"],
            target_topics=["urgent-topic"],
            priority=100
        )
        
        assert rule.rule_id == "test-rule"
        assert rule.rule_type == RoutingRuleType.CONTENT_KEYWORD
        assert rule.target_topics == ["urgent-topic"]
    
    async def test_message_routing(self, message_router, sample_message):
        """Test message routing based on rules."""
        # Add routing rule
        await message_router.add_routing_rule(
            rule_id="urgent-rule",
            rule_type=RoutingRuleType.CONTENT_KEYWORD,
            condition=["urgent"],
            target_topics=["urgent-topic"],
            priority=100
        )
        
        # Test urgent message
        urgent_message = AgentMessage(
            sender_id="test-agent",
            sender_name="Test Agent",
            sender_role="test",
            message_type=MessageType.TEXT,
            content="This is urgent!",
            topic="test-topic"
        )
        
        target_topics = await message_router.route_message(urgent_message)
        assert "urgent-topic" in target_topics
        
        # Test normal message
        target_topics = await message_router.route_message(sample_message)
        assert len(target_topics) == 0


class TestTopicValidator:
    """Test cases for TopicValidator."""
    
    @pytest.fixture
    def topic_validator(self):
        return TopicValidator()
    
    async def test_validate_topic_name(self, topic_validator):
        """Test topic name validation."""
        # Valid topic name
        result = await topic_validator.validate_topic_name("test-topic")
        assert result.is_valid
        assert len(result.errors) == 0
        
        # Invalid topic name (too short)
        result = await topic_validator.validate_topic_name("ab")
        assert not result.is_valid
        assert len(result.errors) > 0
        
        # Invalid topic name (invalid characters)
        result = await topic_validator.validate_topic_name("test_topic!")
        assert not result.is_valid
        assert any("invalid characters" in error for error in result.errors)
    
    async def test_topic_permissions(self, topic_validator):
        """Test topic permission management."""
        # Grant permission
        success = await topic_validator.grant_permission(
            topic="test-topic",
            agent_id="agent-1",
            permission_level="read",
            granted_by="admin"
        )
        assert success
        
        # Check permission
        has_permission = await topic_validator.check_permission(
            topic="test-topic",
            agent_id="agent-1",
            required_permission="read"
        )
        assert has_permission
        
        # Revoke permission
        success = await topic_validator.revoke_permission(
            topic="test-topic",
            agent_id="agent-1",
            revoked_by="admin"
        )
        assert success
        
        # Check permission again
        has_permission = await topic_validator.check_permission(
            topic="test-topic",
            agent_id="agent-1",
            required_permission="read"
        )
        assert not has_permission


class TestErrorHandler:
    """Test cases for ErrorHandler."""
    
    @pytest.fixture
    def error_handler(self):
        retry_config = RetryConfig(
            max_retries=3,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF
        )
        return ErrorHandler(retry_config)
    
    def test_error_classification(self, error_handler):
        """Test error classification."""
        # Test network error
        network_error = ConnectionError("Connection failed")
        error_type = error_handler._classify_error(network_error)
        assert error_type == "network_error"
        
        # Test timeout error
        timeout_error = TimeoutError("Operation timed out")
        error_type = error_handler._classify_error(timeout_error)
        assert error_type == "timeout_error"
    
    async def test_retryable_error_check(self, error_handler):
        """Test retryable error checking."""
        # Network error should be retryable
        network_error = ConnectionError("Connection failed")
        is_retryable = await error_handler.is_error_retryable(network_error)
        assert is_retryable
        
        # Validation error should not be retryable
        validation_error = ValueError("Invalid input")
        is_retryable = await error_handler.is_error_retryable(validation_error)
        assert not is_retryable


class TestConversationManager:
    """Test cases for ConversationManager."""
    
    @pytest.fixture
    def conversation_manager(self):
        return ConversationManager()
    
    @pytest.fixture
    def sample_message(self):
        return AgentMessage(
            sender_id="test-agent",
            sender_name="Test Agent",
            sender_role="test",
            message_type=MessageType.TEXT,
            content="Hello, world!",
            topic="test-topic"
        )
    
    async def test_create_thread(self, conversation_manager, sample_message):
        """Test creating a conversation thread."""
        thread = await conversation_manager.create_thread(
            topic="test-topic",
            initial_message=sample_message,
            title="Test Thread"
        )
        
        assert thread.topic == "test-topic"
        assert thread.title == "Test Thread"
        assert sample_message.sender_id in thread.participants
    
    async def test_add_message_to_thread(self, conversation_manager, sample_message):
        """Test adding messages to a thread."""
        # Create thread
        thread = await conversation_manager.create_thread(
            topic="test-topic",
            initial_message=sample_message
        )
        
        # Add another message
        another_message = AgentMessage(
            sender_id="agent-2",
            sender_name="Agent 2",
            sender_role="test",
            message_type=MessageType.TEXT,
            content="Response message",
            topic="test-topic"
        )
        
        thread_id = await conversation_manager.add_message_to_thread(another_message, thread.thread_id)
        assert thread_id == thread.thread_id
        
        # Check thread messages
        messages = await conversation_manager.get_thread_messages(thread.thread_id)
        assert len(messages) == 2
    
    async def test_conversation_context(self, conversation_manager, sample_message):
        """Test conversation context management."""
        # Create thread
        thread = await conversation_manager.create_thread(
            topic="test-topic",
            initial_message=sample_message
        )
        
        # Get context
        context = await conversation_manager.get_conversation_context(thread.thread_id)
        assert context is not None
        assert context.topic == "test-topic"
        assert len(context.recent_messages) == 1
        assert sample_message.sender_id in context.participants
