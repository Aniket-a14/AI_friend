import logging
import math
from dataclasses import dataclass, field
from typing import Dict, Any, List
from datetime import datetime

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

class StateService:
    """Manages Internal State continuity and Neo4j persistence."""
    def __init__(self, graph_store=None):
        self.graph = graph_store
        self.current_state = AgentState()
        
        self.alpha_mood = 0.1      # Mood decay rate
        self.gamma_energy = 0.05   # Energy decay rate

    async def hydrate_state(self, agent_name: str = "my friend"):
        """Loads state from Neo4j."""
        if not self.graph:
            return
            
        logger.info(f"[State] Hydrating {agent_name} from Neo4j...")
        query = "MATCH (a:Agent {name: $name}) RETURN a"
        res = await self.graph.execute_query(query, {"name": agent_name})
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
        logger.debug(f"[State] Persisted to Neo4j: Mood={self.current_state.mood:.2f}")

    async def update_from_event(self, event_valence: float, user_trust_delta: float = 0.0):
        now = datetime.now()
        dt = (now - self.current_state.last_update).total_seconds() / 3600.0
        
        # 1. Evolution
        self.current_state.mood = (self.current_state.mood * math.exp(-self.alpha_mood * dt) + 
                                   event_valence * (1 - math.exp(-self.alpha_mood * dt)))
        
        self.current_state.trust = max(0.0, min(1.0, self.current_state.trust + user_trust_delta))
        self.current_state.attachment += user_trust_delta * 0.1
        self.current_state.energy -= 0.02
        
        self.current_state.last_update = now
        self._enforce_bounds()
        
        # 2. Persist
        await self.persist_state()

    async def evolve_idle(self, dt_hours: float):
        """Self-evolution and persistence."""
        self.current_state.mood *= math.exp(-self.alpha_mood * dt_hours)
        self.current_state.energy = min(1.0, self.current_state.energy + (0.1 * dt_hours))
        
        self._enforce_bounds()
        await self.persist_state()

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

    def get_emotion_label(self) -> str:
        mood = self.current_state.mood
        if mood > 0.4:
            return "happy"
        if mood < -0.4:
            return "sad"
        if self.current_state.energy > 0.8:
            return "excited"
        return "neutral"
