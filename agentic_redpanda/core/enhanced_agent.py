"""Enhanced agent with advanced communication features."""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set, Callable
from datetime import datetime

from ..providers.base import LLMProvider
from ..schemas.message import AgentMessage, MessageType, MessagePriority
from .message_broker import MessageBroker
from .subscription_manager import SubscriptionManager, SubscriptionType, SubscriptionFilter
from .message_router import MessageRouter, RoutingRuleType
from .topic_validator import TopicValidator, TopicType, PermissionLevel
from .error_handler import ErrorHandler, RetryConfig, RetryStrategy
from .conversation_manager import ConversationManager, ConversationContext

logger = logging.getLogger(__name__)


class EnhancedAgent:
    """Enhanced agent with advanced communication capabilities."""
    
    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        role: str,
        llm_provider: LLMProvider,
        message_broker: MessageBroker,
        topics: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the enhanced agent.
        
        Args:
            agent_id: Unique identifier for the agent
            agent_name: Human-readable name for the agent
            role: Role or type of the agent
            llm_provider: LLM provider instance
            message_broker: Message broker instance
            topics: List of topics to subscribe to
            config: Additional configuration
        """
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.role = role
        self.llm_provider = llm_provider
        self.message_broker = message_broker
        self.config = config or {}
        
        # Initialize managers
        self.subscription_manager = SubscriptionManager()
        self.message_router = MessageRouter()
        self.topic_validator = TopicValidator()
        self.conversation_manager = ConversationManager()
        
        # Initialize error handler
        retry_config = RetryConfig(
            max_retries=self.config.get("max_retries", 3),
            strategy=RetryStrategy(self.config.get("retry_strategy", "exponential_backoff"))
        )
        self.error_handler = ErrorHandler(retry_config)
        
        # Topic management
        self.subscribed_topics: Set[str] = set(topics or [])
        self.running = False
        
        # Message handling
        self.message_handlers: Dict[MessageType, Callable[[AgentMessage], None]] = {
            MessageType.TEXT: self._handle_text_message,
            MessageType.TASK: self._handle_task_message,
            MessageType.QUERY: self._handle_query_message,
            MessageType.NOTIFICATION: self._handle_notification_message,
        }
        
        # Agent state
        self.conversation_history: List[Dict[str, str]] = []
        self.last_activity = None
        
        # Setup default routing rules
        self._setup_default_routing_rules()
    
    def _setup_default_routing_rules(self) -> None:
        """Set up default routing rules for the agent."""
        # Route high priority messages to urgent topics
        asyncio.create_task(self.message_router.add_routing_rule(
            rule_id="high_priority_urgent",
            rule_type=RoutingRuleType.PRIORITY,
            condition=MessagePriority.HIGH,
            target_topics=["urgent", "alerts"],
            priority=100,
            description="Route high priority messages to urgent topics"
        ))
        
        # Route task messages to task topics
        asyncio.create_task(self.message_router.add_routing_rule(
            rule_id="task_routing",
            rule_type=RoutingRuleType.MESSAGE_TYPE,
            condition=MessageType.TASK,
            target_topics=["tasks", "work"],
            priority=50,
            description="Route task messages to task topics"
        ))
    
    async def start(self) -> None:
        """Start the enhanced agent."""
        try:
            # Validate LLM provider
            if not await self.llm_provider.health_check():
                raise RuntimeError("LLM provider is not healthy")
            
            # Start message broker if not already started
            if not self.message_broker.running:
                await self.message_broker.start()
            
            # Subscribe to topics with advanced filtering
            for topic in self.subscribed_topics:
                await self._subscribe_to_topic_advanced(topic)
            
            self.running = True
            logger.info(f"Enhanced agent {self.agent_name} ({self.agent_id}) started")
            
        except Exception as e:
            logger.error(f"Failed to start enhanced agent {self.agent_name}: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the enhanced agent."""
        self.running = False
        
        # Unsubscribe from all topics
        for topic in list(self.subscribed_topics):
            await self.subscription_manager.unsubscribe_agent_from_topic(self.agent_id, topic)
        
        self.subscribed_topics.clear()
        logger.info(f"Enhanced agent {self.agent_name} ({self.agent_id}) stopped")
    
    async def send_message(
        self,
        content: str,
        topic: str,
        message_type: MessageType = MessageType.TEXT,
        priority: MessagePriority = MessagePriority.NORMAL,
        reply_to: Optional[str] = None,
        requires_response: bool = False,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """Send a message with enhanced routing and error handling."""
        message = AgentMessage(
            sender_id=self.agent_id,
            sender_name=self.agent_name,
            sender_role=self.role,
            message_type=message_type,
            priority=priority,
            content=content,
            topic=topic,
            reply_to=reply_to,
            requires_response=requires_response,
            correlation_id=correlation_id,
            metadata=metadata or {},
            tags=tags or []
        )
        
        # Apply routing rules
        target_topics = await self.message_router.route_message(message)
        if target_topics:
            # Send to additional topics based on routing rules
            for target_topic in target_topics:
                if target_topic != topic:
                    await self._send_to_topic(message, target_topic)
        
        # Send to original topic
        await self._send_to_topic(message, topic)
        
        # Add to conversation thread
        await self.conversation_manager.add_message_to_thread(message)
        
        logger.debug(f"Sent message to topic {topic}: {content[:50]}...")
        return str(message.id)
    
    async def _send_to_topic(self, message: AgentMessage, topic: str) -> None:
        """Send message to a specific topic with error handling."""
        try:
            await self.message_broker.publish_message(message)
        except Exception as e:
            await self.error_handler.handle_message_error(e, message, "publish")
    
    async def subscribe_to_topic_advanced(
        self,
        topic: str,
        subscription_type: SubscriptionType = SubscriptionType.ALL_MESSAGES,
        filter_criteria: Optional[SubscriptionFilter] = None
    ) -> bool:
        """Subscribe to a topic with advanced filtering.
        
        Args:
            topic: Topic name
            subscription_type: Type of subscription
            filter_criteria: Optional filter criteria
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create custom handler
            handler = lambda msg: asyncio.create_task(self._handle_message_advanced(msg))
            
            # Subscribe with advanced filtering
            await self.subscription_manager.subscribe_agent_to_topic(
                agent_id=self.agent_id,
                topic=topic,
                subscription_type=subscription_type,
                filter_criteria=filter_criteria,
                handler=handler
            )
            
            # Also subscribe via message broker
            await self.message_broker.subscribe_to_topic(
                topic=topic,
                agent_id=self.agent_id,
                handler=handler
            )
            
            self.subscribed_topics.add(topic)
            return True
            
        except Exception as e:
            logger.error(f"Failed to subscribe to topic {topic}: {e}")
            return False
    
    async def _subscribe_to_topic_advanced(self, topic: str) -> None:
        """Internal method to subscribe to a topic with default settings."""
        # Create role-based filter
        filter_criteria = SubscriptionFilter(
            allowed_roles={self.role, "general"},
            min_priority=MessagePriority.LOW
        )
        
        await self.subscribe_to_topic_advanced(
            topic=topic,
            subscription_type=SubscriptionType.ROLE_BASED,
            filter_criteria=filter_criteria
        )
    
    async def create_topic_advanced(
        self,
        topic_name: str,
        topic_type: TopicType = TopicType.GENERAL,
        description: Optional[str] = None,
        is_private: bool = False,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Create a new topic with validation and permissions.
        
        Args:
            topic_name: Topic name
            topic_type: Type of topic
            description: Topic description
            is_private: Whether topic is private
            tags: Topic tags
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate topic creation
            is_valid, errors = await self.topic_validator.validate_topic_creation(
                topic_name=topic_name,
                topic_type=topic_type,
                created_by=self.agent_id,
                is_private=is_private
            )
            
            if not is_valid:
                logger.error(f"Topic validation failed: {errors}")
                return False
            
            # Create topic in message broker
            await self.message_broker.create_topic(topic_name)
            
            # Grant permissions
            if is_private:
                await self.topic_validator.grant_permission(
                    topic=topic_name,
                    agent_id=self.agent_id,
                    permission_level=PermissionLevel.OWNER,
                    granted_by=self.agent_id
                )
            
            logger.info(f"Created topic {topic_name} with type {topic_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create topic {topic_name}: {e}")
            return False
    
    async def _handle_message_advanced(self, message: AgentMessage) -> None:
        """Handle incoming messages with advanced features."""
        try:
            # Skip messages from self
            if message.sender_id == self.agent_id:
                return
            
            # Check permissions
            if not await self.topic_validator.check_permission(
                topic=message.topic,
                agent_id=self.agent_id,
                required_permission=PermissionLevel.READ
            ):
                logger.warning(f"No permission to read topic {message.topic}")
                return
            
            # Get conversation context
            thread_id = await self.conversation_manager.add_message_to_thread(message)
            context = await self.conversation_manager.get_conversation_context(thread_id)
            
            # Update conversation history
            self.conversation_history.append({
                "role": "user",
                "content": f"[{message.sender_name}] {message.content}"
            })
            
            # Route to appropriate handler
            handler = self.message_handlers.get(message.message_type)
            if handler:
                await handler(message, context)
            else:
                logger.warning(f"No handler for message type {message.message_type}")
            
            # Update last activity
            self.last_activity = message.timestamp
            
        except Exception as e:
            await self.error_handler.handle_message_error(e, message, "handle")
    
    async def _handle_text_message(self, message: AgentMessage, context: Optional[ConversationContext] = None) -> None:
        """Handle text messages with conversation context."""
        # Generate response with context
        response = await self._generate_contextual_response(message, context)
        
        await self.send_message(
            content=response,
            topic=message.topic,
            reply_to=message.sender_id
        )
    
    async def _handle_task_message(self, message: AgentMessage, context: Optional[ConversationContext] = None) -> None:
        """Handle task messages."""
        # Acknowledge task
        await self.send_message(
            content=f"Received task: {message.content}",
            topic=message.topic,
            message_type=MessageType.RESPONSE,
            reply_to=message.sender_id
        )
    
    async def _handle_query_message(self, message: AgentMessage, context: Optional[ConversationContext] = None) -> None:
        """Handle query messages with context."""
        response = await self._generate_contextual_response(message, context)
        
        await self.send_message(
            content=response,
            topic=message.topic,
            message_type=MessageType.RESPONSE,
            reply_to=message.sender_id
        )
    
    async def _handle_notification_message(self, message: AgentMessage, context: Optional[ConversationContext] = None) -> None:
        """Handle notification messages."""
        logger.info(f"Notification from {message.sender_name}: {message.content}")
    
    async def _generate_contextual_response(
        self, 
        message: AgentMessage, 
        context: Optional[ConversationContext] = None
    ) -> str:
        """Generate a response using conversation context."""
        try:
            # Build context-aware prompt
            system_message = f"You are {self.agent_name}, a {self.role} agent. Respond helpfully and concisely."
            
            if context and context.recent_messages:
                # Include recent conversation context
                context_text = "\n".join([
                    f"[{msg.sender_name}]: {msg.content}" 
                    for msg in context.recent_messages[-5:]  # Last 5 messages
                ])
                system_message += f"\n\nRecent conversation context:\n{context_text}"
            
            # Generate response
            response = await self.llm_provider.generate(
                prompt=message.content,
                system_message=system_message
            )
            
            # Update conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": response.content
            })
            
            return response.content
            
        except Exception as e:
            logger.error(f"Error generating contextual response: {e}")
            return f"Sorry, I encountered an error: {str(e)}"
    
    async def get_agent_status(self) -> Dict[str, Any]:
        """Get comprehensive agent status."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "role": self.role,
            "running": self.running,
            "subscribed_topics": list(self.subscribed_topics),
            "conversation_length": len(self.conversation_history),
            "last_activity": self.last_activity,
            "llm_provider": self.llm_provider.__class__.__name__,
            "llm_healthy": await self.llm_provider.health_check(),
            "subscription_stats": await self.subscription_manager.get_subscription_stats(),
            "routing_stats": await self.message_router.get_routing_stats(),
            "conversation_stats": await self.conversation_manager.get_thread_stats(),
            "error_stats": await self.error_handler.get_error_stats()
        }
