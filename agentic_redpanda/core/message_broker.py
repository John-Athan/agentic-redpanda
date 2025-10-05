"""Message broker for Redpanda integration."""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

from ..schemas.message import AgentMessage, TopicInfo
from .topic_manager import TopicManager

logger = logging.getLogger(__name__)


class MessageBroker:
    """Message broker for handling Redpanda/Kafka communication."""
    
    def __init__(
        self,
        bootstrap_servers: List[str] = None,
        security_protocol: str = "PLAINTEXT",
        sasl_mechanism: Optional[str] = None,
        sasl_username: Optional[str] = None,
        sasl_password: Optional[str] = None,
        **kwargs: Any
    ):
        """Initialize the message broker.
        
        Args:
            bootstrap_servers: List of Redpanda/Kafka bootstrap servers
            security_protocol: Security protocol (PLAINTEXT, SASL_PLAINTEXT, etc.)
            sasl_mechanism: SASL mechanism if using SASL
            sasl_username: SASL username if using SASL
            sasl_password: SASL password if using SASL
            **kwargs: Additional Kafka configuration
        """
        self.bootstrap_servers = bootstrap_servers or ["localhost:9092"]
        self.security_protocol = security_protocol
        self.sasl_mechanism = sasl_mechanism
        self.sasl_username = sasl_username
        self.sasl_password = sasl_password
        
        # Kafka configuration
        self.kafka_config = {
            "bootstrap_servers": self.bootstrap_servers,
            "security_protocol": self.security_protocol,
            **kwargs
        }
        
        if sasl_mechanism:
            self.kafka_config.update({
                "sasl_mechanism": sasl_mechanism,
                "sasl_plain_username": sasl_username,
                "sasl_plain_password": sasl_password,
            })
        
        self.producer: Optional[KafkaProducer] = None
        self.consumers: Dict[str, KafkaConsumer] = {}
        self.topic_manager = TopicManager()
        self.message_handlers: Dict[str, Callable[[AgentMessage], None]] = {}
        self.running = False
        
    async def start(self) -> None:
        """Start the message broker."""
        try:
            # Initialize producer
            self.producer = KafkaProducer(
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                **self.kafka_config
            )
            
            self.running = True
            logger.info("Message broker started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start message broker: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the message broker."""
        self.running = False
        
        # Close all consumers
        for consumer in self.consumers.values():
            consumer.close()
        self.consumers.clear()
        
        # Close producer
        if self.producer:
            self.producer.close()
            self.producer = None
        
        logger.info("Message broker stopped")
    
    async def publish_message(self, message: AgentMessage) -> None:
        """Publish a message to a topic.
        
        Args:
            message: The message to publish
        """
        if not self.producer:
            raise RuntimeError("Message broker not started")
        
        try:
            # Ensure topic exists
            await self.topic_manager.ensure_topic_exists(
                message.topic,
                message.sender_id,
                message.sender_name
            )
            
            # Publish message
            future = self.producer.send(
                message.topic,
                value=message.to_dict(),
                key=message.sender_id.encode('utf-8')
            )
            
            # Wait for confirmation
            record_metadata = future.get(timeout=10)
            logger.debug(f"Message published to topic {message.topic}, partition {record_metadata.partition}")
            
        except KafkaError as e:
            logger.error(f"Failed to publish message: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error publishing message: {e}")
            raise
    
    async def subscribe_to_topic(
        self,
        topic: str,
        agent_id: str,
        handler: Callable[[AgentMessage], None]
    ) -> None:
        """Subscribe to a topic.
        
        Args:
            topic: Topic name to subscribe to
            agent_id: ID of the subscribing agent
            handler: Message handler function
        """
        if topic in self.consumers:
            logger.warning(f"Already subscribed to topic {topic}")
            return
        
        try:
            # Create consumer
            consumer = KafkaConsumer(
                topic,
                group_id=f"agent-{agent_id}",
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True,
                **self.kafka_config
            )
            
            self.consumers[topic] = consumer
            self.message_handlers[topic] = handler
            
            # Start consuming in background
            asyncio.create_task(self._consume_messages(topic, consumer, handler))
            
            logger.info(f"Subscribed to topic {topic}")
            
        except Exception as e:
            logger.error(f"Failed to subscribe to topic {topic}: {e}")
            raise
    
    async def unsubscribe_from_topic(self, topic: str) -> None:
        """Unsubscribe from a topic.
        
        Args:
            topic: Topic name to unsubscribe from
        """
        if topic in self.consumers:
            self.consumers[topic].close()
            del self.consumers[topic]
            del self.message_handlers[topic]
            logger.info(f"Unsubscribed from topic {topic}")
    
    async def _consume_messages(
        self,
        topic: str,
        consumer: KafkaConsumer,
        handler: Callable[[AgentMessage], None]
    ) -> None:
        """Consume messages from a topic.
        
        Args:
            topic: Topic name
            consumer: Kafka consumer
            handler: Message handler function
        """
        try:
            while self.running:
                message_batch = consumer.poll(timeout_ms=1000)
                
                for topic_partition, messages in message_batch.items():
                    for message in messages:
                        try:
                            # Parse message
                            message_data = message.value
                            agent_message = AgentMessage.from_dict(message_data)
                            
                            # Call handler
                            handler(agent_message)
                            
                        except Exception as e:
                            logger.error(f"Error processing message from {topic}: {e}")
                            
        except Exception as e:
            logger.error(f"Error consuming messages from {topic}: {e}")
    
    async def list_topics(self) -> List[str]:
        """List all available topics.
        
        Returns:
            List of topic names
        """
        try:
            from kafka.admin import KafkaAdminClient, ConfigResource, ConfigResourceType
            
            admin_client = KafkaAdminClient(**self.kafka_config)
            metadata = admin_client.list_topics()
            return list(metadata)
            
        except Exception as e:
            logger.error(f"Failed to list topics: {e}")
            return []
    
    async def create_topic(
        self,
        topic: str,
        num_partitions: int = 1,
        replication_factor: int = 1
    ) -> None:
        """Create a new topic.
        
        Args:
            topic: Topic name
            num_partitions: Number of partitions
            replication_factor: Replication factor
        """
        try:
            from kafka.admin import KafkaAdminClient, NewTopic
            from kafka.errors import TopicAlreadyExistsError
            
            admin_client = KafkaAdminClient(**self.kafka_config)
            
            topic_list = [NewTopic(
                name=topic,
                num_partitions=num_partitions,
                replication_factor=replication_factor
            )]
            
            admin_client.create_topics(new_topics=topic_list, validate_only=False)
            logger.info(f"Created topic {topic}")
            
        except TopicAlreadyExistsError:
            logger.info(f"Topic {topic} already exists")
        except Exception as e:
            logger.error(f"Failed to create topic {topic}: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check if the message broker is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            if not self.producer:
                return False
            
            # Simple health check - just verify producer exists and is connected
            # The connection is already established when producer is created
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
