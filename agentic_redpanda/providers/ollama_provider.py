"""Ollama provider implementation for local models."""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp

from .base import LLMProvider, LLMResponse


class OllamaProvider(LLMProvider):
    """Ollama local model provider implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Ollama provider."""
        super().__init__(config)
        
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.model = config.get("model", "llama2")
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
        """Generate text using Ollama API."""
        full_prompt = prompt
        if system_message:
            full_prompt = f"System: {system_message}\n\nUser: {prompt}"
        
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "num_predict": self.max_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "repeat_penalty": 1.0 + self.frequency_penalty,
                "presence_penalty": self.presence_penalty,
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    if response.status != 200:
                        raise RuntimeError(f"Ollama API error: {response.status}")
                    
                    result = await response.json()
                    
                    return LLMResponse(
                        content=result.get("response", ""),
                        model=self.model,
                        usage={"prompt_tokens": result.get("prompt_eval_count", 0),
                               "completion_tokens": result.get("eval_count", 0)},
                        metadata={"done": result.get("done", True)}
                    )
                    
        except Exception as e:
            raise RuntimeError(f"Ollama API error: {str(e)}")
    
    async def generate_stream(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        **kwargs: Any
    ) -> AsyncGenerator[LLMResponse, None]:
        """Generate text using streaming."""
        full_prompt = prompt
        if system_message:
            full_prompt = f"System: {system_message}\n\nUser: {prompt}"
        
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": True,
            "options": {
                "num_predict": self.max_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "repeat_penalty": 1.0 + self.frequency_penalty,
                "presence_penalty": self.presence_penalty,
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    if response.status != 200:
                        raise RuntimeError(f"Ollama API error: {response.status}")
                    
                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line.decode('utf-8'))
                                if data.get("response"):
                                    yield LLMResponse(
                                        content=data["response"],
                                        model=self.model,
                                        metadata={"streaming": True, "done": data.get("done", False)}
                                    )
                            except json.JSONDecodeError:
                                continue
                                
        except Exception as e:
            raise RuntimeError(f"Ollama streaming error: {str(e)}")
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any
    ) -> LLMResponse:
        """Chat with Ollama using conversation format."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": self.max_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "repeat_penalty": 1.0 + self.frequency_penalty,
                "presence_penalty": self.presence_penalty,
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    if response.status != 200:
                        raise RuntimeError(f"Ollama API error: {response.status}")
                    
                    result = await response.json()
                    
                    return LLMResponse(
                        content=result.get("message", {}).get("content", ""),
                        model=self.model,
                        usage={"prompt_tokens": result.get("prompt_eval_count", 0),
                               "completion_tokens": result.get("eval_count", 0)},
                        metadata={"done": result.get("done", True)}
                    )
                    
        except Exception as e:
            raise RuntimeError(f"Ollama chat error: {str(e)}")
    
    async def get_embeddings(
        self,
        texts: List[str],
        **kwargs: Any
    ) -> List[List[float]]:
        """Get embeddings using Ollama API."""
        embeddings = []
        
        try:
            async with aiohttp.ClientSession() as session:
                for text in texts:
                    payload = {
                        "model": kwargs.get("model", "nomic-embed-text"),
                        "prompt": text
                    }
                    
                    async with session.post(
                        f"{self.base_url}/api/embeddings",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as response:
                        if response.status != 200:
                            raise RuntimeError(f"Ollama embeddings error: {response.status}")
                        
                        result = await response.json()
                        embeddings.append(result.get("embedding", []))
                        
        except Exception as e:
            raise RuntimeError(f"Ollama embeddings error: {str(e)}")
        
        return embeddings
    
    async def health_check(self) -> bool:
        """Check if Ollama is accessible."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return response.status == 200
        except Exception:
            return False
    
    def get_available_models(self) -> List[str]:
        """Get available Ollama models."""
        return [
            "llama2",
            "llama2:13b",
            "llama2:70b",
            "codellama",
            "mistral",
            "mixtral",
            "nomic-embed-text",
            "all-minilm"
        ]
    
    def validate_config(self) -> bool:
        """Validate Ollama configuration."""
        return bool(self.base_url and self.model)
