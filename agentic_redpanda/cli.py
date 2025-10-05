"""Command-line interface for Agentic Redpanda."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .utils import load_config, setup_logging
from .core.agent import Agent
from .core.message_broker import MessageBroker
from .providers import OpenAIProvider, OllamaProvider


def create_agent_from_config(agent_config, message_broker):
    """Create an agent from configuration."""
    # Create LLM provider
    provider_config = agent_config.llm_provider.dict()
    provider_type = provider_config.pop("provider_type")
    
    if provider_type == "openai":
        llm_provider = OpenAIProvider(provider_config)
    elif provider_type == "ollama":
        llm_provider = OllamaProvider(provider_config)
    else:
        raise ValueError(f"Unsupported provider type: {provider_type}")
    
    # Create agent
    agent = Agent(
        agent_id=agent_config.agent_id,
        agent_name=agent_config.agent_name,
        role=agent_config.role,
        llm_provider=llm_provider,
        message_broker=message_broker,
        topics=agent_config.topics
    )
    
    return agent


async def run_agents(config_path: str):
    """Run agents from configuration file."""
    # Load configuration
    config = load_config(config_path)
    
    # Set up logging
    setup_logging(config.logging)
    logger = logging.getLogger(__name__)
    
    # Create message broker
    message_broker = MessageBroker(**config.message_broker.dict())
    
    # Create agents
    agents = []
    for agent_config in config.agents:
        try:
            agent = create_agent_from_config(agent_config, message_broker)
            agents.append(agent)
        except Exception as e:
            logger.error(f"Failed to create agent {agent_config.agent_id}: {e}")
            continue
    
    if not agents:
        logger.error("No agents could be created")
        return
    
    try:
        # Start message broker
        await message_broker.start()
        
        # Start all agents
        for agent in agents:
            await agent.start()
        
        logger.info(f"Started {len(agents)} agents. Press Ctrl+C to stop.")
        
        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
    
    except Exception as e:
        logger.error(f"Error running agents: {e}")
        raise
    finally:
        # Clean up
        for agent in agents:
            try:
                await agent.stop()
            except Exception as e:
                logger.error(f"Error stopping agent {agent.agent_id}: {e}")
        
        try:
            await message_broker.stop()
        except Exception as e:
            logger.error(f"Error stopping message broker: {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Agentic Redpanda - AI Agent Communication System")
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config/example.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--log-level",
        "-l",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level"
    )
    
    args = parser.parse_args()
    
    # Set up basic logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Check if config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Configuration file not found: {config_path}")
        print("Please create a configuration file or use the example: config/example.yaml")
        sys.exit(1)
    
    # Run agents
    try:
        asyncio.run(run_agents(str(config_path)))
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
