"""Error handling and retry logic for agent communication."""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Type, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from ..schemas.message import AgentMessage

logger = logging.getLogger(__name__)


class ErrorType(str, Enum):
    """Types of errors that can occur."""
    NETWORK_ERROR = "network_error"
    LLM_PROVIDER_ERROR = "llm_provider_error"
    MESSAGE_BROKER_ERROR = "message_broker_error"
    VALIDATION_ERROR = "validation_error"
    PERMISSION_ERROR = "permission_error"
    TIMEOUT_ERROR = "timeout_error"
    UNKNOWN_ERROR = "unknown_error"


class RetryStrategy(str, Enum):
    """Retry strategies for failed operations."""
    IMMEDIATE = "immediate"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    
    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    backoff_multiplier: float = 2.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    retryable_errors: List[ErrorType] = field(default_factory=lambda: [
        ErrorType.NETWORK_ERROR,
        ErrorType.TIMEOUT_ERROR,
        ErrorType.MESSAGE_BROKER_ERROR
    ])


@dataclass
class ErrorContext:
    """Context information for an error."""
    
    error_type: ErrorType
    error_message: str
    timestamp: datetime
    agent_id: Optional[str] = None
    topic: Optional[str] = None
    message_id: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""
    
    attempt_number: int
    timestamp: datetime
    delay: float
    error: Optional[Exception] = None
    success: bool = False


