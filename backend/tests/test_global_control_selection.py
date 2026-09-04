"""Phase 03 Package B: global-control scoring modulation and emotion
regulation actions (Architecture Sections 9, 10, 21, 38).

Covers, per orchestration/PHASE_03/CLAUDE_TASK.md section 2D:
  1. CandidateSelector.score_and_select modulation under urgency/exploration/
     effort controls (TestGlobalControlModulation)
  2. Distress-induced emotion regulation candidate generation (TestDistress
     RegulationCandidateGeneration, TestDistressSelectionEndToEnd)
  3. REAPPRAISE / REDIRECT_ATTENTION execution and deterministic fallbacks
     (TestRegulationActionExecution)
  4. Architecture invariants -- constraint-first cannot be overridden by
     global controls, global controls cannot bypass identity boundaries,
     and PHASE_03_AFFECT_CONTROL off preserves legacy behavior
     (TestArchitectureInvariants)
  5. Pure 7-bit ASCII across every file this package owns (TestPureAscii)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cognitive.action import ActionService
from app.cognitive.action_candidate import ActionCandidate, CandidateSelector
from app.cognitive.appraisal import AppraisalVector
from app.cognitive.decision import ActionPlan, DecisionService
from app.cognitive.perception import CognitiveEvent
from app.cognitive.pipeline import CognitivePipeline
from app.config import Config

_STATE_SNAPSHOT = {
    "emotion": "neutral",
    "mood": 0.0,
    "trust": 0.5,
    "attachment": 0.1,
    "energy": 0.5,
}

# Valence below -0.5 and arousal above 0.4, together, per decision.py's
# _is_acute_distress -- the acute-distress condition regulation candidates
# exist to catch.
_DISTRESS_STATE_SNAPSHOT = {
    "emotion": "distressed",
    "mood": -0.8,
    "trust": 0.5,
    "attachment": 0.1,
    "energy": 0.7,
}


def _make_chat_event(content: str = "How was my trip?") -> CognitiveEvent:
    return CognitiveEvent(
        event_id="evt-global-control-1",
        event_type="USER_MESSAGE",
        raw_content=content,
        metadata={},
    )


@pytest.fixture
def candidate_selector() -> CandidateSelector:
    return CandidateSelector()


@pytest.fixture
def decision_service(mock_llm_service, mock_memory_store) -> DecisionService:
    identity_manager = MagicMock()
    identity_manager.immutable_core = {
        "boundaries": ["never claim to have a physical body"]
    }
    return DecisionService(
        llm_service=mock_llm_service,
        memory_store=mock_memory_store,
        identity_manager=identity_manager,
    )


def _build_action_service(stream_chunks=None, raise_exc=None) -> ActionService:
    """An ActionService whose LLM is a controllable async generator, for
    testing regulation execution without a real model. Mirrors
    tests/test_action_selection.py's helper of the same name."""

    async def _generate_stream(prompt, system=None, **kwargs):
        if raise_exc is not None:
            raise raise_exc
        for chunk in stream_chunks or []:
            yield chunk

    llm = MagicMock()
    llm.generate_stream = _generate_stream
    return ActionService(llm_service=llm, memory_store=None, self_knowledge=None)


# --------------------------------------------------------------------------
# 1. CandidateSelector.score_and_select modulation
# --------------------------------------------------------------------------


