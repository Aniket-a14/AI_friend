"""
Reappraisal Engine — Gross/Bosse Feedback Loop (psychological_layer.md §8).

Implements emotion regulation via parameter-level adaptation, not direct
emotion modification. This maintains consistency with Gross (1998) and
Bosse et al. (2010):

    dE/dt = f(S, A, E)
    Reappraisal acts by modifying A (appraisal), which changes E.

The engine evaluates the outcome of each conversation turn and adjusts
the appraisal weights used by the ALMA mood-pull equations (§2.3).

Kill-switch: REAPPRAISAL_ENABLED=false
"""

import logging
import time
from typing import Dict, Any, Optional

from ..config import Config

logger = logging.getLogger(__name__)


class ReappraisalEngine:
    """
    Feedback loop that refines appraisal weights based on conversation outcomes.

    §8.1: Outcome = w₁·Δ_text + w₂·Δ_acoustic + w₃·BehavioralSignal
    §8.2: w_new = clamp(w_old - η·Δ, w_min, w_max)
    """

    def __init__(self):
        self.enabled = getattr(Config, "REAPPRAISAL_ENABLED", True)
        self.learning_rate = getattr(Config, "REAPPRAISAL_LEARNING_RATE", 0.05)  # η
        self.w_min = 0.1
        self.w_max = 0.9

        # Adaptive appraisal weights (tuned over time by this engine)
        # These feed back into the StateService's mood-pull coefficients
        self.appraisal_weights: Dict[str, float] = {
            "w1_g_to_v": 0.6,  # G → Valence weight
            "w2_ri_to_v": 0.4,  # RI → Valence weight
            "w3_n_to_ar": 0.6,  # N → Arousal weight
            "w4_r_to_ar": 0.4,  # R → Arousal weight
            "w5_a_to_d": 0.6,  # A → Dominance weight
            "w6_na_to_d": 0.4,  # NA → Dominance weight
        }

        # Turn-level state tracking
        self._pre_response_state: Optional[Dict[str, float]] = None
        self._expected_valence: Optional[float] = None
        self._last_evaluation_time: float = 0.0

    def record_pre_response_state(self, state_snapshot: Dict[str, Any]):
        """
        Called before generating a response.
        Captures the emotional baseline for outcome comparison.
        """
        if not self.enabled:
            return

        self._pre_response_state = {
            "valence": state_snapshot.get("mood", state_snapshot.get("valence", 0.0)),
            "arousal": state_snapshot.get("energy", state_snapshot.get("arousal", 0.5)),
            "dominance": state_snapshot.get("dominance", 0.5),
            "trust": state_snapshot.get("trust", 0.5),
        }

    def record_expected_outcome(self, goal: str, current_valence: float):
        """
        Record what the agent expects to happen based on its chosen goal.
        The expected outcome is a function of the goal type.
        """
        if not self.enabled:
            return

        # Goal → expected valence shift
        goal_expectations = {
            "COMFORT": 0.3,  # We expect the user to feel better
            "ENGAGE": 0.1,  # Neutral positive
            "INFORM": 0.05,  # Slight positive from helpfulness
            "TEASE": 0.15,  # Fun should improve mood
            "PROTECT": -0.1,  # Boundary enforcement may cause friction
        }
        self._expected_valence = goal_expectations.get(goal, 0.1)

    async def evaluate_outcome(
        self,
        actual_text_valence: float,
        acoustic_delta: float = 0.0,
        behavioral_signal: float = 0.5,
    ):
        """
        §8.1: Evaluate the outcome of the agent's last response.

        ActualOutcome = w₁·Δ_text + w₂·Δ_acoustic + w₃·BehavioralSignal

        §8.2: Adjust appraisal parameters based on prediction error.
        The system updates appraisal PARAMETERS (w₁, w₂), not emotions.
        """
        if not self.enabled:
            return

        if self._expected_valence is None or self._pre_response_state is None:
            return

        # Rate limiting: don't evaluate more than once per 2 seconds
        now = time.time()
        if now - self._last_evaluation_time < 2.0:
            return
        self._last_evaluation_time = now

        # §8.1: Multi-signal outcome computation
        actual_outcome = (
            0.5 * actual_text_valence + 0.3 * acoustic_delta + 0.2 * behavioral_signal
        )

        # Prediction error
        delta = self._expected_valence - actual_outcome

        # §8.2: Only adapt on significant mismatches
        if abs(delta) < 0.1:
            logger.debug(
                "[Reappraisal] Δ=%.3f — within tolerance, no adaptation.", delta
            )
            self._reset_turn_state()
            return

        # Confidence weighting: reduce learning rate for noisy signals
        confidence = min(1.0, abs(actual_text_valence) + 0.3)
        effective_lr = self.learning_rate * confidence

        # Update valence-related weights (most likely to need correction)
        self.appraisal_weights["w1_g_to_v"] = self._clamp(
            self.appraisal_weights["w1_g_to_v"] - effective_lr * delta
        )
        self.appraisal_weights["w2_ri_to_v"] = self._clamp(
            self.appraisal_weights["w2_ri_to_v"] - effective_lr * delta * 0.5
        )

        logger.info(
            "[Reappraisal] Δ=%.3f η_eff=%.4f → w1=%.3f w2=%.3f",
            delta,
            effective_lr,
            self.appraisal_weights["w1_g_to_v"],
            self.appraisal_weights["w2_ri_to_v"],
        )

        self._reset_turn_state()

    def get_weights(self) -> Dict[str, float]:
        """Returns current adaptive appraisal weights."""
        return self.appraisal_weights.copy()

    def _clamp(self, value: float) -> float:
        return max(self.w_min, min(self.w_max, value))

    def _reset_turn_state(self):
        self._pre_response_state = None
        self._expected_valence = None
