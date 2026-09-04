"""Provider-independent speech contract owned by the cognitive layer.

``SpeechIntent`` records what the brain intends to communicate and how it
intends it to be delivered. Voice compilers may translate that intent into
provider controls, but they must not change this source-of-truth record.
"""

from __future__ import annotations

import uuid
import warnings
from enum import Enum

from pydantic import BaseModel, Field


class SpeechAffect(BaseModel):
    """Affect requested for a spoken turn in PAD coordinates."""

    valence: float = Field(default=0.0, ge=-1.0, le=1.0)
    arousal: float = Field(default=0.0, ge=-1.0, le=1.0)
    dominance: float = Field(default=0.0, ge=-1.0, le=1.0)
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    optional_label_hint: str | None = None


class SpeechEpistemics(BaseModel):
    """The confidence and hedging requirements behind spoken claims."""

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    hedge_required: bool = False


# ``register`` is part of the versioned wire contract, although it shadows a
# BaseModel method and Pydantic warns when it constructs this schema.
with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message=(
            r'Field name "register" in "SpeechRelationship" shadows an '
            r'attribute in parent "BaseModel"'
        ),
        category=UserWarning,
    )

    class SpeechRelationship(BaseModel):
        """Relationship-aware stance and register selected by cognition."""

        stance: str = "WARM"
        familiarity: float = Field(default=0.5, ge=0.0, le=1.0)
        register: str = "CASUAL"


class SpeechDelivery(BaseModel):
    """Provider-neutral acoustic delivery instructions."""

    urgency: float = Field(default=0.0, ge=0.0, le=1.0)
    relative_rate: float = Field(default=1.0, ge=0.5, le=2.0)
    relative_pitch: float = Field(default=1.0, ge=0.5, le=2.0)
    relative_energy: float = Field(default=1.0, ge=0.5, le=2.0)
    style: str | None = None


class TimelineMarkerKind(str, Enum):
    """Kinds of timing or performance cue supported by the stable schema."""

    PAUSE = "PAUSE"
    EMPHASIS = "EMPHASIS"
    VOCALIZATION = "VOCALIZATION"


class SpeechTimelineMarker(BaseModel):
    """A timeline instruction expressed without vendor markup."""

    kind: TimelineMarkerKind
    text_span: str
    strength_or_duration: float = 0.5
    reason: str = ""


class SpeechTurnPolicy(BaseModel):
    """Turn-taking constraints that remain brain-owned across renderers."""

    start_deadline: float = Field(default=0.0, ge=0.0)
    yield_after: bool = True
    expect_response: bool = True
    interruptible: bool = True
    barge_in_behavior: str = "IMMEDIATE_STOP"


class SpeechIntent(BaseModel):
    """The complete versioned speech instruction for one committed turn."""

    schema_version: str = "1.0.0"
    intent_id: str
    turn_id: str
    addressee: str = "user"
    semantic_text: str
    dialogue_act: str = "STATEMENT"
    objective: str = "INFORM"
    claim_evidence_ids: list[str] = Field(default_factory=list)
    affect: SpeechAffect = Field(default_factory=SpeechAffect)
    epistemics: SpeechEpistemics = Field(default_factory=SpeechEpistemics)
    relationship: SpeechRelationship = Field(default_factory=SpeechRelationship)
    delivery: SpeechDelivery = Field(default_factory=SpeechDelivery)
    timeline: list[SpeechTimelineMarker] = Field(default_factory=list)
    turn_policy: SpeechTurnPolicy = Field(default_factory=SpeechTurnPolicy)
    locale: str = "en-US"
    pronunciation_hints: list[str] = Field(default_factory=list)
    safety_constraints: list[str] = Field(default_factory=list)


def new_speech_intent_id() -> str:
    """Return a collision-resistant identifier for a new speech intent."""
    return f"speech-{uuid.uuid4().hex}"


def build_speech_intent(
    *,
    turn_id: str,
    semantic_text: str,
    addressee: str = "user",
    dialogue_act: str = "STATEMENT",
    objective: str = "INFORM",
    claim_evidence_ids: list[str] | None = None,
    affect: SpeechAffect | None = None,
    epistemics: SpeechEpistemics | None = None,
    relationship: SpeechRelationship | None = None,
    delivery: SpeechDelivery | None = None,
    timeline: list[SpeechTimelineMarker] | None = None,
    turn_policy: SpeechTurnPolicy | None = None,
    locale: str = "en-US",
    pronunciation_hints: list[str] | None = None,
    safety_constraints: list[str] | None = None,
) -> SpeechIntent:
    """Build an intent while stamping its fresh, provider-independent ID."""
    return SpeechIntent(
        intent_id=new_speech_intent_id(),
        turn_id=turn_id,
        semantic_text=semantic_text,
        addressee=addressee,
        dialogue_act=dialogue_act,
        objective=objective,
        claim_evidence_ids=claim_evidence_ids or [],
        affect=affect or SpeechAffect(),
        epistemics=epistemics or SpeechEpistemics(),
        relationship=relationship or SpeechRelationship(),
        delivery=delivery or SpeechDelivery(),
        timeline=timeline or [],
        turn_policy=turn_policy or SpeechTurnPolicy(),
        locale=locale,
        pronunciation_hints=pronunciation_hints or [],
        safety_constraints=safety_constraints or [],
    )
