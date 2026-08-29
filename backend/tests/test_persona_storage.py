"""
Where a friend's identity actually lives, and what a reset means.

Three rules under test, each guarding a way the agent could quietly lose or
overwrite who it had become:

1. The durable store is the authority. A boot that hydrates from it must decide
   first-boot-ness from *that* history, not from the git-tracked JSON files.
2. `save()` does not write the JSON files when a durable store exists, so there
   is never a second copy to drift.
3. A reset clears seeded material and keeps lived conversation.
"""

import json
from types import SimpleNamespace

import pytest

from app.cognitive.identity import IdentityManager
from app.persona.biography import BIOGRAPHY_SOURCE
from app.persona.history_migration import (
    HISTORY_SOURCE,
    entry_text,
    fingerprint,
    migrate_history_memories,
    pending_entries,
)
from app.persona.reset import SEEDED_SOURCES, reset_persona

AUTHORED = """
name = "Written"
base_tone = "Dry and exact"
adaptive_traits = ["Eager"]
initial_trust = 0.9
"""


def _persona_file(tmp_path):
    path = tmp_path / "persona.toml"
    path.write_text(AUTHORED, encoding="utf-8")
    return path


class FakeConfigStore:
    """The durable store, with just the surface `IdentityManager` uses."""

    def __init__(self, personality=None, history=None, evolved=""):
        self.personality = json.dumps(personality or {})
        self.history = json.dumps(history or {})
        self.evolved = evolved
        self.updates = []

    async def get_agent_config(self):
        return {
            "personality": self.personality,
            "history": self.history,
            "evolved_learnings": self.evolved,
        }

    async def update_agent_config(self, personality, history, evolved_learnings=""):
        self.updates.append((personality, history, evolved_learnings))


# --------------------------------------------------------------------------
# the durable store is the authority
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_lived_in_store_stops_a_fresh_clone_from_re_seeding(tmp_path):
    """The bug this whole change exists to prevent.

    `personality.json` and `history.json` are tracked in git and ship
    seed-shaped, so on disk **every** fresh clone and every container redeploy
    looks like a first boot. `first_boot` was computed from those files in
    `__init__` and never revisited, so hydrating from a store holding months of
    accumulated persona would still re-apply the authored file over the top.

    The friend would be reset to their original description on every deploy,
    with no error and nothing in the logs to suggest it had happened.
    """
    agent = IdentityManager(
        base_path=str(tmp_path), persona_file=_persona_file(tmp_path)
    )
    assert agent.first_boot is True, "on-disk files are seed-shaped"

    store = FakeConfigStore(
        personality={
            "name": "Lived",
            "core_personality": {"adaptive_traits": ["Grown"]},
        },
        history={"memories": ["we met in October"], "relationship": "Old Friend"},
    )
    await agent.hydrate_from_config_store(store)

    assert agent.first_boot is False, "the store says this friend has lived"
    assert agent.persona.name == "Lived"
    assert agent.persona.adaptive_traits == ["Grown"]
    assert "Eager" not in agent.persona.adaptive_traits


@pytest.mark.asyncio
async def test_a_genuinely_new_store_still_seeds_from_the_file(tmp_path):
    """The other direction, or the fix above would disable seeding entirely.

    An empty durable store is a new friend, and the authored file is the only
    description of them that exists.
    """
    agent = IdentityManager(
        base_path=str(tmp_path), persona_file=_persona_file(tmp_path)
    )
    await agent.hydrate_from_config_store(
        FakeConfigStore(personality={"name": "seed"}, history={"memories": []})
    )

    assert agent.first_boot is True
    assert agent.history[IdentityManager.SEED_MARKER]


@pytest.mark.asyncio
async def test_the_seed_marker_survives_into_the_persisted_history(tmp_path):
    """The marker has to land in the history that gets written back.

    It used to be stamped in `__init__`, onto the file-loaded history that
    hydration then *replaced*. Persisting afterwards would store a history with
    no marker, so the next boot would look new again and re-seed — the marker
    would exist in memory and never once be durable.
    """
    agent = IdentityManager(
        base_path=str(tmp_path), persona_file=_persona_file(tmp_path)
    )
    store = FakeConfigStore(personality={"name": "seed"}, history={"memories": []})
    await agent.hydrate_from_config_store(store)
    await agent.persist_to_config_store()

    persisted = json.loads(store.updates[-1][1])
    assert IdentityManager.SEED_MARKER in persisted


# --------------------------------------------------------------------------
# one copy, not two
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_does_not_touch_the_tracked_json_once_a_store_is_attached(tmp_path):
    """Two writable copies of an identity means one of them is wrong.

    `app/personality.json` is tracked in git. Writing it at runtime dirtied the
    working tree on every test run and, worse, created a second persona that
    drifts from `agent_configs` with nothing to say which one a boot will use.
    """
    path = tmp_path / "personality.json"
    agent = IdentityManager(base_path=str(tmp_path), persona_file=None)
    await agent.hydrate_from_config_store(FakeConfigStore(personality={"name": "X"}))

    before = path.read_text(encoding="utf-8") if path.exists() else None
    agent.save()
    after = path.read_text(encoding="utf-8") if path.exists() else None
    assert after == before, "the durable store owns this now"


