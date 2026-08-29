"""
`export_friend.py` / `import_friend.py` (roadmap Phase 4.1) are a backup path:
the whole point is that what comes back out is what went in. Four things are
protection-critical here and get the most scrutiny:

1. `_pg_cast_for` -- picks the explicit `::type` cast for uuid/jsonb/
   timestamptz/vector columns. Get this wrong and `import_friend` writes rows
   Postgres will either reject or silently mis-store (an uncast jsonb string
   lands as plain `text`, a `vector` column takes a value that never actually
   became a vector).
2. The column-name safety check in `_import_postgres_table` -- column names
   come from the archive's own JSONL and get string-interpolated directly into
   an INSERT statement; nothing sanitizes an archive found on disk more than
   this.
3. `_import_identity_and_state`'s `--force` guard -- these are the local files
   a person may have kept building an evolving friend in since the export was
   taken (same shape of near-miss as the Phase 2 wizard's persona-overwrite
   guard). A guard that doesn't actually block would silently erase them.
4. `import_friend`'s `--force` requirement and manifest schema-version check
   -- both must fail *before* the destructive Postgres TRUNCATE runs, not
   after.

Postgres and Neo4j are faked at the connection/session boundary rather than
hit for real, matching this suite's hermetic design (see CLAUDE.md).
"""

import json
import sqlite3
import sys
import tarfile
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config as config_module
from app.state.graph_db import GraphDB as RealGraphDB
from scripts import export_friend as ef
from scripts import import_friend as imf

# ---------------------------------------------------------------------------
# _json_default
# ---------------------------------------------------------------------------


def test_json_default_serializes_datetime_as_isoformat():
    dt = datetime(2026, 8, 28, 12, 0, 0, tzinfo=UTC)
    assert ef._json_default(dt) == dt.isoformat()


def test_json_default_serializes_date_as_isoformat():
    d = date(2026, 8, 28)
    assert ef._json_default(d) == d.isoformat()


def test_json_default_serializes_uuid_as_string():
    u = UUID("12345678-1234-5678-1234-567812345678")
    assert ef._json_default(u) == str(u)


def test_json_default_serializes_decimal_as_float():
    assert ef._json_default(Decimal("0.75")) == 0.75


def test_json_default_serializes_bytes_as_hex():
    assert ef._json_default(b"\x00\xff") == "00ff"


def test_json_default_raises_for_an_unsupported_type():
    class Unsupported:
        pass

    with pytest.raises(TypeError):
        ef._json_default(Unsupported())


# ---------------------------------------------------------------------------
# _pg_cast_for
# ---------------------------------------------------------------------------


def test_pg_cast_for_uuid():
    assert imf._pg_cast_for("uuid", "uuid") == "uuid"


def test_pg_cast_for_jsonb():
    assert imf._pg_cast_for("jsonb", "jsonb") == "jsonb"


def test_pg_cast_for_json():
    assert imf._pg_cast_for("json", "json") == "json"


def test_pg_cast_for_timestamptz():
    assert imf._pg_cast_for("timestamp with time zone", "timestamptz") == "timestamptz"


def test_pg_cast_for_timestamp_without_tz():
    assert imf._pg_cast_for("timestamp without time zone", "timestamp") == "timestamp"


def test_pg_cast_for_vector():
    assert imf._pg_cast_for("USER-DEFINED", "vector") == "vector"


def test_pg_cast_for_halfvec():
    assert imf._pg_cast_for("USER-DEFINED", "halfvec") == "halfvec"


def test_pg_cast_for_plain_scalar_needs_no_cast():
    assert imf._pg_cast_for("double precision", "float8") is None
    assert imf._pg_cast_for("integer", "int4") is None
    assert imf._pg_cast_for("text", "text") is None
    assert imf._pg_cast_for("boolean", "bool") is None


# ---------------------------------------------------------------------------
# SQLite snapshot / restore round trip (real files, no external infra)
# ---------------------------------------------------------------------------


def _make_sqlite_db(path: Path, value: str) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE t (v TEXT)")
    conn.execute("INSERT INTO t (v) VALUES (?)", (value,))
    conn.commit()
    conn.close()


def test_snapshot_sqlite_copies_data_to_a_fresh_file(tmp_path):
    src = tmp_path / "src.db"
    dest = tmp_path / "dest.db"
    _make_sqlite_db(src, "hello")

    assert ef._snapshot_sqlite(str(src), dest) is True
    conn = sqlite3.connect(str(dest))
    rows = conn.execute("SELECT v FROM t").fetchall()
    conn.close()
    assert rows == [("hello",)]