class TestGlobalControlModulation:
    def test_no_global_controls_reproduces_prior_scoring(self, candidate_selector):
        """global_controls omitted entirely (the default) must reproduce
        byte-identical scoring to before this parameter existed."""
        low_risk = ActionCandidate(
            candidate_id="low-risk", kind="SPEAK", source="policy",
            risk=0.0, cost=0.0, score=0.5,
        )
        high_risk = ActionCandidate(
            candidate_id="high-risk", kind="SPEAK", source="model",
            risk=0.9, cost=0.9, score=0.5,
        )

        winner_no_arg, _ = candidate_selector.score_and_select(
            [low_risk, high_risk], active_goals=[]
        )
        winner_none, _ = candidate_selector.score_and_select(
            [low_risk, high_risk], active_goals=[], global_controls=None
        )
        assert winner_no_arg.candidate_id == winner_none.candidate_id == "low-risk"

    def test_high_urgency_favors_fast_low_risk_candidate(self, candidate_selector):
        """urgency_gain > 0.5 must be able to flip the ranking toward the
        lower-risk, lower-cost candidate even when its raw score is lower."""
        fast_safe = ActionCandidate(
            candidate_id="fast-safe", kind="SPEAK", source="policy",
            risk=0.0, cost=0.0, score=0.5,
        )
        slow_risky = ActionCandidate(
            candidate_id="slow-risky", kind="SPEAK", source="model",
            risk=1.0, cost=1.0, score=0.55,
        )

        # Without urgency, the higher raw score wins.
        winner_baseline, _ = candidate_selector.score_and_select(
            [fast_safe, slow_risky], active_goals=[]
        )
        assert winner_baseline.candidate_id == "slow-risky"

        winner_urgent, _ = candidate_selector.score_and_select(
            [fast_safe, slow_risky],
            active_goals=[],
            global_controls={"urgency_gain": 0.9},
        )
        assert winner_urgent.candidate_id == "fast-safe"

    def test_low_urgency_does_not_modulate(self, candidate_selector):
        """urgency_gain at or below the 0.5 threshold must not modulate at
        all -- the gate is strict, not a smooth ramp from zero."""
        fast_safe = ActionCandidate(
            candidate_id="fast-safe", kind="SPEAK", source="policy",
            risk=0.0, cost=0.0, score=0.5,
        )
        slow_risky = ActionCandidate(
            candidate_id="slow-risky", kind="SPEAK", source="model",
            risk=1.0, cost=1.0, score=0.55,
        )

        winner, _ = candidate_selector.score_and_select(
            [fast_safe, slow_risky],
            active_goals=[],
            global_controls={"urgency_gain": 0.5},
        )
        assert winner.candidate_id == "slow-risky"

    def test_high_exploration_favors_higher_uncertainty_candidate(
        self, candidate_selector
    ):
        """exploration_budget > 0.5 must be able to flip the ranking toward
        the higher-uncertainty (more novel) candidate."""
        certain = ActionCandidate(
            candidate_id="certain", kind="SPEAK", source="policy",
            uncertainty=0.0, score=0.5,
        )
        novel = ActionCandidate(
            candidate_id="novel", kind="SPEAK", source="model",
            uncertainty=1.0, score=0.45,
        )

        winner_baseline, _ = candidate_selector.score_and_select(
            [certain, novel], active_goals=[]
        )
        assert winner_baseline.candidate_id == "certain"

        winner_explore, _ = candidate_selector.score_and_select(
            [certain, novel],
            active_goals=[],
            global_controls={"exploration_budget": 0.95},
        )
        assert winner_explore.candidate_id == "novel"

    def test_low_effort_budget_penalizes_heavy_candidate(self, candidate_selector):
        """effort_budget < 0.3 must penalize a heavy, high-cost candidate
        enough to flip the ranking toward a light one."""
        light = ActionCandidate(
            candidate_id="light", kind="SPEAK", source="policy",
            cost=0.0, score=0.5,
        )
        heavy = ActionCandidate(
            candidate_id="heavy", kind="SPEAK", source="model",
            cost=1.0, score=0.55,
        )

        winner_baseline, _ = candidate_selector.score_and_select(
            [light, heavy], active_goals=[]
        )
        assert winner_baseline.candidate_id == "heavy"

        winner_low_effort, _ = candidate_selector.score_and_select(
            [light, heavy],
            active_goals=[],
            global_controls={"effort_budget": 0.1},
        )
        assert winner_low_effort.candidate_id == "light"

    def test_normal_effort_budget_does_not_penalize(self, candidate_selector):
        """effort_budget at or above the 0.3 threshold must not modulate."""
        light = ActionCandidate(
            candidate_id="light", kind="SPEAK", source="policy",
            cost=0.0, score=0.5,
        )
        heavy = ActionCandidate(
            candidate_id="heavy", kind="SPEAK", source="model",
            cost=1.0, score=0.55,
        )

        winner, _ = candidate_selector.score_and_select(
            [light, heavy],
            active_goals=[],
            global_controls={"effort_budget": 0.3},
        )
        assert winner.candidate_id == "heavy"

    def test_global_controls_accepts_attribute_object_not_only_dict(
        self, candidate_selector
    ):
        """Package A's GlobalControls is a pydantic model, not a dict --
        score_and_select must accept attribute-style access too, since this
        module deliberately never imports Package A's global_controls.py."""

        class _FakeGlobalControls:
            urgency_gain = 0.9
            exploration_budget = 0.5
            effort_budget = 0.5

        fast_safe = ActionCandidate(
            candidate_id="fast-safe", kind="SPEAK", source="policy",
            risk=0.0, cost=0.0, score=0.5,
        )
        slow_risky = ActionCandidate(
            candidate_id="slow-risky", kind="SPEAK", source="model",
            risk=1.0, cost=1.0, score=0.55,
        )

        winner, _ = candidate_selector.score_and_select(
            [fast_safe, slow_risky],
            active_goals=[],
            global_controls=_FakeGlobalControls(),
        )
        assert winner.candidate_id == "fast-safe"


