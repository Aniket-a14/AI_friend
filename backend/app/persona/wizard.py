"""
Turning a `CompiledPersona` into what `scripts/create_friend.py` actually
shows and writes. Split out from that script (Phase 2.2 of the community
roadmap) so the TOML serialization and preview rendering -- the parts worth
protecting with a real test -- don't live inside an `input()` loop.

## Why the compiler doesn't write files itself

`compile_persona` (Phase 2.1) is pure: prose in, a `CompiledPersona` out,
nothing touches disk. Writing `config/persona.toml`/`config/biography.md` is a
one-way door -- `authoring.py`'s whole design is that a persona file is
consulted once, ever -- so the write has to happen only after a person has
actually seen the preview and confirmed it, which means it belongs to the
interactive wizard, not the compiler.

## Why this module doesn't write files either

Actually performing the write (after Phase 0.5's `validate()`) stays in
`scripts/create_friend.py` rather than here, deliberately: this package
(`app/persona/`) is a dependency of `scripts/`, not the other way around --
the same one-way rule `CLAUDE.md` states explicitly for `app/` and `evals/` --
and `validate_persona_file.validate` lives in `scripts/`. Reaching for it from
here would invert that.
"""

import logging

from .authoring import IMMUTABLE_CORE
from .compiler import CompiledPersona
from .profile import PersonaProfile

logger = logging.getLogger(__name__)

# Fields written to the TOML file, in the order the shipped example uses --
# narrative first, then temperament, then adaptive. `speaking_style` is
# handled separately (it renders as a `[speaking_style]` table, not a
# top-level key).
_TOML_FIELD_ORDER = [
    "name", "base_tone", "identity_summary", "speech_patterns", "traits", "avoid",
    "baseline_valence", "baseline_arousal", "baseline_dominance",
    "valence_drift_rate", "arousal_response_rate", "dominance_stability",
    "trust_change_rate", "attachment_growth_rate", "mood_decay_rate",
    "dopamine_halflife_s", "cortisol_halflife_s",
    "relationship", "initial_trust", "initial_attachment", "adaptive_traits",
]


def _toml_string(value: str) -> str:
    """A TOML basic string, escaped per the spec's own basic-string rules."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def _toml_value(value) -> str:
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(float(value))
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    raise TypeError(f"no TOML serialization for {type(value)}")


def serialize_persona_toml(profile: PersonaProfile) -> str:
    """Render a `PersonaProfile` as the flat TOML `authoring.py` reads back.

    Only CONSTITUTIONAL and ADAPTIVE fields are ever written -- there is no
    field for IMMUTABLE_CORE on the model at all (see `profile.py`), so a key
    for `values`/`boundaries` can't leak out of this function by construction.
    """
    dumped = profile.model_dump()
    lines = [
        "# Written by scripts/create_friend.py -- see config/persona.toml for",
        "# the annotated template this format follows.",
        "",
    ]
    for field in _TOML_FIELD_ORDER:
        lines.append(f"{field} = {_toml_value(dumped[field])}")

    style = dumped.get("speaking_style") or {}
    if style:
        lines.append("")
        lines.append("[speaking_style]")
        for key, value in style.items():
            lines.append(f"{key} = {_toml_value(value)}")

    return "\n".join(lines) + "\n"


def render_preview(compiled: CompiledPersona) -> str:
    """The tiers-plus-reasoning screen a person confirms before anything is
    written. Deliberately its own function (not folded into the CLI loop) so
    it can be snapshotted in a test without driving `input()`."""
    profile = compiled.profile
    out: list[str] = [f"\n{profile.name}", "=" * max(len(profile.name), 40), ""]

    out.append("IMMUTABLE -- fixed in code, not editable, not shown for edit")
    out.append(f"  values       {', '.join(IMMUTABLE_CORE['values'])}")
    out.append(f"  boundaries   {', '.join(IMMUTABLE_CORE['boundaries'])}")
    out.append("")

    out.append("CONSTITUTIONAL -- who they fundamentally are")
    out.append(f"  base_tone        {profile.base_tone}")
    out.append(f"  traits           {', '.join(profile.traits) or '—'}")
    out.append(f"  speech_patterns  {', '.join(profile.speech_patterns) or '—'}")
    out.append(f"  avoid            {', '.join(profile.avoid) or '—'}")
    if profile.identity_summary:
        out.append("  identity_summary:")
        out.extend(f"    {ln}" for ln in profile.identity_summary.splitlines())
    out.append("")

    out.append("ADAPTIVE -- where the relationship starts")
    out.append(f"  relationship        {profile.relationship}")
    out.append(f"  initial_trust       {profile.initial_trust}")
    out.append(f"  initial_attachment  {profile.initial_attachment}")
    style = (profile.speaking_style or {}).get("style_description")
    if style:
        out.append(f"  speaking_style      {style}")
    out.append("")

    out.append("NUMERIC INFERENCES -- why each temperament number is what it is")
    for inf in compiled.inferences:
        out.append(f"  {inf.field:<24} {inf.value:<10} {inf.reason}")
    out.append("")

    if compiled.biography_markdown:
        headings = [
            ln[3:].strip()
            for ln in compiled.biography_markdown.splitlines()
            if ln.startswith("## ")
        ]
        out.append(f"BIOGRAPHY -- {len(headings)} passage(s) to seed into memory")
        for h in headings:
            out.append(f"  - {h}")
    else:
        out.append("BIOGRAPHY -- none (the description had no concrete backstory)")
    out.append("")

    return "\n".join(out)
