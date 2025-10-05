"""Base classes for LLM provider implementations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    """Standardized response from any LLM provider."""
    
    content: str = Field(..., description="Generated text content")
    model: str = Field(..., description="Model used for generation")
    usage: Optional[Dict[str, int]] = Field(None, description="Token usage information")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional response metadata")
    finish_reason: Optional[str] = Field(None, description="Reason why generation finished")
    
    def __str__(self) -> str:
        return self.content


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the provider with configuration."""
        self.config = config
        self.model = config.get("model", "default")
        self.max_tokens = config.get("max_tokens", 1000)
        self.temperature = config.get("temperature", 0.7)
        self.top_p = config.get("top_p", 1.0)
        self.frequency_penalty = config.get("frequency_penalty", 0.0)
        self.presence_penalty = config.get("presence_penalty", 0.0)
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """
        Generate text using the LLM provider.
        
        Args:
            prompt: The input prompt
            system_message: Optional system message for context
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse object with generated content
        """
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        **kwargs: Any
    ):
        """
        Generate text using streaming.
        
        Args:
            prompt: The input prompt
            system_message: Optional system message for context
            **kwargs: Additional provider-specific parameters
            
        Yields:
            LLMResponse objects as they are generated
        """
        pass
    
    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any
    ) -> LLMResponse:
        """
        Chat with the LLM using a conversation format.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse object with generated content
        """
        pass
    
    @abstractmethod
    async def get_embeddings(
        self,
        texts: List[str],
        **kwargs: Any
    ) -> List[List[float]]:
        """
        Get embeddings for the given texts.
        
        Args:
            texts: List of texts to embed
            **kwargs: Additional provider-specific parameters
            
        Returns:
            List of embedding vectors
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the provider is healthy and accessible.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    def get_available_models(self) -> List[str]:
        """
        Get list of available models for this provider.
        
        Returns:
            List of model names
        """
        return [self.model]
    
    def validate_config(self) -> bool:
        """
        Validate the provider configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        return True
