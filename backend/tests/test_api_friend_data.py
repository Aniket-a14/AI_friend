"""
`app/api/friend_data.py` (roadmap Phase 4.1 + 5.1). The one thing that
matters most: `/import` must refuse without `force=true` *before* calling
`import_friend` at all -- that function TRUNCATEs the Postgres tables, so
this check is the only thing standing between an unauthenticated-by-intent
form field and a destructive wipe.
"""

from unittest.mock import AsyncMock, patch

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


# ---------------------------------------------------------------------------
# /api/friend/export
# ---------------------------------------------------------------------------


def test_export_returns_the_archive_as_a_download(client, tmp_path):
    async def _fake_export(out_path, *, skip_neo4j=False):
        out_path.write_bytes(b"fake archive bytes")

    with patch("app.api.friend_data.export_friend", _fake_export):
        r = client.post("/api/friend/export", headers=AUTH_HEADERS)

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/gzip"
    assert r.content == b"fake archive bytes"


def test_export_returns_500_and_cleans_up_on_failure(client):
    async def _fake_export(out_path, *, skip_neo4j=False):
        raise RuntimeError("DATABASE_URL is not set")

    with patch("app.api.friend_data.export_friend", _fake_export):
        r = client.post("/api/friend/export", headers=AUTH_HEADERS)

    assert r.status_code == 500


# ---------------------------------------------------------------------------
# /api/friend/import
# ---------------------------------------------------------------------------


def test_import_refuses_without_force_and_never_calls_import_friend(client):
    with patch("app.api.friend_data.import_friend", AsyncMock()) as mock_import:
        r = client.post(
            "/api/friend/import",
            files={"file": ("f.tar.gz", b"fake", "application/gzip")},
            headers=AUTH_HEADERS,
        )

    assert r.status_code == 400
    mock_import.assert_not_called()


def test_import_calls_import_friend_when_forced(client):
    mock_import = AsyncMock()
    with patch("app.api.friend_data.import_friend", mock_import):
        r = client.post(
            "/api/friend/import",
            files={"file": ("f.tar.gz", b"fake archive", "application/gzip")},
            data={"force": "true"},
            headers=AUTH_HEADERS,
        )

    assert r.status_code == 200
    assert r.json() == {"status": "imported"}
    mock_import.assert_awaited_once()
    _, kwargs = mock_import.call_args
    assert kwargs["force"] is True


def test_import_returns_500_when_import_friend_raises(client):
    async def _fake_import(archive_path, *, force, skip_neo4j=False):
        raise ValueError("Archive schema_version mismatch")

    with patch("app.api.friend_data.import_friend", _fake_import):
        r = client.post(
            "/api/friend/import",
            files={"file": ("f.tar.gz", b"fake", "application/gzip")},
            data={"force": "true"},
            headers=AUTH_HEADERS,
        )

    assert r.status_code == 500


def test_import_rejects_an_oversized_archive_before_calling_import(client, monkeypatch):
    import app.api.friend_data as friend_data_module

    monkeypatch.setattr(friend_data_module, "MAX_IMPORT_ARCHIVE_BYTES", 4)
    with patch("app.api.friend_data.import_friend", AsyncMock()) as mock_import:
        r = client.post(
            "/api/friend/import",
            files={"file": ("f.tar.gz", b"12345", "application/gzip")},
            data={"force": "true"},
            headers=AUTH_HEADERS,
        )

    assert r.status_code == 413
    mock_import.assert_not_called()
