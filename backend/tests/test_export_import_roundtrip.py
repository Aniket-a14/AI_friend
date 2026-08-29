import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config as config_module
from scripts import export_friend as ef
from scripts import import_friend as imf


def _query_sqlite_db(path: Path, query: str) -> list:
    conn = sqlite3.connect(str(path))
    rows = conn.execute(query).fetchall()
    conn.close()
    return rows


def test_export_import_sqlite_roundtrip(tmp_path, monkeypatch):
    """Validates the identity & state stores export/import cycle end-to-end using SQLite only."""
    # 1. Setup and Seed
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    identity_dir = base_dir / ".identity_state"
    identity_dir.mkdir()

    # The config and paths resolve relative to cwd in the actual scripts for cache db
    monkeypatch.chdir(base_dir)
    monkeypatch.setattr(
        config_module.config_instance, "IDENTITY_BASE_PATH", str(identity_dir)
    )

    personality_path = identity_dir / "personality.json"
    history_path = identity_dir / "history.json"
    identity_db_path = identity_dir / "identity_core.db"
    state_db_path = base_dir / "state_cache.db"

    personality_path.write_text(
        json.dumps({"name": "Test Persona", "traits": ["kind"]})
    )
    history_path.write_text(json.dumps({"seeded_at": "2023-01-01", "interactions": 10}))

    # Seed identity_core.db
    conn = sqlite3.connect(str(identity_db_path))
    conn.execute(
        "CREATE TABLE identity_core (id INTEGER PRIMARY KEY, key TEXT, value TEXT)"
    )
    conn.executemany(
        "INSERT INTO identity_core (key, value) VALUES (?, ?)",
        [("core_belief", "helpful"), ("core_memory", "birth")],
    )
    conn.commit()
    conn.close()

    # Seed state_cache.db
    conn = sqlite3.connect(str(state_db_path))
    conn.executescript("""
        CREATE TABLE agent_state (id INTEGER PRIMARY KEY, affect TEXT);
        CREATE TABLE adaptive_weights (id INTEGER PRIMARY KEY, weight REAL);
    """)
    conn.executemany(
        "INSERT INTO agent_state (affect) VALUES (?)", [("happy",), ("curious",)]
    )
    conn.executemany(
        "INSERT INTO adaptive_weights (weight) VALUES (?)", [(0.5,), (0.9,)]
    )
    conn.commit()
    conn.close()

    # 2. Export
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    export_result = ef._export_identity_and_state(staging_dir)

    # 3. Verify export
    assert export_result["personality.json"] is True
    assert export_result["history.json"] is True
    assert export_result["identity_core.db"] is True
    assert export_result["state_cache.db"] is True

    assert (staging_dir / "identity_state" / "personality.json").exists()
    assert (staging_dir / "identity_state" / "history.json").exists()
    assert (staging_dir / "identity_state" / "identity_core.db").exists()
    assert (staging_dir / "state_cache.db").exists()

    # 4. Mutate original state to simulate data loss / modification
    personality_path.write_text(json.dumps({"name": "Corrupted"}))
    history_path.unlink()

    conn = sqlite3.connect(str(identity_db_path))
    conn.execute("DELETE FROM identity_core")
    conn.commit()
    conn.close()

    conn = sqlite3.connect(str(state_db_path))
    conn.execute("DROP TABLE adaptive_weights")
    conn.commit()
    conn.close()

    # 5. Import
    import_result = imf._import_identity_and_state(staging_dir, force=True)

    # 6. Assert roundtrip invariance
    assert import_result["personality.json"] is True
    assert import_result["history.json"] is True
    assert import_result["identity_core.db"] is True
    assert import_result["state_cache.db"] is True

    restored_personality = json.loads(personality_path.read_text())
    assert restored_personality["name"] == "Test Persona"
    assert restored_personality["traits"] == ["kind"]

    restored_history = json.loads(history_path.read_text())
    assert restored_history["interactions"] == 10

    identity_rows = _query_sqlite_db(
        identity_db_path, "SELECT key, value FROM identity_core ORDER BY key"
    )
    assert identity_rows == [("core_belief", "helpful"), ("core_memory", "birth")]

    state_rows = _query_sqlite_db(
        state_db_path, "SELECT affect FROM agent_state ORDER BY id"
    )
    assert state_rows == [("happy",), ("curious",)]

    weight_rows = _query_sqlite_db(
        state_db_path, "SELECT weight FROM adaptive_weights ORDER BY id"
    )
    assert weight_rows == [(0.5,), (0.9,)]
