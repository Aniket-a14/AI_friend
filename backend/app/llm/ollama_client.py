"""
Ollama Client - Wrapper for local LLM API calls
Provides OpenAI-compatible interface for Llama 3.2
"""
import json
import logging
import aiohttp
from typing import AsyncGenerator, Dict, Any

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2:3b"):
        self.base_url = base_url
        self.model = model
        
    async def generate_stream(self, prompt: str, system: str = None) -> AsyncGenerator[str, None]:
        """
        Stream responses from Ollama (non-blocking)
        """
        # Build full prompt with system instruction
        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\nUser: {prompt}\nAssistant:"
        
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": True,
            "options": {
                "temperature": 0.8,
                "top_p": 0.9,
                "num_predict": 512
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/api/generate", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.content:
                        if line:
                            try:
                                chunk = json.loads(line)
                                if not chunk.get("done"):
                                    text = chunk.get("response", "")
                                    if text:
                                        yield text
                            except json.JSONDecodeError:
                                pass
                            
        except Exception as e:
            logger.error(f"Ollama streaming failed: {e}")
            yield "I'm having trouble thinking right now..."
    
    async def generate(self, prompt: str, system: str = None) -> str:
        """
        Non-streaming generation (non-blocking)
        """
        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\nUser: {prompt}\nAssistant:"
        
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": 0.8,
                "top_p": 0.9,
                "num_predict": 512
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/api/generate", json=payload, timeout=30) as response:
                    response.raise_for_status()
                    result = await response.json()
                    return result.get("response", "")
                    
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return "Error generating response."
            
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return "I'm having trouble thinking right now..."
    
    def check_health(self) -> bool:
        """Check if Ollama is reachable"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def list_models(self) -> list:
        """List available models"""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except:
            return []
