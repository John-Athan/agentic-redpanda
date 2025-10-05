"""Advanced subscription management for agents."""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Set, Union
from dataclasses import dataclass
from enum import Enum

from ..schemas.message import AgentMessage, MessageType, MessagePriority

logger = logging.getLogger(__name__)


class SubscriptionType(str, Enum):
    """Types of topic subscriptions."""
    ALL_MESSAGES = "all_messages"
    ROLE_BASED = "role_based"
    CONTENT_FILTERED = "content_filtered"
    PRIORITY_FILTERED = "priority_filtered"
    CUSTOM = "custom"


@dataclass
class SubscriptionFilter:
    """Filter criteria for topic subscriptions."""
    
    # Message type filtering
    message_types: Optional[Set[MessageType]] = None
    
    # Priority filtering
    min_priority: Optional[MessagePriority] = None
    
    # Content filtering
    content_keywords: Optional[List[str]] = None
    content_regex: Optional[str] = None
    
    # Sender filtering
    allowed_senders: Optional[Set[str]] = None
    blocked_senders: Optional[Set[str]] = None
    
    # Role-based filtering
    allowed_roles: Optional[Set[str]] = None
    blocked_roles: Optional[Set[str]] = None
    
    # Metadata filtering
    metadata_filters: Optional[Dict[str, Any]] = None
    
    # Custom filter function
    custom_filter: Optional[Callable[[AgentMessage], bool]] = None


@dataclass
class TopicSubscription:
    """Represents an agent's subscription to a topic."""
    
    topic: str
    agent_id: str
    subscription_type: SubscriptionType
    filter_criteria: Optional[SubscriptionFilter] = None
    handler: Optional[Callable[[AgentMessage], None]] = None
    active: bool = True
    created_at: Optional[str] = None
    message_count: int = 0
    last_message_at: Optional[str] = None


