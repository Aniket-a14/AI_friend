"""
Agent State — PAD + Relational Framework (psychological_layer.md §2).

Affective dimensions: Valence (V), Arousal (Ar), Dominance (D)
  — Mehrabian & Russell (1974)

Relational dimensions: Trust (T), Attachment (At)
  — Marsh (1994) for trust, Bowlby for attachment

State updates: ALMA mood-pull + exponential decay (Gebhard, 2005)
"""

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List
from datetime import datetime
from ..config import Config

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AgentState:
    """
    Multidimensional PAD + Relational state for human-like dynamics.

    Backward compatibility: 'mood' and 'energy' are kept as the canonical
    dataclass field names. New PAD vocabulary is provided via properties.
    """

    # PAD Affective Dimensions (Mehrabian & Russell, 1974)
    mood: float = 0.0  # V (Valence): -1.0 to 1.0
    energy: float = 0.5  # Ar (Arousal): 0.0 to 1.0
    dominance: float = 0.5  # D (Dominance): 0.0 to 1.0 — NEW

    # Relational Dimensions
    trust_benevolence: float = 0.5  # Tb (Marsh): 0.0 to 1.0
    trust_competence: float = 0.5  # Tc (Marsh): 0.0 to 1.0
    trust_integrity: float = 0.5  # Ti (Marsh): 0.0 to 1.0
    attachment: float = 0.1  # At (Bowlby): 0.0 to 1.0

    # Interaction Tracking
    interaction_count: int = 0  # For Bowlby attachment frequency
    active_goals: List[str] = field(default_factory=list)
    last_update: datetime = field(default_factory=datetime.now)
    last_user_interaction: float = field(default_factory=time.time)
    fatigue: float = 0.0  # Metabolic fatigue cycle F(t)

    # --- PAD Property Aliases (§2.1) ---
    @property
    def valence(self) -> float:
        """PAD Valence (V) — maps to 'mood'."""
        return self.mood

    @valence.setter
    def valence(self, value: float):
        self.mood = value

    @property
    def arousal(self) -> float:
        """PAD Arousal (Ar) — maps to 'energy' + fatigue-induced restlessness."""
        fatigue_restlessness = 0.2 * self.fatigue
        return max(0.0, min(1.0, self.energy + fatigue_restlessness))

    @arousal.setter
    def arousal(self, value: float):
        self.energy = value

    @property
    def trust(self) -> float:
        """PAD Trust (T) — maps to average of Benevolence, Competence, and Integrity."""
        return (
            self.trust_benevolence + self.trust_competence + self.trust_integrity
        ) / 3.0

    @trust.setter
    def trust(self, value: Any):
        if isinstance(value, dict):
            self.trust_benevolence = float(
                value.get("trust_benevolence", self.trust_benevolence)
            )
            self.trust_competence = float(
                value.get("trust_competence", self.trust_competence)
            )
            self.trust_integrity = float(
                value.get("trust_integrity", self.trust_integrity)
            )
        elif isinstance(value, (list, tuple)) and len(value) == 3:
            self.trust_benevolence = float(value[0])
            self.trust_competence = float(value[1])
            self.trust_integrity = float(value[2])
        else:
            try:
                _ = float(value)
            except (ValueError, TypeError):
                pass

    # --- Endocrine Hormonal Properties (Tier-5 Physiological Control) ---
    @property
    def cortisol(self) -> float:
        """
        Stress hormone. Inversely tracks valence + fatigue contribution.
        High cortisol → rigid/defensive behavior (low LLM temperature).
        Low cortisol → relaxed/creative behavior (higher temperature).
        Range: 0.0 (fully relaxed) to 1.0 (maximum stress).
        """
        base_cortisol = 0.5 - (self.valence / 2.0)
        fatigue_contribution = 0.3 * self.fatigue
        return max(0.0, min(1.0, base_cortisol + fatigue_contribution))

    @property
    def dopamine(self) -> float:
        """
        Reward hormone. Tracks positive valence × arousal.
        High dopamine → exploratory/playful behavior (higher top_p).
        Low dopamine → conservative/flat behavior (lower top_p).
        Range: 0.0 (no reward signal) to 1.0 (peak reward).
        """
        return max(0.0, min(1.0, max(0.0, self.valence) * self.arousal))