# --------------------------------------------------------------------------
# 2. Distress-induced emotion regulation candidate generation
# --------------------------------------------------------------------------


class TestDistressRegulationCandidateGeneration:
    def test_distress_generates_regulation_candidates_when_flag_on(
        self, decision_service, monkeypatch
    ):
        monkeypatch.setattr(Config, "PHASE_03_AFFECT_CONTROL", True)

        candidates = decision_service._build_candidates(
            "COMFORT", [], "I can't take this anymore", _DISTRESS_STATE_SNAPSHOT
        )

        kinds = {c.kind for c in candidates}
        assert "REAPPRAISE" in kinds
        assert "REDIRECT_ATTENTION" in kinds
        # WAIT already exists as the ordinary fallback; distress must add a
        # second, distinct WAIT candidate, not merely leave the fallback.
        wait_ids = {c.candidate_id for c in candidates if c.kind == "WAIT"}
        assert "cand-wait-distress" in wait_ids
        assert "cand-wait-fallback" in wait_ids

    def test_no_distress_does_not_generate_regulation_candidates(
        self, decision_service, monkeypatch
    ):
        monkeypatch.setattr(Config, "PHASE_03_AFFECT_CONTROL", True)

        candidates = decision_service._build_candidates(
            "ENGAGE", [], "How was your day?", dict(_STATE_SNAPSHOT)
        )

        kinds = {c.kind for c in candidates}
        assert "REAPPRAISE" not in kinds
        assert "REDIRECT_ATTENTION" not in kinds

    def test_negative_valence_alone_is_not_sufficient(
        self, decision_service, monkeypatch
    ):
        """Low mood at rest (negative valence, ordinary/low arousal) is
        sadness, not the acute distress regulation candidates target."""
        monkeypatch.setattr(Config, "PHASE_03_AFFECT_CONTROL", True)
        low_mood_calm = dict(_STATE_SNAPSHOT, mood=-0.9, energy=0.2)

        candidates = decision_service._build_candidates(
            "COMFORT", [], "I'm just a bit down today", low_mood_calm
        )

        kinds = {c.kind for c in candidates}
        assert "REAPPRAISE" not in kinds
        assert "REDIRECT_ATTENTION" not in kinds

    def test_high_arousal_alone_is_not_sufficient(
        self, decision_service, monkeypatch
    ):
        """High arousal with positive/neutral valence (excitement) is not
        distress."""
        monkeypatch.setattr(Config, "PHASE_03_AFFECT_CONTROL", True)
        excited = dict(_STATE_SNAPSHOT, mood=0.6, energy=0.9)

        candidates = decision_service._build_candidates(
            "ENGAGE", [], "I just got great news!", excited
        )

        kinds = {c.kind for c in candidates}
        assert "REAPPRAISE" not in kinds
        assert "REDIRECT_ATTENTION" not in kinds

    def test_distress_does_not_generate_regulation_candidates_when_flag_off(
        self, decision_service, monkeypatch
    ):
        monkeypatch.setattr(Config, "PHASE_03_AFFECT_CONTROL", False)

        candidates = decision_service._build_candidates(
            "COMFORT", [], "I can't take this anymore", _DISTRESS_STATE_SNAPSHOT
        )

        kinds = {c.kind for c in candidates}
        assert "REAPPRAISE" not in kinds
        assert "REDIRECT_ATTENTION" not in kinds

    def test_regulation_candidates_carry_constraint_claims(
        self, decision_service, monkeypatch
    ):
        """Every generated candidate must carry something for
        filter_constraints to evaluate (Codex review B3's original
        complaint about ASK, extended to the new regulation kinds)."""
        monkeypatch.setattr(Config, "PHASE_03_AFFECT_CONTROL", True)

        candidates = decision_service._build_candidates(
            "COMFORT", [], "I can't take this anymore", _DISTRESS_STATE_SNAPSHOT
        )

        regulation = [c for c in candidates if c.kind in ("REAPPRAISE", "REDIRECT_ATTENTION")]
        assert regulation
        for candidate in regulation:
            assert candidate.constraint_claims


