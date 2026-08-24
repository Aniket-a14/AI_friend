import json
import time
from unittest.mock import mock_open, patch

import pytest

from app.cognitive.identity import IdentityManager
from app.metrics import SubjectMetrics
from app.state.agent_state import AgentState
from app.utils.segmentation import HybridSegmenter

pytest.importorskip("pytest_benchmark")


# Helper mock for memory rows
def _make_mock_row(content, similarity=1.0, recall_count=1):
    return {
        "content": content,
        "raw_content": content,
        "wing": "personal",
        "room": "lounge",
        "importance_score": 0.8,
        "emotional_weight": 0.5,
        "valence": 0.3,
        "recall_count": recall_count,
        "last_recalled_at": time.time() - 3600,
        "created_at": time.time() - 86400,
        "metadata": "{}",
        "similarity": similarity,
    }


# ==========================================
# 1. ASYNC TELEMETRY BUFFER BENCHMARKS
# ==========================================


@pytest.mark.benchmark
def test_async_telemetry_queue_put_benchmark(benchmark):
    """Profiles the latency of posting metrics to the new asynchronous queue buffer."""
    metrics = SubjectMetrics(tracked_subjects={"chat.input"}, log_every=100)

    def run():
        # Captures start time and queues non-blockingly instantly
        metrics.record("chat.input", direction="rx", latency_ms=1.2)
        return metrics._queue.qsize()

    qsize = benchmark(run)
    metrics.shutdown()
    assert qsize >= 0


@pytest.mark.benchmark
def test_subject_metrics_record_benchmark(benchmark):
    """Profiles end-to-end async telemetry recording and logging aggregation."""
    metrics = SubjectMetrics(tracked_subjects={"chat.input"}, log_every=100)
    payload = {"latency_metadata": {"start_time": time.time() - 0.01}}

    def run():
        metrics.record("chat.input", direction="rx", data=payload)
        return True

    res = benchmark(run)
    metrics.shutdown()
    assert res is True


# ==========================================
# 2. COGNITIVE & IDENTITY APPRAISAL
# ==========================================


@pytest.mark.benchmark
def test_identity_appraisal_benchmark(benchmark):
    """Profiles dynamic prompt generation and identity parsing in the IdentityManager."""
    personality = {
        "name": "Aniket's Assistant",
        "core_personality": {"traits": ["Curious", "Supportive", "Empathetic"]},
        "conversation_rules": {"avoid": ["As an AI", "I am a language model"]},
        "speaking_style": {"pace": "fluent", "common_vocabulary": ["arre", "yaar"]},
    }
    # `patch("builtins.open", mock_open=MagicMock(...))` passed `mock_open` as a
    # keyword to `patch` rather than as the replacement, so the file was never
    # actually read and the test depended entirely on the assignment below.
    m_open = patch("builtins.open", mock_open(read_data=json.dumps(personality)))
    m_exists = patch("os.path.exists", return_value=True)

    with m_open, m_exists:
        manager = IdentityManager(base_path="/fake/path", persona_file=None)

        def run():
            return manager.get_persona_prompt()

        prompt = benchmark(run)
        assert "Aniket's Assistant" in prompt


@pytest.mark.benchmark
def test_reappraisal_cognitive_benchmark(benchmark):
    """Profiles secondary cognitive reappraisal triggers adjusting emotional coping valence using production logic."""
    from app.cognitive.reappraisal import ReappraisalEngine

    engine = ReappraisalEngine()
    engine.enabled = True

    # Pre-populate turn state to bypass return early checks
    state_snap = {"mood": 0.2, "energy": 0.5, "dominance": 0.5, "trust": 0.5}

    def run():
        # Benchmark the full pre-response tracking and outcome evaluation logic
        engine.record_pre_response_state(state_snap)
        engine.record_expected_outcome("COMFORT", 0.2)
        # Bypassing the 2.0s rate limiting by resetting last_evaluation_time to 0
        engine._last_evaluation_time = 0.0

        # Run actual_text_valence evaluation
        import asyncio

        asyncio.run(
            engine.evaluate_outcome(
                actual_text_valence=-0.4, acoustic_delta=-0.2, behavioral_signal=0.1
            )
        )
        return engine.appraisal_weights["w1_g_to_v"]

    w1 = benchmark(run)
    assert w1 > 0.0


