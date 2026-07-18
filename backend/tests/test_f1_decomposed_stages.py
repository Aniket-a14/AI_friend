"""
Unit tests for the stages extracted from the two god-functions (F1).

Before the decomposition none of this was reachable without driving the whole
~1600-line search_memories / ~520-line ActionService.execute pipeline end to
end. Each stage is now independently testable, which is the point of the
refactor: it makes the memory and action paths safe to iterate on.
"""

from unittest.mock import MagicMock

import pytest

from app.cognitive.action import (
    ActionService,
    ControlMarkupSanitizer,
    _ChatStreamState,
    _CHAT_GUIDELINE,
)
from app.state.memory_store import (
    DIRECT_CUE_BOOST,
    SEARCH_STOP_WORDS,
    MemoryStore,
)


# --------------------------------------------------------------------------
# memory_store stages
# --------------------------------------------------------------------------


def _store():
    store = MemoryStore(MagicMock(), MagicMock())
    store.qdrant_store.client = None
    return store


@pytest.mark.parametrize(
    "arousal,cortisol,expected_dim",
    [
        (0.9, 0.0, 256),  # high stress -> narrowest Matryoshka prefix
        (0.0, 0.9, 256),  # cortisol alone is enough
        (0.7, 0.0, 512),  # mid stress
        (0.1, 0.1, 768),  # calm -> full width
    ],
)
def test_mrl_gating_narrows_under_stress(arousal, cortisol, expected_dim):
    dim, _limit = MemoryStore._compute_mrl_gating(arousal, cortisol, 5, True)
    assert dim == expected_dim


def test_mrl_gating_candidate_pool_shrinks_as_stress_rises():
    calm = MemoryStore._compute_mrl_gating(0.1, 0.0, 5, True)[1]
    mid = MemoryStore._compute_mrl_gating(0.7, 0.0, 5, True)[1]
    high = MemoryStore._compute_mrl_gating(0.9, 0.0, 5, True)[1]
    assert calm > mid > high


def test_mrl_gating_without_refresh_uses_smaller_pool():
    with_refresh = MemoryStore._compute_mrl_gating(0.1, 0.0, 5, True)[1]
    without = MemoryStore._compute_mrl_gating(0.1, 0.0, 5, False)[1]
    assert without < with_refresh


def test_mrl_gating_tolerates_none_limit():
    assert MemoryStore._compute_mrl_gating(0.9, 0.0, None, True) == (256, 10)
    assert MemoryStore._compute_mrl_gating(0.1, 0.0, None, False) == (768, 20)


def test_pronoun_cues_flip_between_user_and_self_reflection():
    """"I"/"you" swap referents depending on who is speaking."""
    kwargs = dict(agent_node_name="Aniket", user_node_name="Raj", user_id="Raj")

    user_speaking = MemoryStore._resolve_pronoun_cues(
        "what did I tell you", is_self_reflection=False, **kwargs
    )
    assert "raj" in user_speaking and "aniket" in user_speaking

    self_reflecting = MemoryStore._resolve_pronoun_cues(
        "what did I tell you", is_self_reflection=True, **kwargs
    )
    # Same sentence, same two names surface - the mapping is what inverts.
    assert "raj" in self_reflecting and "aniket" in self_reflecting

    only_first = MemoryStore._resolve_pronoun_cues(
        "what did I do", is_self_reflection=False, **kwargs
    )
    assert only_first == {"raj"}

    only_first_reflecting = MemoryStore._resolve_pronoun_cues(
        "what did I do", is_self_reflection=True, **kwargs
    )
    assert only_first_reflecting == {"aniket"}


def test_pronoun_cues_pick_up_explicit_names():
    cues = MemoryStore._resolve_pronoun_cues(
        "tell me about Raj", "Aniket", "Raj", "Raj", False
    )
    assert "raj" in cues


