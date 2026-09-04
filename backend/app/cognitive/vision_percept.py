"""Structured vision boundary (`FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` SS24).

Vision is a specialist sensor, not cognition: whatever a camera pipeline
infers about tracks, identities, objects, and faces arrives at the brain
kernel as an *uncertain observation*, never as a fact the kernel is obligated
to believe. `StructuredVisionPercept` is the typed shape that observation
takes before it is normalized into a `PerceptEnvelope`
(`app/cognitive/percept.py`) for the cognitive pipeline.

The one invariant this module exists to enforce structurally, not just by
convention: a facial observable reports muscle movement (action units,
blendshape-style descriptors -- the same vocabulary
`app/vision/reflex.py` already scores), never an emotional fact. "The user
is smiling" is an observation a vision system can make; "the user is happy"
is an inference the brain kernel's own appraisal is responsible for, using
the smile alongside everything else it knows. Collapsing that distinction at
the sensor boundary would let a face detector silently assert affect,
bypassing the appraisal path CLAUDE.md documents for every other affect
change. `FacialObservable` rejects emotional language at construction time,
and `validate_vision_invariants` re-checks a whole percept's facial
observables for the case a caller mutates a list field after construction
(Pydantic does not re-run field validators on in-place list mutation, so a
`.append()` after the fact would otherwise slip past the constructor-time
check unnoticed).
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

# Not a general sentiment lexicon and not meant to be exhaustive coverage of
# English emotion vocabulary -- it only needs to catch a vision pipeline (or
# a careless caller) writing an emotional label into a field documented as
# muscle movement. Word-boundary matched and case-insensitive so it catches
# "Angry", "angrily" is not caught, but "angry" embedded in a longer phrase
# ("looks angry today") is.
_EMOTION_LEXICON: frozenset[str] = frozenset(
    {
        "happy",
        "happiness",
        "sad",
        "sadness",
        "angry",
        "anger",
        "afraid",
        "fear",
        "fearful",
        "scared",
        "joy",
        "joyful",
        "disgust",
        "disgusted",
        "surprised",
        "surprise",
        "anxious",
        "anxiety",
        "excited",
        "excitement",
        "content",
        "contentment",
        "distressed",
        "distress",
        "upset",
        "worried",
        "worry",
        "delighted",
        "delight",
        "annoyed",
        "annoyance",
        "frustrated",
        "frustration",
        "love",
        "hate",
        "nervous",
        "embarrassed",
        "embarrassment",
        "proud",
        "pride",
        "ashamed",
        "shame",
        "grief",
        "sorrow",
        "elated",
        "elation",
        "irritated",
        "irritation",
        "pleased",
        "displeased",
        "cheerful",
        "gloomy",
        "miserable",
    }
)

_WORD_RE = re.compile(r"[A-Za-z]+")


def _contains_emotional_language(text: str) -> bool:
    return any(word.lower() in _EMOTION_LEXICON for word in _WORD_RE.findall(text))


class IdentityEstimate(BaseModel):
    """An uncertain guess at who a tracked person is -- never an
    authenticated identity, only a signal the brain kernel may weigh."""

    person_id: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    bounding_box: list[float] | None = None


class DetectedObject(BaseModel):
    label: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    bounding_box: list[float] | None = None
    spatial_relation: str | None = None


class FacialObservable(BaseModel):
    """Muscle-movement observations only. `action_units` and
    `muscle_movement` must describe what moved (an action-unit code, a
    blendshape name, "brow lowered"), never what it is presumed to mean."""

    action_units: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    muscle_movement: str = ""

    @field_validator("action_units")
    @classmethod
    def _reject_emotion_labels_in_action_units(cls, value: list[str]) -> list[str]:
        for unit in value:
            if _contains_emotional_language(unit):
                raise ValueError(
                    "action_units must describe muscle movement, not an "
                    f"emotional fact: {unit!r}"
                )
        return value

    @field_validator("muscle_movement")
    @classmethod
    def _reject_emotion_labels_in_muscle_movement(cls, value: str) -> str:
        if _contains_emotional_language(value):
            raise ValueError(
                "muscle_movement must describe observable movement, not an "
                f"emotional fact: {value!r}"
            )
        return value


class SpatialRelation(BaseModel):
    subject: str
    relation: str
    object: str


class StructuredVisionPercept(BaseModel):
    """The full structured observation a vision adapter hands to
    `to_percept_envelope` for ingestion by `CognitivePipeline`."""

    track_ids: list[str] = Field(default_factory=list)
    identity_estimates: list[IdentityEstimate] = Field(default_factory=list)
    objects: list[DetectedObject] = Field(default_factory=list)
    actions_events: list[str] = Field(default_factory=list)
    gaze_pose: dict[str, float] | None = None
    facial_observables: list[FacialObservable] = Field(default_factory=list)
    scene_deltas: list[str] = Field(default_factory=list)
    spatial_relations: list[SpatialRelation] = Field(default_factory=list)
    staleness_ms: float = 0.0
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: str = "structured_vision"


def validate_vision_invariants(percept: StructuredVisionPercept) -> None:
    """Re-check every facial observable in `percept` for emotional
    language, independent of whatever `FacialObservable`'s own field
    validators already caught at construction time.

    This exists because Pydantic does not re-validate a list field when its
    contents are mutated in place (`observable.action_units.append(...)`
    after construction bypasses the constructor-time check entirely). Any
    code path that hands a `StructuredVisionPercept` to cognition --
    `to_percept_envelope` calls this first -- gets one final, authoritative
    check regardless of how the percept was assembled.
    """
    for observable in percept.facial_observables:
        for unit in observable.action_units:
            if _contains_emotional_language(unit):
                raise ValueError(
                    "StructuredVisionPercept invariant violated: a facial "
                    f"observable's action_units contains an emotional fact: {unit!r}"
                )
        if _contains_emotional_language(observable.muscle_movement):
            raise ValueError(
                "StructuredVisionPercept invariant violated: a facial "
                "observable's muscle_movement contains an emotional fact: "
                f"{observable.muscle_movement!r}"
            )
