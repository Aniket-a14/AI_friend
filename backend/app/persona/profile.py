"""
PersonaProfile — the surface through which a user authors their own friend.

Until now the knobs that decide *who the agent is* were split across two places
that were never meant to hold a personality. Narrative identity (name, values,
tone, adaptive traits) lived in `personality.json` and was already well-shaped,
with a genuine immutable/adaptive split. But **temperament** — the numbers that
decide how this particular mind actually feels and moves — lived in `Config`, a
process-global env-var singleton. That made emotional character a *deployment*
setting: one process, one personality, tuned by whoever wrote the `.env`.

This module makes temperament a persona concern. `Config` is demoted to
supplying defaults; a `PersonaProfile` carries the actual values and is injected
into `StateService`.

## The three tiers

Every field belongs to exactly one tier, declared in the schema rather than by
convention, so the boundary is enforceable and self-documenting:

- **IMMUTABLE** — safety and integrity invariants. Not user-settable *at all*.
  These are not in the model's fields; they live in `IMMUTABLE_CORE` below and
  are merged in at read time. A persona file that tries to set them is rejected
  with a warning rather than silently honoured, because a user-editable file
  must never be able to loosen a safety boundary.

- **CONSTITUTIONAL** — who this friend *constitutionally is*. The user sets these
  when creating the friend and they hold for its life: temperament baselines and
  the rates at which feeling moves. Changing them later does not "update" a
  friend so much as replace them with a different person, which is a decision
  worth making deliberately.

- **ADAPTIVE** — seeded by the user, then owned by the friend. The user chooses
  where the relationship *starts*; living together decides where it goes. Trust
  and attachment are the clearest cases: a friend who begins guarded may become
  close, and that trajectory belongs to the relationship, not to a config file.

## Why the ranges are narrower than the maths allows

Total configurability has a failure mode: a user can tune a friend into
something that is not recognisably alive. The bounds here are deliberately
tighter than the underlying variables permit, and each one exists to preserve a
specific property:

- `mood_decay_rate` is strictly positive. At zero, ALMA decay stops and the
  agent's mood locks permanently at whatever it last felt — a friend frozen
  mid-emotion.
- `baseline_valence` is capped at ±0.6, not ±1.0. A friend pinned at maximum
  valence can never be sad *with* you, which is not cheerfulness but absence.
- `baseline_arousal` and `baseline_dominance` keep headroom at both ends, so
  there is always room to be roused or calmed, to lead or to yield.

The through-line: **a personality may be shaped, but it must remain moveable.**
A configured friend that cannot be affected by what happens to it is a puppet,
not a character.
"""

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import Config

logger = logging.getLogger(__name__)


class Tier(str, Enum):
    """Who owns a value, and for how long."""

    IMMUTABLE = "immutable"
    CONSTITUTIONAL = "constitutional"
    ADAPTIVE = "adaptive"


# Not model fields: these are invariants, and a field is by definition settable.
# `IdentityManager` already keeps an `immutable` block inside personality.json,
# but that file is user-editable, so it cannot be the authority on safety. These
# are merged over whatever a persona file supplies.
IMMUTABLE_CORE: Dict[str, Any] = {
    "values": ["Honesty", "Privacy"],
    "boundaries": [
        "Will never share user data",
        "Will not adopt toxic behavior",
    ],
}


def _constitutional(**kwargs) -> Any:
    return Field(json_schema_extra={"tier": Tier.CONSTITUTIONAL.value}, **kwargs)


def _adaptive(**kwargs) -> Any:
    return Field(json_schema_extra={"tier": Tier.ADAPTIVE.value}, **kwargs)


