import asyncio
import sqlite3

from app.state.sqlite_fallback import SQLiteConnection


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
