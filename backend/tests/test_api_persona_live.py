"""`GET /api/persona/live` (roadmap Phase 5.2's settings surface) exists
because `personal/persona.toml` is a first-boot-only seed --
`app/persona/authoring.py`'s module docstring: "read once, then never
again." A settings page reading the seed file back would show what was
*written* at creation, not who the friend has *become*; this endpoint reads
the same durable-store path `scripts/show_persona.py` does instead.
"""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app

AUTH_HEADERS = {"x-backend-key": "test-key"}


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    from app import config as config_module

    monkeypatch.setattr(config_module.config_instance, "LAN_ONLY", False)
    monkeypatch.setattr(config_module.config_instance, "BACKEND_ACCESS_KEY", "test-key")


@pytest.fixture
def client():
    return TestClient(app)


class _FakeConfigStore:
    """The durable store, with just the surface `IdentityManager` uses --
    matches `tests/test_persona_storage.py`'s `FakeConfigStore` shape."""

    def __init__(self, personality=None, history=None):
        self.pool = None
        self._personality = json.dumps(personality or {})
        self._history = json.dumps(history or {})

    async def initialize(self):
        self.pool = object()

    async def get_agent_config(self):
        return {
            "personality": self._personality,
            "history": self._history,
            "evolved_learnings": "",
        }

    async def close(self):
        pass


class _BrokenConfigStore:
    """`pool` stays `None` (no database reachable), but -- unlike a store
    that's simply absent -- `get_agent_config` is real and would happily
    answer if `hydrate_from_config_store` were ever called against it. That
    makes this fixture only pass through the `store.pool is None` guard
    specifically: a mutation that deleted just that guard would otherwise be
    invisible, since `identity.config_store is None` also produces a 503 for
    a store `hydrate_from_config_store` never touches at all."""

    def __init__(self):
        self.pool = None

    async def initialize(self):
        pass  # self.pool stays None: no database reachable

    async def get_agent_config(self):
        return {"personality": "{}", "history": "{}", "evolved_learnings": ""}

    async def close(self):
        pass


def test_returns_503_when_no_database_is_reachable(client):
    with patch(
        "app.state.conversation_store.ConversationHistoryStore", _BrokenConfigStore
    ):
        r = client.get("/api/persona/live", headers=AUTH_HEADERS)
    assert r.status_code == 503


def test_returns_the_hydrated_persona_not_the_seed_file(client):
    store = _FakeConfigStore(
        personality={
            "name": "Hydrated Name",
            "core_personality": {"traits": ["dry"], "immutable": {"base_tone": "Blunt"}},
        },
        history={"relationship": "Best friend", "persona_seeded_at": "2026-01-01T00:00:00"},
    )

    def _factory():
        return store

    with patch(
        "app.state.conversation_store.ConversationHistoryStore", _factory
    ):
        r = client.get("/api/persona/live", headers=AUTH_HEADERS)

    assert r.status_code == 200
    body = r.json()
    assert body["persona"]["name"] == "Hydrated Name"
    assert body["relationship"] == "Best friend"
    assert body["seeded_from_file"] == "2026-01-01T00:00:00"
    # The safety core is always the code constant, per PersonaProfile.immutable
    # -- never something a hydrated file could have supplied or overridden.
    assert body["immutable_core"]["values"] == ["Honesty", "Privacy"]


def test_immutable_core_cannot_be_smuggled_in_through_hydration(client):
    """`core_personality.immutable` in a hydrated personality blob is exactly
    the path `_reject_immutable_overrides`/`strip_immutable` exist to close
    for the file-seed case -- confirm the live-read endpoint doesn't reopen
    it by trusting IdentityManager.immutable_core over anything hydrated."""
    store = _FakeConfigStore(
        personality={
            "name": "Attempted Escape",
            "core_personality": {
                "immutable": {"values": ["Whatever I want"]},
            },
        },
    )

    with patch("app.state.conversation_store.ConversationHistoryStore", lambda: store):
        r = client.get("/api/persona/live", headers=AUTH_HEADERS)

    assert r.status_code == 200
    assert r.json()["immutable_core"]["values"] == ["Honesty", "Privacy"]