class ErrorHandler:
    """Handles errors and implements retry logic."""
    
    def __init__(self, retry_config: Optional[RetryConfig] = None):
        """Initialize the error handler.
        
        Args:
            retry_config: Retry configuration
        """
        self.retry_config = retry_config or RetryConfig()
        self.error_history: List[ErrorContext] = []
        self.retry_history: List[RetryAttempt] = []
        self.max_history_size = 1000
        
    async def handle_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        retry_func: Optional[Callable] = None
    ) -> Any:
        """Handle an error with retry logic.
        
        Args:
            error: The exception that occurred
            context: Additional context information
            retry_func: Function to retry (if applicable)
            
        Returns:
            Result of retry function or None
        """
        error_type = self._classify_error(error)
        error_context = ErrorContext(
            error_type=error_type,
            error_message=str(error),
            timestamp=datetime.utcnow(),
            metadata=context or {}
        )
        
        # Record error
        self._record_error(error_context)
        
        # Check if error is retryable
        if error_type in self.retry_config.retryable_errors and retry_func:
            return await self._retry_operation(retry_func, error_context)
        
        # Log non-retryable error
        logger.error(f"Non-retryable error: {error_type.value} - {str(error)}")
        return None
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify an error by type.
        
        Args:
            error: Exception to classify
            
        Returns:
            ErrorType
        """
        error_name = type(error).__name__.lower()
        error_message = str(error).lower()
        
        if "timeout" in error_name or "timeout" in error_message:
            return ErrorType.TIMEOUT_ERROR
        elif "network" in error_name or "connection" in error_message:
            return ErrorType.NETWORK_ERROR
        elif "kafka" in error_name or "redpanda" in error_message:
            return ErrorType.MESSAGE_BROKER_ERROR
        elif "openai" in error_name or "anthropic" in error_name or "llm" in error_message:
            return ErrorType.LLM_PROVIDER_ERROR
        elif "validation" in error_name or "invalid" in error_message:
            return ErrorType.VALIDATION_ERROR
        elif "permission" in error_name or "unauthorized" in error_message:
            return ErrorType.PERMISSION_ERROR
        else:
            return ErrorType.UNKNOWN_ERROR
    
    async def _retry_operation(
        self,
        retry_func: Callable,
        error_context: ErrorContext
    ) -> Any:
        """Retry an operation with configured strategy.
        
        Args:
            retry_func: Function to retry
            error_context: Error context
            
        Returns:
            Result of successful retry or None
        """
        for attempt in range(self.retry_config.max_retries):
            try:
                # Calculate delay
                delay = self._calculate_delay(attempt)
                
                # Record retry attempt
                retry_attempt = RetryAttempt(
                    attempt_number=attempt + 1,
                    timestamp=datetime.utcnow(),
                    delay=delay
                )
                self.retry_history.append(retry_attempt)
                
                # Wait before retry (except for first attempt)
                if attempt > 0:
                    logger.info(f"Retrying in {delay:.2f} seconds (attempt {attempt + 1}/{self.retry_config.max_retries})")
                    await asyncio.sleep(delay)
                
                # Execute retry
                result = await retry_func()
                
                # Mark as successful
                retry_attempt.success = True
                logger.info(f"Retry successful on attempt {attempt + 1}")
                return result
                
            except Exception as e:
                retry_attempt.error = e
                error_context.retry_count = attempt + 1
                
                # Check if this is the last attempt
                if attempt == self.retry_config.max_retries - 1:
                    logger.error(f"All retry attempts failed: {str(e)}")
                    return None
                
                # Update error context
                error_context.error_message = str(e)
                self._record_error(error_context)
        
        return None
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt.
        
        Args:
            attempt: Attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        if self.retry_config.strategy == RetryStrategy.IMMEDIATE:
            return 0.0
        elif self.retry_config.strategy == RetryStrategy.FIXED_DELAY:
            return self.retry_config.base_delay
        elif self.retry_config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.retry_config.base_delay * (attempt + 1)
        elif self.retry_config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.retry_config.base_delay * (self.retry_config.backoff_multiplier ** attempt)
        else:
            delay = self.retry_config.base_delay
        
        # Apply jitter to prevent thundering herd
        jitter = delay * 0.1 * (0.5 - asyncio.get_event_loop().time() % 1)
        delay += jitter
        
        # Cap at max delay
        return min(delay, self.retry_config.max_delay)
    
    def _record_error(self, error_context: ErrorContext) -> None:
        """Record an error in the history.
        
        Args:
            error_context: Error context to record
        """
        self.error_history.append(error_context)
        
        # Trim history if too large
        if len(self.error_history) > self.max_history_size:
            self.error_history = self.error_history[-self.max_history_size:]
        
        # Log error
        logger.error(
            f"Error recorded: {error_context.error_type.value} - {error_context.error_message} "
            f"(Agent: {error_context.agent_id}, Topic: {error_context.topic})"
        )
    
    async def get_error_stats(
        self,
        time_window: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """Get error statistics.
        
        Args:
            time_window: Optional time window to filter errors
            
        Returns:
            Dictionary with error statistics
        """
        errors = self.error_history.copy()
        
        # Filter by time window
        if time_window:
            cutoff_time = datetime.utcnow() - time_window
            errors = [e for e in errors if e.timestamp >= cutoff_time]
        
        # Count by error type
        error_counts = {}
        for error in errors:
            error_type = error.error_type.value
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        # Calculate retry success rate
        total_retries = len(self.retry_history)
        successful_retries = len([r for r in self.retry_history if r.success])
        retry_success_rate = (successful_retries / total_retries * 100) if total_retries > 0 else 0
        
        return {
            "total_errors": len(errors),
            "error_types": error_counts,
            "total_retries": total_retries,
            "successful_retries": successful_retries,
            "retry_success_rate": retry_success_rate,
            "time_window": str(time_window) if time_window else "all_time"
        }
    
    async def get_recent_errors(
        self,
        limit: int = 10,
        error_type: Optional[ErrorType] = None
    ) -> List[ErrorContext]:
        """Get recent errors.
        
        Args:
            limit: Maximum number of errors to return
            error_type: Optional filter by error type
            
        Returns:
            List of recent errors
        """
        errors = self.error_history.copy()
        
        # Filter by error type
        if error_type:
            errors = [e for e in errors if e.error_type == error_type]
        
        # Sort by timestamp (most recent first)
        errors.sort(key=lambda e: e.timestamp, reverse=True)
        
        return errors[:limit]
    
    async def clear_history(self) -> None:
        """Clear error and retry history."""
        self.error_history.clear()
        self.retry_history.clear()
        logger.info("Cleared error and retry history")
    
    async def update_retry_config(self, new_config: RetryConfig) -> None:
        """Update retry configuration.
        
        Args:
            new_config: New retry configuration
        """
        self.retry_config = new_config
        logger.info("Updated retry configuration")
    
    async def is_error_retryable(self, error: Exception) -> bool:
        """Check if an error is retryable.
        
        Args:
            error: Exception to check
            
        Returns:
            True if retryable, False otherwise
        """
        error_type = self._classify_error(error)
        return error_type in self.retry_config.retryable_errors


class MessageErrorHandler(ErrorHandler):
    """Specialized error handler for message operations."""
    
    async def handle_message_error(
        self,
        error: Exception,
        message: AgentMessage,
        operation: str
    ) -> bool:
        """Handle errors specific to message operations.
        
        Args:
            error: The exception that occurred
            message: The message that caused the error
            operation: The operation being performed
            
        Returns:
            True if error was handled successfully, False otherwise
        """
        context = {
            "message_id": str(message.id),
            "topic": message.topic,
            "sender_id": message.sender_id,
            "operation": operation
        }
        
        error_context = ErrorContext(
            error_type=self._classify_error(error),
            error_message=str(error),
            timestamp=datetime.utcnow(),
            agent_id=message.sender_id,
            topic=message.topic,
            message_id=str(message.id),
            metadata=context
        )
        
        self._record_error(error_context)
        
        # Check if message should be retried
        if message.should_retry() and self.is_error_retryable(error):
            logger.info(f"Message {message.id} will be retried")
            return True
        
        # Message cannot be retried
        logger.error(f"Message {message.id} failed permanently: {str(error)}")
        return False