@pytest.mark.asyncio
async def test_a_store_that_fails_to_answer_is_not_treated_as_attached(tmp_path):
    """Otherwise a database down at boot means persisting *nowhere*.

    `save()` skips the JSON files whenever a store is attached. Recording the
    store before it has actually answered means a failed hydration disables the
    file fallback (a store exists) while the store itself cannot be written
    (it does not) — so the agent silently stops persisting anything at all.
    A failed hydration has to degrade to exactly the offline behaviour the
    fallback was kept for.
    """

    class Broken:
        async def get_agent_config(self):
            raise RuntimeError("database is down")

    agent = IdentityManager(base_path=str(tmp_path), persona_file=None)
    await agent.hydrate_from_config_store(Broken())

    assert agent.config_store is None, "an unreachable store is not attached"

    agent.persona.name = "Survived"
    agent._sync_personality_from_profile()
    agent.save()
    written = json.loads((tmp_path / "personality.json").read_text(encoding="utf-8"))
    assert written["name"] == "Survived"


def test_identity_files_never_default_into_the_source_tree(monkeypatch, tmp_path):
    """`app/personality.json` and `app/history.json` are tracked in git.

    `base_path` defaults to the package directory, so anything that saves
    without a durable store writes into the repo. The suite did precisely this
    — `test_subconscious_consolidation` builds a `ReflectionService` with no
    identity manager, and `_consolidate` → `evolve_persona` → `save()` rewrote
    the tracked file on every run.

    Redirecting the default is what stops that. If the override is dropped, the
    working tree silently goes dirty again on every test run, and the next
    person to `git add -A` commits whatever the suite happened to invent.
    """
    from app import config as config_module

    monkeypatch.setattr(
        config_module.config_instance, "IDENTITY_BASE_PATH", str(tmp_path)
    )
    agent = IdentityManager(persona_file=None)

    assert agent.personality_path == str(tmp_path / "personality.json")
    assert agent.history_path == str(tmp_path / "history.json")


def test_save_still_writes_files_when_there_is_no_store(tmp_path):
    """The fallback is the point, not an oversight.

    A deployment with neither Postgres nor the SQLite fallback reachable is
    exactly when refusing to persist anything is worst: the friend would forget
    every restart. Files stay as the last resort.
    """
    agent = IdentityManager(base_path=str(tmp_path), persona_file=None)
    agent.persona.name = "Offline"
    agent._sync_personality_from_profile()
    agent.save()

    written = json.loads((tmp_path / "personality.json").read_text(encoding="utf-8"))
    assert written["name"] == "Offline"


# --------------------------------------------------------------------------
# history.memories reaches a store that can recall it
# --------------------------------------------------------------------------


class FakeMemoryStore:
    def __init__(self):
        self.added = []

    async def add_memory(self, **kwargs):
        self.added.append(kwargs)


def test_a_memory_is_read_from_either_shape():
    """The list has never had an enforced shape.

    `evolve_persona` appends whatever the reflection LLM produced, and older
    seeded files used bare strings. Assuming one shape silently drops the other.
    """
    assert entry_text("a bare string") == "a bare string"
    assert entry_text({"content": "a dict"}) == "a dict"
    assert entry_text({"text": "another key"}) == "another key"
    assert entry_text({"unrelated": "x"}) == ""
    assert entry_text(42) == ""


def test_an_unusable_entry_is_skipped_rather_than_stringified():
    """`"{'a': 1}"` as a remembered fact is worse than remembering nothing."""
    assert pending_entries([{"a": 1}, None, "", "real"], []) == ["real"]


def test_the_same_memory_twice_is_stored_once():
    """Reflection re-noticing something is not a second fact."""
    assert pending_entries(["same", "same"], []) == ["same"]


def test_already_migrated_memories_are_not_re_imported():
    """Idempotence is per-entry, so the list can keep being appended to.

    A single 'migrated' flag would force a choice between duplicating
    everything and never importing what reflection added afterwards.
    """
    already = [fingerprint("old")]
    assert pending_entries(["old", "new"], already) == ["new"]


@pytest.mark.asyncio
async def test_migrated_memories_carry_their_own_text_into_the_store():
    """They have to be retrievable *by content*, not merely present.

    These memories currently reach no reader at all: `evolve_persona` appends to
    `history["memories"]` and nothing reads it back. Migrating them into a table
    without their text intact would swap one unreachable copy for another.
    """
    store = FakeMemoryStore()
    stored = await migrate_history_memories(["she hates coriander"], store)

    assert stored == [fingerprint("she hates coriander")]
    assert store.added[0]["content"] == "she hates coriander"
    assert store.added[0]["source"] == HISTORY_SOURCE


@pytest.mark.asyncio
async def test_one_bad_memory_does_not_abandon_the_rest():
    """A partial migration is strictly better than none."""

    class Flaky(FakeMemoryStore):
        async def add_memory(self, **kwargs):
            if "boom" in kwargs["content"]:
                raise RuntimeError("nope")
            await super().add_memory(**kwargs)

    store = Flaky()
    stored = await migrate_history_memories(["fine", "boom", "also fine"], store)

    assert len(stored) == 2
    assert [m["content"] for m in store.added] == ["fine", "also fine"]


