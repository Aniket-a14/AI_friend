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

Peer review (`orchestration/PHASE_05/CODEX_REVIEW_OF_CLAUDE.md`) found the
invariant was bypassable through a second door: `scene_deltas` is free-form
narrative text (the natural home for a VLM caption), and neither the
original lexicon nor `validate_vision_invariants` ever looked at it, so a
caption like "the user is angry" reached `to_percept_envelope` untouched.
`validate_vision_invariants` now inspects `scene_deltas` as well as
`facial_observables`, and `VLMCaptionVisionAdapter`
(`app/vision/adapters.py`) sanitizes caption text before it ever becomes a
scene delta -- see that module's docstring for why dropping the whole
caption, rather than editing out just the offending word, is the safer
default here.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

# Not a general sentiment lexicon and not meant to be exhaustive coverage of
# English emotion vocabulary -- it only needs to catch a vision pipeline (or
# a careless caller) writing an emotional label, or an emotional predicate
# ("appears furious", "looks ecstatic", "is depressed"), into a field
# documented as observation, not inference. Word-boundary matched and
# case-insensitive, so a predicate phrase is caught for free once its
# adjective is in the lexicon -- no separate phrase-pattern parser is
# needed. Both the base form and its common adverbial form are listed
# explicitly (English inflection is irregular enough -- "angry"/"angrily",
# "furious"/"furiously" -- that a suffix-stripping heuristic would either
# miss these or false-positive on unrelated words).
#
# Deliberately excludes "content"/"contentment": once this lexicon is
# applied to free-form scene_deltas text (VLM captions, not just a
# constrained muscle_movement label), "content" collides constantly with
# its ordinary, non-emotional sense ("the content of the frame"). Rejecting
# a caption for using an extremely common English word in its mundane sense
# is a worse failure than missing the rare case where "content" was meant
# as an emotional claim.
_EMOTION_LEXICON: frozenset[str] = frozenset(
    {
        "happy",
        "happiness",
        "happily",
        "sad",
        "sadness",
        "sadly",
        "angry",
        "anger",
        "angrily",
        "furious",
        "furiously",
        "fury",
        "enraged",
        "enrage",
        "rage",
        "raging",
        "irate",
        "livid",
        "afraid",
        "fear",
        "fearful",
        "scared",
        "terrified",
        "terrify",
        "terrifying",
        "terror",
        "petrified",
        "joy",
        "joyful",
        "joyfully",
        "ecstatic",
        "ecstasy",
        "ecstatically",
        "overjoyed",
        "jubilant",
        "jubilation",
        "gleeful",
        "gleefully",
        "glee",
        "disgust",
        "disgusted",
        "surprised",
        "surprise",
        "anxious",
        "anxiety",
        "anxiously",
        "excited",
        "excitement",
        "distressed",
        "distress",
        "distraught",
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
        "nervously",
        "embarrassed",
        "embarrassment",
        "proud",
        "proudly",
        "pride",
        "ashamed",
        "shame",
        "grief",
        "sorrow",
        "sorrowful",
        "elated",
        "elation",
        "irritated",
        "irritation",
        "pleased",
        "displeased",
        "cheerful",
        "gloomy",
        "miserable",
        "depressed",
        "depression",
        "depressing",
        "depressive",
        "devastated",
        "devastating",
        "devastation",
        "heartbroken",
        "melancholy",
        "melancholic",
    }
)

_WORD_RE = re.compile(r"[A-Za-z]+")


def contains_emotional_language(text: str) -> bool:
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
            if contains_emotional_language(unit):
                raise ValueError(
                    "action_units must describe muscle movement, not an "
                    f"emotional fact: {unit!r}"
                )
        return value

    @field_validator("muscle_movement")
    @classmethod
    def _reject_emotion_labels_in_muscle_movement(cls, value: str) -> str:
        if contains_emotional_language(value):
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
    """Re-check every facial observable and scene delta in `percept` for
    emotional language, independent of whatever field-level validation
    already ran at construction time.

    This exists for two distinct reasons. First, Pydantic does not
    re-validate a list field when its contents are mutated in place
    (`observable.action_units.append(...)` after construction bypasses the
    constructor-time check entirely). Second, `scene_deltas` has no
    per-item constructor-time validator at all -- it is free-form narrative
    text (a VLM caption is exactly this shape), so `StructuredVisionPercept(
    scene_deltas=["the user is angry"])` builds without complaint. This
    function is the one place both gaps close: any code path that hands a
    `StructuredVisionPercept` to cognition -- `to_percept_envelope` calls
    this first -- gets one final, authoritative check regardless of how the
    percept was assembled or which field the emotional claim landed in.
    """
    for observable in percept.facial_observables:
        for unit in observable.action_units:
            if contains_emotional_language(unit):
                raise ValueError(
                    "StructuredVisionPercept invariant violated: a facial "
                    f"observable's action_units contains an emotional fact: {unit!r}"
                )
        if contains_emotional_language(observable.muscle_movement):
            raise ValueError(
                "StructuredVisionPercept invariant violated: a facial "
                "observable's muscle_movement contains an emotional fact: "
                f"{observable.muscle_movement!r}"
            )
    for delta in percept.scene_deltas:
        if contains_emotional_language(delta):
            raise ValueError(
                "StructuredVisionPercept invariant violated: a scene delta "
                f"contains an emotional fact assertion: {delta!r}"
            )