def test_snapshot_sqlite_returns_false_when_source_is_missing(tmp_path):
    dest = tmp_path / "dest.db"
    assert ef._snapshot_sqlite(str(tmp_path / "nope.db"), dest) is False
    assert not dest.exists()


def test_restore_sqlite_round_trips_through_export_and_import(tmp_path):
    original = tmp_path / "original.db"
    snapshot = tmp_path / "snapshot.db"
    restored_dir = tmp_path / "restored"
    restored = restored_dir / "restored.db"
    _make_sqlite_db(original, "round-trip-value")

    assert ef._snapshot_sqlite(str(original), snapshot) is True
    imf._restore_sqlite(snapshot, str(restored))

    conn = sqlite3.connect(str(restored))
    rows = conn.execute("SELECT v FROM t").fetchall()
    conn.close()
    assert rows == [("round-trip-value",)]


# ---------------------------------------------------------------------------
# _export_identity_and_state / _import_identity_and_state
# ---------------------------------------------------------------------------


def _seed_identity_dir(identity_dir: Path) -> None:
    identity_dir.mkdir(parents=True, exist_ok=True)
    (identity_dir / "personality.json").write_text('{"name": "Test"}')
    (identity_dir / "history.json").write_text('{"relationship": "Friend"}')
    _make_sqlite_db(identity_dir / "identity_core.db", "core-value")


# `Config.STATE_CACHE_DB_PATH` is not a declared field -- both scripts read it
# via `getattr(Config, "STATE_CACHE_DB_PATH", None) or "state_cache.db"`,
# exactly like the source code they mirror (`state/agent_state.py`'s own
# `db_path="state_cache.db"` default). A relative path resolves from the
# process's cwd, so these tests control it with `monkeypatch.chdir` rather
# than trying to set a Config field that doesn't exist (pydantic-settings
# rejects `setattr` on an undeclared field outright).


def test_export_identity_and_state_reports_present_files(tmp_path, monkeypatch):
    identity_dir = tmp_path / "identity"
    _seed_identity_dir(identity_dir)
    _make_sqlite_db(tmp_path / "state_cache.db", "state-value")
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        config_module.config_instance, "IDENTITY_BASE_PATH", str(identity_dir)
    )

    out_dir = tmp_path / "export_out"
    out_dir.mkdir()
    present = ef._export_identity_and_state(out_dir)

    assert present == {
        "personality.json": True,
        "history.json": True,
        "identity_core.db": True,
        "state_cache.db": True,
    }
    assert (
        out_dir / "identity_state" / "personality.json"
    ).read_text() == '{"name": "Test"}'
    assert (out_dir / "state_cache.db").exists()


def test_export_identity_and_state_reports_missing_files_without_crashing(
    tmp_path, monkeypatch
):
    empty_identity_dir = tmp_path / "empty_identity"
    empty_cwd = tmp_path / "empty_cwd"
    empty_cwd.mkdir()
    monkeypatch.chdir(empty_cwd)
    monkeypatch.setattr(
        config_module.config_instance, "IDENTITY_BASE_PATH", str(empty_identity_dir)
    )

    out_dir = tmp_path / "export_out"
    out_dir.mkdir()
    present = ef._export_identity_and_state(out_dir)

    assert present == {
        "personality.json": False,
        "history.json": False,
        "identity_core.db": False,
        "state_cache.db": False,
    }


def test_import_identity_and_state_writes_when_destination_is_absent(
    tmp_path, monkeypatch
):
    staging = tmp_path / "staging"
    identity_in = staging / "identity_state"
    _seed_identity_dir(identity_in)
    _make_sqlite_db(staging / "state_cache.db", "state-value")

    dest_identity_dir = tmp_path / "dest_identity"
    dest_cwd = tmp_path / "dest_cwd"
    dest_cwd.mkdir()
    monkeypatch.chdir(dest_cwd)
    monkeypatch.setattr(
        config_module.config_instance, "IDENTITY_BASE_PATH", str(dest_identity_dir)
    )

    written = imf._import_identity_and_state(staging, force=False)

    assert all(written.values())
    assert (dest_identity_dir / "personality.json").exists()
    assert (dest_cwd / "state_cache.db").exists()


