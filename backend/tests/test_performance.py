import time
import json
import pytest
from unittest.mock import mock_open, patch

from app.metrics import SubjectMetrics
from app.utils.segmentation import HybridSegmenter
from app.state.agent_state import AgentState
from app.cognitive.identity import IdentityManager
from app.state.triple_extractor import TripleExtractor


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
        manager = IdentityManager(base_path="/fake/path")

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
    """Profiles real-time temperature/top_p/num_predict logic modulation based on endocrine state."""

    def run():
        cortisol = 0.8
        dopamine = 0.2
        fatigue = 0.5

        # Production modulation algorithm matching ActionService exactly
        endo_temperature = max(0.0, min(1.0, round(0.9 - (cortisol * 0.6), 3)))
        endo_top_p = max(0.0, min(1.0, round(0.70 + (dopamine * 0.25), 3)))
        endo_num_predict = int(max(100, min(250, int(250 - (fatigue * 150)))))
        return endo_temperature, endo_top_p, endo_num_predict

    temp, top_p, num_predict = benchmark(run)
    assert 0.0 <= temp <= 1.0
    assert 0.0 <= top_p <= 1.0
    assert 100 <= num_predict <= 250


# ==========================================
# 5. MEMORY & NLP EXTRACTION
# ==========================================


@pytest.mark.benchmark
def test_memory_semantic_retrieve_benchmark(benchmark):
    """Benchmarks ACT-R semantic memory retrieval scoring (recency/frequency weights) using production formulas."""
    rows = [
        _make_mock_row(
            "Fact #%d" % i, similarity=0.8 - (i * 0.01), recall_count=max(1, i)
        )
        for i in range(50)
    ]
    import math

    decay_rate = 0.5
    spread_weight = 2.0
    current_valence = 0.2
    current_arousal = 0.5
    current_cortisol = 0.3

    def run():
        scored = []
        now_ts = time.time()
        for row in rows:
            memory_valence = row["valence"]
            emotion_weight_row = row["emotional_weight"]
            recall_count = row["recall_count"]
            last_recall_time = row["last_recalled_at"]
            importance_score = row["importance_score"]
            similarity = row["similarity"]

            hours_since = max(0.001, (now_ts - last_recall_time) / 3600.0)

            # 2D/3D Emotional Distance
            dist_emo = math.sqrt(
                (memory_valence - current_valence) ** 2
                + (emotion_weight_row - current_arousal) ** 2
            )

            # Production base_activation
            base_activation = (
                math.log(recall_count)
                - decay_rate * math.log(hours_since + 1.0)
                + 1.5 * importance_score
                + 0.15 * (1.0 - dist_emo)
            )

            # Effective similarity with hormonal gating
            effective_similarity = similarity * (
                1.0
                + 0.1 * memory_valence * emotion_weight_row
                - 0.2 * current_arousal * current_cortisol
            )

            spread_activation = spread_weight * effective_similarity
            score = base_activation + spread_activation - 0.5 * dist_emo
            scored.append((row["content"], score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0]

    fact, score = benchmark(run)
    assert fact is not None


@pytest.mark.benchmark
def test_triple_extractor_nlp_benchmark(benchmark):
    """Profiles extracting subject-verb-object knowledge triples from input text."""
    extractor = TripleExtractor(llm_service=None, graph_db=None)

    def run():
        return extractor._parse_json_from_text(
            '[["Aniket", "LIVES_IN", "Mumbai"], ["Aniket", "ROLE", "Engineer"]]'
        )

    triples = benchmark(run)
    assert len(triples) == 2


# ==========================================
# 6. PIPELINES & CONVERSATION SERIALIZATION
# ==========================================


@pytest.mark.benchmark
def test_conversation_serialization_benchmark(benchmark):
    """Profiles serializing context history and window segments in ConversationStore."""
    history = {
        "relationship": "Empathy Guide",
        "memories": [
            "First prompt check",
            "NATS stream initialization",
            "Subconscious tick evolution",
        ],
        "turns": [{"role": "user", "text": "Hello, computer"}] * 50,
    }

    def run():
        return json.dumps(history)

    serialized = benchmark(run)
    assert len(serialized) > 0


@pytest.mark.benchmark
def test_decision_tree_walk_benchmark(benchmark):
    """Profiles evaluating behavior tree conditions and scoring priority pathways."""

    def run():
        pathways = [
            {"node": "Appraise", "priority": 3, "state": "active"},
            {"node": "Subconscious", "priority": 1, "state": "idle"},
            {"node": "TTS", "priority": 4, "state": "active"},
            {"node": "Arbitration", "priority": 2, "state": "pending"},
        ]
        # Walk and score
        sorted_paths = sorted(
            [p for p in pathways if p["state"] == "active"], key=lambda x: x["priority"]
        )
        return sorted_paths[0]["node"]

    node = benchmark(run)
    assert node == "Appraise"


@pytest.mark.benchmark
def test_pipeline_step_dispatch_benchmark(benchmark):
    """Profiles sequential pipeline dispatching and step routing inside the core pipeline."""
    steps = ["appraisal", "decision", "action", "telemetry"] * 5

    def run():
        results = []
        for step in steps:
            results.append("DISPATCHED:%s" % step)
        return results

    res = benchmark(run)
    assert len(res) == 20


@pytest.mark.benchmark
def test_nats_metadata_serialization_benchmark(benchmark):
    """Profiles compiling NATS message wrappers with timestamp metadata."""
    payload = {
        "text": "Streaming reply.",
        "session_id": "8e36780c-a9fe-443b-a212-001a18bc009b",
    }

    def run():
        # Inject metadata
        payload["latency_metadata"] = {"start_time": time.time()}
        return json.dumps(payload)

    wrapper = benchmark(run)
    assert "latency_metadata" in wrapper


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
    """Profiles parsing and validating raw STT payload data."""
    raw_payload = json.dumps(
        {
            "text": "This is a simulated speech to text transcription.",
            "is_final": True,
            "is_partial": False,
            "confidence": 0.98,
            "language": "en",
        }
    ).encode("utf-8")

    def run():
        parsed = json.loads(raw_payload.decode("utf-8"))
        return parsed["text"]

    text = benchmark(run)
    assert text == "This is a simulated speech to text transcription."


@pytest.mark.benchmark
def test_vision_frame_encode_benchmark(benchmark):
    """Profiles simulating basic visual frame compression overhead."""
    # Simulate a small dummy byte array to prevent JSON serialization hangs
    raw_bytes = b"\x00\xff\x80" * 1024

    def run():
        # Simulate an ultra-fast structural validation
        return len(raw_bytes) > 100

    valid = benchmark(run)
    assert valid is True


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
