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

    async def generate_greeting(self):
        prompt = f"""
SYSTEM: {self.personality}

TASK: Generate a short, friendly, natural greeting (1 short sentence max) to start a conversation after being woken up. 
Examples: "Hi there, how can I help?", "Hello! What's on your mind?", "Hey! I'm listening."
Do not include any other text, just the greeting.
"""
        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"LLM greeting generation error: {e}")
            return "Hello! How can I help you?"

    async def generate_farewell(self, user_text):
        prompt = f"""
SYSTEM: {self.personality}

TASK: The user said "{user_text}" to end the session. Generate a short, friendly, natural farewell (1 short sentence max) relevant to what they said.
Examples: 
User: "Goodnight" -> "Sleep well!"
User: "Bye" -> "See you later!"
User: "Stop" -> "Stopping now."
Do not include any other text, just the farewell.
"""
        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"LLM farewell generation error: {e}")
            return "Goodbye!"