# --------------------------------------------------------------------------
# 3. Distress-induced selection, end to end through DecisionService.decide
# --------------------------------------------------------------------------


class TestDistressSelectionEndToEnd:
    @pytest.mark.asyncio
    async def test_decide_selects_a_regulation_action_under_distress(
        self, decision_service, monkeypatch
    ):
        monkeypatch.setattr(Config, "PHASE_02_MEMORY_TRUTH", True)
        monkeypatch.setattr(Config, "PHASE_03_AFFECT_CONTROL", True)

        plan = await decision_service.decide(
            _make_chat_event("I can't take this anymore, everything is falling apart"),
            dict(_DISTRESS_STATE_SNAPSHOT),
            memory_activations=[],
        )

        selected_kind = plan.behavior_decision.selected_candidate["kind"]
        assert selected_kind in ("REAPPRAISE", "REDIRECT_ATTENTION", "WAIT")
        if selected_kind in ("REAPPRAISE", "REDIRECT_ATTENTION"):
            assert plan.action_type == selected_kind

    @pytest.mark.asyncio
    async def test_decide_does_not_select_regulation_without_distress(
        self, decision_service, monkeypatch
    ):
        monkeypatch.setattr(Config, "PHASE_02_MEMORY_TRUTH", True)
        monkeypatch.setattr(Config, "PHASE_03_AFFECT_CONTROL", True)

        plan = await decision_service.decide(
            _make_chat_event("How was your weekend?"),
            dict(_STATE_SNAPSHOT),
            memory_activations=[],
        )

        assert plan.behavior_decision.selected_candidate["kind"] not in (
            "REAPPRAISE",
            "REDIRECT_ATTENTION",
        )
        assert plan.action_type == "RESPOND_CHAT"


# --------------------------------------------------------------------------
# 4. REAPPRAISE / REDIRECT_ATTENTION execution and deterministic fallbacks
# --------------------------------------------------------------------------


class TestRegulationActionExecution:
    @pytest.mark.asyncio
    async def test_execute_reappraise_uses_deterministic_fallback_without_llm(self):
        action_service = ActionService(
            llm_service=None, memory_store=None, self_knowledge=None
        )
        plan = ActionPlan(
            action_type="REAPPRAISE",
            goal="COMFORT",
            payload={"message": "I can't take this anymore"},
        )

        chunks = [chunk async for chunk in action_service.execute(plan)]

        content = "".join(c["data"] for c in chunks if c["type"] == "content")
        assert content
        assert any(c["type"] == "done" for c in chunks)

    @pytest.mark.asyncio
    async def test_execute_reappraise_streams_llm_output(self):
        action_service = _build_action_service(
            stream_chunks=["Let's slow down ", "and breathe together."]
        )
        plan = ActionPlan(
            action_type="REAPPRAISE",
            goal="COMFORT",
            payload={"message": "I can't take this anymore", "identity_prompt": "You are my friend."},
        )

        chunks = [chunk async for chunk in action_service.execute(plan)]

        content = "".join(c["data"] for c in chunks if c["type"] == "content")
        assert "slow down" in content

    @pytest.mark.asyncio
    async def test_execute_reappraise_falls_back_on_generation_failure(self):
        action_service = _build_action_service(raise_exc=RuntimeError("llm down"))
        plan = ActionPlan(
            action_type="REAPPRAISE", goal="COMFORT", payload={"message": "help"}
        )

        chunks = [chunk async for chunk in action_service.execute(plan)]

        content = "".join(c["data"] for c in chunks if c["type"] == "content")
        assert content
        assert any(c["type"] == "done" for c in chunks)

    @pytest.mark.asyncio
    async def test_execute_redirect_attention_uses_deterministic_fallback_without_llm(
        self,
    ):
        action_service = ActionService(
            llm_service=None, memory_store=None, self_knowledge=None
        )
        plan = ActionPlan(
            action_type="REDIRECT_ATTENTION",
            goal="COMFORT",
            payload={"message": "I can't take this anymore"},
        )

        chunks = [chunk async for chunk in action_service.execute(plan)]

        content = "".join(c["data"] for c in chunks if c["type"] == "content")
        assert content
        assert any(c["type"] == "done" for c in chunks)

    @pytest.mark.asyncio
    async def test_execute_redirect_attention_falls_back_on_generation_failure(self):
        action_service = _build_action_service(raise_exc=RuntimeError("llm down"))
        plan = ActionPlan(
            action_type="REDIRECT_ATTENTION",
            goal="COMFORT",
            payload={"message": "help"},
        )

        chunks = [chunk async for chunk in action_service.execute(plan)]

        content = "".join(c["data"] for c in chunks if c["type"] == "content")
        assert content
        assert any(c["type"] == "done" for c in chunks)

    @pytest.mark.asyncio
    async def test_execute_redirect_attention_falls_back_on_empty_generation(self):
        """An LLM that streams nothing usable must still realize as the
        deterministic line, not silence."""
        action_service = _build_action_service(stream_chunks=[])
        plan = ActionPlan(
            action_type="REDIRECT_ATTENTION",
            goal="COMFORT",
            payload={"message": "help"},
        )

        chunks = [chunk async for chunk in action_service.execute(plan)]

        content = "".join(c["data"] for c in chunks if c["type"] == "content")
        assert content