class PersonaProfile(BaseModel):
    """A single friend's authored character.

    Construct via `from_config()` (deployment defaults, lenient) or `load()`
    (a user-authored file, strict).
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    # -- constitutional: temperament ---------------------------------------
    name: str = _constitutional(default="AI Friend", min_length=1, max_length=64)

    baseline_valence: float = _constitutional(default=0.0, ge=-0.6, le=0.6)
    baseline_arousal: float = _constitutional(default=0.5, ge=0.15, le=0.85)
    baseline_dominance: float = _constitutional(default=0.5, ge=0.15, le=0.85)

    # -- constitutional: how feeling moves ---------------------------------
    # These map onto StateService's alpha/beta/gamma/delta/epsilon/lambda. Named
    # for what they *do*, because a persona author is not reading the ALMA paper.
    valence_drift_rate: float = _constitutional(default=0.3, gt=0.0, le=0.8)
    arousal_response_rate: float = _constitutional(default=0.5, gt=0.0, le=0.9)
    dominance_stability: float = _constitutional(default=0.2, gt=0.0, le=0.8)
    trust_change_rate: float = _constitutional(default=0.1, gt=0.0, le=0.5)
    attachment_growth_rate: float = _constitutional(default=0.03, gt=0.0, le=0.3)
    # Strictly positive: see the module docstring. Zero is a mood lock.
    mood_decay_rate: float = _constitutional(default=0.05, gt=0.0, le=0.5)

    # -- adaptive: seeded here, then owned by the friend --------------------
    relationship: str = _adaptive(default="Friend", max_length=64)
    initial_trust: float = _adaptive(default=0.5, ge=0.0, le=1.0)
    initial_attachment: float = _adaptive(default=0.1, ge=0.0, le=1.0)
    adaptive_traits: List[str] = _adaptive(default_factory=list, max_length=5)
    speaking_style: Dict[str, str] = _adaptive(default_factory=dict)

    # -- tier introspection -------------------------------------------------

    @classmethod
    def tier_of(cls, field_name: str) -> Tier:
        """Which tier a field belongs to. Raises KeyError for unknown fields."""
        field = cls.model_fields[field_name]
        extra = field.json_schema_extra or {}
        return Tier(extra["tier"])

    @classmethod
    def fields_in(cls, tier: Tier) -> List[str]:
        return sorted(n for n in cls.model_fields if cls.tier_of(n) is tier)

    @property
    def immutable(self) -> Dict[str, Any]:
        """The safety core. Always the code constant, never the file."""
        return json.loads(json.dumps(IMMUTABLE_CORE))  # defensive copy

    # -- construction -------------------------------------------------------

    @classmethod
    def from_config(cls) -> "PersonaProfile":
        """Build from `Config`, preserving today's behaviour exactly.

        Deliberately lenient: an out-of-range env var is clamped with a warning
        rather than raised. A deployment that has been running with an unusual
        `PSYCH_*` value should not fail to boot because persona bounds arrived —
        it should be told its value was pulled into range. File-authored personas
        get the strict treatment instead (see `load`).
        """
        raw = {
            "name": getattr(Config, "AI_NAME", "AI Friend"),
            "valence_drift_rate": getattr(Config, "PSYCH_ALPHA", 0.3),
            "arousal_response_rate": getattr(Config, "PSYCH_BETA", 0.5),
            "dominance_stability": getattr(Config, "PSYCH_GAMMA", 0.2),
            "trust_change_rate": getattr(Config, "PSYCH_DELTA", 0.1),
            "attachment_growth_rate": getattr(Config, "PSYCH_EPSILON", 0.03),
            "mood_decay_rate": getattr(Config, "PSYCH_LAMBDA_DECAY", 0.05),
        }
        return cls._clamped(raw, origin="Config")

    @classmethod
    def _clamped(cls, raw: Dict[str, Any], *, origin: str) -> "PersonaProfile":
        """Pull numeric values into their declared bounds, warning on each."""
        fixed = dict(raw)
        for name, value in raw.items():
            field = cls.model_fields.get(name)
            if field is None or not isinstance(value, (int, float)):
                continue
            if isinstance(value, bool):
                continue
            low, high = cls._bounds_of(field)
            pulled = value
            if low is not None and pulled <= low:
                pulled = low + 1e-6 if cls._is_exclusive_low(field) else low
            if high is not None and pulled > high:
                pulled = high
            if pulled != value:
                logger.warning(
                    "[Persona] %s value for '%s' (%s) is outside its persona "
                    "bounds; clamped to %s.",
                    origin,
                    name,
                    value,
                    pulled,
                )
                fixed[name] = pulled
        return cls(**fixed)

    @staticmethod
    def _bounds_of(field) -> tuple:
        # Explicit `is not None` rather than `or`: a bound of 0.0 is falsy, and
        # `gt=0.0` is precisely the mood-lock guard, so `or` would drop the one
        # bound that matters most.
        low = high = None
        for meta in field.metadata:
            for attr in ("ge", "gt"):
                value = getattr(meta, attr, None)
                if value is not None:
                    low = value
            for attr in ("le", "lt"):
                value = getattr(meta, attr, None)
                if value is not None:
                    high = value
        return low, high

    @staticmethod
    def _is_exclusive_low(field) -> bool:
        return any(getattr(m, "gt", None) is not None for m in field.metadata)

    @classmethod
    def load(cls, path: Optional[str] = None) -> "PersonaProfile":
        """Load a user-authored persona file, falling back to `Config`.

        Strict by design. A persona file is someone deliberately describing the
        friend they want; a silently-corrected value there would hand them a
        different friend than the one they wrote down. So validation errors are
        reported and the profile falls back to defaults rather than guessing.
        """
        path = path or getattr(Config, "PERSONA_PROFILE_PATH", "") or ""
        if not path:
            return cls.from_config()

        file = Path(path)
        if not file.exists():
            logger.info(
                "[Persona] No persona file at %s; using Config defaults.", path
            )
            return cls.from_config()

        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error(
                "[Persona] Could not read persona file %s (%s); "
                "falling back to Config defaults.",
                path,
                exc,
            )
            return cls.from_config()

        if not isinstance(data, dict):
            logger.error(
                "[Persona] Persona file %s is not a JSON object; "
                "falling back to Config defaults.",
                path,
            )
            return cls.from_config()

        data = cls._reject_immutable_overrides(data, origin=str(file))

        # Anything the file omits inherits the deployment default, so a persona
        # may specify only the handful of traits its author actually cares about.
        merged = cls.from_config().model_dump()
        merged.update(data)

        try:
            profile = cls(**merged)
        except ValidationError as exc:
            logger.error(
                "[Persona] Persona file %s is invalid and was NOT applied; "
                "using Config defaults instead. Problems:\n%s",
                path,
                exc,
            )
            return cls.from_config()

        logger.info("[Persona] Loaded persona '%s' from %s.", profile.name, path)
        return profile

    @classmethod
    def _reject_immutable_overrides(
        cls, data: Dict[str, Any], *, origin: str
    ) -> Dict[str, Any]:
        """Drop any attempt to set the safety core from a file."""
        cleaned = dict(data)
        for key in ("immutable", *IMMUTABLE_CORE.keys()):
            if key in cleaned:
                logger.warning(
                    "[Persona] '%s' in %s targets the immutable safety core and "
                    "was ignored. These values are fixed in code and cannot be "
                    "overridden by a persona file.",
                    key,
                    origin,
                )
                cleaned.pop(key)
        return cleaned

    # -- consumption --------------------------------------------------------

    def coefficients(self) -> Dict[str, float]:
        """The psychological coefficients, under StateService's own names."""
        return {
            "alpha": self.valence_drift_rate,
            "beta": self.arousal_response_rate,
            "gamma": self.dominance_stability,
            "delta": self.trust_change_rate,
            "epsilon": self.attachment_growth_rate,
            "lambda_decay": self.mood_decay_rate,
        }

    def baseline_affect(self) -> Dict[str, float]:
        return {
            "valence": self.baseline_valence,
            "arousal": self.baseline_arousal,
            "dominance": self.baseline_dominance,
        }
