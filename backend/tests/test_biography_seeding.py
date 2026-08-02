"""
Seeding a friend with a life, and doing it exactly once.

`config/persona.toml` describes temperament. It cannot describe a person —
who someone is is mostly episodes, and those belong in the episodic memory
store, not in the persona schema and not in the system prompt.

Prompt-resident material is paid for on every single turn, so a biography of
any real length there would cost latency on each one while most of it is
irrelevant to whatever is being said. Seeded as memories instead, the ordinary
retrieval path decides what surfaces. That is what lets the documentary be long.

The behaviour that needs pinning is idempotence. Seeding is not a one-shot flag
but a per-paragraph fingerprint, because the alternative to that is a choice
between duplicating the whole file every boot and never being able to add to it.
"""

from unittest.mock import AsyncMock

import pytest

from app import config as config_module
from app.persona.biography import (
    BIOGRAPHY_SOURCE,
    BiographyEntry,
    find_biography_file,
    parse_biography,
    pending_entries,
    read_biography,
    seed_biography,
)

DOC = """# Biography

## How she talks

She switches between English and Hindi mid-sentence.

She says "haan haan" twice when only half listening.

## How she argues

She goes quiet rather than loud.
"""


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------


def test_each_paragraph_becomes_its_own_memory():
    """Granularity decides whether retrieval is usable.

    A whole section as one memory returns all-or-nothing, so a question about
    one detail drags in every unrelated detail beside it and crowds the context
    with things nobody asked about.
    """
    entries = parse_biography(DOC)
    texts = [e.text for e in entries]
    assert "She switches between English and Hindi mid-sentence." in texts
    assert 'She says "haan haan" twice when only half listening.' in texts
    assert "She goes quiet rather than loud." in texts


def test_a_paragraph_carries_the_heading_it_sat_under():
    """An isolated line has to still mean something when it surfaces alone.

    "She goes quiet rather than loud" retrieved with no context could be about
    anything; filed under "How she argues" it is an answer.
    """
    entries = parse_biography(DOC)
    argues = next(e for e in entries if "quiet rather than loud" in e.text)
    assert "How she argues" in argues.heading
    assert argues.memory_text.startswith("Biography / How she argues:")


def test_the_heading_is_folded_into_the_stored_text():
    """Retrieval matches on content, not on metadata columns.

    A paragraph filed under "Her sister" that never says "sister" would be
    unreachable by the obvious cue if the heading stayed out of the text.
    """
    entry = BiographyEntry(heading="Her sister", text="They speak every Sunday.")
    assert entry.memory_text == "Her sister: They speak every Sunday."


def test_prose_before_any_heading_is_still_kept():
    """The file is written by a person, not authored against a spec."""
    entries = parse_biography("She is stubborn about small things.\n")
    assert len(entries) == 1
    assert entries[0].heading == ""
    assert entries[0].text == "She is stubborn about small things."


def test_line_wrapping_does_not_split_a_paragraph():
    """People hard-wrap prose. Wrapping is not a semantic boundary."""
    entries = parse_biography("## X\n\nshe is\nvery\nstubborn\n")
    assert len(entries) == 1
    assert entries[0].text == "she is very stubborn"


def test_an_empty_or_missing_biography_yields_nothing():
    assert parse_biography("") == []
    assert parse_biography("## Heading with no body\n") == []
    assert read_biography(None) == []


def test_an_unreadable_biography_does_not_raise(tmp_path):
    """A friend who forgets your history is still a friend you can talk to.
    A process that will not boot is not."""
    assert read_biography(tmp_path / "does_not_exist.md") == []


# --------------------------------------------------------------------------
# seeding exactly once
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seeding_writes_every_passage_the_first_time():
    store = AsyncMock()
    entries = parse_biography(DOC)
    stored = await seed_biography(entries, store)
    assert len(stored) == len(entries)
    assert store.add_memory.await_count == len(entries)


@pytest.mark.asyncio
async def test_seeding_twice_does_not_duplicate_the_history():
    """Re-seeding on every boot would multiply the agent's past.

    The memory store reinforces identical content rather than duplicating it,
    but relying on that would still redo the embedding work for the whole file
    on every start, and would tie correctness to a downstream implementation
    detail.
    """
    store = AsyncMock()
    entries = parse_biography(DOC)

    first = await seed_biography(entries, store)
    second = await seed_biography(entries, store, already_seeded=first)

    assert second == []
    assert store.add_memory.await_count == len(entries)


