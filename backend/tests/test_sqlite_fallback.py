import asyncio
import sqlite3
import time
from unittest.mock import MagicMock

from app.state.memory_store import MemoryStore
from app.state.sqlite_fallback import SQLiteConnection, SQLitePool


def test_update_returning_persists_after_reconnect(tmp_path):
    """A plain `UPDATE ... RETURNING` write must survive a reconnect.

    `fetchrow`/`fetch` run `RETURNING` statements, which sqlite3 opens an
    implicit transaction for just like any other DML. Without an explicit
    commit the write sits uncommitted and is lost when the connection
    (re)opens - which is exactly what happens on process restart.
    """
    db_path = str(tmp_path / "fallback.db")
    conn = SQLiteConnection(db_path)
    asyncio.run(conn.execute("INSERT INTO sessions (id) VALUES ($1)", "s1"))

    asyncio.run(
        conn.fetchrow(
            "UPDATE sessions SET trust_benevolence = $1 WHERE id = $2 RETURNING id",
            0.9,
            "s1",
        )
    )

    # Simulate a fresh process picking the file back up.
    reopened = sqlite3.connect(db_path)
    row = reopened.execute(
        "SELECT trust_benevolence FROM sessions WHERE id = 's1'"
    ).fetchone()
    reopened.close()

    assert row[0] == 0.9


def test_fetchval_on_mutating_returning_statement_persists(tmp_path):
    """`fetchval` never committed at all, unlike `fetch`/`fetchrow`, so an
    `UPDATE ... RETURNING <col>` read through it (a normal way to read back a
    single updated value) ran successfully and then silently lost the write
    on reconnect - regardless of the query's keyword prefix.
    """
    db_path = str(tmp_path / "fallback.db")
    conn = SQLiteConnection(db_path)
    asyncio.run(conn.execute("INSERT INTO sessions (id) VALUES ($1)", "s1"))

    result = asyncio.run(
        conn.fetchval(
            "UPDATE sessions SET trust_competence = $1 WHERE id = $2 RETURNING trust_competence",
            0.42,
            "s1",
        )
    )
    assert result == 0.42

    reopened = sqlite3.connect(db_path)
    row = reopened.execute(
        "SELECT trust_competence FROM sessions WHERE id = 's1'"
    ).fetchone()
    reopened.close()

    assert row[0] == 0.42


async def test_execute_does_not_block_the_event_loop(tmp_path):
    """P2-6 (M2-P3): `SQLiteConnection`'s methods were `async def` with no
    `await` inside them -- coroutines that never yield. Because every agent
    in this mesh runs one asyncio loop, a slow SQLite call used to stall the
    NATS client and every other in-flight cognitive turn for its full
    duration, not just the caller. This proves `execute()` now genuinely
    yields: a concurrent task keeps making progress while a (deliberately
    slowed) query runs on its own worker thread.
    """
    db_path = str(tmp_path / "yield.db")
    conn = SQLiteConnection(db_path)

    real_sync_execute = conn._sync_execute

    def slow_sync_execute(query, args):
        time.sleep(0.2)
        return real_sync_execute(query, args)

    conn._sync_execute = slow_sync_execute

    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0.01)

    ticker_task = asyncio.create_task(ticker())
    await conn.execute("INSERT INTO sessions (id) VALUES ($1)", "s1")
    ticker_task.cancel()

    # ~0.2s of blocking sleep against a 0.01s tick interval. A genuinely
    # blocked loop lets this advance zero or one times regardless of how
    # long the sleep runs, since nothing can service it until the single
    # thread that's blocking returns.
    assert ticks >= 10


async def _seed_row(conn, *, id_, minutes_ago):
    """Insert one `memories` row with a distinct, ordered `last_recalled_at`."""
    await conn.execute(
        "INSERT INTO memories "
        "(id, content, raw_content, wing, embedding, last_recalled_at) "
        "VALUES ($1, $2, $3, $4, $5, datetime('now', $6))",
        id_,
        f"memory {id_}",
        f"memory {id_}",
        "personal",
        "[0.1,0.1]",
        f"-{minutes_ago} minutes",
    )


def test_sqlite_candidate_fetch_does_not_scan_the_whole_table():
    """P2-6 (M2-P3): `SELECT * FROM memories WHERE wing = ?` had no LIMIT at
    all, unlike its Postgres sibling (`_fetch_postgres_candidates`, which
    already receives `candidate_limit`). This seeds more rows than the
    requested limit and checks the cap is actually respected, and that the
    most-recently-recalled rows are the ones kept rather than an arbitrary
    slice.
    """
    pool = SQLitePool(":memory:")
    store = MemoryStore(pool, MagicMock())
    store.qdrant_store.client = None

    async def run():
        async with pool.acquire() as conn:
            # Oldest first: id "m0" is the most recently recalled (0 minutes
            # ago), "m4" the least (4 minutes ago).
            for i in range(5):
                await _seed_row(conn, id_=f"m{i}", minutes_ago=i)

            raw_candidates, _now_ts = await store._fetch_sqlite_candidates(
                conn,
                query_vector=[0.1, 0.1],
                wing="personal",
                room=None,
                excluded=set(),
                threshold=-999.0,
                current_valence=0.0,
                current_arousal=0.5,
                current_cortisol=0.0,
                current_time=None,
                candidate_limit=3,
            )
            return raw_candidates

    raw_candidates = asyncio.run(run())

    assert len(raw_candidates) == 3
    returned_ids = {c["id"] for c in raw_candidates}
    assert returned_ids == {"m0", "m1", "m2"}
