"""Local Phase 05 micro-benchmarks (BM-LOC-P5-01, BM-LOC-P5-02, BM-LOC-P5-03, BM-LOC-P5-04).

Implements local benchmarks per orchestration/PHASE_05/BENCHMARK_PLAN.md.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.cognitive.external_action import (
    ActionReversibility,
    ActionRiskLevel,
    ExternalActionDispatcher,
    ExternalActionIntent,
)
from app.cognitive.speech_intent import (
    SpeechAffect,
    SpeechDelivery,
    SpeechEpistemics,
    SpeechRelationship,
    SpeechTimelineMarker,
    SpeechTurnPolicy,
    TimelineMarkerKind,
    build_speech_intent,
)
from app.llm.model_manifest import ModelCapability
from app.llm.model_roles import (
    FallbackStrategy,
    ModelRole,
    ProviderCapabilityNegotiator,
)
from app.vision.adapters import (
    SpatialTrackingVisionAdapter,
    VLMCaptionVisionAdapter,
    to_percept_envelope,
)
from app.voice.compiler import (
    ElevenLabsVoiceCompiler,
    GPTSoVITSVoiceCompiler,
)


def run_bm_loc_p5_01() -> dict[str, Any]:
    """BM-LOC-P5-01: Voice Compiler Throughput and Intent Loss Telemetry Fidelity.

    Compiles 1,000 SpeechIntent instances across ElevenLabsVoiceCompiler and
    GPTSoVITSVoiceCompiler.
    Target: Mean latency < 0.05 ms (50 us), 100% loss/substitution captured.
    """
    print("\n--- Running BM-LOC-P5-01: Voice Compiler Throughput & Loss Telemetry ---")
    num_iterations = 1000

    eleven_compiler = ElevenLabsVoiceCompiler()
    gpt_compiler = GPTSoVITSVoiceCompiler()

    latencies_us: list[float] = []
    capture_count = 0
    total_checks = 0

    for i in range(num_iterations):
        # Alternate compilers
        compiler = eleven_compiler if (i % 2 == 0) else gpt_compiler

        # Intentionally inject dimensions that compiler cannot render
        intent = build_speech_intent(
            turn_id=f"turn-{i}",
            semantic_text="I understand your concern and will verify the results.",
            affect=SpeechAffect(valence=0.8, arousal=0.6, intensity=0.9),
            epistemics=SpeechEpistemics(confidence=0.6, hedge_required=True),
            relationship=SpeechRelationship(stance="EMPATHETIC", register="INFORMAL"),
            delivery=SpeechDelivery(urgency=0.5, relative_rate=1.1, style="cheerful"),
            timeline=[
                SpeechTimelineMarker(
                    kind=TimelineMarkerKind.PAUSE, text_span="concern", strength_or_duration=0.3
                ),
                SpeechTimelineMarker(
                    kind=TimelineMarkerKind.EMPHASIS, text_span="verify", strength_or_duration=0.8
                ),
            ],
            turn_policy=SpeechTurnPolicy(yield_after=True, interruptible=True),
        )

        t0 = time.perf_counter_ns()
        _payload, loss = compiler.compile(intent)
        t1 = time.perf_counter_ns()

        latencies_us.append((t1 - t0) / 1000.0)

        total_checks += 1
        # Check that loss telemetry properly identified dropped/substituted dimensions
        if loss.dropped_dimensions or loss.substituted_dimensions:
            capture_count += 1

    latencies_us.sort()
    n = len(latencies_us)
    mean_us = sum(latencies_us) / n
    p50_us = latencies_us[int(n * 0.50)]
    p95_us = latencies_us[int(n * 0.95)]
    p99_us = latencies_us[int(n * 0.99)]

    capture_rate = (capture_count / total_checks) * 100.0
    verdict = "PASS" if (mean_us < 50.0 and capture_rate == 100.0) else "FAIL"

    print(f"Iterations: {num_iterations} | Mean: {mean_us:.3f} us | p95: {p95_us:.3f} us")
    print(f"Telemetry Capture Rate: {capture_rate:.1f}%")
    print(f"Verdict: {verdict} (Target: mean < 50.0 us, capture = 100%)")

    return {
        "benchmark_id": "BM-LOC-P5-01",
        "title": "Voice Compiler Throughput & Loss Telemetry",
        "iterations": num_iterations,
        "mean_us": round(mean_us, 3),
        "p50_us": round(p50_us, 3),
        "p95_us": round(p95_us, 3),
        "p99_us": round(p99_us, 3),
        "capture_rate_pct": round(capture_rate, 2),
        "target_mean_us": "< 50.0",
        "verdict": verdict,
    }


def run_bm_loc_p5_02() -> dict[str, Any]:
    """BM-LOC-P5-02: Vision Adapter Normalization and Brain Invariant Stress Test.

    Processes 1,000 visual inputs across VLMCaptionVisionAdapter and
    SpatialTrackingVisionAdapter, converting to PerceptEnvelope.
    Target: Mean latency < 0.05 ms (50 us), 0.0% direct affect/trust corruption.
    """
    print("\n--- Running BM-LOC-P5-02: Vision Adapter Normalization & Invariant Check ---")
    num_iterations = 1000

    vlm_adapter = VLMCaptionVisionAdapter()
    spatial_adapter = SpatialTrackingVisionAdapter()

    latencies_us: list[float] = []
    corruption_detected = False

    raw_spatial_payload = {
        "track_ids": ["track-01", "track-02"],
        "objects": [{"label": "cup", "confidence": 0.92, "bounding_box": [0.1, 0.1, 0.2, 0.2]}],
        "identities": [{"person_id": "user_01", "confidence": 0.88, "bounding_box": [0.3, 0.2, 0.7, 0.8]}],
        "facial_observables": [{"action_units": ["AU12", "AU06"], "confidence": 0.85, "muscle_movement": "lip corner puller"}],
        "spatial_relations": [{"subject": "cup", "relation": "on", "object": "desk"}],
        "staleness_ms": 25.0,
    }

    raw_vlm_caption = "A person sitting at a desk with a laptop and a coffee mug."

    for i in range(num_iterations):
        t0 = time.perf_counter_ns()
        if i % 2 == 0:
            structured = vlm_adapter.process(raw_vlm_caption)
        else:
            structured = spatial_adapter.process(raw_spatial_payload)

        envelope = to_percept_envelope(structured)
        t1 = time.perf_counter_ns()

        latencies_us.append((t1 - t0) / 1000.0)

        # Verify brain invariant: envelope must NOT mutate affect or trust directly
        # and must not contain raw emotion assertions
        if "affect" in envelope.raw_payload or "trust" in envelope.raw_payload:
            corruption_detected = True

    latencies_us.sort()
    n = len(latencies_us)
    mean_us = sum(latencies_us) / n
    p50_us = latencies_us[int(n * 0.50)]
    p95_us = latencies_us[int(n * 0.95)]
    p99_us = latencies_us[int(n * 0.99)]

    verdict = "PASS" if (mean_us < 50.0 and not corruption_detected) else "FAIL"

    print(f"Iterations: {num_iterations} | Mean: {mean_us:.3f} us | p95: {p95_us:.3f} us")
    print(f"Brain Invariant Corruption: {'DETECTED' if corruption_detected else 'None (0.0%)'}")
    print(f"Verdict: {verdict} (Target: mean < 50.0 us, 0% corruption)")

    return {
        "benchmark_id": "BM-LOC-P5-02",
        "title": "Vision Normalization & Invariant Check",
        "iterations": num_iterations,
        "mean_us": round(mean_us, 3),
        "p50_us": round(p50_us, 3),
        "p95_us": round(p95_us, 3),
        "p99_us": round(p99_us, 3),
        "corruption_rate_pct": 0.0 if not corruption_detected else 100.0,
        "target_mean_us": "< 50.0",
        "verdict": verdict,
    }


def run_bm_loc_p5_03() -> dict[str, Any]:
    """BM-LOC-P5-03: Model Role Capability Negotiation & Fallback Evaluation.

    Executes 1,000 negotiation checks across 6 ModelRoles and synthetic capability profiles.
    Target: Mean latency < 0.01 ms (10 us).
    """
    print("\n--- Running BM-LOC-P5-03: Model Role Capability Negotiation Latency ---")
    num_iterations = 1000

    negotiator = ProviderCapabilityNegotiator()
    roles = list(ModelRole)

    profiles = [
        # Fully capable
        ModelCapability(context_window=128000, supports_thinking_tokens=True, streaming=True, structured_output=True, language=["en"]),
        # Missing structured output
        ModelCapability(context_window=32768, supports_thinking_tokens=False, streaming=True, structured_output=False, language=["en"]),
        # Low context
        ModelCapability(context_window=2048, supports_thinking_tokens=False, streaming=True, structured_output=True, language=["en"]),
    ]

    latencies_us: list[float] = []

    for i in range(num_iterations):
        role = roles[i % len(roles)]
        cap = profiles[i % len(profiles)]

        t0 = time.perf_counter_ns()
        _qualified, strategy, _details = negotiator.evaluate_capability(role, cap)
        t1 = time.perf_counter_ns()

        latencies_us.append((t1 - t0) / 1000.0)
        assert strategy in [s.value for s in FallbackStrategy]

    latencies_us.sort()
    n = len(latencies_us)
    mean_us = sum(latencies_us) / n
    p50_us = latencies_us[int(n * 0.50)]
    p95_us = latencies_us[int(n * 0.95)]
    p99_us = latencies_us[int(n * 0.99)]

    verdict = "PASS" if mean_us < 10.0 else "FAIL"

    print(f"Iterations: {num_iterations} | Mean: {mean_us:.3f} us | p95: {p95_us:.3f} us")
    print(f"Verdict: {verdict} (Target: mean < 10.0 us)")

    return {
        "benchmark_id": "BM-LOC-P5-03",
        "title": "Model Role Capability Negotiation Latency",
        "iterations": num_iterations,
        "mean_us": round(mean_us, 3),
        "p50_us": round(p50_us, 3),
        "p95_us": round(p95_us, 3),
        "p99_us": round(p99_us, 3),
        "target_mean_us": "< 10.0",
        "verdict": verdict,
    }


def run_bm_loc_p5_04() -> dict[str, Any]:
    """BM-LOC-P5-04: External Action Authorization and Risk Gating Throughput.

    Evaluates 1,000 external action requests across various risk levels and reversibility.
    Target: 100% block rate for unauthorized high-risk actions, latency < 0.01 ms (10 us).
    """
    print("\n--- Running BM-LOC-P5-04: External Action Risk & Authorization Gating ---")
    num_iterations = 1000

    dispatcher = ExternalActionDispatcher()
    latencies_us: list[float] = []

    unauthorized_high_risk_blocked = 0
    total_unauthorized_high_risk = 0

    for i in range(num_iterations):
        # 50% high/critical risk without token
        if i % 2 == 0:
            intent = ExternalActionIntent(
                action_id=f"act-{i}",
                turn_id=f"t-{i}",
                tool_or_actuator="actuator_arm",
                risk_level=ActionRiskLevel.HIGH if (i % 4 == 0) else ActionRiskLevel.CRITICAL,
                reversibility=ActionReversibility.IRREVERSIBLE,
                authorization_token=None,
            )
            total_unauthorized_high_risk += 1
        else:
            intent = ExternalActionIntent(
                action_id=f"act-{i}",
                turn_id=f"t-{i}",
                tool_or_actuator="ambient_light",
                risk_level=ActionRiskLevel.LOW,
                reversibility=ActionReversibility.REVERSIBLE,
                authorization_token=None,
            )

        t0 = time.perf_counter_ns()
        allowed, reason = dispatcher.validate_action(intent)
        t1 = time.perf_counter_ns()

        latencies_us.append((t1 - t0) / 1000.0)

        if intent.risk_level in (ActionRiskLevel.HIGH, ActionRiskLevel.CRITICAL) or intent.reversibility == ActionReversibility.IRREVERSIBLE:
            if not allowed and "authorization_token is required" in (reason or "").lower():
                unauthorized_high_risk_blocked += 1
        else:
            assert allowed, f"Low risk action unexpectedly blocked: {reason}"

    latencies_us.sort()
    n = len(latencies_us)
    mean_us = sum(latencies_us) / n
    p50_us = latencies_us[int(n * 0.50)]
    p95_us = latencies_us[int(n * 0.95)]
    p99_us = latencies_us[int(n * 0.99)]

    block_rate = (unauthorized_high_risk_blocked / total_unauthorized_high_risk) * 100.0
    verdict = "PASS" if (mean_us < 10.0 and block_rate == 100.0) else "FAIL"

    print(f"Iterations: {num_iterations} | Mean: {mean_us:.3f} us | p95: {p95_us:.3f} us")
    print(f"Unauthorized High-Risk Block Rate: {block_rate:.1f}% ({unauthorized_high_risk_blocked}/{total_unauthorized_high_risk})")
    print(f"Verdict: {verdict} (Target: mean < 10.0 us, block rate = 100%)")

    return {
        "benchmark_id": "BM-LOC-P5-04",
        "title": "External Action Risk & Authorization Gating",
        "iterations": num_iterations,
        "mean_us": round(mean_us, 3),
        "p50_us": round(p50_us, 3),
        "p95_us": round(p95_us, 3),
        "p99_us": round(p99_us, 3),
        "unauthorized_block_rate_pct": round(block_rate, 2),
        "target_mean_us": "< 10.0",
        "verdict": verdict,
    }


def main() -> None:
    print("===================================================================")
    print("      AI FRIEND PHASE 05 LOCAL MICRO-BENCHMARKS                   ")
    print("===================================================================")

    results = {
        "phase": "PHASE_05",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "benchmarks": [
            run_bm_loc_p5_01(),
            run_bm_loc_p5_02(),
            run_bm_loc_p5_03(),
            run_bm_loc_p5_04(),
        ],
    }

    all_pass = all(b["verdict"] == "PASS" for b in results["benchmarks"])
    results["overall_verdict"] = "PASS" if all_pass else "FAIL"

    out_path = os.path.join(BACKEND_ROOT, "..", "orchestration", "PHASE_05", "local_benchmark_results.json")
    with open(out_path, "w", encoding="ascii") as f:
        json.dump(results, f, indent=2)

    print("\n===================================================================")
    print(f"Overall Local Benchmark Verdict: {results['overall_verdict']}")
    print(f"Results saved to: {out_path}")
    print("===================================================================")

    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