def test_import_identity_and_state_refuses_to_overwrite_without_force(
    tmp_path, monkeypatch
):
    staging = tmp_path / "staging"
    identity_in = staging / "identity_state"
    _seed_identity_dir(identity_in)
    (identity_in / "personality.json").write_text('{"name": "Archived"}')

    dest_identity_dir = tmp_path / "dest_identity"
    dest_identity_dir.mkdir()
    # Simulates a friend that kept evolving after the export was taken.
    (dest_identity_dir / "personality.json").write_text('{"name": "StillEvolving"}')
    dest_cwd = tmp_path / "dest_cwd"
    dest_cwd.mkdir()
    monkeypatch.chdir(dest_cwd)

    monkeypatch.setattr(
        config_module.config_instance, "IDENTITY_BASE_PATH", str(dest_identity_dir)
    )

    written = imf._import_identity_and_state(staging, force=False)

    assert written["personality.json"] is False
    assert (
        dest_identity_dir / "personality.json"
    ).read_text() == '{"name": "StillEvolving"}'


def test_import_identity_and_state_overwrites_when_forced(tmp_path, monkeypatch):
    staging = tmp_path / "staging"
    identity_in = staging / "identity_state"
    _seed_identity_dir(identity_in)
    (identity_in / "personality.json").write_text('{"name": "Archived"}')

    dest_identity_dir = tmp_path / "dest_identity"
    dest_identity_dir.mkdir()
    (dest_identity_dir / "personality.json").write_text('{"name": "StillEvolving"}')
    dest_cwd = tmp_path / "dest_cwd"
    dest_cwd.mkdir()
    monkeypatch.chdir(dest_cwd)

    monkeypatch.setattr(
        config_module.config_instance, "IDENTITY_BASE_PATH", str(dest_identity_dir)
    )

    written = imf._import_identity_and_state(staging, force=True)

    assert written["personality.json"] is True
    assert (
        dest_identity_dir / "personality.json"
    ).read_text() == '{"name": "Archived"}'


# ---------------------------------------------------------------------------
# Postgres orchestration, faked at the connection boundary
# ---------------------------------------------------------------------------


class _FakeConn:
    def __init__(self, table_rows=None, column_info=None):
        self.table_rows = table_rows or {}
        self.column_info = column_info or {}
        self.executed = []
        self.closed = False
        self.transaction_entered = False

    class _Transaction:
        def __init__(self, conn):
            self.conn = conn

        async def __aenter__(self):
            self.conn.transaction_entered = True
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def transaction(self):
        return self._Transaction(self)

    async def fetch(self, query, *args):
        if "information_schema.columns" in query:
            table = args[0]
            return [
                {"column_name": c, "data_type": dt, "udt_name": udt}
                for c, dt, udt in self.column_info.get(table, [])
            ]
        table = query.split("FROM", 1)[1].strip()
        return list(self.table_rows.get(table, []))

    async def execute(self, query, *args):
        self.executed.append((query, args))

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_export_postgres_writes_one_jsonl_file_per_table(tmp_path, monkeypatch):
    memory_id = UUID("12345678-1234-5678-1234-567812345678")
    conn = _FakeConn(
        table_rows={
            "memories": [{"id": memory_id, "content": "hi", "importance_score": 0.5}],
            "sessions": [],
        }
    )

    async def _fake_connect(dsn):
        return conn

    monkeypatch.setattr(ef.asyncpg, "connect", _fake_connect, raising=False)

    counts = await ef._export_postgres("postgresql://unused", tmp_path)

    assert counts["memories"] == 1
    assert counts["sessions"] == 0
    lines = (tmp_path / "postgres" / "memories.jsonl").read_text().splitlines()
    assert json.loads(lines[0])["id"] == str(memory_id)
    assert conn.closed is True


@pytest.mark.asyncio
async def test_import_postgres_table_applies_the_right_cast_per_column(tmp_path):
    conn = _FakeConn(
        column_info={
            "memories": [
                ("id", "uuid", "uuid"),
                ("metadata", "jsonb", "jsonb"),
                ("created_at", "timestamp with time zone", "timestamptz"),
                ("importance_score", "double precision", "float8"),
            ]
        }
    )
    row = {
        "id": "12345678-1234-5678-1234-567812345678",
        "metadata": '{"k": "v"}',
        "created_at": "2026-08-28T12:00:00+00:00",
        "importance_score": 0.5,
    }
    path = tmp_path / "memories.jsonl"
    path.write_text(json.dumps(row) + "\n")

    count = await imf._import_postgres_table(conn, "memories", path)

    assert count == 1
    sql, values = conn.executed[0]
    assert "$1::uuid" in sql
    assert "$2::jsonb" in sql
    assert "$3::timestamptz" in sql
    assert "$4::" not in sql  # importance_score needs no cast
    assert values == (
        "12345678-1234-5678-1234-567812345678",
        '{"k": "v"}',
        "2026-08-28T12:00:00+00:00",
        0.5,
    )


