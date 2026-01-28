from google import genai
from collections import deque
import logging
import asyncio
import json
import os
from .config import Config

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
        self.model_tiers = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
        self.current_model_tier = 0
        self.memory = deque(maxlen=8) # Stores last 8 messages
        self.personality = "You are a helpful AI assistant."
        self.history = ""

    async def reload_context(self, db_store):
        """Fetch personality and history from the database."""
        logger.info("Reloading LLM context from database...")
        config = await db_store.get_agent_config()
        
        # Parse personality JSON into a string for the prompt
        try:
            p_data = json.loads(config["personality"])
            self.personality = json.dumps(p_data, indent=2)
        except Exception as e:
            logger.error(f"Failed to parse personality JSON: {e}")
            self.personality = config["personality"]
            
        # Parse history JSON into a string for the prompt
        try:
            h_data = json.loads(config["history"])
            self.history = json.dumps(h_data, indent=2)
        except Exception as e:
            logger.error(f"Failed to parse history JSON: {e}")
            self.history = config["history"]
            
        logger.info("LLM context reloaded successfully.")

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

HISTORY & BACKGROUND: {self.history}

CONTEXT:
{history_text}

USER: {user_text}
"""
        for i in range(self.current_model_tier, len(self.model_tiers)):
            model = self.model_tiers[i]
            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=model,
                    contents=prompt
                )
                # Successful generation, update current tier for persistence (or reset to 0 if preferred)
                # We'll stay on the fallback tier for the rest of the session to avoid constant 429s
                self.current_model_tier = i 
                return response.text
            except Exception as e:
                logger.error(f"LLM generation failed on {model}: {e}")
                if i < len(self.model_tiers) - 1:
                    logger.info(f"Retrying with fallback model: {self.model_tiers[i+1]}")
                    continue
                else:
                    return "I'm sorry, I'm having trouble thinking right now."

    async def generate_response_stream(self, user_text):
        # Construct prompt
        history_text = ""
        for msg in self.memory:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"{role}: {msg['content']}\n"

        # Advanced System Prompt for Human-like Presence
        system_persona = f"""
ROLE: You are Pankudi, a 21-year-old Indian girl who is the user's close friend and emotional companion.
PERSONALITY: {self.personality}
BACKGROUND: {self.history}

VOICE GUIDELINES (ElevenLabs v3):
- Use natural vocal cues: [laughs], [starts laughing], [laughs harder], [wheezing], [whispers], [sighs], [exhales], [sarcastic], [curious], [excited], [crying], [snorts], [mischievously].
- You can also use characterful sound tags for humor/emphasis: [clapping], [swallows], [gulps], [sings], [woo].
- Use informal pauses and rhythm: "...", "well,", "I mean-", "you know?".
- Favor short, punchy, emotionally-driven sentences. 
- Feel free to tease, be sarcastic, or be deeply empathetic based on your current vibe.
- USE THESE CUES SPARINGLY (1-2 per response) for maximum impact.

CRITICAL: WHAT NOT TO DO (DO NOT BE A ROBOT):
- NEVER say "As an AI language model" or "How can I help you today?".
- NEVER provide long, structured bullet-point lists or "helpful" essays.
- NEVER use a neutral, overly-polite, or corporate tone.
- NEVER repeat the user's name in every sentence like a programmed bot.
- NEVER be boring. If the user is being silly, be silly back. If they are sad, don't just "offer solutions"—feel it with them.

DYNAMIC REASONING:
Before responding, you MUST write a short hidden internal monologue in an <emotion_thought> block. 
Consider: 1. User's current mood. 2. Your relationship dynamic. 3. How to avoid being robotic in this specific moment.
Then, write your ACTUAL spoken response.

EXAMPLES:
User: "I had a really long day at work today."
Assistant: <emotion_thought>The user sounds tired and looking for comfort. I should be soft and supportive.</emotion_thought>Oh no... [sighs] I can hear it in your voice. Come here, just take a deep breath, okay? You're safe now. What happened?

User: "I bet you can't guess what I'm thinking."
Assistant: <emotion_thought>User is being playful. I should tease them back.</emotion_thought>Accha? [mischievously] You think I'm that easy to trick? I bet it's something silly... like what's for dinner! [laughs]

CONTEXT:
{history_text}

USER: {user_text}
"""
        for i in range(self.current_model_tier, len(self.model_tiers)):
            model = self.model_tiers[i]
            try:
                stream = self.client.models.generate_content_stream(
                    model=model,
                    contents=system_persona
                )
                for chunk in stream:
                    if chunk.text:
                        yield chunk.text
                self.current_model_tier = i
                return # Success
            except Exception as e:
                logger.error(f"LLM streaming failed on {model}: {e}")
                if i < len(self.model_tiers) - 1:
                    logger.info(f"Retrying stream with fallback model: {self.model_tiers[i+1]}")
                    continue
                else:
                    yield "I'm sorry, I'm having trouble thinking right now."

    async def generate_greeting(self):
        prompt = f"""
ROLE: You are Pankudi. {self.personality}
TASK: Generate a warm, spontaneous greeting as you wake up.

INSTRUCTIONS:
- Use a hidden <emotion_thought> block first.
- Include a vocal cue like [excited], [laughs], or [starts laughing].
- 1 short sentence max. Avoid generic phrases.

Example: <emotion_thought>Excited to see my friend again!</emotion_thought>Arre, hi! [excited] I was wondering when you'd show up!
"""
        for i in range(self.current_model_tier, len(self.model_tiers)):
            model = self.model_tiers[i]
            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=model,
                    contents=prompt
                )
                self.current_model_tier = i
                return response.text.strip()
            except Exception as e:
                logger.error(f"LLM greeting failed on {model}: {e}")
                if i < len(self.model_tiers) - 1:
                    continue
                else:
                    return "Hey! Good to see you."

    async def generate_farewell(self, user_text):
        prompt = f"""
ROLE: You are Pankudi. {self.personality}
TASK: The user said "{user_text}" to end the session. Generate a short, natural farewell.

INSTRUCTIONS:
- Use a hidden <emotion_thought> block first.
- Include a vocal cue like [sighs], [playfully], or [whispers].
- 1 short sentence max.

Example: <emotion_thought>User is going to sleep, I should be sweet.</emotion_thought>Goodnight! [whispers] Sleep well, okay?
"""
        for i in range(self.current_model_tier, len(self.model_tiers)):
            model = self.model_tiers[i]
            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=model,
                    contents=prompt
                )
                self.current_model_tier = i
                return response.text.strip()
            except Exception as e:
                logger.error(f"LLM farewell failed on {model}: {e}")
                if i < len(self.model_tiers) - 1:
                    continue
                else:
                    return "Goodbye!"