# ==========================================
# 3. SUBCONSCIOUS & ARBITRATION
# ==========================================


@pytest.mark.benchmark
def test_subconscious_threat_scan_benchmark(benchmark):
    """Profiles dynamic threat appraisal scanning metrics inside perceptual inputs using production AppraisalEngine."""
    from app.cognitive.appraisal import AppraisalEngine

    engine = AppraisalEngine(identity_core_values=["no hate", "no violence"])
    state_snapshot = {"trust": 0.6}
    user_voice_properties = {"pitch_f0": 260.0, "energy_rms": 0.2}

    def run():
        # Profile actual production appraisal calculation (calling Rust extension)
        vector = engine.appraise(
            event_content="This is toxic and dangerous fire",
            event_type="USER_MESSAGE",
            emotional_bias=-0.8,
            state_snapshot=state_snapshot,
            identity_boundaries=["fire is bad", "stop danger"],
            user_voice_properties=user_voice_properties,
        )
        return vector.goal_congruence

    goal_congruence = benchmark(run)
    assert -1.0 <= goal_congruence <= 1.0


@pytest.mark.benchmark
def test_arbitration_layer_benchmark(benchmark):
    """Profiles behavioral node arbitration resolving conflicting state values using DecisionService conflict resolver."""
    from app.cognitive.decision import DecisionService

    decision_service = DecisionService(llm_service=None, memory_store=None)

    def run():
        # Call actual production conflict resolver (speculative stop arbitration)
        confirmed = decision_service.is_speculative_stop_confirmed(
            backbone_text="Wait, I actually agree with your point.",
            perception_keywords=["wait"],
        )
        return confirmed

    confirmed = benchmark(run)
    assert confirmed is False


# ==========================================
# 4. ENDOCRINE SYSTEM DERIVATIONS
# ==========================================


@pytest.mark.benchmark
def test_endocrine_state_decay_benchmark(benchmark):
    """Profiles the computational cost of derived stress hormones (Cortisol/Dopamine)."""
    state = AgentState(mood=-0.5, energy=0.9)

    def run():
        # Access properties that trigger derivation logic
        return state.cortisol, state.dopamine

    cortisol, dopamine = benchmark(run)
    assert 0.0 <= cortisol <= 1.0
    assert 0.0 <= dopamine <= 1.0


@pytest.mark.benchmark
def test_personality_modulation_benchmark(benchmark):
    """Profiles ActionService._compute_endocrine_options -- the real
    cortisol/dopamine/fatigue -> temperature/top_p/num_predict mapping, not a
    hand-copied reimplementation of its formula that would keep passing after
    the real one changed."""
    from app.cognitive.action import ActionService

    payload = {"cortisol": 0.8, "dopamine": 0.2, "fatigue": 0.5}

    def run():
        return ActionService._compute_endocrine_options(payload)

    options = benchmark(run)
    assert 0.0 <= options["temperature"] <= 1.0
    assert 0.0 <= options["top_p"] <= 1.0
    assert 100 <= options["num_predict"] <= 250


# ==========================================
# 5. MEMORY & NLP EXTRACTION
# ==========================================


