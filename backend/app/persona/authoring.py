"""
Reading the file a user writes their friend into.

`PersonaProfile` says what a persona *is*; this module decides how an authored
file becomes one, and — the part that carries the weight — **when it stops being
consulted**.

The answer is the same for everything the file can set: **read once, then
never again.**

- IMMUTABLE      never comes from a file at all. Rejected on every read.
- CONSTITUTIONAL seeds the friend's temperament on the first boot.
- ADAPTIVE       seeds their starting relationship on the first boot.

After that the durable store owns all of it and the file is inert. Trust and
attachment are built over months of conversation, and a config file that
quietly reset them on restart would make the relationship worthless — but the
same is true of temperament, just more slowly. A person modelled on someone
real has to be allowed to stop matching the document, or the document is not a
seed, it is a leash.

The tiers still exist and still matter: they are what the *schema* enforces
(bounds, what may be evolved) and what the log names back to the author. They
just no longer decide which boot a value applies on.

Starting over is `scripts/reset_persona.py` — deliberate, confirmed, and
distinct from editing a file.
"""

import logging
import tomllib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .profile import IMMUTABLE_CORE, PersonaProfile, Tier

logger = logging.getLogger(__name__)

DEFAULT_PERSONA_FILE = "config/persona.toml"

# Distinguishes "look for the file" from "there is no file". `None` cannot do
# both jobs, and conflating them is how discovery becomes unavoidable: a test
# building an agent from a temp directory would still walk up and find the
# developer's own persona, so every case would silently inherit whatever
# character happened to be checked out.
AUTO_DISCOVER = object()


def find_persona_file(explicit: Optional[str] = None) -> Optional[Path]:
    """Locate the authored persona file.

    Walks up from this module rather than trusting the process working
    directory, because the agents are launched from several places (the repo
    root, `backend/`, and a container WORKDIR) and a relative path would resolve
    differently in each — the kind of bug that only appears in one deployment.
    """
    if explicit:
        path = Path(explicit)
        return path if path.exists() else None

    for parent in Path(__file__).resolve().parents:
        candidate = parent / DEFAULT_PERSONA_FILE
        if candidate.exists():
            return candidate
    return None


def read_persona_file(path: Path) -> Dict[str, Any]:
    """Parse an authored file, returning `{}` on any problem.

    Never raises. A malformed persona file must not stop the agent from
    booting — a friend with default temperament is recoverable, a friend that
    will not start is not. The error is logged loudly enough to act on.
    """
    try:
        if path.suffix.lower() == ".toml":
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        else:
            import json

            data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error(
            "[Persona] Could not read %s (%s). Booting with defaults; your "
            "authored persona was NOT applied.",
            path,
            exc,
        )
        return {}

    if not isinstance(data, dict):
        logger.error("[Persona] %s is not a table of values; ignoring.", path)
        return {}
    return data


def strip_immutable(data: Dict[str, Any], *, origin: str) -> Dict[str, Any]:
    """Drop any attempt to set a safety invariant from the file."""
    cleaned = dict(data)
    for key in ("immutable", *IMMUTABLE_CORE.keys()):
        if key in cleaned:
            logger.warning(
                "[Persona] '%s' in %s targets the immutable safety core and was "
                "ignored. These are fixed in code and cannot be set by a file.",
                key,
                origin,
            )
            cleaned.pop(key)
    return cleaned


def split_by_tier(
    data: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Sort authored keys into (constitutional, adaptive, unknown).

    Unknown keys are returned rather than dropped silently so a typo can be
    reported. Someone who writes `baseline_valance` and gets no warning will
    conclude the setting does not work, not that they misspelled it.
    """
    constitutional: Dict[str, Any] = {}
    adaptive: Dict[str, Any] = {}
    unknown: Dict[str, Any] = {}

    for key, value in data.items():
        if key not in PersonaProfile.model_fields:
            unknown[key] = value
        elif PersonaProfile.tier_of(key) is Tier.ADAPTIVE:
            adaptive[key] = value
        else:
            constitutional[key] = value
    return constitutional, adaptive, unknown


def authored_overrides(
    path: Optional[Path],
    *,
    first_boot: bool,
) -> Dict[str, Any]:
    """The fields an authored file may contribute to *this* boot.

    On a first boot, everything it declares. On any later boot, **nothing**.

    This used to keep applying the constitutional half forever, on the argument
    that temperament is who someone fundamentally is and so an edit should take
    effect. The argument holds for a persona you are authoring iteratively. It
    does not hold for the case this file exists to serve — describing a real
    person so the agent can start out as them — because there the file is a
    snapshot of one moment, and re-applying it on every boot pins the friend to
    that moment permanently. Constitutional values move slowly, not never.

    So the tier split no longer decides *when* a value applies; it decides what
    the log can tell the user about what they wrote. Re-seeding from an edited
    file is `scripts/reset_persona.py`, which is a deliberate act with a
    confirmation prompt rather than something a text editor does silently.
    """
    if path is None:
        return {}

    data = strip_immutable(read_persona_file(path), origin=str(path))
    if not data:
        return {}

    constitutional, adaptive, unknown = split_by_tier(data)

    for key in sorted(unknown):
        logger.warning(
            "[Persona] '%s' in %s is not a persona setting and was ignored. "
            "Check the spelling against config/persona.toml's comments.",
            key,
            path,
        )

    if first_boot:
        logger.info(
            "[Persona] First boot: seeding your friend from %s (%d settings).",
            path,
            len(constitutional) + len(adaptive),
        )
        return {**constitutional, **adaptive}

    written = sorted({*constitutional, *adaptive})
    if written:
        logger.info(
            "[Persona] %s was already used to seed this friend; %s left as they "
            "have grown them. Run scripts/reset_persona.py to start over from "
            "the file.",
            path,
            ", ".join(written),
        )
    return {}