class StateService:
    """Manages Internal State continuity and Neo4j persistence."""

    def __init__(self, graph_store=None):
        self.graph = graph_store
        self.current_state = AgentState()
        self.last_speculative_intent = None  # Transient sensory state

        # --- Psychological Coefficients (§2.4) ---
        self.alpha = getattr(Config, "PSYCH_ALPHA", 0.3)  # Valence drift rate
        self.beta = getattr(Config, "PSYCH_BETA", 0.5)  # Arousal response rate
        self.gamma = getattr(Config, "PSYCH_GAMMA", 0.2)  # Dominance stability
        self.delta = getattr(Config, "PSYCH_DELTA", 0.1)  # Trust change rate (Marsh)
        self.epsilon = getattr(
            Config, "PSYCH_EPSILON", 0.03
        )  # Attachment growth rate (Bowlby)
        self.lambda_decay = getattr(Config, "PSYCH_LAMBDA_DECAY", 0.05)  # ALMA decay

        # Legacy coefficients (kept for idle evolution)
        self.trust_baseline = 0.5
        self.sensory_weight = getattr(Config, "STATE_SENSORY_WEIGHT", 0.20)
        self.min_perception_confidence = getattr(
            Config, "MIN_PERCEPTION_CONFIDENCE", 0.55
        )
        self.sensory_persist_interval = getattr(
            Config, "STATE_SENSORY_PERSIST_INTERVAL", 2.0
        )
        self._last_sensory_persist = 0.0
        self._last_proactive_attempt = 0.0

    async def hydrate_state(self, agent_name: str = "my friend"):
        """Loads state from Neo4j."""
        if not self.graph:
            return

        logger.info(f"[State] Hydrating {agent_name} from Neo4j...")
        query = "MATCH (a:Agent {name: $name}) RETURN a"
        res = await self.graph.execute_query(
            query, {"name": agent_name}, use_cache=False, strong_consistency=True
        )
        if res:
            props = res[0]["a"]
            self.current_state.mood = props.get("mood", 0.0)
            self.current_state.energy = props.get("energy", 0.5)
            self.current_state.dominance = props.get("dominance", 0.5)

            # Dimensional trust hydration with legacy fallback
            self.current_state.trust_benevolence = props.get(
                "trust_benevolence", props.get("trust", 0.5)
            )
            self.current_state.trust_competence = props.get(
                "trust_competence", props.get("trust", 0.5)
            )
            self.current_state.trust_integrity = props.get(
                "trust_integrity", props.get("trust", 0.5)
            )

            self.current_state.attachment = props.get("attachment", 0.1)
            self.current_state.fatigue = props.get("fatigue", 0.0)
            self.current_state.last_user_interaction = props.get(
                "last_user_interaction", self.current_state.last_user_interaction
            )
            self.current_state.interaction_count = props.get("interaction_count", 0)

    async def persist_state(self, agent_name: str = "my friend"):
        """Saves current state to Neo4j."""
        if not self.graph:
            return

        query = """
        MERGE (a:Agent {name: $name})
        SET a.mood = $mood,
            a.energy = $energy,
            a.dominance = $dominance,
            a.trust_benevolence = $trust_benevolence,
            a.trust_competence = $trust_competence,
            a.trust_integrity = $trust_integrity,
            a.trust = $trust,
            a.attachment = $attachment,
            a.fatigue = $fatigue,
            a.last_user_interaction = $last_user_interaction,
            a.interaction_count = $interaction_count,
            a.last_sync = datetime()
        """
        params = {
            "name": agent_name,
            "mood": self.current_state.mood,
            "energy": self.current_state.energy,
            "dominance": self.current_state.dominance,
            "trust_benevolence": self.current_state.trust_benevolence,
            "trust_competence": self.current_state.trust_competence,
            "trust_integrity": self.current_state.trust_integrity,
            "trust": self.current_state.trust,
            "attachment": self.current_state.attachment,
            "fatigue": self.current_state.fatigue,
            "last_user_interaction": self.current_state.last_user_interaction,
            "interaction_count": self.current_state.interaction_count,
        }
        await self.graph.execute_query(query, params, write=True)
        if hasattr(self.graph, "invalidate_cache"):
            await self.graph.invalidate_cache(agent_name)
        logger.debug(
            f"[State] Persisted to Neo4j: V={self.current_state.mood:.2f} Ar={self.current_state.energy:.2f} D={self.current_state.dominance:.2f}"
        )

    def record_user_interaction(self):
        """Mark that the user just interacted. Called by BrainAgent on every chat.input."""
        self.current_state.last_user_interaction = time.time()

    async def update_from_appraisal(self, appraisal):
        """
        PAD + Relational update driven by appraisal vector (§2.3).

        ALMA mood-pull: Each appraisal dimension pulls the corresponding
        PAD dimension toward the appraised value.
        Marsh trust: RI directly modulates trust.
        Bowlby attachment: Trust × interaction frequency.
        """
        G = appraisal.goal_congruence
        RI = appraisal.relationship_impact
        N = appraisal.novelty
        R = appraisal.relevance
        A = appraisal.agency
        NA = appraisal.norm_alignment

        # PAD mood-pull (§2.3)
        self.current_state.mood = (
            1 - self.alpha
        ) * self.current_state.mood + self.alpha * (0.6 * G + 0.4 * RI)
        self.current_state.energy = (
            1 - self.beta
        ) * self.current_state.energy + self.beta * (0.6 * N + 0.4 * R)
        self.current_state.dominance = (
            1 - self.gamma
        ) * self.current_state.dominance + self.gamma * (0.6 * A + 0.4 * NA)

        # Relational updates (§2.3)
        self.current_state.trust_benevolence = max(
            0.0, min(1.0, self.current_state.trust_benevolence + self.delta * RI)
        )
        self.current_state.trust_competence = max(
            0.0,
            min(
                1.0,
                self.current_state.trust_competence + self.delta * (0.6 * G + 0.4 * R),
            ),
        )
        self.current_state.trust_integrity = max(
            0.0, min(1.0, self.current_state.trust_integrity + self.delta * NA)
        )
        self.current_state.interaction_count += 1
        freq = min(1.0, self.current_state.interaction_count / 100.0)
        self.current_state.attachment = max(
            0.0,
            min(
                1.0,
                self.current_state.attachment
                + self.epsilon * self.current_state.trust * freq,
            ),
        )

        self.current_state.last_update = datetime.now()
        self._enforce_bounds()
        await self.persist_state()

        logger.debug(
            "[State] PAD update: V=%.3f Ar=%.3f D=%.3f T=%.3f At=%.3f",
            self.current_state.mood,
            self.current_state.energy,
            self.current_state.dominance,
            self.current_state.trust,
            self.current_state.attachment,
        )

    async def update_from_event(
        self, event_valence: float, user_trust_delta: float = 0.0
    ):
        """
        Legacy Cognitive Update (backward-compatible).
        Wraps the new appraisal-driven update for code that still uses valence floats.
        """
        now = datetime.now()
        self.current_state.last_user_interaction = time.time()

        # Apply Cognitive Weight (0.7)
        self.current_state.mood = (self.current_state.mood * 0.3) + (
            event_valence * 0.7
        )

        self.current_state.trust = max(
            0.0, min(1.0, self.current_state.trust + user_trust_delta)
        )
        self.current_state.attachment += user_trust_delta * 0.1
        self.current_state.energy -= 0.02

        self.current_state.interaction_count += 1
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

        # Confidence-scaled emotional bias
        weight = self.sensory_weight * max(0.0, min(1.0, confidence))
        self.current_state.mood = (self.current_state.mood * (1 - weight)) + (
            emotion_bias * weight
        )

        # Arousal modulation from acoustic events
        for event in events:
            if event == "Laughter":
                self.current_state.energy = min(1.0, self.current_state.energy + 0.15)
                self.current_state.trust = min(1.0, self.current_state.trust + 0.05)
                logger.info("😄 Agent sensed laughter - Energy/Trust boosted.")
            elif event == "Applause":
                self.current_state.energy = min(1.0, self.current_state.energy + 0.2)
                logger.info("👏 Agent sensed applause - Energy spike.")
            elif event in ["Cough", "Sneeze"]:
                self.current_state.attachment = min(
                    1.0, self.current_state.attachment + 0.02
                )
                logger.debug(f"🤧 Agent sensed {event} - Attachment nudged (Empathy).")

        self._enforce_bounds()
        await self._persist_sensory_state_if_due()

    async def handle_system_tick(self, tick_metadata: Dict[str, Any]):
        """
        Idle evolution triggered by NATS system.tick.
        Implements ALMA exponential decay (§2.2) and Fatigue updates.
        """
        now = tick_metadata.get("timestamp", time.time())
        dt_hours = tick_metadata.get("interval", 60) / 3600.0

        # Evolve fatigue
        hour = datetime.fromtimestamp(now).hour
        is_night = hour >= 22 or hour < 6
        try:
            import cognitive_rust

            rust_state = cognitive_rust.FatigueState(
                self.current_state.fatigue, self.current_state.last_user_interaction
            )
            updated_rust = cognitive_rust.update_fatigue(
                rust_state, now, dt_hours, is_night
            )
            self.current_state.fatigue = updated_rust.fatigue
        except ImportError:
            self._update_fatigue_python(now, dt_hours, is_night)
        except Exception:
            logger.exception(
                "[State] Unexpected Rust fatigue update error; using Python fallback."
            )
            self._update_fatigue_python(now, dt_hours, is_night)

        # ALMA Decay (§2.2): I(t) = I₀ · exp(−λ · t)
        self.current_state.mood *= math.exp(-self.lambda_decay * dt_hours)
        self.current_state.energy = min(
            1.0, self.current_state.energy + (0.02 * dt_hours)
        )
        # Dominance does NOT decay — it's trait-like (Mehrabian)

        tb_drift = (self.trust_baseline - self.current_state.trust_benevolence) * 0.01
        tc_drift = (self.trust_baseline - self.current_state.trust_competence) * 0.01
        ti_drift = (self.trust_baseline - self.current_state.trust_integrity) * 0.01
        self.current_state.trust_benevolence += tb_drift
        self.current_state.trust_competence += tc_drift
        self.current_state.trust_integrity += ti_drift

        self.current_state.last_update = datetime.fromtimestamp(now)
        self._enforce_bounds()
        await self.persist_state()
        logger.debug(
            "[State Heartbeat] V=%.3f Ar=%.3f D=%.3f F=%.3f",
            self.current_state.mood,
            self.current_state.energy,
            self.current_state.dominance,
            self.current_state.fatigue,
        )

    def check_proactive_eligibility(self) -> bool:
        """
        Phase 1: Proactive Engagement.
        Evaluates whether the agent should spontaneously initiate contact.
        """
        if not getattr(Config, "PROACTIVE_ENABLED", False):
            return False

        now = time.time()

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

        cooldown = getattr(Config, "PROACTIVE_COOLDOWN_SECONDS", 3600)
        if (now - self._last_proactive_attempt) < cooldown:
            return False

        min_energy = getattr(Config, "PROACTIVE_MIN_ENERGY", 0.2)
        if self.current_state.energy < min_energy:
            logger.debug(
                "[State] Proactive SKIPPED: energy %.2f < min %.2f",
                self.current_state.energy,
                min_energy,
            )
            return False

        logger.info(
            "[State] Proactive ELIGIBLE: idle=%.0fs threshold=%.0fs energy=%.2f",
            idle_duration,
            threshold,
            self.current_state.energy,
        )
        return True

    def mark_proactive_attempt(self):
        """Record that a proactive generation was initiated."""
        self._last_proactive_attempt = time.time()

    def _enforce_bounds(self):
        self.current_state.mood = max(-1.0, min(1.0, self.current_state.mood))
        self.current_state.energy = max(0.0, min(1.0, self.current_state.energy))
        self.current_state.dominance = max(0.0, min(1.0, self.current_state.dominance))
        self.current_state.trust_benevolence = max(
            0.0, min(1.0, self.current_state.trust_benevolence)
        )
        self.current_state.trust_competence = max(
            0.0, min(1.0, self.current_state.trust_competence)
        )
        self.current_state.trust_integrity = max(
            0.0, min(1.0, self.current_state.trust_integrity)
        )
        self.current_state.attachment = max(
            0.0, min(1.0, self.current_state.attachment)
        )
        self.current_state.fatigue = max(0.0, min(1.0, self.current_state.fatigue))

    def get_context_snapshot(self) -> Dict[str, Any]:
        return {
            "emotion": self.get_emotion_label(),
            "mood": self.current_state.mood,
            "energy": self.current_state.energy,
            "dominance": self.current_state.dominance,
            "trust": self.current_state.trust,
            "trust_benevolence": self.current_state.trust_benevolence,
            "trust_competence": self.current_state.trust_competence,
            "trust_integrity": self.current_state.trust_integrity,
            "attachment": self.current_state.attachment,
            "interaction_count": self.current_state.interaction_count,
            "active_goals": self.current_state.active_goals,
            # PAD aliases for new consumers
            "valence": self.current_state.mood,
            "arousal": self.current_state.arousal,
            "fatigue": self.current_state.fatigue,
            # Endocrine hormones (Tier-5)
            "cortisol": self.current_state.cortisol,
            "dopamine": self.current_state.dopamine,
        }

    def get_behavioral_directive(self) -> str:
        """Translates internal state into a natural language directive for the LLM."""
        V = self.current_state.mood
        Ar = self.current_state.energy
        D = self.current_state.dominance
        T = self.current_state.trust

        if V < -0.6:
            direct = "You are feeling deeply melancholic and reserved."
        elif V > 0.6:
            direct = "You are in a vibrant, optimistic state."
        else:
            direct = "You are grounded and emotionally stable."

        if Ar < 0.3:
            direct += " Your energy is low; keep replies brief and pacing slow."
        elif Ar > 0.8:
            direct += " You are high-energy; use expressive, dynamic language."

        if D < 0.3:
            direct += " You feel uncertain and deferential — ask more, assert less."
        elif D > 0.7:
            direct += " You feel confident and in control — speak with conviction."

        if T < 0.3:
            direct += " You are feeling skeptical and maintaining boundaries."
        elif T > 0.8:
            direct += " You feel a deep, familiar bond with the user."

        return direct

    def get_emotion_label(self) -> str:
        V = self.current_state.mood
        Ar = self.current_state.energy
        D = self.current_state.dominance

        if V > 0.4 and Ar > 0.6:
            return "excited"
        if V > 0.4:
            return "happy"
        if V < -0.4 and Ar > 0.6:
            return "angry"
        if V < -0.4:
            return "sad"
        if Ar > 0.8:
            return "alert"
        if D < 0.3:
            return "uncertain"
        return "neutral"

    async def _persist_sensory_state_if_due(self):
        now = time.time()
        if now - self._last_sensory_persist < self.sensory_persist_interval:
            return
        self._last_sensory_persist = now
        await self.persist_state()

    def _update_fatigue_python(self, now: float, dt_hours: float, is_night: bool):
        """Fallback fatigue update matching Rust behavior."""
        circadian_multiplier = 1.8 if is_night else 1.0
        idle_duration = now - self.current_state.last_user_interaction
        is_idle = idle_duration > 300.0
        k_drain = 0.15
        k_restore = 0.20
        if is_idle:
            next_fatigue = self.current_state.fatigue - (
                k_restore * dt_hours / circadian_multiplier
            )
        else:
            next_fatigue = self.current_state.fatigue + (
                k_drain * dt_hours * circadian_multiplier
            )
        self.current_state.fatigue = max(0.0, min(1.0, next_fatigue))