@pytest.mark.benchmark
def test_memory_semantic_retrieve_benchmark(benchmark):
    """Benchmarks ACT-R semantic memory retrieval scoring using the real,
    named production formulas -- MemoryStore._base_activation,
    ._effective_similarity and .spread_weight -- instead of a hand-copied
    reimplementation that would keep passing after those formulas changed.
    The emotional-distance term itself has no shared helper in production
    (it's inlined at each of three call sites in memory_store.py), so it is
    inlined here too rather than invented as a fourth."""
    from app.state.memory_store import ACTR_EMO_DISTANCE_PENALTY, MemoryStore

    store = MemoryStore(None, None)
    rows = [
        _make_mock_row(
            f"Fact #{i}", similarity=0.8 - (i * 0.01), recall_count=max(1, i)
        )
        for i in range(50)
    ]
    current_valence = 0.2
    current_arousal = 0.5
    current_cortisol = 0.3

    def run():
        scored = []
        now_ts = time.time()
        for row in rows:
            hours_since = max(0.001, (now_ts - row["last_recalled_at"]) / 3600.0)
            dist_emo = (
                (row["valence"] - current_valence) ** 2
                + (row["emotional_weight"] - current_arousal) ** 2
            ) ** 0.5

            base_activation = store._base_activation(
                row["recall_count"], hours_since, row["importance_score"], dist_emo
            )
            effective_similarity = store._effective_similarity(
                row["similarity"],
                row["valence"],
                row["emotional_weight"],
                current_arousal,
                current_cortisol,
            )
            spread_activation = store.spread_weight * effective_similarity
            score = (
                base_activation
                + spread_activation
                - ACTR_EMO_DISTANCE_PENALTY * dist_emo
            )
            scored.append((row["content"], score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0]

    fact, _score = benchmark(run)
    assert fact is not None


@pytest.mark.benchmark
def test_conversation_serialization_benchmark(benchmark):
    """Profiles building and serializing a per-chunk assistant reply via
    SpeechCoordinator.create_chunk_payload -- the real ChatOutput
    construction every streamed word-chunk goes through before publish.
    There is no production 'conversation history/window' serializer to
    target: ConversationHistoryStore only issues SQL, and per-chunk output
    construction is the closest real analogue to what this benchmark's name
    describes."""
    from app.utils.speech import SpeechCoordinator

    coordinator = SpeechCoordinator(segmenter=None)
    state_snap = {"valence": 0.3, "arousal": 0.5, "trust": 0.6, "fatigue": 0.1}
    words = ["Hello,", "computer.", "How", "are", "you", "today?"]

    def run():
        payload = coordinator.create_chunk_payload(
            words=words, state_snap=state_snap, turn_id="bench-turn"
        )
        return payload.model_dump_json()

    serialized = benchmark(run)
    assert len(serialized) > 0


@pytest.mark.benchmark
def test_decision_tree_walk_benchmark(benchmark):
    """Profiles DecisionService._score_goals_maut -- the real Multi-Attribute
    Utility Theory scoring that picks among ENGAGE/COMFORT/INFORM/TEASE/
    PROTECT, not a `sorted()` over an unrelated hardcoded priority list."""
    from app.cognitive.decision import GOALS, DecisionService

    decision_service = DecisionService(llm_service=None, memory_store=None)
    appraisal = {
        "relevance": 0.7,
        "goal_congruence": 0.4,
        "novelty": 0.6,
        "norm_alignment": 1.0,
    }
    state = {"mood": 0.2, "energy": 0.6, "trust": 0.5}

    def run():
        return decision_service._score_goals_maut(appraisal, state)

    goal = benchmark(run)
    assert goal in GOALS


@pytest.mark.benchmark
def test_pipeline_step_dispatch_benchmark(benchmark):
    """Profiles CognitivePipeline.execute()'s real dispatch/extraction stage
    for a below-threshold speculative (VAP) signal -- the early-exit branch
    the real pipeline takes many times per second during live speech --
    instead of a loop of unrelated f-string formatting that never calls into
    the pipeline at all."""
    import asyncio

    from app.cognitive.core import CognitiveService

    service = CognitiveService(llm_service=None, memory_store=None, graph_db=None)
    raw_event = {
        "event_type": "VAP_SIGNAL",
        "is_partial": True,
        "vap_probability": 0.1,
    }

    def run():
        async def _drain():
            return [chunk async for chunk in service.pipeline.execute(raw_event)]

        return asyncio.run(_drain())

    chunks = benchmark(run)
    assert chunks == []


@pytest.mark.benchmark
def test_nats_metadata_serialization_benchmark(benchmark):
    """Profiles BaseAgent.publish()'s real metadata/hop-tracking wrapper
    construction and orjson serialization (JetStream transport mocked out),
    not a `json.dumps` on a dict shaped by hand to merely look similar."""
    import asyncio

    from app.agents.base import BaseAgent

    sent: dict[str, bytes] = {}

    class _NoopJS:
        async def publish(self, subject, payload, timeout=None, headers=None):
            sent["payload"] = payload

    agent = BaseAgent(name="metadata_serialization_bench_agent")
    agent.js = _NoopJS()
    payload = {
        "text": "Streaming reply.",
        "session_id": "8e36780c-a9fe-443b-a212-001a18bc009b",
    }

    def run():
        asyncio.run(agent.publish("chat.output", dict(payload)))
        return sent["payload"]

    try:
        wrapper = benchmark(run)
        assert b"latency_metadata" in wrapper
    finally:
        agent._metrics.shutdown()


@pytest.mark.benchmark
def test_hybrid_segmenter_benchmark(benchmark):
    """Profiles the HybridSegmenter algorithm splitting text strings under high word counts."""
    segmenter = HybridSegmenter(target_size=8)
    words = ["hello", "there,", "how", "are", "you?", "today"] * 200

    def run():
        return [
            segmenter.score_split_point(word, i % 14) for i, word in enumerate(words)
        ]

    scores = benchmark(run)
    assert len(scores) == len(words)


# ==========================================
# 7. SENSORY & PROSODY MAPPING
# ==========================================


@pytest.mark.benchmark
def test_stt_payload_parsing_benchmark(benchmark):
    """Profiles CognitiveService._on_audio_perception -- the real handler for
    `audio.perception` events off the STT fast path (payload shape matches
    the AudioPerception contract), not a bare `json.loads` on a shape no
    production code actually receives."""
    import asyncio

    from app.cognitive.core import CognitiveService

    service = CognitiveService(llm_service=None, memory_store=None, graph_db=None)
    # Pin the rate-limited persistence gate as "just persisted" so the whole
    # benchmark run (well under its 2s default interval) never takes the real
    # DB-write side effect -- a deterministic setup choice, not a stubbed-out
    # formula.
    service.state._last_sensory_persist = time.time()

    payload = {
        "text": "That's really funny!",
        "intent": "REACT",
        "confidence": 0.9,
        "metadata": {
            "confidence": 0.9,
            "emotional_bias": 0.4,
            "events": ["Laughter"],
        },
    }

    def run():
        # Reset to a known baseline each iteration so the assertion below
        # can tell a real mood blend from a no-op -- 0.0 <= mood <= 1.0 would
        # pass even if the handler never touched state at all.
        service.state.current_state.mood = 0.0
        asyncio.run(service._on_audio_perception(dict(payload)))
        return service.state.current_state.mood

    mood = benchmark(run)
    assert mood > 0.0, (
        "a positive emotional_bias from a 0.0 baseline must blend mood "
        "upward -- an unchanged 0.0 means the handler did not run"
    )


@pytest.mark.benchmark
def test_vision_frame_encode_benchmark(benchmark):
    """Profiles VisualAppraisalService._compute_visual_vector -- the real
    per-frame downsample-to-vector conversion used for habituation gating
    (OpenCV resize when available, PIL resize otherwise -- see M3-A9), not
    a `len(raw_bytes) > 100` structural check that measures nothing about
    encoding at all."""
    import base64
    import io

    from PIL import Image

    from app.vision.appraisal import VisualAppraisalService

    service = VisualAppraisalService(ollama_client=None)
    # A real, decodable JPEG: both the cv2 and PIL downsampling paths need
    # actual image bytes, not arbitrary data -- neither can decode the
    # `b"\x00\xff\x80" * 1024` filler this benchmark used before M3-A9
    # removed the SHA-256 fallback that used to paper over that.
    img = Image.new("RGB", (64, 64), color=(120, 60, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    frame_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    def run():
        return service._compute_visual_vector(frame_b64)

    vector = benchmark(run)
    assert vector is not None
    assert len(vector) == 256
    assert all(0.0 <= v <= 1.0 for v in vector)


@pytest.mark.benchmark
def test_affective_prosody_mapping_benchmark(benchmark):
    """Profiles mapping PAD emotional state variables to GPT-SoVITS prosody parameters using production Rust implementation."""
    import cognitive_rust

    def run():
        pleasure = 0.6
        arousal = 0.8
        dominance = 0.4
        fatigue = 0.0

        # Call production Rust PyO3 implementation for prosody trajectory generation
        trajectory = cognitive_rust.generate_apra_trajectory(
            pleasure, arousal, dominance, fatigue
        )
        return trajectory

    trajectory = benchmark(run)
    assert len(trajectory) == 60
    # First frame checks
    t_ms, rate, pitch, volume = trajectory[0]
    assert t_ms == 0
    assert rate > 0.0
    assert pitch > 0.0
    assert volume > 0.0


# ==========================================
# LATENCY SANITY TESTS
# ==========================================


@pytest.mark.latency
def test_compute_latency_clamps_future_start_times(monkeypatch):
    monkeypatch.setattr("app.metrics.time.time", lambda: 10.0)
    assert SubjectMetrics.compute_latency(20.0) == 0.0
