"""P4-1 -- IdentityCoreStore was a complete, tested Tier-1 SQLite cache with
its own `cache.sync` invalidation broadcast that nothing in app/ ever
constructed. `BaseAgent` both publishes and subscribes to `cache.sync`
(agents/base.py) for exactly this store, so the channel was live on one end
and dead on the other. `IdentityManager` now constructs one and mirrors the
immutable core into it on every refresh.
"""

import asyncio

import pytest

from app.cognitive.identity import IdentityManager
from app.persona.profile import IMMUTABLE_CORE
from app.state.identity_core_store import IdentityCoreStore


def test_seed_default_identity_matches_immutable_core():
    """`_seed_default_identity`'s literal used to say ["Honesty", "Privacy",
    "Curiosity"] while the real IMMUTABLE_CORE says ["Honesty", "Privacy"] --
    a copy that could silently drift from the actual safety core. It now
    reads IMMUTABLE_CORE directly, so this seed can no longer disagree with
    it."""
    store = IdentityCoreStore(db_path=":memory:")

    seeded = store.get_identity()

    assert seeded["values"] == IMMUTABLE_CORE["values"]
    assert seeded["boundaries"] == IMMUTABLE_CORE["boundaries"]


def test_identity_manager_constructs_a_real_identity_core_store(tmp_path):
    """Before the fix, nothing in app/ ever called `IdentityCoreStore()` --
    the class existed, compiled, and had its own tests, but was dead code in
    every running process."""
    manager = IdentityManager(base_path=str(tmp_path), persona_file=None)

    assert manager.identity_core is not None
    stored = manager.identity_core.get_identity()
    assert stored, "IdentityCoreStore's cache must be populated, not empty"
    assert stored["boundaries"] == manager.immutable_core["boundaries"]
    assert stored["base_tone"] == manager.immutable_core["base_tone"]


def test_refresh_mirrors_the_current_immutable_core_into_the_cache(tmp_path):
    """_refresh_immutable_core recomputes self.immutable_core from
    IMMUTABLE_CORE + the persona's base_tone; the Tier-1 cache must reflect
    whatever that computation currently says, not a stale snapshot from
    construction."""
    manager = IdentityManager(base_path=str(tmp_path), persona_file=None)

    manager.persona.base_tone = "A completely different tone for this test"
    manager._refresh_immutable_core()

    stored = manager.identity_core.get_identity()
    assert stored["base_tone"] == "A completely different tone for this test"


@pytest.mark.asyncio
async def test_publish_cb_is_wired_through_to_the_cache_sync_broadcast(tmp_path):
    """The whole point of constructing the store is that its `cache.sync`
    broadcast becomes real -- BaseAgent already listens for it
    (_on_cache_sync_received). Without publish_cb reaching IdentityCoreStore,
    a change on one process would never invalidate another's local cache.

    `update_identity`'s broadcast is fire-and-forget (spawn_background), so
    this needs a running event loop and a yield after the refresh for the
    scheduled task to actually execute.
    """
    published = []

    async def fake_publish_cb(subject, data):
        published.append((subject, data))

    manager = IdentityManager(
        base_path=str(tmp_path), persona_file=None, publish_cb=fake_publish_cb
    )
    await asyncio.sleep(0)  # let the constructor-time broadcast run
    published.clear()

    manager.persona.base_tone = "Another tone, to trigger a second broadcast"
    manager._refresh_immutable_core()
    await asyncio.sleep(0)  # let the spawned broadcast task actually run

    cache_sync_calls = [p for p in published if p[0] == "cache.sync"]
    assert len(cache_sync_calls) == 1, (
        "a real identity change must broadcast exactly one cache.sync "
        "invalidation for other processes to pick up"
    )
    assert cache_sync_calls[0][1]["store"] == "identity_core"
    assert cache_sync_calls[0][1]["action"] == "invalidate"


def test_broken_identity_core_storage_degrades_instead_of_crashing_init(monkeypatch):
    """IdentityManager must still produce a usable persona even if the
    Tier-1 cache's own storage cannot be opened (e.g. base_path exists only
    in a test's mocked open() and was never created as a real directory on
    disk, which SQLite still needs)."""
    manager = IdentityManager(base_path="/definitely/not/a/real/directory", persona_file=None)

    # Must not have raised, and must still have a usable in-memory fallback.
    assert manager.identity_core is not None
    assert manager.immutable_core["boundaries"]
    stored = manager.identity_core.get_identity()
    assert stored, "the in-memory fallback must still be populated"
