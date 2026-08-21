import logging
from unittest.mock import patch

import pytest

from app.state.conversation_store import ConversationHistoryStore


@pytest.mark.asyncio
async def test_postgres_failure_sets_fallback_flag_and_logs_critical(caplog, tmp_path):
    """H5: a PostgreSQL outage used to fail over to local SQLite with only a
    `logger.warning` and no queryable signal - a prior conversation's history
    (in Postgres) goes silently unreachable, and nothing distinguishes that
    from a fresh install. `used_fallback_storage` gives a health check
    something to report, and the log level makes it hard to miss in
    aggregated logs that filter below CRITICAL/ERROR.
    """
    store = ConversationHistoryStore()
    store.dsn = "postgresql://user:pass@nonexistent-host:5432/db"

    with (
        patch(
            "asyncpg.create_pool",
            side_effect=ConnectionError("could not connect to server"),
        ),
        patch(
            "app.state.sqlite_fallback.SQLitePool",
            return_value=type(
                "FakePool",
                (),
                {
                    "acquire": lambda self: _NullAcquire(),
                },
            )(),
        ),
        caplog.at_level(logging.CRITICAL),
    ):
        await store.initialize()

    assert store.used_fallback_storage is True
    assert any(
        record.levelno >= logging.CRITICAL and "PostgreSQL" in record.message
        for record in caplog.records
    )


class _NullAcquire:
    async def __aenter__(self):
        raise RuntimeError("not needed for this test")

    async def __aexit__(self, *args):
        return False