def test_direct_cue_boost_scales_with_match_count_and_reports_indices():
    candidates = [
        {"content": "cricket in kolkata", "score": 0.0},
        {"content": "nothing relevant here", "score": 0.0},
        {"content": "cricket cricket", "score": 0.0},
    ]
    boosted = MemoryStore._apply_direct_cue_boost(candidates, ["cricket", "kolkata"])

    assert boosted == {0, 2}
    assert candidates[0]["score"] == pytest.approx(2 * DIRECT_CUE_BOOST)
    assert candidates[1]["score"] == 0.0
    # "cricket" appears once as a substring check per cue, not per occurrence
    assert candidates[2]["score"] == pytest.approx(1 * DIRECT_CUE_BOOST)


def test_direct_cue_boost_no_cues_is_a_noop():
    candidates = [{"content": "anything", "score": 1.0}]
    assert MemoryStore._apply_direct_cue_boost(candidates, []) == set()
    assert candidates[0]["score"] == 1.0


def test_format_results_drops_sub_threshold_and_projects_shape():
    from datetime import datetime, timezone

    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    raw = [
        {
            "content": "keep me",
            "raw_content": "keep me",
            "wing": "personal",
            "room": "social",
            "score": 2.0,
            "valence": 0.3,
            "created_at": created,
            "recall_count": 2,
            "metadata": {"k": "v"},
            "lifespan_stage": "adulthood",
            "crisis": "intimacy",
            "virtue": "love",
            "relations": "friend",
            "relation_circles": "inner",
            "modality": "text",
        },
        {
            "content": "drop me",
            "raw_content": "drop me",
            "wing": "personal",
            "room": None,
            "score": 0.5,
            "valence": 0.0,
            "created_at": None,
            "recall_count": 1,
            "metadata": {},
        },
    ]
    results = MemoryStore._format_results(raw, threshold=1.0)

    assert [r["content"] for r in results] == ["keep me"]
    assert results[0]["created_at"] == created.isoformat()
    assert results[0]["lifespan_stage"] == "adulthood"
    # score is strictly greater-than the threshold, not >=
    assert MemoryStore._format_results(raw, threshold=2.0) == []


def test_build_entity_graph_is_symmetric_and_adds_cooccurrence():
    entity_records = [{"name": "Raj"}, {"name": "Kolkata"}, {"name": "Aniket"}]
    relation_records = [{"source": "Raj", "target": "Aniket"}]
    candidates = [{"content": "Raj visited Kolkata", "metadata": {}}]

    names, adj = MemoryStore._build_entity_graph(
        entity_records, relation_records, candidates
    )

    assert names == ["Raj", "Kolkata", "Aniket"]
    # explicit relation, both directions
    assert "Aniket" in adj["Raj"] and "Raj" in adj["Aniket"]
    # co-occurrence discovered from the memory text, both directions
    assert "Kolkata" in adj["Raj"] and "Raj" in adj["Kolkata"]


def test_resolve_identity_nodes_prefers_described_agent():
    entity_records = [
        {"name": "Bruno", "description": "A dog"},
        {"name": "Aniket", "description": "The central cognitive system."},
        {"name": "Raj", "description": "User / Companion"},
    ]
    names = [r["name"] for r in entity_records]
    agent, user = MemoryStore._resolve_identity_nodes(entity_records, names, {}, "Raj")
    assert agent == "Aniket"
    assert user == "Raj"


def test_resolve_identity_nodes_falls_back_when_graph_is_empty():
    agent, user = MemoryStore._resolve_identity_nodes([], [], {}, None)
    assert agent  # configured AI_NAME
    assert user == "user"


def test_normalize_recall_ts_handles_every_stored_shape():
    from datetime import datetime, timezone

    now_ts = 1_700_000_000.0
    dt = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert MemoryStore._normalize_recall_ts(None, now_ts) == now_ts
    assert MemoryStore._normalize_recall_ts(dt, now_ts) == dt.timestamp()
    assert MemoryStore._normalize_recall_ts(123.5, now_ts) == 123.5
    assert MemoryStore._normalize_recall_ts("123.5", now_ts) == 123.5
    assert MemoryStore._normalize_recall_ts("2026-01-01 00:00:00", now_ts) == (
        dt.timestamp()
    )
    assert MemoryStore._normalize_recall_ts("not a date", now_ts) == now_ts


