"""Phase 1 causal slice (`CLAUDE_TASK.md`, `ACCEPTANCE_CRITERIA.md` AC-01/04/05/06):
end-to-end verification that a cognitive turn is traceable from a normalized
`PerceptEnvelope`, through an `ActionIntent` committed against a workspace
revision, to a terminal `OutcomeRecord` matching what was actually delivered
or cut short.

`WorkspaceStore`/`CognitiveWorkspace` (Codex's `app/state/workspace.py`) is a
parallel, not-yet-integrated work package -- these tests use a minimal
structural stand-in (`_FakeWorkspaceSnapshot`) satisfying
`pipeline.WorkspaceSnapshotLike` rather than importing that module, per
`CLAUDE_TASK.md`'s file-ownership split.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.brain_agent import BrainAgent
from app.cognitive import percept
from app.cognitive.action_intent import ActionIntent, OutcomeRecord
from app.cognitive.appraisal import AppraisalVector
from app.cognitive.behavior_contracts import BehaviorDecision, CommunicativeIntent
from app.cognitive.decision import ActionPlan
from app.cognitive.pipeline import CognitivePipeline

# --- PerceptEnvelope normalization (AC-04) --------------------------------


@pytest.mark.parametrize(
    "converter_name, raw_payload, expected",
    [
        (
            "from_chat_input",
            {
                "text": "hello there",
                "utterance_id": "utt-1",
                "turn_id": "turn-1",
                "metadata": {"source": "whisper", "confidence": 0.87},
            },
            {
                "modality": "text",
                "text_content": "hello there",
                "source": "whisper",
                "confidence": 0.87,
                "percept_prefix": "text-",
            },
        ),
        (
            # No metadata at all: every field must fall back to the
            # converter's own hardcoded defaults, not the real-metadata case's
            # values above (mutmut: catches a swallowed/defaulted metadata
            # dict that happens to produce the same result as real metadata).
            "from_chat_input",
            {"text": "hi"},
            {
                "modality": "text",
                "text_content": "hi",
                "source": "chat_input",
                "confidence": 0.9,
                "percept_prefix": "text-",
            },
        ),
        (
            "from_vision_description",
            {
                "description": "user is smiling",
                "source": "webcam",
                "timestamp": 123.0,
                "user_distance": 0.8,
                "is_novel": True,
            },
            {
                "modality": "vision",
                "text_content": "user is smiling",
                "source": "webcam",
                "confidence": 1.0,
                "observed_at": 123.0,
                "percept_prefix": "vision-",
            },
        ),
        (
            # is_novel=False takes the *other* branch of the confidence
            # ternary -- the True case above never exercises it.
            "from_vision_description",
            {"description": "same scene again", "is_novel": False},
            {
                "modality": "vision",
                "text_content": "same scene again",
                "source": "screen",
                "confidence": 0.5,
                "percept_prefix": "vision-",
            },
        ),
        (
            # is_novel key entirely absent: must fall back to the `True`
            # default (confidence 1.0), not the explicit-False case above --
            # an explicit key always shadows a mutated default, so only an
            # absent key can distinguish this branch's own default value.
            "from_vision_description",
            {"description": "first look"},
            {
                "modality": "vision",
                "text_content": "first look",
                "source": "screen",
                "confidence": 1.0,
                "percept_prefix": "vision-",
            },
        ),
        (
            "from_facial_reflex",
            {
                "name": "startle",
                "valence_delta": -0.2,
                "arousal_delta": 0.4,
                "dopamine_spike": 0.0,
                "evidence": "startle=0.91",
                "timestamp": 456.0,
                # Deliberately distinct from the "source absent" case's
                # hardcoded fallback ("camera") below, so a mutated key
                # name/lookup can't hide behind a coincidental match.
                "source": "external_mic_array",
            },
            {
                "modality": "reflex",
                "text_content": "startle=0.91",
                "source": "external_mic_array",
                "observed_at": 456.0,
                "percept_prefix": "reflex-",
            },
        ),
        (
            "from_facial_reflex",
            {"name": "smile", "evidence": "smile=0.6"},
            {
                "modality": "reflex",
                "text_content": "smile=0.6",
                "source": "camera",  # hardcoded default when source is absent
                "percept_prefix": "reflex-",
            },
        ),
        (
            "from_audio_stop",
            {
                "interrupt": True,
                "speculative": False,
                "reason": "confirmed_command",
                "command_text": "stop please",
                "intent_type": "VISION_INTERRUPTION",  # deliberately distinct
                "confidence": 0.75,  # from the hardcoded
                "perception_text": "hold on",  # fallback defaults, so
                "utterance_id": "utt-2",  # a fallback bug can't
                "turn_id": "turn-2",  # hide behind a
            },  # coincidental match.
            {
                "modality": "audio",
                "text_content": "hold on",
                "source": "VISION_INTERRUPTION",
                "confidence": 0.75,
                "percept_prefix": "audio-",
            },
        ),
        (
            # No perception_text (falls through to command_text) and no
            # confidence/intent_type (both hardcoded defaults).
            "from_audio_stop",
            {"interrupt": True, "speculative": False, "command_text": "stop"},
            {
                "modality": "audio",
                "text_content": "stop",
                "source": "VOICE_INTERRUPTION",
                "confidence": 0.0,
                "percept_prefix": "audio-",
            },
        ),
        (
            "from_system_tick",
            {
                "timestamp": 789.0,
                "uptime": 10.0,
                "interval": 5,
                # Deliberately distinct from the hardcoded "system_agent"
                # fallback below, so a mutated key name/lookup can't hide
                # behind SystemAgent's real tick payload happening to match
                # the fallback value too.
                "source": "heartbeat_monitor",
            },
            {
                "modality": "system",
                "text_content": None,
                "source": "heartbeat_monitor",
                "observed_at": 789.0,
                "percept_prefix": "system-",
            },
        ),
        (
            "from_system_tick",
            {"uptime": 1.0, "interval": 5},
            {
                "modality": "system",
                "text_content": None,
                "source": "system_agent",
                "percept_prefix": "system-",
            },
        ),
        (
            "from_playback_progress",
            {
                "utterance_id": "utt-3",
                "character_offset": 12,
                "word_index": 2,
                "completed": False,
            },
            {
                "modality": "playback",
                "text_content": None,
                "source": "transport_agent",
                "percept_prefix": "playback-",
            },
        ),
    ],
)
def test_percept_envelope_from_all_modalities(converter_name, raw_payload, expected):
    """AC-04: every modality converter must produce a validated
    `PerceptEnvelope` whose `modality`/`source`/`confidence`/`observed_at`/
    `text_content`/`raw_payload` losslessly reflect the source event -- a
    converter that drops or falls back to a default instead of the real field
    (e.g. a swallowed `metadata` dict) silently breaks every later stage that
    trusts these values to route or attribute on. Each modality is exercised
    both with its optional fields present (must read the real value, not
    coincide with the hardcoded default) and absent (must fall back to the
    documented default, not crash or silently produce something else)."""
    converter = getattr(percept, converter_name)
    envelope = converter(raw_payload)

    assert envelope.modality == expected["modality"]
    assert envelope.text_content == expected["text_content"]
    assert envelope.source == expected["source"]
    assert envelope.raw_payload == raw_payload
    assert envelope.percept_id.startswith(expected["percept_prefix"])
    if "confidence" in expected:
        assert envelope.confidence == pytest.approx(expected["confidence"])
    else:
        assert 0.0 <= envelope.confidence <= 1.0
    if "observed_at" in expected:
        assert envelope.observed_at == pytest.approx(expected["observed_at"])
    else:
        # No payload timestamp: must fall back to "now", not crash or leave
        # a stale/zero value -- this is the only way to distinguish the
        # `time.time()` default from a mutant that drops it (both produce
        # "now" when a real timestamp is supplied, so that case alone can't
        # tell them apart).
        import time as time_module

        assert abs(envelope.observed_at - time_module.time()) < 5.0


def test_percept_ids_are_unique_per_call():
    """Two percepts from the same raw payload must not collide -- a
    downstream ActionIntent linking to `percept_id` would otherwise bind to
    the wrong event whenever two of the same modality fire in a row."""
    first = percept.from_chat_input({"text": "hi", "metadata": {}})
    second = percept.from_chat_input({"text": "hi", "metadata": {}})
    assert first.percept_id != second.percept_id


@pytest.mark.parametrize(
    "raw_value, default, expected",
    [
        (0.42, 1.0, 0.42),
        (None, 0.9, 0.9),  # missing/non-numeric input falls back to default
        ("not-a-number", 0.9, 0.9),
        (-5.0, 1.0, 0.0),  # clamped to the lower bound
        (5.0, 1.0, 1.0),  # clamped to the upper bound
    ],
)
def test_clamp_confidence_bounds(raw_value, default, expected):
    """AC-04: confidence must stay a valid probability -- a converter that
    passes an out-of-range or unparsable source value through unclamped would
    violate `PerceptEnvelope.confidence`'s own `ge=0.0, le=1.0` contract."""
    assert percept._clamp_confidence(raw_value, default=default) == pytest.approx(
        expected
    )


