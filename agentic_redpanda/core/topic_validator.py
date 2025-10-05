"""Topic validation and permission management."""

import re
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

from ..schemas.message import TopicInfo

logger = logging.getLogger(__name__)


class TopicType(str, Enum):
    """Types of topics."""
    GENERAL = "general"
    TEAM = "team"
    PROJECT = "project"
    PRIVATE = "private"
    SYSTEM = "system"
    RANDOM = "random"


class PermissionLevel(str, Enum):
    """Permission levels for topic access."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    OWNER = "owner"


@dataclass
class TopicPermission:
    """Represents a permission for a topic."""
    
    agent_id: str
    permission_level: PermissionLevel
    granted_by: str
    granted_at: str


@dataclass
class TopicValidationResult:
    """Result of topic validation."""
    
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]


class TopicValidator:
    """Validates topic names and manages permissions."""
    
    def __init__(self):
        """Initialize the topic validator."""
        self.topic_permissions: Dict[str, List[TopicPermission]] = {}  # topic -> permissions
        self.reserved_topics: Set[str] = {
            "system", "admin", "config", "logs", "metrics", "health"
        }
        self.topic_patterns: Dict[TopicType, str] = {
            TopicType.TEAM: r"^team-[a-z0-9-]+$",
            TopicType.PROJECT: r"^project-[a-z0-9-]+$",
            TopicType.PRIVATE: r"^private-[a-z0-9-]+$",
            TopicType.GENERAL: r"^[a-z0-9-]+$",
            TopicType.RANDOM: r"^random$"
        }
        self.max_topic_length = 50
        self.min_topic_length = 3
    
    async def validate_topic_name(
        self,
        topic_name: str,
        topic_type: Optional[TopicType] = None,
        created_by: Optional[str] = None
    ) -> TopicValidationResult:
        """Validate a topic name.
        
        Args:
            topic_name: Topic name to validate
            topic_type: Expected topic type
            created_by: Agent creating the topic
            
        Returns:
            TopicValidationResult
        """
        errors = []
        warnings = []
        suggestions = []
        
        # Check length
        if len(topic_name) < self.min_topic_length:
            errors.append(f"Topic name too short (minimum {self.min_topic_length} characters)")
        elif len(topic_name) > self.max_topic_length:
            errors.append(f"Topic name too long (maximum {self.max_topic_length} characters)")
        
        # Check for reserved names
        if topic_name.lower() in self.reserved_topics:
            errors.append(f"Topic name '{topic_name}' is reserved")
        
        # Check for invalid characters
        if not re.match(r"^[a-z0-9-]+$", topic_name):
            errors.append("Topic name can only contain lowercase letters, numbers, and hyphens")
        
        # Check for consecutive hyphens
        if "--" in topic_name:
            errors.append("Topic name cannot contain consecutive hyphens")
        
        # Check for leading/trailing hyphens
        if topic_name.startswith("-") or topic_name.endswith("-"):
            errors.append("Topic name cannot start or end with a hyphen")
        
        # Check topic type pattern
        if topic_type and topic_type in self.topic_patterns:
            pattern = self.topic_patterns[topic_type]
            if not re.match(pattern, topic_name):
                errors.append(f"Topic name does not match {topic_type.value} pattern: {pattern}")
        
        # Suggest improvements
        if errors:
            # Suggest a cleaned version
            cleaned = re.sub(r"[^a-z0-9-]", "-", topic_name.lower())
            cleaned = re.sub(r"-+", "-", cleaned)
            cleaned = cleaned.strip("-")
            
            if cleaned and len(cleaned) >= self.min_topic_length:
                suggestions.append(f"Consider using: {cleaned}")
        
        # Check for similar existing topics
        similar_topics = await self._find_similar_topics(topic_name)
        if similar_topics:
            warnings.append(f"Similar topics exist: {', '.join(similar_topics)}")
        
        is_valid = len(errors) == 0
        
        return TopicValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )
    
    async def _find_similar_topics(self, topic_name: str) -> List[str]:
        """Find topics similar to the given name.
        
        Args:
            topic_name: Topic name to find similarities for
            
        Returns:
            List of similar topic names
        """
        # This would typically query the topic manager
        # For now, return empty list
        return []
    
    async def grant_permission(
        self,
        topic: str,
        agent_id: str,
        permission_level: PermissionLevel,
        granted_by: str
    ) -> bool:
        """Grant permission to an agent for a topic.
        
        Args:
            topic: Topic name
            agent_id: Agent ID
            permission_level: Permission level
            granted_by: Agent granting the permission
            
        Returns:
            True if successful, False otherwise
        """
        if topic not in self.topic_permissions:
            self.topic_permissions[topic] = []
        
        # Check if permission already exists
        for perm in self.topic_permissions[topic]:
            if perm.agent_id == agent_id:
                # Update existing permission
                perm.permission_level = permission_level
                perm.granted_by = granted_by
                logger.info(f"Updated permission for agent {agent_id} on topic {topic}")
                return True
        
        # Add new permission
        permission = TopicPermission(
            agent_id=agent_id,
            permission_level=permission_level,
            granted_by=granted_by,
            granted_at="now"  # Would use actual timestamp
        )
        
        self.topic_permissions[topic].append(permission)
        logger.info(f"Granted {permission_level.value} permission to agent {agent_id} for topic {topic}")
        return True
    
    async def revoke_permission(
        self,
        topic: str,
        agent_id: str,
        revoked_by: str
    ) -> bool:
        """Revoke permission from an agent for a topic.
        
        Args:
            topic: Topic name
            agent_id: Agent ID
            revoked_by: Agent revoking the permission
            
        Returns:
            True if successful, False otherwise
        """
        if topic not in self.topic_permissions:
            return False
        
        # Remove permission
        original_length = len(self.topic_permissions[topic])
        self.topic_permissions[topic] = [
            perm for perm in self.topic_permissions[topic]
            if perm.agent_id != agent_id
        ]
        
        if len(self.topic_permissions[topic]) < original_length:
            logger.info(f"Revoked permission for agent {agent_id} on topic {topic}")
            return True
        
        return False
    
    async def check_permission(
        self,
        topic: str,
        agent_id: str,
        required_permission: PermissionLevel
    ) -> bool:
        """Check if an agent has the required permission for a topic.
        
        Args:
            topic: Topic name
            agent_id: Agent ID
            required_permission: Required permission level
            
        Returns:
            True if agent has permission, False otherwise
        """
        if topic not in self.topic_permissions:
            return False
        
        for permission in self.topic_permissions[topic]:
            if permission.agent_id == agent_id:
                return self._permission_level_sufficient(
                    permission.permission_level,
                    required_permission
                )
        
        return False
    
    def _permission_level_sufficient(
        self,
        current_level: PermissionLevel,
        required_level: PermissionLevel
    ) -> bool:
        """Check if current permission level is sufficient for required level.
        
        Args:
            current_level: Current permission level
            required_level: Required permission level
            
        Returns:
            True if sufficient, False otherwise
        """
        level_hierarchy = {
            PermissionLevel.READ: 1,
            PermissionLevel.WRITE: 2,
            PermissionLevel.ADMIN: 3,
            PermissionLevel.OWNER: 4
        }
        
        return level_hierarchy.get(current_level, 0) >= level_hierarchy.get(required_level, 0)
    
    async def get_topic_permissions(self, topic: str) -> List[TopicPermission]:
        """Get all permissions for a topic.
        
        Args:
            topic: Topic name
            
        Returns:
            List of permissions
        """
        return self.topic_permissions.get(topic, []).copy()
    
    async def get_agent_permissions(self, agent_id: str) -> Dict[str, PermissionLevel]:
        """Get all permissions for an agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Dictionary mapping topic names to permission levels
        """
        permissions = {}
        
        for topic, topic_permissions in self.topic_permissions.items():
            for permission in topic_permissions:
                if permission.agent_id == agent_id:
                    permissions[topic] = permission.permission_level
        
        return permissions
    
    async def suggest_topic_name(
        self,
        base_name: str,
        topic_type: TopicType = TopicType.GENERAL
    ) -> str:
        """Suggest a valid topic name based on a base name.
        
        Args:
            base_name: Base name to work with
            topic_type: Type of topic
            
        Returns:
            Suggested topic name
        """
        # Clean the base name
        suggested = re.sub(r"[^a-z0-9-]", "-", base_name.lower())
        suggested = re.sub(r"-+", "-", suggested)
        suggested = suggested.strip("-")
        
        # Ensure minimum length
        if len(suggested) < self.min_topic_length:
            suggested = f"{suggested}-topic"
        
        # Apply topic type prefix if needed
        if topic_type == TopicType.TEAM and not suggested.startswith("team-"):
            suggested = f"team-{suggested}"
        elif topic_type == TopicType.PROJECT and not suggested.startswith("project-"):
            suggested = f"project-{suggested}"
        elif topic_type == TopicType.PRIVATE and not suggested.startswith("private-"):
            suggested = f"private-{suggested}"
        
        # Ensure it's not too long
        if len(suggested) > self.max_topic_length:
            suggested = suggested[:self.max_topic_length].rstrip("-")
        
        return suggested
    
    async def validate_topic_creation(
        self,
        topic_name: str,
        topic_type: TopicType,
        created_by: str,
        is_private: bool = False
    ) -> Tuple[bool, List[str]]:
        """Validate topic creation request.
        
        Args:
            topic_name: Topic name
            topic_type: Topic type
            created_by: Agent creating the topic
            is_private: Whether topic is private
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Validate topic name
        validation_result = await self.validate_topic_name(topic_name, topic_type, created_by)
        if not validation_result.is_valid:
            errors.extend(validation_result.errors)
        
        # Check if topic already exists
        if topic_name in self.topic_permissions:
            errors.append(f"Topic '{topic_name}' already exists")
        
        # Additional validation for private topics
        if is_private and topic_type != TopicType.PRIVATE:
            errors.append("Private topics must be of type PRIVATE")
        
        return len(errors) == 0, errors
    
    async def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics.
        
        Returns:
            Dictionary with validation statistics
        """
        total_permissions = sum(len(perms) for perms in self.topic_permissions.values())
        
        permission_levels = {}
        for perms in self.topic_permissions.values():
            for perm in perms:
                level = perm.permission_level.value
                permission_levels[level] = permission_levels.get(level, 0) + 1
        
        return {
            "total_topics": len(self.topic_permissions),
            "total_permissions": total_permissions,
            "permission_levels": permission_levels,
            "reserved_topics": len(self.reserved_topics),
            "topic_patterns": len(self.topic_patterns)
        }