@pytest.mark.asyncio
async def test_adding_to_the_documentary_seeds_only_the_new_part():
    """The reason fingerprints are per paragraph rather than per file.

    A single "seeded" flag forces a choice between duplicating everything and
    never being able to write another page.
    """
    store = AsyncMock()
    original = parse_biography(DOC)
    seeded = await seed_biography(original, store)
    store.reset_mock()

    extended = parse_biography(DOC + "\n## Work\n\nShe teaches chemistry.\n")
    new = await seed_biography(extended, store, already_seeded=seeded)

    assert len(new) == 1
    assert store.add_memory.await_count == 1
    assert "chemistry" in store.add_memory.await_args.kwargs["content"]


def test_moving_a_passage_to_another_section_counts_as_new():
    """A paragraph's meaning depends on what it was filed under."""
    a = BiographyEntry(heading="How she argues", text="She goes quiet.")
    b = BiographyEntry(heading="How she grieves", text="She goes quiet.")
    assert a.fingerprint != b.fingerprint


def test_pending_entries_reports_what_is_left():
    entries = parse_biography(DOC)
    assert pending_entries(entries, []) == entries
    assert pending_entries(entries, [e.fingerprint for e in entries]) == []


# --------------------------------------------------------------------------
# how it is stored
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seeded_memories_are_marked_as_seeded_not_lived():
    """The agent's sense of a shared past should be honest about its origin.

    Without a distinguishable source there is no way to re-seed, prune, or
    later tell the user which memories came from a file they wrote rather than
    from a conversation that happened.
    """
    store = AsyncMock()
    await seed_biography(parse_biography(DOC)[:1], store)
    kwargs = store.add_memory.await_args.kwargs
    assert kwargs["source"] == BIOGRAPHY_SOURCE
    assert kwargs["metadata"]["biography_fingerprint"]
    assert kwargs["importance"] > 0.5, "biography should outrank a passing remark"


@pytest.mark.asyncio
async def test_one_bad_passage_does_not_abandon_the_rest():
    """A partly-seeded history beats none, and the next boot retries the gap."""
    store = AsyncMock()
    calls = {"n": 0}

    async def flaky(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("qdrant down")

    store.add_memory = flaky
    entries = parse_biography(DOC)
    stored = await seed_biography(entries, store)

    assert len(stored) == len(entries) - 1
    # The failed one is absent, so it is still pending next time.
    assert pending_entries(entries, stored)


@pytest.mark.asyncio
async def test_no_memory_store_is_not_an_error():
    """Agents without a memory store still have to start."""
    assert await seed_biography(parse_biography(DOC), None) == []


# --------------------------------------------------------------------------
# the shipped file
# --------------------------------------------------------------------------


def test_the_shipped_biography_parses(no_biography_setting):
    """The example a user starts from must survive its own parser."""
    found = find_biography_file()
    assert found is not None and found.name == "biography.md"
    assert read_biography(found), "the shipped biography produced no passages"


# --------------------------------------------------------------------------
# locating the file
# --------------------------------------------------------------------------


@pytest.fixture
def no_biography_setting(monkeypatch):
    """Neutralise an ambient BIOGRAPHY_PATH so discovery is what is tested."""
    monkeypatch.setattr(config_module.config_instance, "BIOGRAPHY_PATH", None)


def test_biography_path_setting_overrides_discovery(monkeypatch, tmp_path):
    """A biography is a real person's life; it must be storable outside the repo.

    Without this the only readable location is the tracked `config/biography.md`,
    which forces that material into git in order to be used at all.
    """
    external = tmp_path / "elsewhere.md"
    external.write_text("# Her\n\nShe is real.\n", encoding="utf-8")
    monkeypatch.setattr(
        config_module.config_instance, "BIOGRAPHY_PATH", str(external)
    )
    assert find_biography_file() == external


def test_a_missing_biography_path_does_not_fall_back_to_the_shipped_file(
    monkeypatch, tmp_path
):
    """A typo'd path must mean "no biography", never "the repo's example".

    Seeding is fingerprinted and effectively one-way, so a silent fallback
    would plant the shipped example person's history in a real agent's memory,
    which then has to be pruned back out passage by passage.
    """
    monkeypatch.setattr(
        config_module.config_instance,
        "BIOGRAPHY_PATH",
        str(tmp_path / "typo.md"),
    )
    assert find_biography_file() is None


def test_an_explicit_argument_beats_the_setting(monkeypatch, tmp_path):
    """Callers that pass a path mean it -- deployment config must not win."""
    wanted = tmp_path / "wanted.md"
    wanted.write_text("# Her\n\nThis one.\n", encoding="utf-8")
    other = tmp_path / "other.md"
    other.write_text("# Her\n\nNot this one.\n", encoding="utf-8")
    monkeypatch.setattr(config_module.config_instance, "BIOGRAPHY_PATH", str(other))
    assert find_biography_file(str(wanted)) == wanted


def test_discovery_still_works_when_the_setting_is_unset(no_biography_setting):
    """The historical behaviour is the default; the setting is opt-in."""
    found = find_biography_file()
    assert found is not None and found.name == "biography.md"
