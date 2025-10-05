#!/usr/bin/env python3
"""Round-trip demo: publish -> agent listens -> agent replies."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

# Add project root
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from agentic_redpanda.core import Agent, MessageBroker
from agentic_redpanda.schemas.message import AgentMessage, MessageType
from agentic_redpanda.providers.base import LLMProvider, LLMResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class EchoProvider(LLMProvider):
    async def generate(self, prompt: str, system_message: Optional[str] = None, **kwargs) -> LLMResponse:
        return LLMResponse(content=f"Echo: {prompt}", model="echo")

    async def generate_stream(self, prompt: str, system_message: Optional[str] = None, **kwargs):
        yield LLMResponse(content=f"Echo: {prompt}", model="echo")

    async def chat(self, messages, **kwargs) -> LLMResponse:
        return LLMResponse(content=f"Echo chat: {messages[-1]['content']}", model="echo")

    async def get_embeddings(self, texts, **kwargs):
        return [[0.0] * 3 for _ in texts]

    async def health_check(self) -> bool:
        return True


class SimpleResponder(Agent):
    async def process_message(self, message: AgentMessage) -> Optional[str]:
        # Respond with a simple acknowledgement
        return f"Acknowledged: {message.content}"

    async def _handle_text_message(self, message: AgentMessage) -> None:
        # Generate a response using provider (echo)
        response = await self._generate_response(message.content)
        await self.send_message(
            content=response,
            topic=message.topic,
            message_type=MessageType.RESPONSE,
            reply_to=message.sender_id
        )


async def main():
    topic = "demo-ask"

    # Use external listener for host apps
    broker = MessageBroker(bootstrap_servers=["localhost:19092"]) 

    # Agent setup
    provider = EchoProvider({})
    agent = SimpleResponder(
        agent_id="agent-echo",
        agent_name="Echo Agent",
        role="responder",
        llm_provider=provider,
        message_broker=broker,
        topics=[topic]
    )

    received_replies = []

    async def user_reply_handler(message: AgentMessage):
        if message.message_type == MessageType.RESPONSE:
            received_replies.append(message)
            logger.info(f"Reply received from {message.sender_name}: {message.content}")

    await broker.start()
    await agent.start()

    # Subscribe the demo to the same topic to receive replies
    await broker.subscribe_to_topic(topic=topic, agent_id="demo-client", handler=user_reply_handler)

    # Publish initial message
    logger.info("Publishing initial message...")
    await agent.send_message(
        content="Hello agent, can you respond?",
        topic=topic,
        message_type=MessageType.TEXT
    )

    # Wait for reply
    for _ in range(10):
        if received_replies:
            break
        await asyncio.sleep(0.5)

    success = bool(received_replies)

    # Cleanup
    await agent.stop()
    await broker.stop()

    if success:
        logger.info("Round-trip demo successful.")
        return 0
    else:
        logger.error("Round-trip demo failed: no reply received.")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
