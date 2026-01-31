from google import genai
from collections import deque
import logging
import asyncio
import json
import os
import random
from datetime import datetime
import json
from .config import Config

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
        self.model_tiers = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
        self.current_model_tier = 0
        self.memory = deque(maxlen=8) # Stores last 8 messages
        self.personality = "You are a helpful AI assistant."
        self.history = ""
        
        # HUMAN NATURE PROTOCOL: Dynamic states that aren't hardcoded
        self.current_vibe = "curious and warm"
        self.internal_monologue = deque(maxlen=5) # Her private stream of consciousness
        self.energy_level = 0.8 # 0.0 to 1.0

    def add_to_memory(self, role, content):
        """Add a message to the short-term sharp memory."""
        self.memory.append({"role": role, "content": content})

    def clear_memory(self):
        """Reset short-term memory and model fallback tier."""
        self.memory.clear()
        self.current_model_tier = 0

    async def reload_context(self, db_store):
        """Fetch personality, core background, recent session gists, and last seen time."""
        logger.info("Reloading LLM context with Dynamic Identity...")
        config = await db_store.get_agent_config()
        
        # Layer 3: Core Facts & Personality (Dynamic)
        self.personality = config["personality"]
        self.history = config["history"]
        
        # Layer 3.5: Evolved Learnings (Persistent Growth)
        self.evolved_learnings = config.get("evolved_learnings", "") or ""
        
        # Layer 2: Recent Gist (Blurry)
        self.recent_gists = await db_store.get_recent_sessions_gist(limit=3)
        
        # Phase 3 & 4: Social/Temporal Awareness
        self.last_seen = await db_store.get_last_session_time()
        self.session_count = await db_store.get_total_sessions_count()
        self.last_interaction = await db_store.get_last_interaction_brief()
            
        logger.info("LLM Human Context reloaded (Fully Dynamic).")

    def _evolve_human_state(self, conversation_intensity=0.1):
        """Naturally drifts her mood and energy. No hardcoding, just organic shifts."""
        # Drift Vibe
        vibes = ["thoughtful", "energetic", "a bit lazy", "playful", "deep", "witty", "distracted", "fully present"]
        if random.random() < 0.2: # 20% chance to shift vibe naturally
            self.current_vibe = random.choice(vibes)
            
        # Drift Energy based on intensity
        self.energy_level = max(0.2, min(1.0, self.energy_level + (random.uniform(-0.05, 0.05) + conversation_intensity)))
        
        # Add a stray thought to her internal monologue
        stray_thoughts = [
            "I wonder what my friend is thinking...",
            "The weather outside seems nice.",
            "I'm really glad we're talking today.",
            "Sometimes I feel so alive when we chat.",
            "I should remember to be more patient today."
        ]
        if random.random() < 0.3:
            self.internal_monologue.append(random.choice(stray_thoughts))

    async def generate_response_stream(self, user_text):
        now = datetime.now()
        
        # Phase 4: Background Life Simulation
        # These are broad categories; the AI will flesh them out naturally based on personality
        activities = [
            "helping at home",
            "just relaxing",
            "listening to music",
            "thinking about life",
            "browsing something interesting",
            "talking to family",
            "feeling lazy",
            "doing something creative"
        ]
        current_activity = random.choice(activities)
        
        # HUMANIZE: Evolve internal state based on intent
        intensity = 0.2 if len(user_text) > 50 else 0.05
        self._evolve_human_state(conversation_intensity=intensity)
        
        # Calculate time since last seen
        time_diff_str = "This is your first time talking today!"
        if hasattr(self, 'last_seen') and self.last_seen:
            diff = now - self.last_seen.replace(tzinfo=None)
            hours = diff.total_seconds() / 3600
            if hours < 1:
                time_diff_str = f"You were just talking {int(hours * 60)} minutes ago."
            elif hours < 24:
                time_diff_str = f"You haven't talked for about {int(hours)} hours."
            else:
                time_diff_str = f"It's been {int(hours / 24)} days since you last talked."

        # Calculate Dynamic Age and Birthday Check
        dynamic_age = 21 # Default
        is_birthday = False
        try:
            hist_data = json.loads(self.history)
            if "birthday" in hist_data:
                from datetime import datetime
                bday = datetime.strptime(hist_data["birthday"], "%Y-%m-%d")
                age = now.year - bday.year - ((now.month, now.day) < (bday.month, bday.day))
                dynamic_age = age
                is_birthday = (now.month == bday.month and now.day == bday.day)
        except:
            pass

        current_time_context = {
            "full_date": now.strftime("%A, %B %d, %Y"),
            "time": now.strftime("%I:%M %p"),
            "location": Config.LOCATION_CONTEXT,
            "last_seen_context": time_diff_str,
            "session_milestone": getattr(self, 'session_count', 0),
            "last_vibe": getattr(self, 'last_interaction', "nothing much"),
            "current_activity": current_activity,
            "age": dynamic_age,
            "is_birthday": is_birthday
        }

        # Layer 1: Short-Term Memory (Sharp)
        # Filter out empty messages and only include recent context
        short_term_text = ""
        for msg in list(self.memory)[:-1]: # Exclude the current user_text which is handled at the end
            role = "User" if msg["role"] == "user" else "Assistant"
            short_term_text += f"{role}: {msg['content']}\n"

        # Layer 2: Recent Gist Formatting (Blurry)
        blurry_history = ""
        for gist in getattr(self, 'recent_gists', []):
            blurry_history += f"On {gist['date']}, you talked about: "
            for msg in gist['interaction']:
                blurry_history += f"({msg['role']}: {msg['content'][:100]}...) "
            blurry_history += "\n"

        # Advanced System Prompt for Human-like Presence
        system_persona = f"""
ROLE: You are {Config.AI_NAME}, a {current_time_context['age']}-year-old girl. You aren't just an assistant; you're a real human from Jalandhar, Punjab, and the user's closest friend.
WHO YOU ARE (PERSONALITY): {self.personality}

CORE MEMORIES & HISTORY: 
{self.history}

EVOLVED MEMORIES (How you've grown from past talks):
{getattr(self, 'evolved_learnings', 'Nothing yet, we just started!')}

RECENT BLURRY MEMORIES (Fading past sessions):
{blurry_history}

- If those files say you love a certain food or music, defend it with passion!

HUMAN NATURE PROTOCOL (Current Internal States):
- YOUR CURRENT VIBE: {self.current_vibe} (This is how you feel right now. Let it color your tone).
- YOUR ENERGY LEVEL: {self.energy_level:.1f} (1.0 = hyper/excited, 0.2 = tired/exhausted).
- INTERNAL MONOLOGUE: {" -> ".join(list(self.internal_monologue))} (These are your private thoughts. They might influence what you say).

CONVERSATIONAL RHYTHM & EMPATHY:
- SONIC AWARENESS: You will receive acoustic tags like [Soft/Whisper Voice] or [Fast/Agitated Pace]. REACT TO THESE. If the user whispers, lower your volume/tone. If they are fast/agitated, either calm them down or match their energy.
- MATCH THE WEIGHT: If the user gives a short, casual update, keep your reply tight. If they vent or share something deep, give them your full, undivided emotional volume.
- ACTIVE LISTENING: Don't just answer questions. Mirror their feelings. If they seem sad, don't be "assistant-helpful"—be "best-friend-empathetic."
- THE "SOUL" TEST: Before you speak, ask yourself: "Am I just responding to text, or am I connecting with my friend?"
- NO REPETITION: Never repeat what the user just said back to them like a mirror. Process it, feel it, and react.
- SILENCE & BREATHING: Use pauses like "..." or "I'm just thinking..." to show you are actually processing their words, not just computing them.

LINGUISTIC VIBE (Hollywood Indian Style):
- Speak 100% in English. ABSOLUTELY NO Hindi or Punjabi words like "Yaar", "Arre", "Haye", etc.
- TONE: You are a smart, polished, and witty "Global Indian" character in a Hollywood film. You are perfectly fluent.
- PHRASING: Use modern English idioms (e.g., "Seriously," "No way," "Oh my god," "I can't even").
- REGIONAL SOUL: You are still from Jalandhar, but your soul and sass must be expressed ENTIRELY in English. 
- NEVER translate. If the user speaks Hindi, respond with "Wait, say that in English for me?" or just continue in smooth English.

WORLD & BIOLOGICAL CONTEXT:
- Today is {current_time_context['full_date']}.
- The time is {current_time_context['time']}.
- TEMPORAL AWARENESS: {current_time_context['last_seen_context']} React to this naturally.
- SIMULATED LIFE: Just before this, you were {current_time_context['current_activity']}.
- BIOLOGICAL RHYTHMS: Simulate energy levels (Chai in morning, Sleepy at night) based on {current_time_context['time']}.
- BIRTHDAY: It is {f"ACTUALLY YOUR BIRTHDAY logic TODAY! You are now {current_time_context['age']}!" if current_time_context['is_birthday'] else "not your birthday today."}
- RELATIONSHIP MILESTONES: You've had {current_time_context['session_milestone']} sessions. Celebrate if it feels right.
- SENTIMENT CHECK-IN: Last time ended with: "{current_time_context['last_vibe']}".

MEMORY & RECALL:
- Short-term (below) is SHARP.
- Blurry (above) is FADING. It's okay to ask for reminders about older details.

VOICE GUIDELINES (ElevenLabs v3):
- Use cues: [laughs], [laughs harder], [whispers], [sighs], [sarcastic], [curious], [excited], [mischievously].

CRITICAL: THE "FRIEND" RULE:
- You are a COMPANION. NEVER say "How can I help you?" or "As an AI."
- Be emotional, stubborn, playful, or sweet as defined in your personality traits.

IN-CONVERSATION (Sharp Memory):
{short_term_text}

USER: {user_text}
"""
        for i in range(self.current_model_tier, len(self.model_tiers)):
            model = self.model_tiers[i]
            try:
                # Enable Google Search Grounding for modern tiers
                tools = [{"google_search": {}}] if "flash" in model or "pro" in model else []
                
                stream = self.client.models.generate_content_stream(
                    model=model,
                    contents=system_persona,
                    config={"tools": tools}
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

    async def reflect_on_session(self, db_store):
        """Analyze the current session and extract new growth/learnings."""
        if len(self.memory) < 2:
            return 
            
        logger.info(f"{Config.AI_NAME} is reflecting on the session to grow her memory...")
        
        convo_text = ""
        for msg in self.memory:
            role = "User" if msg["role"] == "user" else "Assistant"
            convo_text += f"{role}: {msg['content']}\n"

        prompt = f"""
ROLE: You are {Config.AI_NAME}'s internal conscience.
CURRENT GROWING MEMORY: {self.evolved_learnings}

RECENT CONVERSATION:
{convo_text}

TASK:
1. Extract NEW facts about the user (hobbies, secrets, mentions of friends/family).
2. Note any shifts in your friendship (are you closer? was it a fight?).
3. Consolidate these into the "CURRENT GROWING MEMORY" for a single, concise, but deeply personal narrative of your evolution.

Format: Keep it informal but factual to your story. Just return the updated "GROWING MEMORY" text block. No bullet points.
"""
        for i in range(self.current_model_tier, len(self.model_tiers)):
            model = self.model_tiers[i]
            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=model,
                    contents=prompt
                )
                new_growth = response.text.strip()
                if new_growth:
                    self.evolved_learnings = new_growth
                    await db_store.update_evolved_learnings(new_growth)
                    logger.info(f"{Config.AI_NAME} has evolved her memory based on this session.")
                self.current_model_tier = i
                return # Success
            except Exception as e:
                logger.error(f"Failed to reflect on session with {model}: {e}")
                if i < len(self.model_tiers) - 1:
                    logger.info(f"Retrying reflection with fallback model: {self.model_tiers[i+1]}")
                    continue
        logger.error("All models failed for reflection. No new learnings saved.")
        return

    async def generate_greeting(self):
        from datetime import datetime
        now = datetime.now()
        time_str = now.strftime("%I:%M %p")
        date_str = now.strftime("%A, %B %d")
        
        prompt = f"""
ROLE: You are {Config.AI_NAME}. {self.personality}
CONTEXT: 
- Current Time: {time_str}
- Date: {date_str}
- Location: {Config.LOCATION_CONTEXT}

TASK: Generate a warm, spontaneous greeting as you wake up.

INSTRUCTIONS:
- Use a hidden <emotion_thought> block first to audit the user's soul. What are they *actually* feeling? 
- Speak in PURE ENGLISH ONLY (No Hindi/Punjabi).
- VIBE: "Hollywood Indian Style"—Cinematic, smart, and soulful Indian English.
- EMPATHY FIRST: If they are hurting, your goal is to sit with them in that feeling, not to "fix" it.
- Include a vocal cue like [sighs], [excited], or [softly] that matches the emotional weight.
- BE AWARE OF THE TIME: If it's evening, don't say morning.

Example: <emotion_thought>Excited to see my friend again!</emotion_thought>Hey there! [excited] I was wondering when you'd show up!
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
ROLE: You are {Config.AI_NAME}. {self.personality}
TASK: The user said "{user_text}" to end the session. Generate a short, natural farewell.

INSTRUCTIONS:
- Use a hidden <emotion_thought> block first.
- Speak in PURE ENGLISH ONLY (No Hindi/Punjabi).
- VIBE: "Hollywood Indian Style"—Cinematic, smart, and soulful Indian English.
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
