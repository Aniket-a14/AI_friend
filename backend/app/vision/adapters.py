"""Vision adapters (`FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` SS24) -- the
boundary between whatever a concrete vision system produces and the
`StructuredVisionPercept` contract cognition actually consumes.

Two adapters are provided, matching the two vision sources already in this
repo's mesh: `VLMCaptionVisionAdapter` wraps the free-text description
`VisualAppraisalService` (`app/vision/appraisal.py`) produces from a VLM,
and `SpatialTrackingVisionAdapter` wraps a structured detector/tracker that
already emits track IDs, bounding boxes, and per-face action units (the
kind of pipeline `app/vision/reflex.py`'s blendshape scoring is one
CPU-only slice of). Both return the same `StructuredVisionPercept` shape so
a caller does not need to special-case which vision source produced it.

`to_percept_envelope` is the single point where a `StructuredVisionPercept`
is normalized into the `PerceptEnvelope` the cognitive pipeline ingests
(`app/cognitive/percept.py`), and it re-validates the anti-emotion-fact
invariant one last time before that happens -- the last chance to catch a
percept assembled or mutated in a way that slipped past its own field
validators.
"""

from __future__ import annotations

import math
import time
import uuid
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from app.cognitive.percept import PerceptEnvelope
from app.cognitive.vision_percept import (
    DetectedObject,
    FacialObservable,
    IdentityEstimate,
    SpatialRelation,
    StructuredVisionPercept,
    contains_emotional_language,
    validate_vision_invariants,
)


@runtime_checkable
class VisionAdapterProtocol(Protocol):
    """Anything that can turn raw vision-source data into a
    `StructuredVisionPercept` satisfies this without inheriting from it."""

    def process(self, raw_data: Any) -> StructuredVisionPercept: ...


