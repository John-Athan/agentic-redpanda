"""Message schema definitions for agent communication."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class MessageType(str, Enum):
    """Types of messages agents can send."""
    TEXT = "text"
    TASK = "task"
    RESULT = "result"
    QUERY = "query"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class MessagePriority(str, Enum):
    """Message priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class AgentMessage(BaseModel):
    """Standard message format for agent communication."""
    
    # Message identification
    id: UUID = Field(default_factory=uuid4, description="Unique message identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message creation timestamp")
    
    # Agent information
    sender_id: str = Field(..., description="ID of the agent sending the message")
    sender_name: str = Field(..., description="Human-readable name of the sending agent")
    sender_role: str = Field(..., description="Role or type of the sending agent")
    
    # Message content
    message_type: MessageType = Field(..., description="Type of message")
    priority: MessagePriority = Field(default=MessagePriority.NORMAL, description="Message priority")
    content: str = Field(..., description="Main message content")
    
    # Topic and routing
    topic: str = Field(..., description="Redpanda topic name")
    reply_to: Optional[str] = Field(None, description="Topic to reply to (for request-response patterns)")
    
    # Message metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional message metadata")
    tags: List[str] = Field(default_factory=list, description="Message tags for categorization")
    
    # Response handling
    correlation_id: Optional[UUID] = Field(None, description="ID for correlating request-response pairs")
    requires_response: bool = Field(default=False, description="Whether this message requires a response")
    response_timeout: Optional[int] = Field(None, description="Response timeout in seconds")
    
    # Message lifecycle
    ttl: Optional[int] = Field(None, description="Time to live in seconds")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    
    @validator('content')
    def content_not_empty(cls, v):
        """Ensure content is not empty."""
        if not v or not v.strip():
            raise ValueError('Message content cannot be empty')
        return v.strip()
    
    @validator('sender_id', 'sender_name', 'sender_role', 'topic')
    def fields_not_empty(cls, v):
        """Ensure required fields are not empty."""
        if not v or not v.strip():
            raise ValueError('Required fields cannot be empty')
        return v.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for serialization."""
        data = self.dict()
        # Convert UUIDs to strings for JSON serialization
        if 'id' in data and data['id']:
            data['id'] = str(data['id'])
        if 'correlation_id' in data and data['correlation_id']:
            data['correlation_id'] = str(data['correlation_id'])
        # Convert datetime to ISO string for JSON serialization
        if 'timestamp' in data and data['timestamp']:
            data['timestamp'] = data['timestamp'].isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Create message from dictionary."""
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if message has expired based on TTL."""
        if self.ttl is None:
            return False
        
        age = (datetime.utcnow() - self.timestamp).total_seconds()
        return age > self.ttl
    
    def should_retry(self) -> bool:
        """Check if message should be retried."""
        return self.retry_count < self.max_retries and not self.is_expired()
    
    def increment_retry(self) -> "AgentMessage":
        """Create a new message with incremented retry count."""
        return self.copy(update={"retry_count": self.retry_count + 1})


class TopicInfo(BaseModel):
    """Information about a Redpanda topic."""
    
    name: str = Field(..., description="Topic name")
    description: Optional[str] = Field(None, description="Topic description")
    created_by: str = Field(..., description="Agent that created the topic")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Topic creation time")
    message_count: int = Field(default=0, description="Number of messages in topic")
    subscribers: List[str] = Field(default_factory=list, description="List of subscriber agent IDs")
    is_private: bool = Field(default=False, description="Whether topic is private")
    tags: List[str] = Field(default_factory=list, description="Topic tags for categorization")
    
    def add_subscriber(self, agent_id: str) -> None:
        """Add a subscriber to the topic."""
        if agent_id not in self.subscribers:
            self.subscribers.append(agent_id)
    
    def remove_subscriber(self, agent_id: str) -> None:
        """Remove a subscriber from the topic."""
        if agent_id in self.subscribers:
            self.subscribers.remove(agent_id)
