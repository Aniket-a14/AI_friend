"""
The facial reflex channel (Bucket 13, voice remediation Phase 3) --
the continuous, CPU-only counterpart to `VisualAppraisalService`'s VLM poll.

## Why this exists

`VLM_APPRAISAL_INTERVAL` (5.0s) and `VISION_SUSPEND_DURING_TURN` (True) are an
honest, forced tradeoff at an 8GB VRAM ceiling: the VLM and the LLM genuinely
contend for the same GPU. But the consequence is that vision is a slow
background poll, architecturally blind to anything that happens between polls
or while the agent is speaking -- a flinch, a look away, a smile mid-sentence
are all invisible to it, not because they weren't worth noticing but because
the poll never ran at that moment.

MediaPipe's Face Landmarker runs entirely on CPU (XNNPACK), continuously, at
video frame rate, for free next to an LLM that needs the GPU. It costs zero
VRAM, so unlike the VLM it does not need to suspend during the turn. This
module is deliberately *not* a captioner: it never produces a description or
calls a language model. It scores a small, named set of blendshape
coefficients against fixed thresholds and turns a clear onset into a small,
signed affect nudge -- the same "unconscious" posture `_compute_endocrine_options`
already takes with hormones (CLAUDE.md): shaping affect without ever being
represented as a proposition the system has to reason about.

## Why only three signals, and why refractory-gated

MediaPipe's Face Landmarker exposes 52 ARKit-style blendshape coefficients.
Modeling all 52 into affect would be building an unvalidated emotion
classifier from scratch. Three are used here, chosen because they are the
least ambiguous:

- **smile** (mouthSmileLeft/Right): unambiguously positive.
- **brow_furrow** (browDownLeft/Right): unambiguously negative-valenced
  tension, whatever its cause (concentration, mild distress) -- kept small
  and valence-only for exactly that reason.
- **startle** (eyeWideLeft/Right *and* jawOpen together): high arousal,
  deliberately valence-*less* -- a startle can be delighted or alarmed, and
  guessing the direction would be worse than not guessing. The compound gate
  (both must fire) exists because `jawOpen` alone fires constantly during
  ordinary speech and would be pure noise on its own.

A continuous per-frame signal would otherwise fire on every single video
frame a held expression is still present -- a five-second smile at 15fps is
75 identical events, not one. `FacialReflexTracker` suppresses a re-fire of
the same signal within `REFRACTORY_SECONDS`, so a held expression counts as
one onset.

## What this deliberately does not do (yet)

Blink rate and gaze on/off are named in the remediation plan as reflex-worthy
signals but are not implemented here: both need a rolling time window rather
than a single-frame threshold, and are engagement/attention signals rather
than affect signals -- a different consumer (turn-taking, `VISION_SUSPEND_DURING_TURN`
policy) than the PAD wiring this module feeds. Left for a later pass.

This module also does not talk to a camera, MediaPipe, or the NATS mesh --
see `app/vision/agent.py` for where a live capture loop will call into
`score_blendshapes` and publish the result as a `FacialReflexEvent`
(`app/contracts.py`) on `Topics.VISION_FACIAL_REFLEX`. That wiring needs a
live camera and is intentionally not part of this change (NOT MEASURED --
see the ledger entry for what is and isn't verified).
"""

from dataclasses import dataclass, field

# Onset thresholds. MediaPipe blendshape scores run 0.0-1.0; these were picked
# by hand against real output on a sample face (0.5+ was a clear, deliberate
# expression; ordinary neutral faces measured well under 0.1 on all three in
# that same sample) -- not derived from a calibration dataset. Treat as a
# first-pass tunable, not a measured constant.
SMILE_THRESHOLD = 0.5
BROW_FURROW_THRESHOLD = 0.5
STARTLE_EYE_THRESHOLD = 0.4
STARTLE_JAW_THRESHOLD = 0.3

# How long a signal must stay quiet before it can fire again. Chosen to be
# long enough that a single held expression (a multi-second smile) reads as
# one event, short enough that a real second smile a few seconds later still
# registers as its own event. A tunable, not a measured constant.
REFRACTORY_SECONDS = 5.0