class SubscriptionManager:
    """Manages advanced topic subscriptions for agents."""
    
    def __init__(self):
        """Initialize the subscription manager."""
        self.subscriptions: Dict[str, List[TopicSubscription]] = {}  # topic -> list of subscriptions
        self.agent_subscriptions: Dict[str, List[TopicSubscription]] = {}  # agent_id -> list of subscriptions
        self.message_handlers: Dict[str, Callable[[AgentMessage], None]] = {}
        
    async def subscribe_agent_to_topic(
        self,
        agent_id: str,
        topic: str,
        subscription_type: SubscriptionType = SubscriptionType.ALL_MESSAGES,
        filter_criteria: Optional[SubscriptionFilter] = None,
        handler: Optional[Callable[[AgentMessage], None]] = None
    ) -> TopicSubscription:
        """Subscribe an agent to a topic with advanced filtering.
        
        Args:
            agent_id: ID of the subscribing agent
            topic: Topic name
            subscription_type: Type of subscription
            filter_criteria: Optional filter criteria
            handler: Optional custom message handler
            
        Returns:
            TopicSubscription object
        """
        subscription = TopicSubscription(
            topic=topic,
            agent_id=agent_id,
            subscription_type=subscription_type,
            filter_criteria=filter_criteria,
            handler=handler
        )
        
        # Add to topic subscriptions
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
        self.subscriptions[topic].append(subscription)
        
        # Add to agent subscriptions
        if agent_id not in self.agent_subscriptions:
            self.agent_subscriptions[agent_id] = []
        self.agent_subscriptions[agent_id].append(subscription)
        
        # Store handler
        if handler:
            self.message_handlers[f"{agent_id}:{topic}"] = handler
        
        logger.info(f"Agent {agent_id} subscribed to topic {topic} with {subscription_type} filtering")
        return subscription
    
    async def unsubscribe_agent_from_topic(self, agent_id: str, topic: str) -> bool:
        """Unsubscribe an agent from a topic.
        
        Args:
            agent_id: Agent ID
            topic: Topic name
            
        Returns:
            True if successful, False otherwise
        """
        removed = False
        
        # Remove from topic subscriptions
        if topic in self.subscriptions:
            self.subscriptions[topic] = [
                sub for sub in self.subscriptions[topic] 
                if not (sub.agent_id == agent_id and sub.topic == topic)
            ]
            if not self.subscriptions[topic]:
                del self.subscriptions[topic]
            removed = True
        
        # Remove from agent subscriptions
        if agent_id in self.agent_subscriptions:
            self.agent_subscriptions[agent_id] = [
                sub for sub in self.agent_subscriptions[agent_id] 
                if sub.topic != topic
            ]
            if not self.agent_subscriptions[agent_id]:
                del self.agent_subscriptions[agent_id]
        
        # Remove handler
        handler_key = f"{agent_id}:{topic}"
        if handler_key in self.message_handlers:
            del self.message_handlers[handler_key]
        
        if removed:
            logger.info(f"Agent {agent_id} unsubscribed from topic {topic}")
        
        return removed
    
    async def route_message(self, message: AgentMessage) -> List[TopicSubscription]:
        """Route a message to appropriate subscribers.
        
        Args:
            message: Message to route
            
        Returns:
            List of subscriptions that should receive the message
        """
        if message.topic not in self.subscriptions:
            return []
        
        matching_subscriptions = []
        
        for subscription in self.subscriptions[message.topic]:
            if not subscription.active:
                continue
            
            # Skip if message is from the same agent
            if subscription.agent_id == message.sender_id:
                continue
            
            # Apply filters
            if await self._message_matches_filter(message, subscription.filter_criteria):
                matching_subscriptions.append(subscription)
                subscription.message_count += 1
                subscription.last_message_at = message.timestamp.isoformat()
        
        return matching_subscriptions
    
    async def _message_matches_filter(
        self, 
        message: AgentMessage, 
        filter_criteria: Optional[SubscriptionFilter]
    ) -> bool:
        """Check if a message matches the filter criteria.
        
        Args:
            message: Message to check
            filter_criteria: Filter criteria
            
        Returns:
            True if message matches, False otherwise
        """
        if not filter_criteria:
            return True
        
        # Message type filtering
        if filter_criteria.message_types and message.message_type not in filter_criteria.message_types:
            return False
        
        # Priority filtering
        if filter_criteria.min_priority:
            priority_order = {
                MessagePriority.LOW: 0,
                MessagePriority.NORMAL: 1,
                MessagePriority.HIGH: 2,
                MessagePriority.URGENT: 3
            }
            if priority_order.get(message.priority, 0) < priority_order.get(filter_criteria.min_priority, 0):
                return False
        
        # Content keyword filtering
        if filter_criteria.content_keywords:
            content_lower = message.content.lower()
            if not any(keyword.lower() in content_lower for keyword in filter_criteria.content_keywords):
                return False
        
        # Content regex filtering
        if filter_criteria.content_regex:
            import re
            if not re.search(filter_criteria.content_regex, message.content, re.IGNORECASE):
                return False
        
        # Sender filtering
        if filter_criteria.allowed_senders and message.sender_id not in filter_criteria.allowed_senders:
            return False
        
        if filter_criteria.blocked_senders and message.sender_id in filter_criteria.blocked_senders:
            return False
        
        # Role-based filtering
        if filter_criteria.allowed_roles and message.sender_role not in filter_criteria.allowed_roles:
            return False
        
        if filter_criteria.blocked_roles and message.sender_role in filter_criteria.blocked_roles:
            return False
        
        # Metadata filtering
        if filter_criteria.metadata_filters:
            for key, value in filter_criteria.metadata_filters.items():
                if key not in message.metadata or message.metadata[key] != value:
                    return False
        
        # Custom filter
        if filter_criteria.custom_filter:
            try:
                return filter_criteria.custom_filter(message)
            except Exception as e:
                logger.error(f"Error in custom filter: {e}")
                return False
        
        return True
    
    async def get_agent_subscriptions(self, agent_id: str) -> List[TopicSubscription]:
        """Get all subscriptions for an agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of subscriptions
        """
        return self.agent_subscriptions.get(agent_id, [])
    
    async def get_topic_subscribers(self, topic: str) -> List[TopicSubscription]:
        """Get all subscribers for a topic.
        
        Args:
            topic: Topic name
            
        Returns:
            List of subscriptions
        """
        return self.subscriptions.get(topic, [])
    
    async def update_subscription_filter(
        self,
        agent_id: str,
        topic: str,
        new_filter: SubscriptionFilter
    ) -> bool:
        """Update the filter criteria for a subscription.
        
        Args:
            agent_id: Agent ID
            topic: Topic name
            new_filter: New filter criteria
            
        Returns:
            True if successful, False otherwise
        """
        for subscription in self.agent_subscriptions.get(agent_id, []):
            if subscription.topic == topic:
                subscription.filter_criteria = new_filter
                logger.info(f"Updated filter for agent {agent_id} on topic {topic}")
                return True
        
        return False
    
    async def pause_subscription(self, agent_id: str, topic: str) -> bool:
        """Pause a subscription without removing it.
        
        Args:
            agent_id: Agent ID
            topic: Topic name
            
        Returns:
            True if successful, False otherwise
        """
        for subscription in self.agent_subscriptions.get(agent_id, []):
            if subscription.topic == topic:
                subscription.active = False
                logger.info(f"Paused subscription for agent {agent_id} on topic {topic}")
                return True
        
        return False
    
    async def resume_subscription(self, agent_id: str, topic: str) -> bool:
        """Resume a paused subscription.
        
        Args:
            agent_id: Agent ID
            topic: Topic name
            
        Returns:
            True if successful, False otherwise
        """
        for subscription in self.agent_subscriptions.get(agent_id, []):
            if subscription.topic == topic:
                subscription.active = True
                logger.info(f"Resumed subscription for agent {agent_id} on topic {topic}")
                return True
        
        return False
    
    async def get_subscription_stats(self) -> Dict[str, Any]:
        """Get subscription statistics.
        
        Returns:
            Dictionary with subscription statistics
        """
        total_subscriptions = sum(len(subs) for subs in self.subscriptions.values())
        active_subscriptions = sum(
            len([sub for sub in subs if sub.active]) 
            for subs in self.subscriptions.values()
        )
        
        return {
            "total_subscriptions": total_subscriptions,
            "active_subscriptions": active_subscriptions,
            "paused_subscriptions": total_subscriptions - active_subscriptions,
            "total_topics": len(self.subscriptions),
            "total_agents": len(self.agent_subscriptions),
            "subscription_types": {
                sub_type.value: sum(
                    len([sub for sub in subs if sub.subscription_type == sub_type])
                    for subs in self.subscriptions.values()
                )
                for sub_type in SubscriptionType
            }
        }
