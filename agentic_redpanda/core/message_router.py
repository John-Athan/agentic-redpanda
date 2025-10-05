"""Message routing and filtering system."""

import asyncio
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set, Union
from dataclasses import dataclass
from enum import Enum

from ..schemas.message import AgentMessage, MessageType, MessagePriority

logger = logging.getLogger(__name__)


class RoutingRuleType(str, Enum):
    """Types of routing rules."""
    CONTENT_KEYWORD = "content_keyword"
    CONTENT_REGEX = "content_regex"
    SENDER_ROLE = "sender_role"
    MESSAGE_TYPE = "message_type"
    PRIORITY = "priority"
    METADATA = "metadata"
    CUSTOM = "custom"


@dataclass
class RoutingRule:
    """A routing rule for message filtering."""
    
    rule_id: str
    rule_type: RoutingRuleType
    condition: Union[str, Dict[str, Any], Callable]
    target_topics: List[str]
    priority: int = 0  # Higher priority rules are evaluated first
    active: bool = True
    description: Optional[str] = None


@dataclass
class MessageRoute:
    """Represents a message route."""
    
    message: AgentMessage
    target_topics: List[str]
    routing_rules: List[RoutingRule]
    timestamp: str


class MessageRouter:
    """Routes messages based on configurable rules."""
    
    def __init__(self):
        """Initialize the message router."""
        self.routing_rules: List[RoutingRule] = []
        self.route_history: List[MessageRoute] = []
        self.max_history_size = 1000
        
    async def add_routing_rule(
        self,
        rule_id: str,
        rule_type: RoutingRuleType,
        condition: Union[str, Dict[str, Any], Callable],
        target_topics: List[str],
        priority: int = 0,
        description: Optional[str] = None
    ) -> RoutingRule:
        """Add a new routing rule.
        
        Args:
            rule_id: Unique identifier for the rule
            rule_type: Type of routing rule
            condition: Condition for the rule
            target_topics: Topics to route matching messages to
            priority: Rule priority (higher = evaluated first)
            description: Optional description
            
        Returns:
            Created RoutingRule
        """
        rule = RoutingRule(
            rule_id=rule_id,
            rule_type=rule_type,
            condition=condition,
            target_topics=target_topics,
            priority=priority,
            description=description
        )
        
        self.routing_rules.append(rule)
        # Sort by priority (highest first)
        self.routing_rules.sort(key=lambda r: r.priority, reverse=True)
        
        logger.info(f"Added routing rule {rule_id} with priority {priority}")
        return rule
    
    async def remove_routing_rule(self, rule_id: str) -> bool:
        """Remove a routing rule.
        
        Args:
            rule_id: Rule identifier
            
        Returns:
            True if removed, False if not found
        """
        for i, rule in enumerate(self.routing_rules):
            if rule.rule_id == rule_id:
                del self.routing_rules[i]
                logger.info(f"Removed routing rule {rule_id}")
                return True
        return False
    
    async def route_message(self, message: AgentMessage) -> List[str]:
        """Route a message based on active rules.
        
        Args:
            message: Message to route
            
        Returns:
            List of target topics
        """
        target_topics = set()
        matched_rules = []
        
        # Evaluate rules in priority order
        for rule in self.routing_rules:
            if not rule.active:
                continue
            
            if await self._evaluate_rule(message, rule):
                target_topics.update(rule.target_topics)
                matched_rules.append(rule)
                logger.debug(f"Message matched rule {rule.rule_id}")
        
        # Record the route
        route = MessageRoute(
            message=message,
            target_topics=list(target_topics),
            routing_rules=matched_rules,
            timestamp=message.timestamp.isoformat()
        )
        
        self.route_history.append(route)
        
        # Trim history if too large
        if len(self.route_history) > self.max_history_size:
            self.route_history = self.route_history[-self.max_history_size:]
        
        return list(target_topics)
    
    async def _evaluate_rule(self, message: AgentMessage, rule: RoutingRule) -> bool:
        """Evaluate a routing rule against a message.
        
        Args:
            message: Message to evaluate
            rule: Rule to evaluate
            
        Returns:
            True if rule matches, False otherwise
        """
        try:
            if rule.rule_type == RoutingRuleType.CONTENT_KEYWORD:
                keywords = rule.condition if isinstance(rule.condition, list) else [rule.condition]
                return any(keyword.lower() in message.content.lower() for keyword in keywords)
            
            elif rule.rule_type == RoutingRuleType.CONTENT_REGEX:
                return bool(re.search(rule.condition, message.content, re.IGNORECASE))
            
            elif rule.rule_type == RoutingRuleType.SENDER_ROLE:
                allowed_roles = rule.condition if isinstance(rule.condition, list) else [rule.condition]
                return message.sender_role in allowed_roles
            
            elif rule.rule_type == RoutingRuleType.MESSAGE_TYPE:
                allowed_types = rule.condition if isinstance(rule.condition, list) else [rule.condition]
                return message.message_type in allowed_types
            
            elif rule.rule_type == RoutingRuleType.PRIORITY:
                min_priority = rule.condition
                priority_order = {
                    MessagePriority.LOW: 0,
                    MessagePriority.NORMAL: 1,
                    MessagePriority.HIGH: 2,
                    MessagePriority.URGENT: 3
                }
                return priority_order.get(message.priority, 0) >= priority_order.get(min_priority, 0)
            
            elif rule.rule_type == RoutingRuleType.METADATA:
                if not isinstance(rule.condition, dict):
                    return False
                for key, value in rule.condition.items():
                    if key not in message.metadata or message.metadata[key] != value:
                        return False
                return True
            
            elif rule.rule_type == RoutingRuleType.CUSTOM:
                if callable(rule.condition):
                    return rule.condition(message)
                return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error evaluating rule {rule.rule_id}: {e}")
            return False
    
    async def get_routing_rules(self) -> List[RoutingRule]:
        """Get all routing rules.
        
        Returns:
            List of routing rules
        """
        return self.routing_rules.copy()
    
    async def get_rule_by_id(self, rule_id: str) -> Optional[RoutingRule]:
        """Get a routing rule by ID.
        
        Args:
            rule_id: Rule identifier
            
        Returns:
            RoutingRule or None if not found
        """
        for rule in self.routing_rules:
            if rule.rule_id == rule_id:
                return rule
        return None
    
    async def update_rule(
        self,
        rule_id: str,
        **updates: Any
    ) -> bool:
        """Update a routing rule.
        
        Args:
            rule_id: Rule identifier
            **updates: Fields to update
            
        Returns:
            True if updated, False if not found
        """
        for rule in self.routing_rules:
            if rule.rule_id == rule_id:
                for key, value in updates.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)
                
                # Re-sort by priority if priority was updated
                if 'priority' in updates:
                    self.routing_rules.sort(key=lambda r: r.priority, reverse=True)
                
                logger.info(f"Updated routing rule {rule_id}")
                return True
        return False
    
    async def enable_rule(self, rule_id: str) -> bool:
        """Enable a routing rule.
        
        Args:
            rule_id: Rule identifier
            
        Returns:
            True if enabled, False if not found
        """
        return await self.update_rule(rule_id, active=True)
    
    async def disable_rule(self, rule_id: str) -> bool:
        """Disable a routing rule.
        
        Args:
            rule_id: Rule identifier
            
        Returns:
            True if disabled, False if not found
        """
        return await self.update_rule(rule_id, active=False)
    
    async def get_route_history(
        self,
        limit: Optional[int] = None,
        topic_filter: Optional[str] = None
    ) -> List[MessageRoute]:
        """Get routing history.
        
        Args:
            limit: Maximum number of routes to return
            topic_filter: Filter by target topic
            
        Returns:
            List of message routes
        """
        history = self.route_history.copy()
        
        if topic_filter:
            history = [route for route in history if topic_filter in route.target_topics]
        
        if limit:
            history = history[-limit:]
        
        return history
    
    async def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics.
        
        Returns:
            Dictionary with routing statistics
        """
        total_rules = len(self.routing_rules)
        active_rules = len([r for r in self.routing_rules if r.active])
        
        rule_types = {}
        for rule in self.routing_rules:
            rule_type = rule.rule_type.value
            rule_types[rule_type] = rule_types.get(rule_type, 0) + 1
        
        return {
            "total_rules": total_rules,
            "active_rules": active_rules,
            "inactive_rules": total_rules - active_rules,
            "rule_types": rule_types,
            "total_routes": len(self.route_history),
            "average_targets_per_route": (
                sum(len(route.target_topics) for route in self.route_history) / len(self.route_history)
                if self.route_history else 0
            )
        }
    
    async def clear_history(self) -> None:
        """Clear routing history."""
        self.route_history.clear()
        logger.info("Cleared routing history")
    
    async def export_rules(self) -> List[Dict[str, Any]]:
        """Export routing rules as dictionaries.
        
        Returns:
            List of rule dictionaries
        """
        rules = []
        for rule in self.routing_rules:
            rule_dict = {
                "rule_id": rule.rule_id,
                "rule_type": rule.rule_type.value,
                "condition": rule.condition,
                "target_topics": rule.target_topics,
                "priority": rule.priority,
                "active": rule.active,
                "description": rule.description
            }
            rules.append(rule_dict)
        return rules
    
    async def import_rules(self, rules: List[Dict[str, Any]]) -> int:
        """Import routing rules from dictionaries.
        
        Args:
            rules: List of rule dictionaries
            
        Returns:
            Number of rules imported
        """
        imported = 0
        for rule_dict in rules:
            try:
                rule = RoutingRule(
                    rule_id=rule_dict["rule_id"],
                    rule_type=RoutingRuleType(rule_dict["rule_type"]),
                    condition=rule_dict["condition"],
                    target_topics=rule_dict["target_topics"],
                    priority=rule_dict.get("priority", 0),
                    active=rule_dict.get("active", True),
                    description=rule_dict.get("description")
                )
                self.routing_rules.append(rule)
                imported += 1
            except Exception as e:
                logger.error(f"Error importing rule {rule_dict.get('rule_id', 'unknown')}: {e}")
        
        # Re-sort by priority
        self.routing_rules.sort(key=lambda r: r.priority, reverse=True)
        
        logger.info(f"Imported {imported} routing rules")
        return imported
