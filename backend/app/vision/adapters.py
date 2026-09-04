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

from app.cognitive.percept import PerceptEnvelope
from app.cognitive.vision_percept import (
    DetectedObject,
    FacialObservable,
    IdentityEstimate,
    SpatialRelation,
    StructuredVisionPercept,
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
            staleness_ms = float(raw_data.get("staleness_ms", 0.0) or 0.0)
        else:
            caption = str(raw_data or "").strip()
            confidence = self.default_confidence
            staleness_ms = 0.0

        percept = StructuredVisionPercept(
            scene_deltas=[caption] if caption else [],
            confidence=confidence,
            staleness_ms=staleness_ms,
            provenance="vlm_caption",
        )
        validate_vision_invariants(percept)
        return percept


class SpatialTrackingVisionAdapter:
    """Adapts a structured tracker/detector payload -- track IDs, object
    boxes, per-face action units, spatial relations -- into a
    `StructuredVisionPercept`.

    Every nested structure is built through its own Pydantic model
    (`DetectedObject`, `IdentityEstimate`, `FacialObservable`,
    `SpatialRelation`), so a raw payload that tries to smuggle an emotional
    label into a face's action units is rejected by `FacialObservable`'s own
    field validator before it ever reaches the returned percept.
    """

    default_confidence: float = 0.85

    def process(self, raw_data: Any) -> StructuredVisionPercept:
        data = raw_data if isinstance(raw_data, dict) else {}

        percept = StructuredVisionPercept(
            track_ids=[str(t) for t in data.get("track_ids", [])],
            identity_estimates=[
                IdentityEstimate(**entry)
                for entry in data.get("identity_estimates", [])
            ],
            objects=[DetectedObject(**entry) for entry in data.get("objects", [])],
            actions_events=[str(a) for a in data.get("actions_events", [])],
            gaze_pose=data.get("gaze_pose"),
            facial_observables=[
                FacialObservable(**entry)
                for entry in data.get("facial_observables", [])
            ],
            scene_deltas=[str(s) for s in data.get("scene_deltas", [])],
            spatial_relations=[
                SpatialRelation(**entry)
                for entry in data.get("spatial_relations", [])
            ],
            staleness_ms=float(data.get("staleness_ms", 0.0) or 0.0),
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