def test_clamp_confidence_uses_its_own_default_when_caller_omits_one():
    """Every converter always passes an explicit `default=`, so this is the
    only path that exercises `_clamp_confidence`'s own default parameter
    value directly."""
    assert percept._clamp_confidence(None) == pytest.approx(1.0)


# --- ActionIntent commitment (AC-01, AC-05) --------------------------------


# --- ActionIntent/OutcomeRecord constructors -------------------------------


def test_build_outcome_record_defaults_character_offset_to_zero():
    """A COMPLETED/CANCELLED outcome with nothing delivered must record a
    real zero offset, not an arbitrary non-zero default that would misreport
    how much was heard."""
    from app.cognitive.action_intent import build_action_intent, build_outcome_record

    intent = build_action_intent(
        turn_id="turn-x",
        workspace_epoch=0,
        workspace_revision=0,
        kind="SPEAK",
        behavior_decision={},
    )
    record = build_outcome_record(intent, status="CANCELLED")
    assert record.character_offset == 0


def test_build_outcome_record_elapsed_ms_measures_real_time_since_commit():
    """`elapsed_ms` must be derived from the real gap between when the
    ActionIntent was committed and when the outcome was recorded -- a wrong
    scale (e.g. seconds instead of milliseconds) or sign would make every
    downstream latency measurement (AC-GPU-01) meaningless."""
    import time as time_module

    from app.cognitive.action_intent import build_action_intent, build_outcome_record

    intent = build_action_intent(
        turn_id="turn-x",
        workspace_epoch=0,
        workspace_revision=0,
        kind="SPEAK",
        behavior_decision={},
    )
    time_module.sleep(0.1)
    record = build_outcome_record(intent, status="COMPLETED")

    # Real elapsed wall-clock time is ~100ms; allow generous scheduling
    # slack but reject anything that isn't roughly milliseconds-scaled
    # (a seconds-scaled bug would read ~0.1, a microseconds-scaled bug
    # would read ~100000).
    assert 50.0 <= record.elapsed_ms <= 2000.0


