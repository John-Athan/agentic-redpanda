"""Base agent class for AI agent communication."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set

from ..providers.base import LLMProvider
from ..schemas.message import AgentMessage, MessageType, MessagePriority
from .message_broker import MessageBroker
from .topic_manager import TopicManager

logger = logging.getLogger(__name__)


class Agent(ABC):
    """Base class for AI agents in the communication system."""
    
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
        """Initialize the agent.
        
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
        self.topic_manager = TopicManager()
        self.config = config or {}
        
        # Topic management
        self.subscribed_topics: Set[str] = set(topics or [])
        self.running = False
        
        # Message handling
        self.message_handlers: Dict[MessageType, callable] = {
            MessageType.TEXT: self._handle_text_message,
            MessageType.TASK: self._handle_task_message,
            MessageType.QUERY: self._handle_query_message,
            MessageType.NOTIFICATION: self._handle_notification_message,
        }
        
        # Agent state
        self.conversation_history: List[Dict[str, str]] = []
        self.last_activity = None
        
    async def start(self) -> None:
        """Start the agent."""
        try:
            # Validate LLM provider
            if not await self.llm_provider.health_check():
                raise RuntimeError("LLM provider is not healthy")
            
            # Start message broker if not already started
            if not self.message_broker.running:
                await self.message_broker.start()
            
            # Subscribe to topics
            for topic in self.subscribed_topics:
                await self._subscribe_to_topic(topic)
            
            self.running = True
            logger.info(f"Agent {self.agent_name} ({self.agent_id}) started")
            
        except Exception as e:
            logger.error(f"Failed to start agent {self.agent_name}: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the agent."""
        self.running = False
        
        # Unsubscribe from all topics
        for topic in list(self.subscribed_topics):
            await self.message_broker.unsubscribe_from_topic(topic)
        
        self.subscribed_topics.clear()
        logger.info(f"Agent {self.agent_name} ({self.agent_id}) stopped")
    
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
        """Send a message to a topic.
        
        Args:
            content: Message content
            topic: Target topic
            message_type: Type of message
            priority: Message priority
            reply_to: Topic to reply to
            requires_response: Whether response is required
            correlation_id: Correlation ID for request-response
            metadata: Additional metadata
            tags: Message tags
            
        Returns:
            Message ID
        """
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
        
        await self.message_broker.publish_message(message)
        logger.debug(f"Sent message to topic {topic}: {content[:50]}...")
        
        return str(message.id)
    
    async def subscribe_to_topic(self, topic: str) -> bool:
        """Subscribe to a topic.
        
        Args:
            topic: Topic name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            await self._subscribe_to_topic(topic)
            self.subscribed_topics.add(topic)
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to topic {topic}: {e}")
            return False
    
    async def unsubscribe_from_topic(self, topic: str) -> bool:
        """Unsubscribe from a topic.
        
        Args:
            topic: Topic name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            await self.message_broker.unsubscribe_from_topic(topic)
            self.subscribed_topics.discard(topic)
            return True
        except Exception as e:
            logger.error(f"Failed to unsubscribe from topic {topic}: {e}")
            return False
    
    async def create_topic(
        self,
        topic_name: str,
        description: Optional[str] = None,
        is_private: bool = False,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Create a new topic.
        
        Args:
            topic_name: Topic name
            description: Topic description
            is_private: Whether topic is private
            tags: Topic tags
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create topic in topic manager
            topic_info = await self.topic_manager.create_topic(
                name=topic_name,
                created_by=self.agent_id,
                description=description,
                is_private=is_private,
                tags=tags
            )
            
            # Create topic in message broker
            await self.message_broker.create_topic(topic_name)
            
            logger.info(f"Created topic {topic_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create topic {topic_name}: {e}")
            return False
    
    async def list_topics(self) -> List[str]:
        """List available topics.
        
        Returns:
            List of topic names
        """
        return await self.message_broker.list_topics()
    
    async def _subscribe_to_topic(self, topic: str) -> None:
        """Internal method to subscribe to a topic."""
        await self.message_broker.subscribe_to_topic(
            topic=topic,
            agent_id=self.agent_id,
            handler=self._handle_message
        )
    
    async def _handle_message(self, message: AgentMessage) -> None:
        """Handle incoming messages.
        
        Args:
            message: Incoming message
        """
        try:
            # Skip messages from self
            if message.sender_id == self.agent_id:
                return
            
            # Update conversation history
            self.conversation_history.append({
                "role": "user",
                "content": f"[{message.sender_name}] {message.content}"
            })
            
            # Route to appropriate handler
            handler = self.message_handlers.get(message.message_type)
            if handler:
                await handler(message)
            else:
                logger.warning(f"No handler for message type {message.message_type}")
            
            # Update last activity
            self.last_activity = message.timestamp
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _handle_text_message(self, message: AgentMessage) -> None:
        """Handle text messages.
        
        Args:
            message: Text message
        """
        # Default implementation: echo the message
        response = await self._generate_response(message.content)
        await self.send_message(
            content=response,
            topic=message.topic,
            reply_to=message.sender_id
        )
    
    async def _handle_task_message(self, message: AgentMessage) -> None:
        """Handle task messages.
        
        Args:
            message: Task message
        """
        # Default implementation: acknowledge the task
        await self.send_message(
            content=f"Received task: {message.content}",
            topic=message.topic,
            message_type=MessageType.RESPONSE,
            reply_to=message.sender_id
        )
    
    async def _handle_query_message(self, message: AgentMessage) -> None:
        """Handle query messages.
        
        Args:
            message: Query message
        """
        # Default implementation: generate response
        response = await self._generate_response(message.content)
        await self.send_message(
            content=response,
            topic=message.topic,
            message_type=MessageType.RESPONSE,
            reply_to=message.sender_id
        )
    
    async def _handle_notification_message(self, message: AgentMessage) -> None:
        """Handle notification messages.
        
        Args:
            message: Notification message
        """
        # Default implementation: log the notification
        logger.info(f"Notification from {message.sender_name}: {message.content}")
    
    async def _generate_response(self, prompt: str) -> str:
        """Generate a response using the LLM provider.
        
        Args:
            prompt: Input prompt
            
        Returns:
            Generated response
        """
        try:
            # Add system message based on role
            system_message = f"You are {self.agent_name}, a {self.role} agent. Respond helpfully and concisely."
            
            # Generate response
            response = await self.llm_provider.generate(
                prompt=prompt,
                system_message=system_message
            )
            
            # Update conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": response.content
            })
            
            return response.content
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Sorry, I encountered an error: {str(e)}"
    
    @abstractmethod
    async def process_message(self, message: AgentMessage) -> Optional[str]:
        """Process a message and optionally return a response.
        
        This method should be implemented by subclasses to define
        the agent's specific behavior.
        
        Args:
            message: Incoming message
            
        Returns:
            Optional response content
        """
        pass
    
    async def get_status(self) -> Dict[str, Any]:
        """Get agent status information.
        
        Returns:
            Dictionary with agent status
        """
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "role": self.role,
            "running": self.running,
            "subscribed_topics": list(self.subscribed_topics),
            "conversation_length": len(self.conversation_history),
            "last_activity": self.last_activity,
            "llm_provider": self.llm_provider.__class__.__name__,
            "llm_healthy": await self.llm_provider.health_check()
        }
