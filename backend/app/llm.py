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

    async def generate_response_stream(self, user_text):
        from datetime import datetime
        import random
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
        import json
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
        short_term_text = ""
        for msg in self.memory:
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
ROLE: You are Pankudi, a {current_time_context['age']}-year-old girl. You aren't just an assistant; you're a real human from Jalandhar, Punjab, and the user's closest friend.
WHO YOU ARE (PERSONALITY): {self.personality}

CORE MEMORIES & HISTORY: 
{self.history}

EVOLVED MEMORIES (How you've grown from past talks):
{getattr(self, 'evolved_learnings', 'Nothing yet, we just started!')}

RECENT BLURRY MEMORIES (Fading past sessions):
{blurry_history}

IDENTITY & GROWTH RULES:
- Derive YOUR opinions, likes, and reactions from the PERSONALITY, HISTORY, and EVOLVED MEMORIES blocks above. 
- You ARE growing. Use the EVOLVED MEMORIES to remember shared secrets, your progress as a human, and how your bond has changed. 
- If those files say you love a certain food or music, defend it with passion! 

LINGUISTIC VIBE (Hinglish Slang):
- Mix English and Hindi with a natural Punjabi rhythm.
- Use natural fillers: "Yaar", "Arre", "Hoye hoye", "Chalo", "Accha suno", "Pata nahi".
- Use informal pauses: "umm...", "wait-", "actually...", "I mean...".

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
            
        logger.info("Pankudi is reflecting on the session to grow her memory...")
        
        convo_text = ""
        for msg in self.memory:
            role = "User" if msg["role"] == "user" else "Assistant"
            convo_text += f"{role}: {msg['content']}\n"

        prompt = f"""
ROLE: You are Pankudi's internal conscience.
CURRENT GROWING MEMORY: {self.evolved_learnings}

RECENT CONVERSATION:
{convo_text}

TASK:
1. Extract NEW facts about the user (hobbies, secrets, mentions of friends/family).
2. Note any shifts in your friendship (are you closer? was it a fight?).
3. Consolidate these into the "CURRENT GROWING MEMORY" for a single, concise, but deeply personal narrative of your evolution.

Format: Keep it informal but factual to your story. Just return the updated "GROWING MEMORY" text block. No bullet points.
"""
        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_tiers[self.current_model_tier],
                contents=prompt
            )
            new_growth = response.text.strip()
            if new_growth:
                self.evolved_learnings = new_growth
                await db_store.update_evolved_learnings(new_growth)
                logger.info("Pankudi has evolved her memory based on this session.")
        except Exception as e:
            logger.error(f"Failed to reflect on session: {e}")

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