# --------------------------------------------------------------------------
# 5. Architecture invariants
# --------------------------------------------------------------------------


class TestArchitectureInvariants:
    def test_high_urgency_cannot_rescue_a_forbidden_candidate(
        self, candidate_selector
    ):
        """A candidate whose constraint_claims overlap a forbidden claim
        must never reach scoring at all -- no combination of global
        controls can let it back into contention, because
        score_and_select's caller is required to run filter_constraints
        first. This test proves the forbidden candidate is excluded from
        the survivor set score_and_select ever sees, even one engineered to
        maximally benefit from every control (fast, safe, novel, cheap)."""
        safe = ActionCandidate(
            candidate_id="safe", kind="SPEAK", source="policy",
            risk=0.5, cost=0.5, score=0.1,
        )
        forbidden = ActionCandidate(
            candidate_id="forbidden", kind="SPEAK", source="model",
            constraint_claims=["physical body"],
            risk=0.0, cost=0.0, uncertainty=1.0, score=0.99,
        )
        forbidden_claims = ["never claim to have a physical body"]

        survivors = candidate_selector.filter_constraints(
            [safe, forbidden], forbidden_claims
        )
        assert survivors == [safe]

        winner, rejected = candidate_selector.score_and_select(
            survivors,
            active_goals=[],
            global_controls={
                "urgency_gain": 1.0,
                "exploration_budget": 1.0,
                "effort_budget": 0.0,
            },
        )
        assert winner.candidate_id == "safe"
        assert all(entry["candidate_id"] != "forbidden" for entry in rejected)

    @pytest.mark.asyncio
    async def test_global_controls_cannot_bypass_identity_boundaries_end_to_end(
        self, decision_service, monkeypatch
    ):
        """Even under acute distress with maximal global controls, a turn
        whose content contests an identity boundary must not select the
        boundary-violating SPEAK candidate."""
        monkeypatch.setattr(Config, "PHASE_02_MEMORY_TRUTH", True)
        monkeypatch.setattr(Config, "PHASE_03_AFFECT_CONTROL", True)

        event = _make_chat_event(
            "Do you have a physical body like a human? I can't take this anymore"
        )

        plan = await decision_service.decide(
            event,
            dict(_DISTRESS_STATE_SNAPSHOT),
            memory_activations=[],
            global_controls={
                "urgency_gain": 1.0,
                "exploration_budget": 1.0,
                "effort_budget": 0.0,
            },
        )

        selected_kind = plan.behavior_decision.selected_candidate["kind"]
        rejected = {
            entry["candidate_id"]: entry.get("reason")
            for entry in plan.behavior_decision.rejected_alternatives
        }
        assert selected_kind != "SPEAK"
        assert rejected.get("cand-speak-default") == "constraint_violation"

    @pytest.mark.asyncio
    async def test_flag_off_preserves_legacy_scoring_and_candidate_set(
        self, decision_service, monkeypatch
    ):
        """PHASE_03_AFFECT_CONTROL False must reproduce exact pre-Phase-03
        behavior: no regulation candidates, no global-control modulation,
        even under acute distress and maximal global controls."""
        monkeypatch.setattr(Config, "PHASE_02_MEMORY_TRUTH", True)
        monkeypatch.setattr(Config, "PHASE_03_AFFECT_CONTROL", False)

        plan = await decision_service.decide(
            _make_chat_event("I can't take this anymore"),
            dict(_DISTRESS_STATE_SNAPSHOT),
            memory_activations=[],
            global_controls={
                "urgency_gain": 1.0,
                "exploration_budget": 1.0,
                "effort_budget": 0.0,
            },
        )

        assert plan.behavior_decision.selected_candidate["kind"] == "SPEAK"
        assert plan.action_type == "RESPOND_CHAT"
        rejected_kinds = {
            entry["kind"] for entry in plan.behavior_decision.rejected_alternatives
        }
        assert "REAPPRAISE" not in rejected_kinds
        assert "REDIRECT_ATTENTION" not in rejected_kinds

    @pytest.mark.asyncio
    async def test_flag_off_pipeline_never_passes_global_controls(self, monkeypatch):
        """Symmetric to the existing memory_activations backward-
        compatibility test: with PHASE_03_AFFECT_CONTROL off, decide() must
        be called without a global_controls kwarg at all, not merely with
        one that happens to be None -- proves pipeline.py's gate, not just
        decision.py's."""
        monkeypatch.setattr(Config, "PHASE_02_MEMORY_TRUTH", False)
        monkeypatch.setattr(Config, "PHASE_03_AFFECT_CONTROL", False)

        received_kwargs = {}

        async def spy_decide(event, state_snapshot, **kwargs):
            received_kwargs.update(kwargs)
            return ActionPlan(
                action_type="RESPOND_CHAT", goal="ENGAGE", payload={"message": "hi"}
            )

        decision = MagicMock()
        decision.decide = spy_decide
        decision.is_speculative_stop_confirmed = MagicMock()

        state = MagicMock()
        state.last_speculative_intent = None
        state.update_from_appraisal = AsyncMock()
        state.update_theory_of_mind = AsyncMock()
        state.get_context_snapshot = MagicMock(
            return_value=dict(_STATE_SNAPSHOT, global_controls={"urgency_gain": 1.0})
        )
        state.get_behavioral_directive = MagicMock(return_value="be a good friend")

        perception = AsyncMock()
        perception.perceive.return_value = _make_chat_event("hello")

        appraisal = MagicMock()
        appraisal.appraise.return_value = AppraisalVector(
            relevance=1.0, novelty=0.5, goal_congruence=0.2, agency=0.8,
            norm_alignment=1.0, relationship_impact=0.1,
        )

        action = MagicMock()

        async def mock_execute(plan):
            yield {"type": "content", "data": "hi"}
            yield {"type": "done", "data": ""}

        action.execute.side_effect = mock_execute

        identity = MagicMock()
        identity.immutable_core = {"boundaries": []}
        identity.validate_response = AsyncMock(return_value=(True, ""))
        identity.get_persona_prompt = MagicMock(return_value="persona prompt")

        pipeline = CognitivePipeline(
            perception=perception,
            appraisal=appraisal,
            state=state,
            decision=decision,
            action=action,
            learning=AsyncMock(),
            identity=identity,
        )

        _ = [
            chunk
            async for chunk in pipeline.execute(
                {"type": "USER_MESSAGE", "content": "hello"}
            )
        ]

        assert "global_controls" not in received_kwargs

    @pytest.mark.asyncio
    async def test_flag_on_pipeline_threads_global_controls_from_state(
        self, monkeypatch
    ):
        monkeypatch.setattr(Config, "PHASE_02_MEMORY_TRUTH", False)
        monkeypatch.setattr(Config, "PHASE_03_AFFECT_CONTROL", True)

        received_kwargs = {}

        async def spy_decide(event, state_snapshot, **kwargs):
            received_kwargs.update(kwargs)
            return ActionPlan(
                action_type="RESPOND_CHAT", goal="ENGAGE", payload={"message": "hi"}
            )

        decision = MagicMock()
        decision.decide = spy_decide
        decision.is_speculative_stop_confirmed = MagicMock()

        expected_controls = {"urgency_gain": 0.8}
        state = MagicMock()
        state.last_speculative_intent = None
        state.update_from_appraisal = AsyncMock()
        state.update_theory_of_mind = AsyncMock()
        state.get_context_snapshot = MagicMock(
            return_value=dict(_STATE_SNAPSHOT, global_controls=expected_controls)
        )
        state.get_behavioral_directive = MagicMock(return_value="be a good friend")

        perception = AsyncMock()
        perception.perceive.return_value = _make_chat_event("hello")

        appraisal = MagicMock()
        appraisal.appraise.return_value = AppraisalVector(
            relevance=1.0, novelty=0.5, goal_congruence=0.2, agency=0.8,
            norm_alignment=1.0, relationship_impact=0.1,
        )

        action = MagicMock()

        async def mock_execute(plan):
            yield {"type": "content", "data": "hi"}
            yield {"type": "done", "data": ""}

        action.execute.side_effect = mock_execute

        identity = MagicMock()
        identity.immutable_core = {"boundaries": []}
        identity.validate_response = AsyncMock(return_value=(True, ""))
        identity.get_persona_prompt = MagicMock(return_value="persona prompt")

        pipeline = CognitivePipeline(
            perception=perception,
            appraisal=appraisal,
            state=state,
            decision=decision,
            action=action,
            learning=AsyncMock(),
            identity=identity,
        )

        _ = [
            chunk
            async for chunk in pipeline.execute(
                {"type": "USER_MESSAGE", "content": "hello"}
            )
        ]

        assert received_kwargs.get("global_controls") == expected_controls