def test_parse_stored_embedding_accepts_json_list_and_literal():
    assert MemoryStore._parse_stored_embedding([0.1, 0.2]) == [0.1, 0.2]
    assert MemoryStore._parse_stored_embedding("[0.1, 0.2]") == [0.1, 0.2]
    # pgvector-style literal that is not valid JSON still yields floats
    assert MemoryStore._parse_stored_embedding("(0.5,-0.25)") == [0.5, -0.25]
    assert MemoryStore._parse_stored_embedding(None) is None


def test_stop_words_are_generic_not_corpus_specific():
    """B1 guard: the hoisted list must not re-acquire benchmark proper nouns."""
    for leaked in ("rasgulla", "kolkata", "mimi", "bruno", "aniket", "raj"):
        assert leaked not in SEARCH_STOP_WORDS
    for generic in ("the", "and", "because", "yourselves"):
        assert generic in SEARCH_STOP_WORDS


def test_goal_buffer_boost_is_noop_without_active_concepts():
    store = _store()
    store.goal_buffer.flush()
    candidates = [{"content": "anything at all", "score": 1.0}]
    store._apply_goal_buffer_boost(candidates)
    assert candidates[0]["score"] == 1.0


# --------------------------------------------------------------------------
# action stages
# --------------------------------------------------------------------------


def _service():
    return ActionService(llm_service=MagicMock(), memory_store=MagicMock())


def test_endocrine_options_none_when_no_signal():
    assert ActionService._compute_endocrine_options({}) is None


def test_endocrine_cortisol_lowers_temperature():
    calm = ActionService._compute_endocrine_options({"cortisol": 0.0})
    stressed = ActionService._compute_endocrine_options({"cortisol": 1.0})
    assert calm["temperature"] > stressed["temperature"]
    assert stressed["temperature"] == pytest.approx(0.3)


def test_endocrine_dopamine_raises_top_p_and_fatigue_shortens_output():
    low = ActionService._compute_endocrine_options({"dopamine": 0.0})
    high = ActionService._compute_endocrine_options({"dopamine": 1.0})
    assert high["top_p"] > low["top_p"]

    fresh = ActionService._compute_endocrine_options({"fatigue": 0.0})
    tired = ActionService._compute_endocrine_options({"fatigue": 1.0})
    assert fresh["num_predict"] == 250
    assert tired["num_predict"] == 100


def test_endocrine_num_predict_stays_bounded_for_out_of_range_fatigue():
    over = ActionService._compute_endocrine_options({"fatigue": 99.0})
    under = ActionService._compute_endocrine_options({"fatigue": -5.0})
    assert over["num_predict"] == 100
    assert under["num_predict"] == 250


def test_endocrine_bad_types_fall_back_to_defaults():
    opts = ActionService._compute_endocrine_options(
        {"cortisol": "nope", "dopamine": "nope", "fatigue": "nope"}
    )
    assert opts["temperature"] == 0.7
    assert opts["top_p"] == 0.8
    assert opts["num_predict"] == 250


def test_endocrine_missing_field_uses_neutral_default():
    opts = ActionService._compute_endocrine_options({"cortisol": 0.5})
    assert opts["top_p"] == 0.8  # dopamine absent -> neutral


@pytest.mark.parametrize(
    "arousal,valence,expected",
    [
        (0.9, -0.9, "<breath_fast> "),  # agitated + negative
        (0.2, -0.2, "<sigh_soft> "),  # subdued + negative
        (0.9, 0.9, ""),  # positive -> no opener
        (0.5, 0.5, ""),
    ],
)
def test_prepended_affect_tag(arousal, valence, expected):
    assert ActionService._prepended_affect_tag(arousal, valence) == expected


def test_build_tom_context_empty_without_model():
    assert ActionService._build_tom_context(None) == ""
    assert ActionService._build_tom_context({}) == ""


