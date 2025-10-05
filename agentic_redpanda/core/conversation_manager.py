"""Conversation management and threading for agent communications."""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from ..schemas.message import AgentMessage, MessageType

logger = logging.getLogger(__name__)


@dataclass
class ConversationThread:
    """Represents a conversation thread."""
    
    thread_id: UUID
    topic: str
    title: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    participants: Set[str] = field(default_factory=set)
    message_count: int = 0
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationContext:
    """Context for a conversation."""
    
    thread_id: UUID
    topic: str
    recent_messages: List[AgentMessage]
    participants: Set[str]
    thread_title: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)


class ConversationManager:
    """Manages conversation threads and context."""
    
    def __init__(self, max_context_messages: int = 10, thread_timeout: timedelta = timedelta(hours=24)):
        """Initialize the conversation manager.
        
        Args:
            max_context_messages: Maximum number of messages to keep in context
            thread_timeout: Timeout for inactive threads
        """
        self.max_context_messages = max_context_messages
        self.thread_timeout = thread_timeout
        
        # Thread management
        self.threads: Dict[UUID, ConversationThread] = {}
        self.topic_threads: Dict[str, List[UUID]] = {}  # topic -> list of thread IDs
        self.agent_threads: Dict[str, Set[UUID]] = {}  # agent_id -> set of thread IDs
        
        # Message threading
        self.message_threads: Dict[str, UUID] = {}  # message_id -> thread_id
        self.thread_messages: Dict[UUID, List[AgentMessage]] = {}  # thread_id -> messages
        
        # Context management
        self.conversation_contexts: Dict[UUID, ConversationContext] = {}
        
    async def create_thread(
        self,
        topic: str,
        initial_message: AgentMessage,
        title: Optional[str] = None
    ) -> ConversationThread:
        """Create a new conversation thread.
        
        Args:
            topic: Topic name
            initial_message: Initial message in the thread
            title: Optional thread title
            
        Returns:
            Created ConversationThread
        """
        thread_id = uuid4()
        
        thread = ConversationThread(
            thread_id=thread_id,
            topic=topic,
            title=title or self._generate_thread_title(initial_message),
            participants={initial_message.sender_id}
        )
        
        # Store thread
        self.threads[thread_id] = thread
        
        # Add to topic threads
        if topic not in self.topic_threads:
            self.topic_threads[topic] = []
        self.topic_threads[topic].append(thread_id)
        
        # Add to agent threads
        if initial_message.sender_id not in self.agent_threads:
            self.agent_threads[initial_message.sender_id] = set()
        self.agent_threads[initial_message.sender_id].add(thread_id)
        
        # Store initial message
        self.thread_messages[thread_id] = [initial_message]
        self.message_threads[str(initial_message.id)] = thread_id
        
        # Create context
        context = ConversationContext(
            thread_id=thread_id,
            topic=topic,
            recent_messages=[initial_message],
            participants={initial_message.sender_id},
            thread_title=thread.title
        )
        self.conversation_contexts[thread_id] = context
        
        logger.info(f"Created conversation thread {thread_id} in topic {topic}")
        return thread
    
    async def add_message_to_thread(
        self,
        message: AgentMessage,
        thread_id: Optional[UUID] = None
    ) -> UUID:
        """Add a message to a conversation thread.
        
        Args:
            message: Message to add
            thread_id: Optional specific thread ID
            
        Returns:
            Thread ID where message was added
        """
        # Determine thread ID
        if thread_id is None:
            thread_id = await self._find_or_create_thread(message)
        
        # Add message to thread
        if thread_id not in self.thread_messages:
            self.thread_messages[thread_id] = []
        
        self.thread_messages[thread_id].append(message)
        self.message_threads[str(message.id)] = thread_id
        
        # Update thread
        if thread_id in self.threads:
            thread = self.threads[thread_id]
            thread.participants.add(message.sender_id)
            thread.message_count += 1
            thread.last_activity = message.timestamp
            
            # Update agent threads
            if message.sender_id not in self.agent_threads:
                self.agent_threads[message.sender_id] = set()
            self.agent_threads[message.sender_id].add(thread_id)
        
        # Update context
        await self._update_conversation_context(thread_id, message)
        
        logger.debug(f"Added message {message.id} to thread {thread_id}")
        return thread_id
    
    async def _find_or_create_thread(self, message: AgentMessage) -> UUID:
        """Find existing thread or create new one for a message.
        
        Args:
            message: Message to find thread for
            
        Returns:
            Thread ID
        """
        # Check for existing active threads in the topic
        if message.topic in self.topic_threads:
            for thread_id in self.topic_threads[message.topic]:
                if thread_id in self.threads and self.threads[thread_id].is_active:
                    # Check if thread is still active (recent activity)
                    thread = self.threads[thread_id]
                    if datetime.utcnow() - thread.last_activity < self.thread_timeout:
                        return thread_id
        
        # Create new thread
        thread = await self.create_thread(message.topic, message)
        return thread.thread_id
    
    async def _update_conversation_context(self, thread_id: UUID, message: AgentMessage) -> None:
        """Update conversation context for a thread.
        
        Args:
            thread_id: Thread ID
            message: New message
        """
        if thread_id not in self.conversation_contexts:
            return
        
        context = self.conversation_contexts[thread_id]
        
        # Add message to recent messages
        context.recent_messages.append(message)
        
        # Keep only recent messages
        if len(context.recent_messages) > self.max_context_messages:
            context.recent_messages = context.recent_messages[-self.max_context_messages:]
        
        # Update participants
        context.participants.add(message.sender_id)
        
        # Update activity
        context.last_activity = message.timestamp
    
    def _generate_thread_title(self, message: AgentMessage) -> str:
        """Generate a thread title from a message.
        
        Args:
            message: Initial message
            
        Returns:
            Generated title
        """
        # Simple title generation - could be enhanced with LLM
        content = message.content.strip()
        if len(content) <= 50:
            return content
        else:
            return content[:47] + "..."
    
    async def get_conversation_context(self, thread_id: UUID) -> Optional[ConversationContext]:
        """Get conversation context for a thread.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            ConversationContext or None if not found
        """
        return self.conversation_contexts.get(thread_id)
    
    async def get_thread_messages(
        self,
        thread_id: UUID,
        limit: Optional[int] = None
    ) -> List[AgentMessage]:
        """Get messages in a thread.
        
        Args:
            thread_id: Thread ID
            limit: Optional limit on number of messages
            
        Returns:
            List of messages
        """
        messages = self.thread_messages.get(thread_id, [])
        
        if limit:
            messages = messages[-limit:]
        
        return messages
    
    async def get_agent_threads(self, agent_id: str) -> List[ConversationThread]:
        """Get threads for an agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of threads
        """
        thread_ids = self.agent_threads.get(agent_id, set())
        return [self.threads[tid] for tid in thread_ids if tid in self.threads]
    
    async def get_topic_threads(self, topic: str) -> List[ConversationThread]:
        """Get threads for a topic.
        
        Args:
            topic: Topic name
            
        Returns:
            List of threads
        """
        thread_ids = self.topic_threads.get(topic, [])
        return [self.threads[tid] for tid in thread_ids if tid in self.threads]
    
    async def close_thread(self, thread_id: UUID, closed_by: str) -> bool:
        """Close a conversation thread.
        
        Args:
            thread_id: Thread ID
            closed_by: Agent closing the thread
            
        Returns:
            True if successful, False otherwise
        """
        if thread_id not in self.threads:
            return False
        
        thread = self.threads[thread_id]
        thread.is_active = False
        
        logger.info(f"Closed thread {thread_id} by agent {closed_by}")
        return True
    
    async def archive_old_threads(self) -> int:
        """Archive old inactive threads.
        
        Returns:
            Number of threads archived
        """
        archived_count = 0
        cutoff_time = datetime.utcnow() - self.thread_timeout
        
        for thread_id, thread in self.threads.items():
            if thread.is_active and thread.last_activity < cutoff_time:
                thread.is_active = False
                archived_count += 1
        
        if archived_count > 0:
            logger.info(f"Archived {archived_count} old threads")
        
        return archived_count
    
    async def search_threads(
        self,
        query: str,
        topic: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> List[ConversationThread]:
        """Search for threads by content.
        
        Args:
            query: Search query
            topic: Optional topic filter
            agent_id: Optional agent filter
            
        Returns:
            List of matching threads
        """
        matching_threads = []
        query_lower = query.lower()
        
        # Get candidate threads
        candidate_threads = []
        if topic:
            candidate_threads = await self.get_topic_threads(topic)
        elif agent_id:
            candidate_threads = await self.get_agent_threads(agent_id)
        else:
            candidate_threads = list(self.threads.values())
        
        # Search in thread content
        for thread in candidate_threads:
            # Search in title
            if thread.title and query_lower in thread.title.lower():
                matching_threads.append(thread)
                continue
            
            # Search in messages
            messages = await self.get_thread_messages(thread.thread_id)
            for message in messages:
                if query_lower in message.content.lower():
                    matching_threads.append(thread)
                    break
        
        return matching_threads
    
    async def get_thread_stats(self) -> Dict[str, Any]:
        """Get conversation thread statistics.
        
        Returns:
            Dictionary with thread statistics
        """
        total_threads = len(self.threads)
        active_threads = len([t for t in self.threads.values() if t.is_active])
        
        total_messages = sum(len(msgs) for msgs in self.thread_messages.values())
        
        # Average messages per thread
        avg_messages_per_thread = total_messages / total_threads if total_threads > 0 else 0
        
        # Threads by topic
        topic_counts = {}
        for thread in self.threads.values():
            topic_counts[thread.topic] = topic_counts.get(thread.topic, 0) + 1
        
        return {
            "total_threads": total_threads,
            "active_threads": active_threads,
            "archived_threads": total_threads - active_threads,
            "total_messages": total_messages,
            "avg_messages_per_thread": avg_messages_per_thread,
            "threads_by_topic": topic_counts,
            "total_participants": len(self.agent_threads)
        }
    
    async def cleanup_old_data(self) -> Dict[str, int]:
        """Clean up old conversation data.
        
        Returns:
            Dictionary with cleanup statistics
        """
        cleanup_stats = {
            "archived_threads": 0,
            "removed_contexts": 0,
            "removed_messages": 0
        }
        
        # Archive old threads
        cleanup_stats["archived_threads"] = await self.archive_old_threads()
        
        # Remove contexts for archived threads
        for thread_id, thread in self.threads.items():
            if not thread.is_active and thread_id in self.conversation_contexts:
                del self.conversation_contexts[thread_id]
                cleanup_stats["removed_contexts"] += 1
        
        # Remove old messages (keep only recent ones)
        for thread_id, messages in self.thread_messages.items():
            if len(messages) > self.max_context_messages * 2:
                old_count = len(messages)
                self.thread_messages[thread_id] = messages[-self.max_context_messages:]
                cleanup_stats["removed_messages"] += old_count - len(self.thread_messages[thread_id])
        
        return cleanup_stats