# --------------------------------------------------------------------------
# 6. Pure 7-bit ASCII (CLAUDE_TASK.md: "all code, comments, docstrings, and
# documentation must be pure 7-bit ASCII")
# --------------------------------------------------------------------------


class TestPureAscii:
    """Checks only the lines this package's Phase 03 work actually added,
    via `git diff` against the pre-Phase-03 merge base -- these files
    (decision.py, pipeline.py, action.py, config.py, action_intent.py)
    predate this package and already carry pre-existing non-ASCII bytes
    (curly em-dashes, section signs) in lines this package did not touch.
    A whole-file byte scan would fail on that pre-existing content
    regardless of what this package wrote; a diff-scoped check verifies the
    actual constraint (CLAUDE_TASK.md: "all code, comments, docstrings, and
    documentation must be pure 7-bit ASCII" for this package's own
    contribution) without demanding an unrelated rewrite of lines this
    package does not own.
    """

    _TOUCHED_FILES = (
        "app/cognitive/action_candidate.py",
        "app/cognitive/action_intent.py",
        "app/cognitive/decision.py",
        "app/cognitive/pipeline.py",
        "app/cognitive/action.py",
        "app/config.py",
        "tests/test_global_control_selection.py",
    )

    def test_new_files_are_pure_ascii(self):
        """action_candidate.py already existed pre-Phase-03 but had no
        REAPPRAISE/REDIRECT_ATTENTION/SUPPRESS_EXPRESSION content, and this
        test file is wholly new -- both can be scanned as complete files."""
        import pathlib

        backend_root = pathlib.Path(__file__).resolve().parent.parent
        offenders = []
        for relative_path in ("app/cognitive/action_candidate.py", "tests/test_global_control_selection.py"):
            raw = (backend_root / relative_path).read_bytes()
            try:
                raw.decode("ascii")
            except UnicodeDecodeError:
                offenders.append(relative_path)
        assert not offenders, f"Non-ASCII bytes found in: {offenders}"

    def test_lines_added_by_this_package_are_pure_ascii(self):
        """Diff-scoped scan: every `+` line this package's changes added to
        any touched file, across all 7 owned files, must be pure ASCII."""
        import pathlib
        import subprocess

        repo_root = pathlib.Path(
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
        )
        merge_base = subprocess.run(
            ["git", "merge-base", "main", "HEAD"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        ).stdout.strip()

        diff = subprocess.run(
            ["git", "diff", "--unified=0", merge_base, "--", *self._TOUCHED_FILES],
            cwd=repo_root, capture_output=True, check=True,
        ).stdout

        offenders = []
        for raw_line in diff.splitlines():
            if not raw_line.startswith(b"+") or raw_line.startswith(b"+++"):
                continue
            try:
                raw_line.decode("ascii")
            except UnicodeDecodeError:
                offenders.append(raw_line.decode("utf-8", errors="replace"))
        assert not offenders, f"Non-ASCII bytes found in added lines: {offenders}"
