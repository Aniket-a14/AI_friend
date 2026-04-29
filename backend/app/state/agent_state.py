import logging
import inspect
import math
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List
from datetime import datetime
from ..config import Config

logger = logging.getLogger(__name__)

@dataclass
class AgentState:
    """Multidimensional state for human-like dynamics."""
    mood: float = 0.0          # Valence: -1.0 to 1.0
    energy: float = 0.8        # Arousal: 0.0 to 1.0
    trust: float = 0.5         # 0.0 to 1.0
    attachment: float = 0.1    # 0.0 to 1.0
    active_goals: List[str] = field(default_factory=list)
    last_update: datetime = field(default_factory=datetime.now)
    last_user_interaction: float = field(default_factory=time.time)  # Unix timestamp


class StateService:
    """Manages Internal State continuity and Neo4j persistence."""
    def __init__(self, graph_store=None):
        self.graph = graph_store
        self.current_state = AgentState()
        self.last_speculative_intent = None # Transient sensory state
        
        self.alpha_mood = 0.05      # Slower mood decay for idle
        self.gamma_energy = 0.02   # Slower energy decay
        self.trust_baseline = 0.5  # Neutral trust target
        self.sensory_weight = getattr(Config, "STATE_SENSORY_WEIGHT", 0.20)
        self.min_perception_confidence = getattr(Config, "MIN_PERCEPTION_CONFIDENCE", 0.55)
        self.sensory_persist_interval = getattr(Config, "STATE_SENSORY_PERSIST_INTERVAL", 2.0)
        self._last_sensory_persist = 0.0
        self._last_proactive_attempt = 0.0  # Unix timestamp of last proactive generation

    async def hydrate_state(self, agent_name: str = "my friend"):
        """Loads state from Neo4j."""
        if not self.graph:
            return
            
        logger.info(f"[State] Hydrating {agent_name} from Neo4j...")
        query = "MATCH (a:Agent {name: $name}) RETURN a"
        # Agent state must reflect the latest write, not a TTL-delayed cache snapshot.
        res = await self.graph.execute_query(query, {"name": agent_name}, use_cache=False)
        if res:
            props = res[0]["a"]
            self.current_state.mood = props.get("mood", 0.0)
            self.current_state.energy = props.get("energy", 0.8)
            self.current_state.trust = props.get("trust", 0.5)
            self.current_state.attachment = props.get("attachment", 0.1)

    async def persist_state(self, agent_name: str = "my friend"):
        """Saves current state to Neo4j."""
        if not self.graph:
            return
            
        query = """
        MERGE (a:Agent {name: $name})
        SET a.mood = $mood,
            a.energy = $energy,
            a.trust = $trust,
            a.attachment = $attachment,
            a.last_sync = datetime()
        """
        params = {
            "name": agent_name,
            "mood": self.current_state.mood,
            "energy": self.current_state.energy,
            "trust": self.current_state.trust,
            "attachment": self.current_state.attachment
        }
        await self.graph.execute_query(query, params)
        if hasattr(self.graph, "invalidate_cache"):
            cache_invalidation = self.graph.invalidate_cache(agent_name)
            if inspect.isawaitable(cache_invalidation):
                await cache_invalidation
        logger.debug(f"[State] Persisted to Neo4j: Mood={self.current_state.mood:.2f}")

    def record_user_interaction(self):
        """Mark that the user just interacted. Called by BrainAgent on every chat.input."""
        self.current_state.last_user_interaction = time.time()

    async def update_from_event(self, event_valence: float, user_trust_delta: float = 0.0):
        """
        Cognitive Update (0.7 weight).
        Triggered after LLM sentiment analysis or explicit user actions.
        """
        now = datetime.now()
        
        # Track that the user is actively interacting
        self.current_state.last_user_interaction = time.time()
        
        # Apply Cognitive Weight (0.7)
        self.current_state.mood = (self.current_state.mood * 0.3) + (event_valence * 0.7)
        
        self.current_state.trust = max(0.0, min(1.0, self.current_state.trust + user_trust_delta))
        self.current_state.attachment += user_trust_delta * 0.1
        self.current_state.energy -= 0.02
        
        self.current_state.last_update = now
        self._enforce_bounds()
        await self.persist_state()

    async def apply_sensory_perception(self, perception_metadata: Dict[str, Any]):
        """
        Acoustic Perception Update (confidence-scaled low weight).
        Triggered by SenseVoice emotional/event cues.
        """
        emotion_bias = perception_metadata.get("emotional_bias", 0.0)
        confidence = perception_metadata.get("confidence", 1.0)
        events = perception_metadata.get("events", [])

        if confidence < self.min_perception_confidence and not events:
            logger.debug(
                "[State] Ignored low-confidence acoustic perception: %.2f",
                confidence,
            )
            return
        
        # 1. Apply confidence-scaled emotional bias. Acoustic emotion is useful,
        # but should not dominate semantic state over repeated 400ms chunks.
        weight = self.sensory_weight * max(0.0, min(1.0, confidence))
        self.current_state.mood = (
            self.current_state.mood * (1 - weight)
        ) + (emotion_bias * weight)
        
        # 2. Map Acoustic Events (AED)
        for event in events:
            if event == "Laughter":
                self.current_state.energy = min(1.0, self.current_state.energy + 0.15)
                self.current_state.trust = min(1.0, self.current_state.trust + 0.05)
                logger.info("😄 Agent sensed laughter - Energy/Trust boosted.")
            elif event == "Applause":
                self.current_state.energy = min(1.0, self.current_state.energy + 0.2)
                logger.info("👏 Agent sensed applause - Energy spike.")
            elif event in ["Cough", "Sneeze"]:
                self.current_state.attachment = min(1.0, self.current_state.attachment + 0.02)
                logger.debug(f"🤧 Agent sensed {event} - Attachment nudged (Empathy).")
        
        self._enforce_bounds()
        await self._persist_sensory_state_if_due()

    async def handle_system_tick(self, tick_metadata: Dict[str, Any]):
        """
        Idle evolution triggered by NATS system.tick.
        Metadata: {timestamp, uptime, interval}
        """
        now = tick_metadata.get("timestamp", time.time())
        dt_hours = tick_metadata.get("interval", 60) / 3600.0
        
        self.current_state.mood *= math.exp(-self.alpha_mood * dt_hours)
        self.current_state.energy = min(1.0, self.current_state.energy + (self.gamma_energy * dt_hours))
        
        trust_drift = (self.trust_baseline - self.current_state.trust) * 0.01
        self.current_state.trust += trust_drift
        
        self.current_state.last_update = datetime.fromtimestamp(now)
        self._enforce_bounds()
        await self.persist_state()
        logger.debug(f"[State Heartbeat] Mood: {self.current_state.mood:.3f}")

    def check_proactive_eligibility(self) -> bool:
        """
        Phase 1: Proactive Engagement.
        Evaluates whether the agent should spontaneously initiate contact.
        Returns True only when ALL conditions are met:
          1. Proactive feature is enabled
          2. Idle duration exceeds threshold
          3. Cooldown period has elapsed since last proactive attempt
          4. Agent has enough energy (not exhausted)
        """
        if not getattr(Config, "PROACTIVE_ENABLED", False):
            return False

        now = time.time()

        # Resolve the effective threshold (debug override takes priority)
        debug_override = getattr(Config, "PROACTIVE_DEBUG_THRESHOLD_OVERRIDE", None)
        if debug_override is not None:
            try:
                threshold = float(debug_override)
            except (TypeError, ValueError):
                threshold = Config.PROACTIVE_IDLE_THRESHOLD_SECONDS
        else:
            threshold = Config.PROACTIVE_IDLE_THRESHOLD_SECONDS

        idle_duration = now - self.current_state.last_user_interaction
        if idle_duration < threshold:
            return False

        # Cooldown: don't re-trigger if we already spoke proactively recently
        cooldown = getattr(Config, "PROACTIVE_COOLDOWN_SECONDS", 3600)
        if (now - self._last_proactive_attempt) < cooldown:
            return False

        # Energy gate: too tired to initiate
        min_energy = getattr(Config, "PROACTIVE_MIN_ENERGY", 0.2)
        if self.current_state.energy < min_energy:
            logger.debug(
                "[State] Proactive SKIPPED: energy %.2f < min %.2f",
                self.current_state.energy, min_energy,
            )
            return False

        logger.info(
            "[State] Proactive ELIGIBLE: idle=%.0fs threshold=%.0fs energy=%.2f",
            idle_duration, threshold, self.current_state.energy,
        )
        return True

    def mark_proactive_attempt(self):
        """Record that a proactive generation was initiated."""
        self._last_proactive_attempt = time.time()

    def _enforce_bounds(self):
        self.current_state.mood = max(-1.0, min(1.0, self.current_state.mood))
        self.current_state.energy = max(0.0, min(1.0, self.current_state.energy))
        self.current_state.trust = max(0.0, min(1.0, self.current_state.trust))
        self.current_state.attachment = max(0.0, min(1.0, self.current_state.attachment))

    def get_context_snapshot(self) -> Dict[str, Any]:
        return {
            "emotion": self.get_emotion_label(),
            "mood": self.current_state.mood,
            "energy": self.current_state.energy,
            "trust": self.current_state.trust,
            "attachment": self.current_state.attachment,
            "active_goals": self.current_state.active_goals
        }

    def get_behavioral_directive(self) -> str:
        """Translates internal state into a natural language directive for the LLM."""
        mood = self.current_state.mood
        energy = self.current_state.energy
        trust = self.current_state.trust
        
        if mood < -0.6:
            direct = "You are feeling deeply melancholic and reserved."
        elif mood > 0.6:
            direct = "You are in a vibrant, optimistic state."
        else:
            direct = "You are grounded and emotionally stable."
            
        if energy < 0.3:
            direct += " Your energy is low; keep replies brief and pacing slow."
        elif energy > 0.8:
            direct += " You are high-energy; use expressive, dynamic language."
            
        if trust < 0.3:
            direct += " You are feeling skeptical and maintaining boundaries."
        elif trust > 0.8:
            direct += " You feel a deep, familiar bond with the user."
            
        return direct

    def get_emotion_label(self) -> str:
        mood = self.current_state.mood
        if mood > 0.4:
            return "happy"
        if mood < -0.4:
            return "sad"
        if self.current_state.energy > 0.8:
            return "excited"
        return "neutral"

    async def _persist_sensory_state_if_due(self):
        now = time.time()
        if now - self._last_sensory_persist < self.sensory_persist_interval:
            return
        self._last_sensory_persist = now
        await self.persist_state()
