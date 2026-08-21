"""
#155: the backend must promise HSTS to browsers once it is actually running
behind TLS (ENVIRONMENT=production), but never in local/LAN HTTP development,
where advertising HSTS would be a lie the browser then remembers for a year.

The middleware is registered at module import time (`if Config.ENVIRONMENT ==
"production":` at the top level of main.py), so flipping the setting after
import has no effect on an already-built FastAPI app -- these tests reload
`main` under each setting to observe the registration decision itself.
"""

import importlib

from fastapi.testclient import TestClient

from app import config as config_module


def _import_main_with_environment(monkeypatch, environment: str):
    monkeypatch.setattr(config_module.config_instance, "ENVIRONMENT", environment)
    import main

    importlib.reload(main)
    return main


def test_hsts_header_present_in_production(monkeypatch):
    main = _import_main_with_environment(monkeypatch, "production")
    client = TestClient(main.app)

    response = client.get("/")

    assert (
        response.headers.get("strict-transport-security")
        == "max-age=31536000; includeSubDomains"
    )


def test_hsts_header_absent_outside_production(monkeypatch):
    main = _import_main_with_environment(monkeypatch, "development")
    client = TestClient(main.app)

    response = client.get("/")

    assert "strict-transport-security" not in response.headers