@dataclass
class _FakeWorkspaceSnapshot:
    """Structural stand-in for Codex's `CognitiveWorkspaceSnapshot` --
    satisfies `pipeline.WorkspaceSnapshotLike` (any object exposing
    `epoch`/`revision`) without importing the not-yet-integrated
    `app/state/workspace.py`."""

    epoch: int
    revision: int


def _mock_pipeline_components():
    state = MagicMock()
    state.last_speculative_intent = None
    state.update_from_appraisal = AsyncMock()
    state.update_theory_of_mind = AsyncMock()
    state.get_context_snapshot = MagicMock(return_value={"mood": 0.0})
    state.get_behavioral_directive = MagicMock(return_value="be friendly")

    decision = MagicMock()
    decision.decide = AsyncMock()
    decision.is_speculative_stop_confirmed = MagicMock()

    action = MagicMock()

    identity = MagicMock()
    identity.validate_response = AsyncMock(return_value=(True, ""))
    identity.get_persona_prompt = MagicMock(return_value="system prompt")
    identity.immutable_core = {"boundaries": []}

    perception = AsyncMock()
    perception.perceive.return_value = MagicMock(
        event_type="USER_MESSAGE",
        raw_content="hello",
        intent="CHAT",
        event_id="evt-1",
        metadata={},
    )

    appraisal = MagicMock()
    appraisal.appraise.return_value = AppraisalVector(
        relevance=1.0,
        novelty=0.5,
        goal_congruence=0.2,
        agency=0.8,
        norm_alignment=1.0,
        relationship_impact=0.1,
    )

    return {
        "perception": perception,
        "appraisal": appraisal,
        "state": state,
        "decision": decision,
        "action": action,
        "learning": AsyncMock(),
        "identity": identity,
    }


