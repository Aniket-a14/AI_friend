from unittest.mock import patch

import pytest

from app.state.conversation_store import ConversationHistoryStore


@pytest.mark.asyncio
async def test_strict_storage_raises_instead_of_falling_back(monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(
        config_module.config_instance, "ORGANISM_MODE_STRICT_STORAGE", True
    )
    store = ConversationHistoryStore()
    store.dsn = "postgresql://user:pass@unavailable/db"

    with patch(
        "asyncpg.create_pool",
        side_effect=ConnectionError("database unavailable"),
    ):
        with pytest.raises(
            RuntimeError, match="Strict storage mode forbids falling back"
        ):
            await store.initialize()

    assert store.used_fallback_storage is True
    assert store.pool is None

