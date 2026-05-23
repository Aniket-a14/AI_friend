import logging
import sqlite3
import re
import os

logger = logging.getLogger("sqlite_fallback")


class SQLiteConnection:
    def __init__(self, db_path=":memory:"):
        # Ensure parent directory exists if referencing a file
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        self.conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self):
        cursor = self.conn.cursor()

        # Sessions Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                trust_benevolence REAL DEFAULT 0.5,
                trust_competence REAL DEFAULT 0.5,
                trust_integrity REAL DEFAULT 0.5,
                metadata TEXT DEFAULT '{}'
            )
        """)

        # Schema migration for existing databases
        cursor.execute("PRAGMA table_info(sessions)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        for col in ["trust_benevolence", "trust_competence", "trust_integrity"]:
            if col not in existing_cols:
                cursor.execute(
                    f"ALTER TABLE sessions ADD COLUMN {col} REAL DEFAULT 0.5"
                )

        # Messages Table (Consolidated column handles ACT-R processing)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                consolidated INTEGER DEFAULT 0,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)

        # Agent Configs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_configs (
                id INTEGER PRIMARY KEY,
                personality TEXT,
                background_history TEXT,
                evolved_learnings TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Memories Table (pgvector fallback storage in SQLite)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT,
                raw_content TEXT,
                wing TEXT DEFAULT 'personal',
                room TEXT,
                embedding TEXT,
                importance_score REAL DEFAULT 0.5,
                emotional_weight REAL DEFAULT 0.0,
                valence REAL DEFAULT 0.0,
                certainty REAL DEFAULT 1.0,
                source TEXT DEFAULT 'user',
                recall_count INTEGER DEFAULT 0,
                last_recalled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                lifespan_stage TEXT,
                crisis TEXT,
                virtue TEXT,
                relations TEXT,
                relation_circles TEXT,
                modality TEXT
            )
        """)

        # Migration for existing memories table to add developmental stage columns
        cursor.execute("PRAGMA table_info(memories)")
        existing_mem_cols = {row[1] for row in cursor.fetchall()}
        for col in [
            "lifespan_stage",
            "crisis",
            "virtue",
            "relations",
            "relation_circles",
            "modality",
        ]:
            if col not in existing_mem_cols:
                cursor.execute(f"ALTER TABLE memories ADD COLUMN {col} TEXT")

        # Migration for memories.id column type: ensure it's TEXT for UUID compatibility
        cursor.execute("PRAGMA table_info(memories)")
        id_col_info = [row for row in cursor.fetchall() if row[1] == "id"]
        if id_col_info and id_col_info[0][2].upper() != "TEXT":
            logger.info(
                f"Migrating memories.id from {id_col_info[0][2]} to TEXT for UUID compatibility"
            )
            # Create temp table with correct schema
            cursor.execute("""
                CREATE TABLE memories_new (
                    id TEXT PRIMARY KEY,
                    content TEXT,
                    raw_content TEXT,
                    wing TEXT DEFAULT 'personal',
                    room TEXT,
                    embedding TEXT,
                    importance_score REAL DEFAULT 0.5,
                    emotional_weight REAL DEFAULT 0.0,
                    valence REAL DEFAULT 0.0,
                    certainty REAL DEFAULT 1.0,
                    source TEXT DEFAULT 'user',
                    recall_count INTEGER DEFAULT 0,
                    last_recalled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT DEFAULT '{}',
                    lifespan_stage TEXT,
                    crisis TEXT,
                    virtue TEXT,
                    relations TEXT,
                    relation_circles TEXT,
                    modality TEXT
                )
            """)
            # Copy data, converting id to TEXT
            cursor.execute("""
                INSERT INTO memories_new
                SELECT CAST(id AS TEXT), content, raw_content, wing, room, embedding,
                       importance_score, emotional_weight, valence, certainty, source,
                       recall_count, last_recalled_at, created_at, metadata,
                       lifespan_stage, crisis, virtue, relations, relation_circles, modality
                FROM memories
            """)
            # Drop old table and rename new one
            cursor.execute("DROP TABLE memories")
            cursor.execute("ALTER TABLE memories_new RENAME TO memories")

        self.conn.commit()

    def _translate_query(self, query: str):
        # 1. Translate PostgreSQL $1, $2 placeholders to SQLite ?
        translated = re.sub(r"\$\d+", "?", query)

        # 2. Replace Postgres NOW() with SQLite's CURRENT_TIMESTAMP
        translated = re.sub(
            r"\bNOW\(\)", "CURRENT_TIMESTAMP", translated, flags=re.IGNORECASE
        )

        # 3. Replace clock_timestamp() with CURRENT_TIMESTAMP
        translated = re.sub(
            r"\bclock_timestamp\(\)",
            "CURRENT_TIMESTAMP",
            translated,
            flags=re.IGNORECASE,
        )

        # 4. Handle UUID / VARCHAR types (SQLite handles these as TEXT naturally)
        translated = re.sub(r"\bUUID\b", "TEXT", translated, flags=re.IGNORECASE)
        translated = re.sub(
            r"\bVARCHAR\(\d+\)\b", "TEXT", translated, flags=re.IGNORECASE
        )
        translated = re.sub(r"\bBOOLEAN\b", "INTEGER", translated, flags=re.IGNORECASE)
        translated = re.sub(r"\bFALSE\b", "0", translated, flags=re.IGNORECASE)
        translated = re.sub(r"\bTRUE\b", "1", translated, flags=re.IGNORECASE)
        translated = re.sub(
            r"\bTIMESTAMP WITH TIME ZONE\b",
            "TIMESTAMP",
            translated,
            flags=re.IGNORECASE,
        )
        translated = re.sub(r"\bJSONB\b", "TEXT", translated, flags=re.IGNORECASE)
        translated = re.sub(
            r"\bALTER TABLE messages ADD COLUMN IF NOT EXISTS consolidated.*",
            "SELECT 1",
            translated,
            flags=re.IGNORECASE,
        )

        # 5. Translate PostgreSQL ON CONFLICT DO UPDATE to SQLite INSERT OR REPLACE INTO or ON CONFLICT(id) DO UPDATE
        if "ON CONFLICT" in translated.upper() and "DO UPDATE" in translated.upper():
            # If SQLite supports ON CONFLICT (id) DO UPDATE (3.24.0+), we can try to translate it or simplify
            # For simplicity, convert simple ON CONFLICT DO UPDATE patterns:
            # e.g., ON CONFLICT (id) DO UPDATE SET personality = EXCLUDED.personality -> DO UPDATE SET personality = excluded.personality
            translated = re.sub(
                r"\bEXCLUDED\b", "excluded", translated, flags=re.IGNORECASE
            )

        return translated

    async def execute(self, query, *args):
        translated = self._translate_query(query)
        cleaned_args = [str(arg) if hasattr(arg, "hex") else arg for arg in args]

        # Strip trailing comments or empty statements that SQLite driver rejects
        translated = "\n".join(
            line
            for line in translated.splitlines()
            if not line.strip().startswith("--")
        )

        cursor = self.conn.cursor()
        try:
            # Handle multiple SQL statements separated by semicolons
            if ";" in translated and len(translated.strip().split(";")) > 2:
                cursor.executescript(translated)
            else:
                cursor.execute(translated, cleaned_args)
            self.conn.commit()
        except sqlite3.OperationalError as e:
            # Guard against pg-specific extension checks like "create extension" or indexing
            if "vector" in str(e) or "hnsw" in str(e) or "pgcrypto" in str(e):
                logger.debug(
                    f"SQLite Schema Guard: Ignored PG-specific index/extension statement: {e}"
                )
            else:
                logger.error(
                    f"SQLite execution failed for query: {query}\nTranslated: {translated}\nError: {e}"
                )
                raise
        return None

    async def fetch(self, query, *args):
        translated = self._translate_query(query)
        cleaned_args = [str(arg) if hasattr(arg, "hex") else arg for arg in args]
        cursor = self.conn.cursor()
        cursor.execute(translated, cleaned_args)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    async def fetchrow(self, query, *args):
        translated = self._translate_query(query)
        cleaned_args = [str(arg) if hasattr(arg, "hex") else arg for arg in args]
        cursor = self.conn.cursor()
        cursor.execute(translated, cleaned_args)
        row = cursor.fetchone()
        return dict(row) if row else None

    async def fetchval(self, query, *args):
        translated = self._translate_query(query)
        cleaned_args = [str(arg) if hasattr(arg, "hex") else arg for arg in args]
        cursor = self.conn.cursor()
        cursor.execute(translated, cleaned_args)
        row = cursor.fetchone()
        return row[0] if row else None


class SQLitePoolAcquisition:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class SQLitePool:
    def __init__(self, db_path="app.db"):
        self.connection = SQLiteConnection(db_path)

    def acquire(self):
        return SQLitePoolAcquisition(self.connection)

    async def close(self):
        pass