@pytest.mark.asyncio
async def test_import_postgres_wraps_wipe_and_rows_in_a_transaction(
    tmp_path, monkeypatch
):
    conn = _FakeConn()

    async def _fake_connect(dsn):
        return conn

    monkeypatch.setattr(imf.asyncpg, "connect", _fake_connect, raising=False)
    await imf._import_postgres("postgresql://unused", tmp_path)

    assert conn.transaction_entered is True


@pytest.mark.asyncio
async def test_import_postgres_table_rejects_an_unsafe_column_name(tmp_path):
    conn = _FakeConn(column_info={"memories": []})
    row = {"id; DROP TABLE memories; --": "value"}
    path = tmp_path / "memories.jsonl"
    path.write_text(json.dumps(row) + "\n")

    with pytest.raises(ValueError):
        await imf._import_postgres_table(conn, "memories", path)
    assert conn.executed == []


@pytest.mark.asyncio
async def test_import_postgres_table_skips_missing_export_file(tmp_path):
    conn = _FakeConn()
    count = await imf._import_postgres_table(
        conn, "memories", tmp_path / "absent.jsonl"
    )
    assert count == 0
    assert conn.executed == []


@pytest.mark.asyncio
async def test_wipe_postgres_truncates_every_table():
    conn = _FakeConn()
    await imf._wipe_postgres(conn)
    assert len(conn.executed) == 1
    sql, _ = conn.executed[0]
    assert sql.startswith("TRUNCATE TABLE")
    for table in imf.POSTGRES_IMPORT_ORDER:
        assert table in sql
    assert "CASCADE" in sql


@pytest.mark.asyncio
async def test_import_friend_refuses_without_force(tmp_path, monkeypatch):
    def _must_not_connect(*args, **kwargs):
        raise AssertionError("must not connect to Postgres without --force")

    monkeypatch.setattr(imf.asyncpg, "connect", _must_not_connect, raising=False)

    with pytest.raises(ValueError):
        await imf.import_friend(tmp_path / "whatever.tar.gz", force=False)


@pytest.mark.asyncio
async def test_import_friend_rejects_a_schema_version_mismatch_before_wiping(
    tmp_path, monkeypatch
):
    archive_dir = tmp_path / "friend_export"
    archive_dir.mkdir()
    (archive_dir / "manifest.json").write_text(json.dumps({"schema_version": 999}))
    archive_path = tmp_path / "bad.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(archive_dir, arcname="friend_export")

    def _must_not_connect(*args, **kwargs):
        raise AssertionError("must not touch Postgres on a schema_version mismatch")

    monkeypatch.setattr(imf.asyncpg, "connect", _must_not_connect, raising=False)
    monkeypatch.setattr(
        config_module.config_instance, "DATABASE_URL", "postgresql://unused"
    )

    with pytest.raises(ValueError):
        await imf.import_friend(archive_path, force=True)


# ---------------------------------------------------------------------------
# Neo4j orchestration, faked at the GraphDB boundary
# ---------------------------------------------------------------------------


async def _aiter(items):
    for item in items:
        yield item


class _FakeTx:
    def __init__(self, log):
        self.log = log

    async def run(self, query, **params):
        self.log.append((query, params))


class _FakeSession:
    def __init__(self, node_records=(), rel_records=(), tx_log=None):
        self.node_records = list(node_records)
        self.rel_records = list(rel_records)
        self.tx_log = tx_log if tx_log is not None else []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def run(self, query, **params):
        if "MATCH (a)-[r]->(b)" in query:
            return _aiter(self.rel_records)
        return _aiter(self.node_records)

    async def execute_write(self, fn, *args):
        return await fn(_FakeTx(self.tx_log), *args)


class _FakeDriver:
    def __init__(self, session):
        self._session = session

    def session(self):
        return self._session


class _FakeGraphDB:
    def __init__(self, node_records=(), rel_records=()):
        self.tx_log: list = []
        self._session = _FakeSession(node_records, rel_records, self.tx_log)
        self.driver = _FakeDriver(self._session)
        self.bootstrapped = False

    async def bootstrap_constraints(self):
        self.bootstrapped = True

    async def close(self):
        pass


def _patch_graphdb(monkeypatch, fake_db: "_FakeGraphDB") -> None:
    """`_import_neo4j`/`_export_neo4j` both do `from app.state.graph_db import
    GraphDB` then use it two ways: `GraphDB()` to construct, and
    `GraphDB._safe_relation(...)` as a class-level validator. A bare
    `lambda: fake_db` satisfies the first and breaks the second (a function
    has no `_safe_relation` attribute) -- this wrapper satisfies both, and
    reuses the *real* `_safe_relation` so the fake can't silently drift from
    what production actually rejects.
    """

    class _Patched:
        _safe_relation = staticmethod(RealGraphDB._safe_relation)

        def __new__(cls):
            return fake_db

    monkeypatch.setattr("app.state.graph_db.GraphDB", _Patched)