def test_build_tom_context_caps_known_concepts_at_ten():
    ctx = ActionService._build_tom_context(
        {"known_concepts": [f"c{i}" for i in range(25)], "implied_goals": ["vent"]}
    )
    assert "c24" in ctx and "c15" in ctx
    assert "c14" not in ctx  # only the last 10 survive
    assert "vent" in ctx


def test_build_tom_context_survives_wrong_goals_type():
    ctx = ActionService._build_tom_context({"implied_goals": "not-a-list"})
    assert "Implied Goals" not in ctx  # coerced to empty, not crashed


def test_build_shared_history_edge_loads_most_relevant():
    memories = [
        {"content": "A", "score": 0.9},
        {"content": "B", "score": 0.8},
        {"content": "C", "score": 0.7},
    ]
    block = ActionService._build_shared_history(memories)
    lines = [ln for ln in block.split("\n") if ln.startswith("- ")]
    # Highest-relevance items bracket the block (A first, B last)
    assert lines[0] == "- A"
    assert lines[-1] == "- B"


def test_build_shared_history_empty_for_no_memories():
    assert ActionService._build_shared_history([]) == ""


def test_split_thought_returns_tail_after_closing_tag():
    assert ActionService._split_thought("<thought>reasoning</thought>spoken") == (
        "spoken"
    )
    assert ActionService._split_thought("<thought>only</thought>") == ""


def test_chat_guideline_carries_the_grounding_contract():
    assert "GROUNDING" in _CHAT_GUIDELINE
    assert "Do not invent memories" in _CHAT_GUIDELINE
    assert _CHAT_GUIDELINE.startswith("Guideline:")


def test_chat_stream_state_defaults():
    state = _ChatStreamState(dominance=0.3)
    assert state.accumulated_response == ""
    assert state.in_thought is False
    assert state.has_hesitated is False
    assert state.dominance == 0.3


@pytest.mark.asyncio
async def test_emit_validated_injects_one_hesitation_only():
    svc = _service()
    state = _ChatStreamState(dominance=0.2)

    first = [o async for o in svc._emit_validated("well, ok", state, "ENGAGE")]
    assert first[0]["data"] == "well <hesitate>, ok"
    assert state.has_hesitated is True

    second = [o async for o in svc._emit_validated("more, text", state, "ENGAGE")]
    assert second[0]["data"] == "more, text"  # budget already spent


@pytest.mark.asyncio
async def test_emit_validated_skips_hesitation_when_disallowed():
    svc = _service()
    state = _ChatStreamState(dominance=0.1)
    out = [
        o
        async for o in svc._emit_validated(
            "a, b", state, "ENGAGE", allow_hesitation=False
        )
    ]
    assert out[0]["data"] == "a, b"
    assert state.has_hesitated is False


@pytest.mark.asyncio
async def test_emit_validated_accumulates_and_raises_on_violation():
    from app.cognitive.action import MetacognitiveException

    svc = _service()
    state = _ChatStreamState(dominance=0.9)

    [o async for o in svc._emit_validated("hello ", state, "ENGAGE")]
    assert state.accumulated_response == "hello "

    with pytest.raises(MetacognitiveException):
        [o async for o in svc._emit_validated("as an AI I cannot", state, "ENGAGE")]
    # a rejected chunk must not be accumulated
    assert state.accumulated_response == "hello "


def test_control_markup_sanitizer_drops_emotion_keeps_timing():
    s = ControlMarkupSanitizer()
    assert s.feed("<emotion happy>hi</emotion> there") == "hi there"
    s2 = ControlMarkupSanitizer()
    assert s2.feed("wait <pause=300ms> ok") == "wait <pause=300ms> ok"


def test_control_markup_sanitizer_holds_partial_tag_until_flush():
    s = ControlMarkupSanitizer()
    assert s.feed("text <emo") == "text "
    assert s.feed("tion sad>rest") == "rest"
    assert s.flush() == ""