# Affect deltas per firing. Deliberately much smaller than
# `apply_somatic_perception`'s ±0.15/±0.10 spikes: that channel fires on a
# comparatively rare recognized-comfort-object match, this can fire many
# times per conversation, and ALMA decay pulls affect back toward baseline
# between hits regardless -- these do not need to be large to matter.
SMILE_VALENCE_DELTA = 0.04
SMILE_DOPAMINE_SPIKE = 0.08
BROW_FURROW_VALENCE_DELTA = -0.03
STARTLE_AROUSAL_DELTA = 0.06


@dataclass(frozen=True, slots=True)
class FacialAffectSignal:
    """One detected expression onset, ready to become a `FacialReflexEvent`."""

    name: str
    valence_delta: float = 0.0
    arousal_delta: float = 0.0
    dopamine_spike: float = 0.0
    evidence: str = ""


@dataclass(slots=True)
class FacialReflexTracker:
    """Per-signal refractory gate, held across frames by whatever loop calls
    `score_blendshapes` repeatedly. One instance per camera/session -- it is
    the only state this module carries, and it is not safe to share across
    concurrent capture loops.
    """

    _last_fired: dict[str, float] = field(default_factory=dict)

    def ready(self, name: str, now: float) -> bool:
        last = self._last_fired.get(name)
        return last is None or (now - last) >= REFRACTORY_SECONDS

    def mark_fired(self, name: str, now: float) -> None:
        self._last_fired[name] = now


def score_blendshapes(
    blendshapes: dict[str, float],
    now: float,
    tracker: FacialReflexTracker,
) -> list[FacialAffectSignal]:
    """Turn one frame's blendshape scores into 0+ affect signals.

    `blendshapes` is a plain ``{category_name: score}`` mapping -- the shape
    `mediapipe.tasks.python.vision.FaceLandmarkerResult.face_blendshapes[0]`
    reduces to once the `Category` objects are unwrapped, kept as a plain
    dict here specifically so this function has no MediaPipe import and can
    be unit-tested without a model, a camera, or MediaPipe installed at all.
    Missing keys score 0.0, not an error -- a caller that only detected some
    landmarks (or an off-model test fixture) should degrade to "no signal
    fired" rather than raise.
    """
    signals: list[FacialAffectSignal] = []

    smile = (
        blendshapes.get("mouthSmileLeft", 0.0) + blendshapes.get("mouthSmileRight", 0.0)
    ) / 2.0
    if smile >= SMILE_THRESHOLD and tracker.ready("smile", now):
        signals.append(
            FacialAffectSignal(
                name="smile",
                valence_delta=SMILE_VALENCE_DELTA,
                dopamine_spike=SMILE_DOPAMINE_SPIKE,
                evidence=f"smile={smile:.2f}",
            )
        )
        tracker.mark_fired("smile", now)

    brow_furrow = (
        blendshapes.get("browDownLeft", 0.0) + blendshapes.get("browDownRight", 0.0)
    ) / 2.0
    if brow_furrow >= BROW_FURROW_THRESHOLD and tracker.ready("brow_furrow", now):
        signals.append(
            FacialAffectSignal(
                name="brow_furrow",
                valence_delta=BROW_FURROW_VALENCE_DELTA,
                evidence=f"brow_furrow={brow_furrow:.2f}",
            )
        )
        tracker.mark_fired("brow_furrow", now)

    eye_wide = (
        blendshapes.get("eyeWideLeft", 0.0) + blendshapes.get("eyeWideRight", 0.0)
    ) / 2.0
    jaw_open = blendshapes.get("jawOpen", 0.0)
    if (
        eye_wide >= STARTLE_EYE_THRESHOLD
        and jaw_open >= STARTLE_JAW_THRESHOLD
        and tracker.ready("startle", now)
    ):
        signals.append(
            FacialAffectSignal(
                name="startle",
                arousal_delta=STARTLE_AROUSAL_DELTA,
                evidence=f"eye_wide={eye_wide:.2f} jaw_open={jaw_open:.2f}",
            )
        )
        tracker.mark_fired("startle", now)

    return signals
