"""
The persona prompt is paid for on every single turn.

Everything in `get_persona_prompt` is assembled from persona fields, and the
whole block is prepended to each request. So an unbounded field there is not a
storage question — it is a per-turn latency and context-budget question, and it
compounds: reflection reads the prompt and can write back into it.

Every narrative field had a declared ceiling except `style_description`, which
reflection writes free text into. These tests pin the ceilings so a later field
cannot quietly remove one.
"""

import pytest

from app.cognitive.identity import IdentityManager
from app.persona.profile import PersonaProfile

# Deliberately in characters rather than tokens: a real tokenizer would make
# this test depend on a model, and the point is to catch an unbounded *field*,
# not to predict a token count to the unit.
#
# Fully saturated the prompt measures ~5900 characters. The budget is set above
# that with room to spare on purpose. A tight budget would fail every time
# someone rewords a static line of the template — noise, not signal — whereas
# the failure this exists to catch is a field with no ceiling at all, and that
# overshoots by an order of magnitude rather than a few percent (the verbose
# reflection below would contribute ~40,000 characters unbounded).
WORST_CASE_PROMPT_CHARS = 7000


def _saturated(tmp_path) -> IdentityManager:
    """An agent with every bounded narrative field pushed to its limit."""
    agent = IdentityManager(base_path=str(tmp_path), persona_file=None)
    p = agent.persona
    p.name = "N" * 64
    p.identity_summary = "S" * 1200
    p.speech_patterns = ["P" * 80 for _ in range(20)]
    p.adaptive_traits = ["T" * 80 for _ in range(5)]
    p.relationship = "R" * 64
    p.speaking_style = {
        "style_description": "D" * PersonaProfile.MAX_STYLE_DESCRIPTION,
        "common_vocabulary": ["V" * 40 for _ in range(200)],
    }
    return agent


def test_the_persona_prompt_has_a_ceiling(tmp_path):
    """Every field saturated must still fit a budget stated in advance.

    If this fails after a new field is added, the field is unbounded or its
    bound is too loose — the prompt is not the place to discover that, because
    the cost is paid on every turn by every user before anyone notices.
    """
    prompt = _saturated(tmp_path).get_persona_prompt("mood directive")

    assert len(prompt) < WORST_CASE_PROMPT_CHARS, (
        f"persona prompt reached {len(prompt)} chars; a field is unbounded "
        "or its ceiling was raised without raising this budget deliberately"
    )


def test_vocabulary_cannot_grow_the_prompt_without_limit(tmp_path):
    """`common_vocabulary` has no item cap in the schema, only a read-time slice.

    The slice is what bounds it. If someone removes the `[:30]` believing the
    schema constrains the list, the prompt grows with every word the agent ever
    learns.
    """
    agent = _saturated(tmp_path)
    agent.persona.speaking_style = {
        "style_description": "",
        "common_vocabulary": ["word" for _ in range(5000)],
    }

    prompt = agent.get_persona_prompt("")

    assert prompt.count("word") <= 30


@pytest.mark.asyncio
async def test_a_verbose_reflection_cannot_permanently_enlarge_every_turn(tmp_path):
    """The compounding case, and the reason this field needed a bound at all.

    `style_description` is the one part of the per-turn prompt that the agent
    rewrites by itself, straight from reflection output. An LLM that returns a
    paragraph instead of a phrase would enlarge every subsequent prompt — and
    the next reflection reads that larger prompt, so it can grow again. Nothing
    in the loop pulls it back down.
    """
    agent = IdentityManager(base_path=str(tmp_path), persona_file=None)

    await agent.evolve_persona({"speaking_style": "verbose " * 5000})

    stored = agent.persona.speaking_style["style_description"]
    assert len(stored) == PersonaProfile.MAX_STYLE_DESCRIPTION
    # Bounded in storage, not merely on read: clipping at render time would let
    # the durable column grow forever while hiding that it had.
    assert len(agent.get_persona_prompt("")) < WORST_CASE_PROMPT_CHARS


@pytest.mark.asyncio
async def test_an_ordinary_style_is_left_exactly_as_written(tmp_path):
    """The bound must be invisible at normal length.

    A ceiling that trims typical output would silently reword the agent's own
    description of its voice.
    """
    agent = IdentityManager(base_path=str(tmp_path), persona_file=None)
    voice = "Warm and unhurried, with a habit of asking one question too many."

    await agent.evolve_persona({"speaking_style": voice})

    assert agent.persona.speaking_style["style_description"] == voice
