"""
P1-6: /health must surface the emergency-only SQLite fallback so it stops
being invisible - runtime_bootstrap.py writes a sentinel file from a
different process (brain_agent), and /health (main.py's own process) reads
it back.
"""

import importlib
import json

from fastapi.testclient import TestClient

from app import config as config_module


def _import_main(monkeypatch, sentinel_path):
    monkeypatch.setattr(
        config_module.config_instance, "SQLITE_FALLBACK_HEALTH_FILE", str(sentinel_path)
    )
    import main

    importlib.reload(main)
    # /health carries the app-wide require_lan_client dependency (LAN_ONLY
    # defaults True); TestClient's synthetic host isn't a real IP, so it
    # fails that check with 403 unless overridden - unrelated to what this
    # test is actually checking.
    main.app.dependency_overrides[main.require_lan_client] = lambda: None
    return main


def test_health_reports_degraded_when_sentinel_present(tmp_path, monkeypatch):
    sentinel = tmp_path / "sqlite_fallback_active"
    sentinel.write_text(
        json.dumps({"reason": "PostgreSQL connection failed: timeout", "timestamp": 0.0})
    )

    main = _import_main(monkeypatch, sentinel)
    client = TestClient(main.app)

    response = client.get("/health")

    body = response.json()
    assert body["degraded"] is True
    assert body["degraded_reason"] == "PostgreSQL connection failed: timeout"


def test_health_does_not_report_degraded_when_sentinel_absent(tmp_path, monkeypatch):
    sentinel = tmp_path / "does_not_exist"

    main = _import_main(monkeypatch, sentinel)
    client = TestClient(main.app)

    response = client.get("/health")

    body = response.json()
    assert "degraded" not in body
    assert body["status"] == "healthy"


def test_health_tolerates_a_corrupt_sentinel_file(tmp_path, monkeypatch):
    """A malformed sentinel (partial write, disk full mid-write) must not
    take /health itself down."""
    sentinel = tmp_path / "sqlite_fallback_active"
    sentinel.write_text("not valid json{{{")

    main = _import_main(monkeypatch, sentinel)
    client = TestClient(main.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert "degraded" not in response.json()