@pytest.mark.asyncio
async def test_export_neo4j_writes_nodes_and_relationships(tmp_path, monkeypatch):
    node_records = [
        {"labels": ["Entity"], "props": {"name": "reading"}},
        {"labels": ["Agent"], "props": {"name": "Friend"}},
    ]
    rel_records = [
        {
            "a_labels": ["Agent"],
            "a_props": {"name": "Friend"},
            "b_labels": ["Entity"],
            "b_props": {"name": "reading"},
            "rel_type": "LIKES",
            "rel_props": {"weight": 1},
        }
    ]
    fake_db = _FakeGraphDB(node_records=node_records, rel_records=rel_records)
    _patch_graphdb(monkeypatch, fake_db)

    counts = await ef._export_neo4j(tmp_path)

    assert counts == {"nodes": 2, "relationships": 1}
    node_lines = (tmp_path / "neo4j" / "nodes.jsonl").read_text().splitlines()
    assert json.loads(node_lines[0])["props"]["name"] == "reading"
    rel_lines = (tmp_path / "neo4j" / "relationships.jsonl").read_text().splitlines()
    assert json.loads(rel_lines[0])["rel_type"] == "LIKES"


@pytest.mark.asyncio
async def test_import_neo4j_merges_valid_nodes_and_relationships(tmp_path, monkeypatch):
    staging = tmp_path / "staging"
    graph_dir = staging / "neo4j"
    graph_dir.mkdir(parents=True)
    (graph_dir / "nodes.jsonl").write_text(
        json.dumps({"labels": ["Agent"], "props": {"name": "Friend"}})
        + "\n"
        + json.dumps({"labels": ["Entity"], "props": {"name": "reading"}})
        + "\n"
    )
    (graph_dir / "relationships.jsonl").write_text(
        json.dumps(
            {
                "a_labels": ["Agent"],
                "a_props": {"name": "Friend"},
                "b_labels": ["Entity"],
                "b_props": {"name": "reading"},
                "rel_type": "LIKES",
                "rel_props": {"weight": 1},
            }
        )
        + "\n"
    )

    fake_db = _FakeGraphDB()
    _patch_graphdb(monkeypatch, fake_db)

    counts = await imf._import_neo4j(staging)

    assert counts == {"nodes": 2, "relationships": 1}
    assert fake_db.bootstrapped is True
    # 2 node MERGEs (Agent, Entity) + 1 relationship MATCH...MERGE (which
    # also contains the substring "MERGE") = 3.
    merge_queries = [q for q, _ in fake_db.tx_log if "MERGE" in q]
    assert len(merge_queries) == 3
    node_merges = [q for q in merge_queries if q.startswith("MERGE (n:")]
    rel_merges = [q for q in merge_queries if "MATCH" in q]
    assert len(node_merges) == 2
    assert len(rel_merges) == 1


@pytest.mark.asyncio
async def test_import_neo4j_skips_a_node_with_no_recognized_label(
    tmp_path, monkeypatch
):
    staging = tmp_path / "staging"
    graph_dir = staging / "neo4j"
    graph_dir.mkdir(parents=True)
    (graph_dir / "nodes.jsonl").write_text(
        json.dumps({"labels": ["SomethingElse"], "props": {"name": "x"}}) + "\n"
    )

    fake_db = _FakeGraphDB()
    _patch_graphdb(monkeypatch, fake_db)

    counts = await imf._import_neo4j(staging)

    assert counts["nodes"] == 0
    assert fake_db.tx_log == []


@pytest.mark.asyncio
async def test_import_neo4j_skips_a_relationship_with_an_unsafe_type(
    tmp_path, monkeypatch
):
    staging = tmp_path / "staging"
    graph_dir = staging / "neo4j"
    graph_dir.mkdir(parents=True)
    (graph_dir / "nodes.jsonl").write_text("")
    (graph_dir / "relationships.jsonl").write_text(
        json.dumps(
            {
                "a_labels": ["Agent"],
                "a_props": {"name": "Friend"},
                "b_labels": ["Entity"],
                "b_props": {"name": "reading"},
                "rel_type": "LIKES) DETACH DELETE (n",
                "rel_props": {},
            }
        )
        + "\n"
    )

    fake_db = _FakeGraphDB()
    _patch_graphdb(monkeypatch, fake_db)

    counts = await imf._import_neo4j(staging)

    assert counts["relationships"] == 0
    assert fake_db.tx_log == []