async def _drain(pipeline, raw_event, **kwargs):
    chunks = []
    async for chunk in pipeline.execute(raw_event, **kwargs):
        chunks.append(chunk)
    return chunks


@pytest.mark.asyncio
async def test_pipeline_commits_action_intent():
    """AC-01/AC-05: Stage 6 must commit a typed `ActionIntent` -- carrying
    the exact `(workspace_epoch, workspace_revision)` this turn read from --
    before Stage 8 generates any content."""
    components = _mock_pipeline_components()
    components["decision"].decide.return_value = ActionPlan(
        action_type="RESPOND_CHAT",
        payload={"message": "hi"},
        goal="ENGAGE",
        behavior_decision=BehaviorDecision(
            intent=CommunicativeIntent(act="CHAT", goal="ENGAGE")
        ),
    )

    async def mock_execute(plan):
        yield {"type": "content", "data": "Hi there!"}
        yield {"type": "done", "data": ""}

    components["action"].execute.side_effect = mock_execute
    pipeline = CognitivePipeline(**components)

    my_percept = percept.from_chat_input({"text": "hello", "metadata": {}})
    workspace = _FakeWorkspaceSnapshot(epoch=3, revision=7)

    chunks = await _drain(
        pipeline,
        {"id": "evt-1", "type": "USER_MESSAGE", "content": "hello", "metadata": {}},
        percept=my_percept,
        workspace=workspace,
    )

    intent_chunks = [c for c in chunks if c["type"] == "action_intent"]
    assert len(intent_chunks) == 1, (
        "Stage 6 must commit exactly one ActionIntent per turn"
    )

    intent = ActionIntent.model_validate(intent_chunks[0]["data"])
    assert intent.workspace_epoch == 3
    assert intent.workspace_revision == 7
    assert intent.kind == "SPEAK"
    assert intent.behavior_decision["percept_id"] == my_percept.percept_id

    # The intent must be committed before any content is streamed (Stage 6
    # precedes Stage 8) -- not merely present somewhere in the chunk stream.
    intent_index = chunks.index(intent_chunks[0])
    first_content_index = next(
        i for i, c in enumerate(chunks) if c["type"] == "content"
    )
    assert intent_index < first_content_index


@pytest.mark.asyncio
async def test_pipeline_action_intent_defaults_workspace_when_absent():
    """AC-01: a caller that predates workspace wiring (today's production
    caller, `CognitiveService.process_event`) must still get a causal trace
    -- degraded to a `(0, 0)` tuple, never silently dropped."""
    components = _mock_pipeline_components()
    components["decision"].decide.return_value = ActionPlan(
        action_type="BACKGROUND_CONSOLIDATION",
        payload={},
        goal="REFLECT",
        priority=0,
        behavior_decision=BehaviorDecision(
            intent=CommunicativeIntent(act="REFLECT", goal="REFLECT")
        ),
    )

    async def mock_execute(plan):
        yield {"type": "done", "data": ""}

    components["action"].execute.side_effect = mock_execute
    pipeline = CognitivePipeline(**components)

    chunks = await _drain(
        pipeline,
        {"id": "evt-2", "type": "USER_MESSAGE", "content": "hello", "metadata": {}},
    )

    intent_chunks = [c for c in chunks if c["type"] == "action_intent"]
    assert len(intent_chunks) == 1
    intent = ActionIntent.model_validate(intent_chunks[0]["data"])
    assert (intent.workspace_epoch, intent.workspace_revision) == (0, 0)
    assert intent.kind == "REFLECT"


# --- Terminal OutcomeRecord (AC-06) ----------------------------------------


def _make_agent(graph_db, memory_store) -> BrainAgent:
    return BrainAgent(
        ollama_url="http://dummy",
        graph_db=graph_db,
        memory_store=memory_store,
        conversation_store=None,
    )


def _seed_active_intent(agent: BrainAgent, turn_id: str = "turn-1") -> ActionIntent:
    intent = ActionIntent(
        intent_id="intent-1",
        turn_id=turn_id,
        workspace_epoch=1,
        workspace_revision=1,
        kind="SPEAK",
        behavior_decision={"goal": "ENGAGE"},
    )
    agent._active_action_intent = intent
    agent._active_response_turn_id = turn_id
    return intent


