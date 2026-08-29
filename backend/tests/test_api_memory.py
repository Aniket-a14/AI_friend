"""
`app/api/memory.py` (roadmap Phase 5.1) is a read-only browse endpoint, but
`sort_by` is string-interpolated directly into the ORDER BY clause -- there
is no bind-parameter form for a column name -- so the allowlist check is the
one thing standing between a query string and arbitrary SQL there. asyncpg
is faked at the connection boundary, matching this suite's hermetic design
and the same pattern `tests/test_export_import_friend.py` already uses.
"""

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
    monkeypatch.setattr(
        config_module.config_instance, "DATABASE_URL", "postgresql://unused"
    )


@pytest.fixture
def client():
    return TestClient(app)


class _FakeConn:
    def __init__(self, rows, total):
        self.rows = rows
        self.total = total
        self.fetch_calls = []

    async def fetch(self, query, *args):
        self.fetch_calls.append((query, args))
        return self.rows

    async def fetchval(self, query):
        return self.total

    async def close(self):
        pass


def test_rejects_an_unrecognized_sort_column(client):
    r = client.get("/api/memory/recent?sort_by=nope", headers=AUTH_HEADERS)
    assert r.status_code == 400


def test_rejects_a_sort_column_that_is_not_on_the_allowlist_even_if_it_looks_like_sql(
    client,
):
    # The allowlist is what stands between this query string and the ORDER
    # BY clause -- there is no bind-parameter form for a column name.
    r = client.get(
        "/api/memory/recent?sort_by=created_at%3B%20DROP%20TABLE%20memories%3B%20--",
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 400


def test_returns_503_when_database_url_is_unset(client, monkeypatch):
    from app import config as config_module

    monkeypatch.setattr(config_module.config_instance, "DATABASE_URL", None)
    r = client.get("/api/memory/recent", headers=AUTH_HEADERS)
    assert r.status_code == 503


def test_returns_503_when_the_database_is_unreachable(client):
    async def _refused(dsn):
        raise OSError("Connect call failed")

    with patch("app.api.memory.asyncpg.connect", _refused, create=True):
        r = client.get("/api/memory/recent", headers=AUTH_HEADERS)
    assert r.status_code == 503


def test_returns_recent_memories_and_the_total_count(client):
    fake_conn = _FakeConn(
        rows=[{"id": "1", "content": "hi", "importance_score": 0.5}], total=42
    )

    async def _connect(dsn):
        return fake_conn

    with patch("app.api.memory.asyncpg.connect", _connect, create=True):
        r = client.get("/api/memory/recent?limit=5&offset=10", headers=AUTH_HEADERS)

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 42
    assert body["limit"] == 5
    assert body["offset"] == 10
    assert body["memories"] == [{"id": "1", "content": "hi", "importance_score": 0.5}]
    query, args = fake_conn.fetch_calls[0]
    assert "created_at DESC" in query
    assert args == (5, 10)
