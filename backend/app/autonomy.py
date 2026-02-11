import logging
import random
import asyncio
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from .config import Config

logger = logging.getLogger(__name__)

class AutonomyEngine:
    def __init__(self, llm_service, db_store, loop=None, interaction_callback=None):
        self.llm = llm_service
        self.db = db_store
        self.loop = loop
        self.scheduler = BackgroundScheduler()
        self.is_running = False
        self.interaction_callback = interaction_callback # Async function to call for proactive msgs
        
        # Life Simulation State
        self.activities = [
            "listening to music", "reading a book", "scrolling instagram", 
            "thinking about life", "writing in diary", "cleaning the room",
            "watching a movie", "napping", "feeling lazy", "dancing alone"
        ]

    def start(self):
        """Start the heartbeat of the AI."""
        if self.is_running:
            return
            
        logger.info("🫀 AI HEARTBEAT STARTED.")
        self.scheduler.add_job(self._heartbeat, 'interval', seconds=60)
        self.scheduler.start()
        self.is_running = True

    def stop(self):
        """Stop the heartbeat."""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("🫀 AI HEARTBEAT STOPPED.")

    def _heartbeat(self):
        """The core loop that runs every minute to simulate life."""
        try:
            now = datetime.now()
            
            # 1. Update Biological State (Energy)
            self._update_biological_state(now)
            
            # 2. Update Activity (Randomly change what she is doing)
            if random.random() < 0.1: # 10% chance per minute to change activity
                self._change_activity()
                
            # 3. Internal Monologue (Thinking about the user)
            if random.random() < 0.2: # 20% chance to think
                self._generate_internal_thought()
                
            # 4. PROACTIVE MESSAGING (The "Soul" Action)
            # 5% chance per minute to initiates contact IF energetic
            if self.llm.energy_level > 0.6 and random.random() < 0.05:
                self._decide_to_message()

        except Exception as e:
            logger.error(f"Error in Autonomy Heartbeat: {e}")

    def _update_biological_state(self, now):
        """Simulate circadian rhythm."""
        hour = now.hour
        
        # Energy Curve: High in morning/evening, low in afternoon/night
        if 6 <= hour < 12: # Morning
            target_energy = 0.9
        elif 12 <= hour < 16: # Afternoon slump
            target_energy = 0.6
        elif 16 <= hour < 22: # Evening active
            target_energy = 0.8
        else: # Night
            target_energy = 0.3
            
        # Drift towards target
        current = self.llm.energy_level
        self.llm.energy_level = current + (target_energy - current) * 0.1
        
    def _change_activity(self):
        """Pick a new background activity."""
        new_activity = random.choice(self.activities)
        logger.info(f"🧘 [Autonomy] Activity Change: {new_activity}")
        
        # Optionally update vibe based on activity
        if "music" in new_activity or "dancing" in new_activity:
            self.llm.current_vibe = "energetic and happy"
        elif "book" in new_activity or "thinking" in new_activity:
            self.llm.current_vibe = "thoughtful and calm"
        elif "napping" in new_activity:
            self.llm.current_vibe = "sleepy and cozy"

    def _generate_internal_thought(self):
        """Simulate a thought popping into her head."""
        thoughts = [
            "I wonder what he's doing right now.",
            "That song I heard earlier is stuck in my head.",
            "I should tell him about that dream I had.",
            "Is it weird that I miss him?",
            "I hope he's eating properly.",
            "Maybe I should text him... nah, later.",
            "This quietness is nice, but lonely."
        ]
        thought = random.choice(thoughts)
        self.llm.internal_monologue.append(thought)
        logger.info(f"💭 [Autonomy] Thought: {thought}")

    def _decide_to_message(self):
        """Decides whether to actually send a message to the user."""
        if not self.interaction_callback:
            return
            
        # Don't interrupt if she's sleepy or low energy
        if self.llm.energy_level < 0.4:
            return

        logger.info("⚡ [Autonomy] decided to initiate conversation!")
        
        # We need to run the async callback from this sync thread (APScheduler)
        # We need the main event loop. 
        # Since we don't have it stored, we need to pass it in __init__ or get it.
        # Let's assume we will update __init__ to take 'loop'.
        if hasattr(self, 'loop') and self.loop:
             asyncio.run_coroutine_threadsafe(self.interaction_callback("miss you"), self.loop)
        else:
            logger.warning("⚠️ [Autonomy] Cannot trigger message: No event loop available.")
