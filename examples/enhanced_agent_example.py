"""Example demonstrating enhanced agent features."""

import asyncio
import logging
from typing import Optional

from agentic_redpanda.core import (
    EnhancedAgent, MessageBroker, SubscriptionType, SubscriptionFilter,
    TopicType, MessageType, MessagePriority, RoutingRuleType
)
from agentic_redpanda.providers import OpenAIProvider
from agentic_redpanda.schemas.message import AgentMessage
from agentic_redpanda.utils import setup_logging, load_config

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)


class SmartAssistant(EnhancedAgent):
    """A smart assistant with enhanced communication capabilities."""
    
    async def _handle_text_message(self, message: AgentMessage, context: Optional[dict] = None) -> None:
        """Handle text messages with smart routing."""
        # Check if message contains urgent keywords
        urgent_keywords = ["urgent", "emergency", "asap", "critical"]
        is_urgent = any(keyword in message.content.lower() for keyword in urgent_keywords)
        
        if is_urgent:
            # Route to urgent topic
            await self.send_message(
                content=f"URGENT: {message.content}",
                topic="urgent",
                priority=MessagePriority.URGENT,
                reply_to=message.sender_id
            )
        
        # Generate contextual response
        response = await self._generate_contextual_response(message, context)
        
        await self.send_message(
            content=response,
            topic=message.topic,
            reply_to=message.sender_id
        )
    
    async def _handle_task_message(self, message: AgentMessage, context: Optional[dict] = None) -> None:
        """Handle task messages with task management."""
        # Parse task
        task_content = message.content
        
        # Acknowledge task
        await self.send_message(
            content=f"Task received: {task_content}",
            topic=message.topic,
            message_type=MessageType.RESPONSE,
            reply_to=message.sender_id
        )
        
        # Route to task management topic
        await self.send_message(
            content=f"New task assigned: {task_content}",
            topic="task-management",
            message_type=MessageType.NOTIFICATION,
            metadata={"task_id": f"task-{message.id}", "assigned_to": self.agent_id}
        )


class CodeReviewer(EnhancedAgent):
    """A code reviewer agent with specialized capabilities."""
    
    async def _handle_text_message(self, message: AgentMessage, context: Optional[dict] = None) -> None:
        """Handle code review requests."""
        # Check if message contains code
        if "```" in message.content or "def " in message.content or "class " in message.content:
            # This looks like code, route to code review
            await self.send_message(
                content=f"Code review request: {message.content}",
                topic="code-review",
                message_type=MessageType.TASK,
                reply_to=message.sender_id,
                metadata={"review_type": "code", "language": "python"}
            )
        
        # Generate response
        response = await self._generate_contextual_response(message, context)
        
        await self.send_message(
            content=response,
            topic=message.topic,
            reply_to=message.sender_id
        )


async def setup_routing_rules(agent: EnhancedAgent):
    """Set up routing rules for the agent."""
    
    # Route urgent messages
    await agent.message_router.add_routing_rule(
        rule_id="urgent_routing",
        rule_type=RoutingRuleType.CONTENT_KEYWORD,
        condition=["urgent", "emergency", "critical"],
        target_topics=["urgent", "alerts"],
        priority=100,
        description="Route urgent messages to alert topics"
    )
    
    # Route code-related messages
    await agent.message_router.add_routing_rule(
        rule_id="code_routing",
        rule_type=RoutingRuleType.CONTENT_KEYWORD,
        condition=["code", "review", "bug", "fix"],
        target_topics=["code-review", "development"],
        priority=50,
        description="Route code-related messages"
    )
    
    # Route task messages
    await agent.message_router.add_routing_rule(
        rule_id="task_routing",
        rule_type=RoutingRuleType.MESSAGE_TYPE,
        condition=MessageType.TASK,
        target_topics=["task-management", "work"],
        priority=75,
        description="Route task messages to management topics"
    )


async def main():
    """Main function demonstrating enhanced agent features."""
    try:
        # Load configuration
        config = load_config("config/example.yaml")
        
        # Create message broker
        message_broker = MessageBroker(**config.message_broker.dict())
        
        # Create smart assistant
        assistant_config = config.agents[0]
        llm_provider = OpenAIProvider(assistant_config.llm_provider.dict())
        
        smart_assistant = SmartAssistant(
            agent_id="smart-assistant-1",
            agent_name="Smart Assistant",
            role="assistant",
            llm_provider=llm_provider,
            message_broker=message_broker,
            topics=["general", "urgent", "tasks"]
        )
        
        # Create code reviewer
        code_reviewer = CodeReviewer(
            agent_id="code-reviewer-1",
            agent_name="Code Reviewer",
            role="code_reviewer",
            llm_provider=llm_provider,
            message_broker=message_broker,
            topics=["code-review", "development", "general"]
        )
        
        # Start message broker
        await message_broker.start()
        
        # Set up routing rules
        await setup_routing_rules(smart_assistant)
        await setup_routing_rules(code_reviewer)
        
        # Start agents
        await smart_assistant.start()
        await code_reviewer.start()
        
        logger.info("Enhanced agents are running. Press Ctrl+C to stop.")
        
        # Create some topics
        await smart_assistant.create_topic_advanced(
            topic_name="urgent",
            topic_type=TopicType.SYSTEM,
            description="Urgent messages and alerts"
        )
        
        await smart_assistant.create_topic_advanced(
            topic_name="code-review",
            topic_type=TopicType.PROJECT,
            description="Code review requests and discussions"
        )
        
        # Send test messages
        await smart_assistant.send_message(
            content="Hello! I'm a smart assistant. How can I help you today?",
            topic="general"
        )
        
        await code_reviewer.send_message(
            content="I'm ready to review code. Send me your code snippets!",
            topic="code-review"
        )
        
        # Send an urgent message to test routing
        await smart_assistant.send_message(
            content="This is an urgent message that should be routed to urgent topics!",
            topic="general",
            priority=MessagePriority.HIGH
        )
        
        # Send a code review request
        await smart_assistant.send_message(
            content="Can you review this code?\n```python\ndef hello():\n    print('Hello, world!')\n```",
            topic="general"
        )
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
                
                # Print status every 30 seconds
                if int(asyncio.get_event_loop().time()) % 30 == 0:
                    status = await smart_assistant.get_agent_status()
                    logger.info(f"Agent status: {status['conversation_length']} messages, "
                              f"{status['subscription_stats']['active_subscriptions']} active subscriptions")
        
        except KeyboardInterrupt:
            logger.info("Shutting down...")
    
    except Exception as e:
        logger.error(f"Error running enhanced agents: {e}")
        raise
    finally:
        # Clean up
        if 'smart_assistant' in locals():
            await smart_assistant.stop()
        if 'code_reviewer' in locals():
            await code_reviewer.stop()
        if 'message_broker' in locals():
            await message_broker.stop()


if __name__ == "__main__":
    asyncio.run(main())
