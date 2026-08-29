"""
Set-membership predicates across the two SQL backends.

`memory_store.py` carries a Postgres branch and a SQLite branch for nearly every
query. Most of those differ for real reasons. A handful differed only in how the
dialect spells `IN`, and that handful is what `_in_predicate` absorbs.

These tests pin both dialects explicitly rather than testing "whatever the
current backend is" — a helper that silently emits SQLite syntax to Postgres
fails at the database, far from the code that chose it.
"""

import sqlite3
from types import SimpleNamespace

import pytest

from app.state.memory_store import MemoryStore


def _store(is_sqlite: bool) -> MemoryStore:
    """A store forced onto one backend.

    `is_sqlite` is a read-only property that inspects the pool (A5), so the
    backend is selected by giving the pool the right shape rather than by
    assigning to it — assignment raises, which is the point of the property.
    """
    store = object.__new__(MemoryStore)
    conn = sqlite3.connect(":memory:") if is_sqlite else object()
    store.pool = SimpleNamespace(connection=SimpleNamespace(conn=conn))
    assert store.is_sqlite is is_sqlite
    return store


def test_sqlite_cannot_be_given_a_postgres_array_parameter():
    """SQLite has no array parameter; it needs `IN (?,?,?)`."""
    where, args = _store(True)._in_predicate("id", ["a", "b", "c"])

    assert where == "id IN (?,?,?)"
    assert args == ["a", "b", "c"]


def test_postgres_is_not_flattened_to_one_placeholder_per_value():
    """`= ANY($1)` passes the whole list as one argument.

    Flattening Postgres to N placeholders would also work, which is exactly why
    this is asserted: it would be an easy and invisible regression, and it
    discards the array form the planner handles better.
    """
    where, args = _store(False)._in_predicate("id", ["a", "b", "c"])

    assert where == "id = ANY($1)"
    assert args == [["a", "b", "c"]]


def test_a_hardcoded_parameter_index_would_bind_the_wrong_argument():
    """The predicate is rarely the first parameter in a real query.

    Hardcoding `$1` would silently bind against whatever argument happened to be
    first — a query that runs and returns the wrong rows, which is worse than
    one that errors.
    """
    where, _ = _store(False)._in_predicate("content", ["x"], param_index=4)
    assert where == "content = ANY($4)"


@pytest.mark.parametrize("backend", [True, False])
def test_a_hardcoded_column_name_would_query_the_wrong_field(backend):
    """Both call sites use a different column, so it cannot be hardcoded."""
    where, _ = _store(backend)._in_predicate("content", ["x"])
    assert where.startswith("content ")


def test_a_one_element_list_does_not_emit_broken_syntax():
    """The one-element case is the common one for a targeted lookup.

    `",".join("?" * 1)` is a place where a plausible-looking implementation
    yields `""` or `"?,"` instead of `"?"`.
    """
    assert _store(True)._in_predicate("id", ["only"])[0] == "id IN (?)"


class _CapturingConn:
    def __init__(self):
        self.sql = None
        self.args = None

    async def execute(self, sql, *args):
        self.sql = sql
        self.args = args

    async def fetch(self, sql, *args):
        self.sql = sql
        self.args = args
        return []


def _pool_returning(conn, is_sqlite: bool):
    """A pool that both hands out `conn` and still answers `is_sqlite`.

    The backend is read off `pool.connection.conn` (A5), so a pool built only to
    capture SQL would silently flip the store to Postgres — which is how the
    first version of this test failed while the code was correct.
    """

    class _Ctx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *exc):
            return False

    backing = sqlite3.connect(":memory:") if is_sqlite else object()
    return SimpleNamespace(
        acquire=lambda: _Ctx(),
        connection=SimpleNamespace(conn=backing),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "is_sqlite,expected_literal",
    [(True, "consolidated = 1"), (False, "consolidated = TRUE")],
)
async def test_a_shared_boolean_literal_would_break_postgres(
    is_sqlite, expected_literal
):
    """Postgres will not accept the integer `1` for a boolean column.

    This is the one dialect literal left inline beside the shared predicate, so
    it is the one most likely to be "simplified" into a single spelling later.
    Doing so fails at the database rather than in the code that chose it, and
    only on the backend that is not being run locally.

    Added because a mutation collapsing this to `"1"` survived the first version
    of these tests: the predicate was covered and the literal beside it was not.
    """
    store = _store(is_sqlite)
    conn = _CapturingConn()
    store.pool = _pool_returning(conn, is_sqlite)
    assert store.is_sqlite is is_sqlite  # the swap must not change the backend

    await MemoryStore.mark_episodes_consolidated(store, ["m1", "m2"])

    assert expected_literal in conn.sql


def test_a_collapsed_branch_would_send_one_dialect_the_wrong_sql():
    """A guard against the helper collapsing to one branch.

    If a refactor made `is_sqlite` always false (or the branch unreachable),
    every test above that checks a single backend would still pass while the
    other dialect silently received the wrong SQL.
    """
    sqlite_where, _ = _store(True)._in_predicate("id", ["a", "b"])
    pg_where, _ = _store(False)._in_predicate("id", ["a", "b"])

    assert sqlite_where != pg_where
