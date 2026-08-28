"""
`app/api/persona.py` (roadmap Phase 5.1) is the HTTP mirror of
`scripts/create_friend.py`'s wizard. Two things matter most here:

1. `/commit`'s existing-file guard -- the same near-miss shape as the CLI's
   own guard (and the Phase 2 wizard near-miss this repo already hit once):
   a person's evolving friend must not be silently overwritten.
2. `/commit` writes exactly what the client sent back from `/compile`,
   never recompiling -- an LLM is not perfectly reproducible, so committing
   from a freshly recompiled description could save something the person
   never actually saw and approved.

The LLM boundary (`build_llm_client`, `compile_persona`) is mocked -- this
suite is hermetic by design (CLAUDE.md); a live compile is
`scripts/testing/verify_persona_compiler_friction.py`'s job.
"""

import dataclasses
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.persona.compiler import CompiledPersona, Inference, PersonaCompilationError
from app.persona.profile import PersonaProfile
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


def _compiled() -> CompiledPersona:
    return CompiledPersona(
        profile=PersonaProfile(name="Test Friend", traits=["blunt"]),
        biography_markdown="# Test Friend\n\nA test.",
        inferences=[Inference(field="baseline_valence", value=0.1, reason="warmth=0.2")],
        dimensions={"warmth": 0.2},
    )


# ---------------------------------------------------------------------------
# /api/persona/compile
# ---------------------------------------------------------------------------


def test_compile_rejects_empty_description(client):
    r = client.post(
        "/api/persona/compile", json={"description": "   "}, headers=AUTH_HEADERS
    )
    assert r.status_code == 400


def test_compile_rejects_an_unbounded_description(client):
    r = client.post(
        "/api/persona/compile",
        json={"description": "x" * 20_001},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 422


def test_compile_returns_the_full_compiled_payload(client):
    fake_client = AsyncMock()
    fake_client.close = AsyncMock()
    with (
        patch("app.api.persona.build_llm_client", return_value=fake_client),
        patch("app.api.persona.compile_persona", AsyncMock(return_value=_compiled())),
    ):
        r = client.post(
            "/api/persona/compile",
            json={"description": "she's blunt and loyal"},
            headers=AUTH_HEADERS,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["profile"]["name"] == "Test Friend"
    assert body["biography_markdown"] == "# Test Friend\n\nA test."
    assert body["inferences"] == [dataclasses.asdict(Inference("baseline_valence", 0.1, "warmth=0.2"))]
    assert body["dimensions"] == {"warmth": 0.2}
    # Read fresh off IMMUTABLE_CORE on every response, never hardcoded in a
    # client -- the exact drift ground-truth finding 0.2 fixed once already.
    from app.persona.authoring import IMMUTABLE_CORE

    assert body["immutable_core"] == IMMUTABLE_CORE


def test_compile_closes_the_llm_client_even_on_failure(client):
    fake_client = AsyncMock()
    fake_client.close = AsyncMock()
    with (
        patch("app.api.persona.build_llm_client", return_value=fake_client),
        patch(
            "app.api.persona.compile_persona",
            AsyncMock(side_effect=PersonaCompilationError("bad json")),
        ),
    ):
        r = client.post(
            "/api/persona/compile", json={"description": "hi"}, headers=AUTH_HEADERS
        )
    assert r.status_code == 422
    fake_client.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# /api/persona/dry-run-chat
# ---------------------------------------------------------------------------


def test_dry_run_chat_returns_the_llm_reply(client):
    fake_client = AsyncMock()
    fake_client.generate = AsyncMock(return_value="Hey, what's up?")
    fake_client.close = AsyncMock()
    with patch("app.api.persona.build_llm_client", return_value=fake_client):
        r = client.post(
            "/api/persona/dry-run-chat",
            json={"profile": PersonaProfile().model_dump(), "message": "hi"},
            headers=AUTH_HEADERS,
        )
    assert r.status_code == 200
    assert r.json()["reply"] == "Hey, what's up?"


# ---------------------------------------------------------------------------
# /api/persona/commit
# ---------------------------------------------------------------------------


def _commit_body(**overrides):
    body = {
        "profile": PersonaProfile(name="Test Friend").model_dump(),
        "biography_markdown": "# Test Friend",
        "force": False,
    }
    body.update(overrides)
    return body


def test_commit_refuses_an_existing_persona_file_without_force(client, tmp_path, monkeypatch):
    import app.api.persona as persona_module

    persona_path = tmp_path / "persona.toml"
    persona_path.write_text("name = \"Already here\"\n")
    monkeypatch.setattr(persona_module, "PERSONA_PATH", persona_path)
    monkeypatch.setattr(persona_module, "BIOGRAPHY_PATH", tmp_path / "biography.md")
    monkeypatch.setattr(persona_module, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(persona_module, "REPO_ROOT", tmp_path)

    r = client.post("/api/persona/commit", json=_commit_body(), headers=AUTH_HEADERS)

    assert r.status_code == 409
    assert persona_path.read_text() == "name = \"Already here\"\n"


def test_commit_writes_persona_and_biography_when_absent(client, tmp_path, monkeypatch):
    import app.api.persona as persona_module

    persona_path = tmp_path / "personal" / "persona.toml"
    biography_path = tmp_path / "personal" / "biography.md"
    env_path = tmp_path / ".env"
    env_path.write_text("")
    monkeypatch.setattr(persona_module, "PERSONA_PATH", persona_path)
    monkeypatch.setattr(persona_module, "BIOGRAPHY_PATH", biography_path)
    monkeypatch.setattr(persona_module, "ENV_PATH", env_path)
    monkeypatch.setattr(persona_module, "REPO_ROOT", tmp_path)

    r = client.post(
        "/api/persona/commit",
        json=_commit_body(biography_markdown="# Test Friend\n\nBio."),
        headers=AUTH_HEADERS,
    )

    assert r.status_code == 200
    assert persona_path.exists()
    assert 'name = "Test Friend"' in persona_path.read_text()
    assert biography_path.read_text() == "# Test Friend\n\nBio."
    assert "PERSONA_PROFILE_PATH" in env_path.read_text()


def test_commit_overwrites_when_forced(client, tmp_path, monkeypatch):
    import app.api.persona as persona_module

    persona_path = tmp_path / "persona.toml"
    persona_path.write_text("name = \"Old Friend\"\n")
    biography_path = tmp_path / "biography.md"
    env_path = tmp_path / ".env"
    env_path.write_text("")
    monkeypatch.setattr(persona_module, "PERSONA_PATH", persona_path)
    monkeypatch.setattr(persona_module, "BIOGRAPHY_PATH", biography_path)
    monkeypatch.setattr(persona_module, "ENV_PATH", env_path)
    monkeypatch.setattr(persona_module, "REPO_ROOT", tmp_path)

    r = client.post(
        "/api/persona/commit", json=_commit_body(force=True), headers=AUTH_HEADERS
    )

    assert r.status_code == 200
    assert 'name = "Test Friend"' in persona_path.read_text()