def _clamp_unit(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return max(0.0, min(1.0, number))


def _new_percept_uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _safe_staleness_ms(value: Any) -> float:
    """Coerce a raw-payload staleness value to a finite, non-negative float,
    defaulting to 0.0 for anything that isn't one -- missing, non-numeric,
    NaN/infinite, or negative all collapse to the same safe default rather
    than raising or silently carrying a nonsensical value forward."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number) or number < 0.0:
        return 0.0
    return number


def _sanitize_caption(caption: str) -> str:
    """Return `caption` unchanged if it makes no emotional-fact claim, else
    an empty string.

    A VLM caption is the least trustworthy vision source this boundary
    accepts: an off-the-shelf captioner asked to "describe what you see"
    routinely volunteers an emotional inference unprompted ("the user looks
    happy"), and that inference must never reach `scene_deltas` as if it
    were an observation. Editing the sentence down to just its
    non-emotional clause was considered and rejected -- word-level surgery
    on a sentence you didn't generate risks leaving a grammatically broken
    or, worse, misleadingly-reworded fragment that still reads as
    authoritative. Dropping the caption whole and reporting no observation
    for this frame is the safe default when it cannot be trusted verbatim;
    `validate_vision_invariants` still re-checks the result before it
    leaves `process()`, so a gap in this sanitizer is not the only line of
    defense.
    """
    return "" if contains_emotional_language(caption) else caption


class VLMCaptionVisionAdapter:
    """Adapts an unstructured VLM caption (a plain string, or a dict shaped
    like `VisualAppraisalService`'s output) into a low-confidence
    `StructuredVisionPercept`.

    A caption is a single natural-language guess about a whole scene, not a
    structured detection -- it carries no track IDs, no bounding boxes, and
    no facial observables, only a scene delta. `default_confidence` is
    deliberately below the model default of 1.0: an unstructured caption is
    the weakest observation this boundary accepts.
    """

    default_confidence: float = 0.35

    def process(self, raw_data: Any) -> StructuredVisionPercept:
        if isinstance(raw_data, dict):
            caption = str(
                raw_data.get("description")
                or raw_data.get("caption")
                or raw_data.get("text")
                or ""
            ).strip()
            confidence = _clamp_unit(
                raw_data.get("confidence"), default=self.default_confidence
            )
            staleness_ms = _safe_staleness_ms(raw_data.get("staleness_ms"))
        else:
            caption = str(raw_data or "").strip()
            confidence = self.default_confidence
            staleness_ms = 0.0

        caption = _sanitize_caption(caption)

        percept = StructuredVisionPercept(
            scene_deltas=[caption] if caption else [],
            confidence=confidence,
            staleness_ms=staleness_ms,
            provenance="vlm_caption",
        )
        validate_vision_invariants(percept)
        return percept


def _coerce_raw_list(data: dict[str, Any], key: str) -> list[Any]:
    """Return the raw list at `key`, or an empty list for anything that
    isn't actually one -- a missing key, an explicit `None`, or (the sharp
    edge here) a plain string, which Python happily iterates one character
    at a time instead of raising. A malformed upstream tracker payload
    should degrade to "no observation for this field," not crash the
    caller with a raw `TypeError`."""
    value = data.get(key)
    return value if isinstance(value, list) else []


def _coerce_model_list[ModelT: BaseModel](
    data: dict[str, Any], key: str, model: type[ModelT]
) -> list[ModelT]:
    """Build a list of `model` instances from `data[key]`, silently
    dropping any entry that isn't a mapping `model(**entry)` could even be
    attempted on (a bare string or number in the list, for example) rather
    than letting `TypeError`/`AttributeError` from `**entry` unpacking
    propagate out of `process()`."""
    return [
        model(**entry)
        for entry in _coerce_raw_list(data, key)
        if isinstance(entry, dict)
    ]


class SpatialTrackingVisionAdapter:
    """Adapts a structured tracker/detector payload -- track IDs, object
    boxes, per-face action units, spatial relations -- into a
    `StructuredVisionPercept`.

    Every nested structure is built through its own Pydantic model
    (`DetectedObject`, `IdentityEstimate`, `FacialObservable`,
    `SpatialRelation`), so a raw payload that tries to smuggle an emotional
    label into a face's action units is rejected by `FacialObservable`'s own
    field validator before it ever reaches the returned percept.

    The raw payload comes from an upstream tracker process, not from
    cognition's own typed boundary, so every list-shaped field is coerced
    defensively (`_coerce_raw_list`/`_coerce_model_list`) rather than
    assumed well-formed: a missing key, an explicit `None`, a string where
    a list was expected, or a malformed nested entry all degrade to "no
    observation for that field" instead of raising a raw `TypeError` out of
    `process()`.
    """

    default_confidence: float = 0.85

    def process(self, raw_data: Any) -> StructuredVisionPercept:
        data = raw_data if isinstance(raw_data, dict) else {}

        percept = StructuredVisionPercept(
            track_ids=[str(t) for t in _coerce_raw_list(data, "track_ids")],
            identity_estimates=_coerce_model_list(
                data, "identity_estimates", IdentityEstimate
            ),
            objects=_coerce_model_list(data, "objects", DetectedObject),
            actions_events=[str(a) for a in _coerce_raw_list(data, "actions_events")],
            gaze_pose=data.get("gaze_pose"),
            facial_observables=_coerce_model_list(
                data, "facial_observables", FacialObservable
            ),
            scene_deltas=[str(s) for s in _coerce_raw_list(data, "scene_deltas")],
            spatial_relations=_coerce_model_list(
                data, "spatial_relations", SpatialRelation
            ),
            staleness_ms=_safe_staleness_ms(data.get("staleness_ms")),
            confidence=_clamp_unit(
                data.get("confidence"), default=self.default_confidence
            ),
            provenance="spatial_tracking",
        )
        validate_vision_invariants(percept)
        return percept


def to_percept_envelope(structured: StructuredVisionPercept) -> PerceptEnvelope:
    """Normalize a `StructuredVisionPercept` into the `PerceptEnvelope`
    shape `CognitivePipeline` ingests.

    Re-runs `validate_vision_invariants` immediately before conversion: this
    is the last point before the percept leaves the vision boundary and
    enters cognition, so it is the last point at which an emotional fact
    smuggled in after adapter construction (a mutated list, a hand-built
    percept that skipped the adapters entirely) can still be caught.
    """
    validate_vision_invariants(structured)

    text_parts = [part for part in (*structured.scene_deltas, *structured.actions_events) if part]
    text_content = "; ".join(text_parts) if text_parts else None

    return PerceptEnvelope(
        percept_id=_new_percept_uid(structured.provenance),
        modality="vision",
        source=structured.provenance,
        observed_at=time.time(),
        confidence=structured.confidence,
        raw_payload=structured.model_dump(mode="json"),
        text_content=text_content,
        provenance=structured.provenance,
    )