# --------------------------------------------------------------------------
# seeding runs exactly once, whatever the source
# --------------------------------------------------------------------------


def _service(tmp_path, memory_store):
    """A cognitive service whose identity lives in tmp_path.

    `base_path` is mandatory here, not tidiness: the default resolves to the
    real `app/` directory, so a `save()` during the test would write the
    git-tracked `personality.json`.
    """
    from app.cognitive.core import CognitiveService

    return CognitiveService(
        llm_service=None,
        memory_store=memory_store,
        graph_db=None,
        base_path=str(tmp_path),
    )


@pytest.mark.asyncio
async def test_biography_seeding_across_two_boots_stores_each_passage_once(tmp_path):
    """The fingerprint ledger is what makes seeding survivable.

    Neither `seed_biography_once` nor `migrate_history_once` had any test at
    all — the existing biography suite covers the `seed_biography` *function*,
    not the method that records what was stored. If the ledger is not written,
    or not read back, every restart re-seeds the whole documentary: duplicate
    memories, repeated embedding work, and a friend whose past grows a copy of
    itself on each boot.
    """
    bio = tmp_path / "biography.md"
    bio.write_text("## Her sister\n\nThey text every morning.\n", encoding="utf-8")

    store = FakeMemoryStore()
    service = _service(tmp_path, store)

    assert await service.seed_biography_once(bio) == 1
    assert await service.seed_biography_once(bio) == 0, "already seeded"
    assert len(store.added) == 1


@pytest.mark.asyncio
async def test_history_migration_across_two_boots_stores_each_memory_once(tmp_path):
    """Same ledger contract, the other source.

    Reflection keeps appending to `history["memories"]`, so this runs on every
    boot with a list that is mostly already migrated.
    """
    store = FakeMemoryStore()
    service = _service(tmp_path, store)
    service.identity.history["memories"] = ["she hates coriander"]

    assert await service.migrate_history_once() == 1
    assert await service.migrate_history_once() == 0, "already migrated"

    service.identity.history["memories"].append("she sings while cooking")
    assert await service.migrate_history_once() == 1, "new entries still import"
    assert len(store.added) == 2


# --------------------------------------------------------------------------
# reset
# --------------------------------------------------------------------------


class FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    async def fetch(self, query, *args):
        table = "archived_memories" if "archived_memories" in query else "memories"
        return [{"id": i} for i, src in self.rows.get(table, []) if src in args]

    async def execute(self, query, *args):
        self.executed.append((query, args))


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self):
                return pool.conn

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


def _stores(rows):
    conn = FakeConn(rows)
    pool = FakePool(conn)
    memory = SimpleNamespace(pool=pool, is_sqlite=True, qdrant_store=None)
    config = SimpleNamespace(pool=pool)
    return conn, config, memory


@pytest.mark.asyncio
async def test_a_reset_keeps_what_the_user_actually_said():
    """The trade a reset must never make.

    Correcting a typo in a temperament setting cannot cost someone months of
    real conversation. Only file-seeded material is cleared; anything the agent
    was actually told survives, so the friend goes back to their original nature
    but still remembers you.
    """
    conn, config, memory = _stores(
        {
            "memories": [
                ("bio-1", BIOGRAPHY_SOURCE),
                ("said-1", "user"),
                ("hist-1", HISTORY_SOURCE),
            ]
        }
    )
    result = await reset_persona(config, memory)

    assert result["memories_removed"] == 2
    deleted = " ".join(str(args) for _, args in conn.executed)
    assert "bio-1" in deleted and "hist-1" in deleted
    assert "said-1" not in deleted


@pytest.mark.asyncio
async def test_a_reset_clears_the_archive_too():
    """A seeded memory that decayed can be promoted back.

    Clearing only the active tier would let the old persona resurface weeks
    later — the most confusing possible outcome of a reset that reported success.
    """
    _, config, memory = _stores({"archived_memories": [("old-bio", BIOGRAPHY_SOURCE)]})
    result = await reset_persona(config, memory)
    assert result["memories_removed"] == 1


@pytest.mark.asyncio
async def test_a_reset_deletes_the_persona_row_so_the_next_boot_is_a_first_boot():
    """Deleting beats rewriting.

    `_ensure_config_exists` already knows how to seed a missing row from the
    shipped defaults. Re-implementing 'a fresh agent' here would create a second
    definition that can drift from the real one.
    """
    conn, config, memory = _stores({})
    result = await reset_persona(config, memory)

    assert result["persona_cleared"] is True
    assert any("DELETE FROM agent_configs" in q for q, _ in conn.executed)


def test_only_file_seeded_sources_are_resettable():
    """The allow-list is the whole safety property of a reset.

    If `user` ever appeared here, running the script would silently destroy
    every conversation the agent has ever had.
    """
    assert set(SEEDED_SOURCES) == {BIOGRAPHY_SOURCE, HISTORY_SOURCE}
    assert "user" not in SEEDED_SOURCES
