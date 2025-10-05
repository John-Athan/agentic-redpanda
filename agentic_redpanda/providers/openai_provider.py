"""OpenAI provider implementation."""

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional

import openai
from openai import AsyncOpenAI

from .base import LLMProvider, LLMResponse


class OpenAIProvider(LLMProvider):
    """OpenAI API provider implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize OpenAI provider."""
        super().__init__(config)
        
        self.api_key = config.get("api_key")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = config.get("model", "gpt-3.5-turbo")
        self.max_tokens = config.get("max_tokens", 1000)
        self.temperature = config.get("temperature", 0.7)
        self.top_p = config.get("top_p", 1.0)
        self.frequency_penalty = config.get("frequency_penalty", 0.0)
        self.presence_penalty = config.get("presence_penalty", 0.0)
    
    async def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate text using OpenAI API."""
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                frequency_penalty=self.frequency_penalty,
                presence_penalty=self.presence_penalty,
                **kwargs
            )
            
            choice = response.choices[0]
            usage = response.usage.dict() if response.usage else None
            
            return LLMResponse(
                content=choice.message.content,
                model=self.model,
                usage=usage,
                finish_reason=choice.finish_reason,
                metadata={"response_id": response.id}
            )
            
        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {str(e)}")
    
    async def generate_stream(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        **kwargs: Any
    ) -> AsyncGenerator[LLMResponse, None]:
        """Generate text using streaming."""
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                frequency_penalty=self.frequency_penalty,
                presence_penalty=self.presence_penalty,
                stream=True,
                **kwargs
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield LLMResponse(
                        content=chunk.choices[0].delta.content,
                        model=self.model,
                        metadata={"streaming": True}
                    )
                    
        except Exception as e:
            raise RuntimeError(f"OpenAI streaming error: {str(e)}")
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any
    ) -> LLMResponse:
        """Chat with OpenAI using conversation format."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                frequency_penalty=self.frequency_penalty,
                presence_penalty=self.presence_penalty,
                **kwargs
            )
            
            choice = response.choices[0]
            usage = response.usage.dict() if response.usage else None
            
            return LLMResponse(
                content=choice.message.content,
                model=self.model,
                usage=usage,
                finish_reason=choice.finish_reason,
                metadata={"response_id": response.id}
            )
            
        except Exception as e:
            raise RuntimeError(f"OpenAI chat error: {str(e)}")
    
    async def get_embeddings(
        self,
        texts: List[str],
        **kwargs: Any
    ) -> List[List[float]]:
        """Get embeddings using OpenAI API."""
        try:
            response = await self.client.embeddings.create(
                model=kwargs.get("model", "text-embedding-ada-002"),
                input=texts
            )
            
            return [embedding.embedding for embedding in response.data]
            
        except Exception as e:
            raise RuntimeError(f"OpenAI embeddings error: {str(e)}")
    
    async def health_check(self) -> bool:
        """Check if OpenAI API is accessible."""
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False
    
    def get_available_models(self) -> List[str]:
        """Get available OpenAI models."""
        return [
            "gpt-4",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
            "text-embedding-ada-002",
            "text-embedding-3-small",
            "text-embedding-3-large"
        ]
    
    def validate_config(self) -> bool:
        """Validate OpenAI configuration."""
        return bool(self.api_key and self.model)
