"""Topic management for organizing agent communication."""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

from ..schemas.message import TopicInfo

logger = logging.getLogger(__name__)


class TopicManager:
    """Manages topic creation, discovery, and organization."""
    
    def __init__(self):
        """Initialize the topic manager."""
        self.topics: Dict[str, TopicInfo] = {}
        self.agent_subscriptions: Dict[str, Set[str]] = {}  # agent_id -> set of topics
    
    async def create_topic(
        self,
        name: str,
        created_by: str,
        description: Optional[str] = None,
        is_private: bool = False,
        tags: Optional[List[str]] = None
    ) -> TopicInfo:
        """Create a new topic.
        
        Args:
            name: Topic name
            created_by: ID of the agent creating the topic
            description: Optional topic description
            is_private: Whether the topic is private
            tags: Optional topic tags
            
        Returns:
            TopicInfo object for the created topic
        """
        if name in self.topics:
            logger.warning(f"Topic {name} already exists")
            return self.topics[name]
        
        topic_info = TopicInfo(
            name=name,
            description=description,
            created_by=created_by,
            is_private=is_private,
            tags=tags or []
        )
        
        self.topics[name] = topic_info
        logger.info(f"Created topic {name} by agent {created_by}")
        
        return topic_info
    
    async def get_topic(self, name: str) -> Optional[TopicInfo]:
        """Get topic information.
        
        Args:
            name: Topic name
            
        Returns:
            TopicInfo object or None if not found
        """
        return self.topics.get(name)
    
    async def list_topics(
        self,
        agent_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        include_private: bool = False
    ) -> List[TopicInfo]:
        """List topics with optional filtering.
        
        Args:
            agent_id: Filter by agent subscriptions
            tags: Filter by tags
            include_private: Include private topics
            
        Returns:
            List of TopicInfo objects
        """
        topics = list(self.topics.values())
        
        # Filter by agent subscriptions
        if agent_id:
            agent_topics = self.agent_subscriptions.get(agent_id, set())
            topics = [t for t in topics if t.name in agent_topics]
        
        # Filter by tags
        if tags:
            topics = [t for t in topics if any(tag in t.tags for tag in tags)]
        
        # Filter private topics
        if not include_private:
            topics = [t for t in topics if not t.is_private]
        
        return topics
    
    async def subscribe_agent_to_topic(self, agent_id: str, topic_name: str) -> bool:
        """Subscribe an agent to a topic.
        
        Args:
            agent_id: Agent ID
            topic_name: Topic name
            
        Returns:
            True if successful, False otherwise
        """
        if topic_name not in self.topics:
            logger.error(f"Topic {topic_name} does not exist")
            return False
        
        if agent_id not in self.agent_subscriptions:
            self.agent_subscriptions[agent_id] = set()
        
        self.agent_subscriptions[agent_id].add(topic_name)
        self.topics[topic_name].add_subscriber(agent_id)
        
        logger.info(f"Agent {agent_id} subscribed to topic {topic_name}")
        return True
    
    async def unsubscribe_agent_from_topic(self, agent_id: str, topic_name: str) -> bool:
        """Unsubscribe an agent from a topic.
        
        Args:
            agent_id: Agent ID
            topic_name: Topic name
            
        Returns:
            True if successful, False otherwise
        """
        if agent_id not in self.agent_subscriptions:
            return False
        
        if topic_name in self.agent_subscriptions[agent_id]:
            self.agent_subscriptions[agent_id].remove(topic_name)
            self.topics[topic_name].remove_subscriber(agent_id)
            logger.info(f"Agent {agent_id} unsubscribed from topic {topic_name}")
            return True
        
        return False
    
    async def get_agent_topics(self, agent_id: str) -> List[TopicInfo]:
        """Get all topics an agent is subscribed to.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of TopicInfo objects
        """
        if agent_id not in self.agent_subscriptions:
            return []
        
        topic_names = self.agent_subscriptions[agent_id]
        return [self.topics[name] for name in topic_names if name in self.topics]
    
    async def search_topics(
        self,
        query: str,
        agent_id: Optional[str] = None
    ) -> List[TopicInfo]:
        """Search topics by name or description.
        
        Args:
            query: Search query
            agent_id: Optional agent ID to filter by subscriptions
            
        Returns:
            List of matching TopicInfo objects
        """
        topics = await self.list_topics(agent_id=agent_id)
        query_lower = query.lower()
        
        matching_topics = []
        for topic in topics:
            if (query_lower in topic.name.lower() or 
                (topic.description and query_lower in topic.description.lower())):
                matching_topics.append(topic)
        
        return matching_topics
    
    async def ensure_topic_exists(
        self,
        topic_name: str,
        created_by: str,
        created_by_name: str
    ) -> TopicInfo:
        """Ensure a topic exists, creating it if necessary.
        
        Args:
            topic_name: Topic name
            created_by: ID of the agent
            created_by_name: Name of the agent
            
        Returns:
            TopicInfo object
        """
        if topic_name in self.topics:
            return self.topics[topic_name]
        
        return await self.create_topic(
            name=topic_name,
            created_by=created_by,
            description=f"Auto-created by {created_by_name}"
        )
    
    async def delete_topic(self, topic_name: str, deleted_by: str) -> bool:
        """Delete a topic.
        
        Args:
            topic_name: Topic name
            deleted_by: ID of the agent deleting the topic
            
        Returns:
            True if successful, False otherwise
        """
        if topic_name not in self.topics:
            return False
        
        # Check if the agent has permission to delete
        topic = self.topics[topic_name]
        if topic.created_by != deleted_by and not topic.is_private:
            logger.warning(f"Agent {deleted_by} not authorized to delete topic {topic_name}")
            return False
        
        # Remove from all agent subscriptions
        for agent_id, topics in self.agent_subscriptions.items():
            topics.discard(topic_name)
        
        # Delete topic
        del self.topics[topic_name]
        logger.info(f"Deleted topic {topic_name} by agent {deleted_by}")
        
        return True
    
    async def get_topic_stats(self) -> Dict[str, int]:
        """Get topic statistics.
        
        Returns:
            Dictionary with topic statistics
        """
        total_topics = len(self.topics)
        private_topics = sum(1 for t in self.topics.values() if t.is_private)
        public_topics = total_topics - private_topics
        total_subscribers = sum(len(t.subscribers) for t in self.topics.values())
        
        return {
            "total_topics": total_topics,
            "public_topics": public_topics,
            "private_topics": private_topics,
            "total_subscribers": total_subscribers,
            "avg_subscribers_per_topic": total_subscribers / total_topics if total_topics > 0 else 0
        }