@pytest.mark.asyncio
async def test_turn_completion_emits_completed_outcome(
    mock_graph_db, mock_memory_store
):
    """AC-06: a normal, uninterrupted turn's playback-completed signal must
    produce a terminal OutcomeRecord whose delivered text/offset match the
    full generated response."""
    agent = _make_agent(mock_graph_db, mock_memory_store)
    intent = _seed_active_intent(agent)
    full_text = "This is the complete assistant reply."
    agent.last_assistant_response = full_text

    await agent._on_audio_playback_progress(
        {
            "utterance_id": "turn-1",
            "character_offset": len(full_text),
            "word_index": len(full_text.split()),
            "completed": True,
        }
    )

    record = agent._last_outcome_record
    assert record is not None
    assert isinstance(record, OutcomeRecord)
    assert record.intent_id == intent.intent_id
    assert record.turn_id == intent.turn_id
    assert record.status == "COMPLETED"
    assert record.actual_delivered_text == full_text
    assert record.character_offset == len(full_text)


@pytest.mark.asyncio
async def test_turn_interruption_emits_truncated_outcome(
    mock_graph_db, mock_memory_store
):
    """AC-06: a barge-in truncation must produce an OutcomeRecord whose
    `character_offset` matches the exact playback-reported offset, not the
    full generated text length."""
    agent = _make_agent(mock_graph_db, mock_memory_store)
    intent = _seed_active_intent(agent)
    full_text = "I was about to say something long but got cut off here."
    agent.last_assistant_response = full_text

    class _Progress:
        completed = False
        character_offset = 20

    agent.last_audio_progress = _Progress()

    await agent._truncate_interrupted_reply()

    record = agent._last_outcome_record
    assert record is not None
    assert record.intent_id == intent.intent_id
    assert record.status == "TRUNCATED"
    assert record.character_offset == 20
    assert record.actual_delivered_text == full_text[:20].strip()
    # The progress marker must be cleared regardless of outcome so a later
    # interrupt cannot truncate against a stale offset.
    assert agent.last_audio_progress is None


@pytest.mark.asyncio
async def test_cancelled_generation_emits_cancelled_outcome(
    mock_graph_db, mock_memory_store
):
    """AC-06: a generation cancelled before any content streamed (nothing to
    truncate) must still produce a terminal OutcomeRecord, distinct from
    TRUNCATED, so a turn that never spoke is not left without any record."""
    agent = _make_agent(mock_graph_db, mock_memory_store)
    intent = _seed_active_intent(agent)
    agent.last_assistant_response = None  # nothing was ever generated

    import asyncio

    async def never_finishes():
        await asyncio.Event().wait()

    agent._active_generation_task = asyncio.create_task(never_finishes())

    await agent._cancel_active_generation("confirmed_user_speech")

    record = agent._last_outcome_record
    assert record is not None
    assert record.intent_id == intent.intent_id
    assert record.status == "CANCELLED"
    assert record.error == "confirmed_user_speech"
    assert record.actual_delivered_text is None


@pytest.mark.asyncio
async def test_cancel_active_generation_defers_to_truncation_when_text_exists(
    mock_graph_db, mock_memory_store
):
    """A cancellation that lands *after* content has already streamed must
    not also emit a CANCELLED record -- `_truncate_interrupted_reply` (called
    immediately after by the only production caller, `_on_audio_stop`) owns
    the terminal record for that case, so a turn gets exactly one, not two
    disagreeing outcomes."""
    agent = _make_agent(mock_graph_db, mock_memory_store)
    _seed_active_intent(agent)
    agent.last_assistant_response = "partial reply already streamed"

    import asyncio

    async def never_finishes():
        await asyncio.Event().wait()

    agent._active_generation_task = asyncio.create_task(never_finishes())

    await agent._cancel_active_generation("confirmed_command")

    assert agent._last_outcome_record is None


@pytest.mark.asyncio
async def test_outcome_record_with_no_active_intent_is_skipped(
    mock_graph_db, mock_memory_store
):
    """A subconscious/proactive turn never reaches Stage 6 (it bypasses
    `CognitivePipeline` entirely via `generate_proactive_response`), so there
    is no `ActionIntent` to attribute an outcome to -- this must be a no-op,
    not a fabricated record."""
    agent = _make_agent(mock_graph_db, mock_memory_store)
    agent._active_action_intent = None
    agent.last_assistant_response = "some proactive text"

    result = await agent._emit_outcome_record(
        None, status="COMPLETED", actual_delivered_text="some proactive text"
    )

    assert result is None
    assert agent._last_outcome_record is None
