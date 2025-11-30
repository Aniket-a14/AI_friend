from google import genai
from collections import deque
import logging
import asyncio
from .config import Config

import json
import os

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
        self.model_name = "gemini-2.5-pro"
        self.memory = deque(maxlen=8) # Stores last 8 messages
        
        # Load personality
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            personality_path = os.path.join(current_dir, "personality.json")
            with open(personality_path, "r", encoding="utf-8") as f:
                self.personality = json.dumps(json.load(f), indent=2)
        except Exception as e:
            logger.error(f"Failed to load personality.json: {e}")
            self.personality = "You are a helpful AI assistant."

    def add_to_memory(self, role, content):
        self.memory.append({"role": role, "content": content})

    def clear_memory(self):
        self.memory.clear()

    async def generate_response(self, user_text):
        # Construct prompt
        history_text = ""
        for msg in self.memory:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"{role}: {msg['content']}\n"

        prompt = f"""
SYSTEM: {self.personality}

CONTEXT:
{history_text}

USER: {user_text}
"""
        try:
            # Running synchronous call in a thread to avoid blocking the event loop
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt
            )
            reply = response.text
            return reply
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            return "I'm sorry, I'm having trouble thinking right now."
