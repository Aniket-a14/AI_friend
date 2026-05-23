import asyncio
import logging
from pathlib import Path
from typing import List

import asyncpg
import httpx

from .config import Config
from .nats_streams import setup_streams

logger = logging.getLogger("runtime_bootstrap")


async def bootstrap_runtime() -> None:
    """Run idempotent runtime bootstrap so one-command deploy reaches a working mesh."""
    retries = max(1, int(getattr(Config, "RUNTIME_BOOTSTRAP_RETRIES", 12)))

    await _run_with_retry("database schema", _ensure_database_schema, retries=retries)
    await _run_with_retry("nats streams", _ensure_nats_streams, retries=retries)
    await _run_with_retry("ollama models", _ensure_ollama_models, retries=retries)

    logger.info("[Bootstrap] Runtime prerequisites verified.")


async def _run_with_retry(
    label: str, fn, retries: int, base_delay: float = 2.0
) -> None:
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            await fn()
            if attempt > 1:
                logger.info(
                    "[Bootstrap] %s recovered on attempt %s/%s.",
                    label,
                    attempt,
                    retries,
                )
            return
        except (
            Exception
        ) as e:  # pragma: no cover - exercised through integration behavior
            last_error = e
            if attempt == retries:
                break
            delay = min(15.0, base_delay * attempt)
            logger.warning(
                "[Bootstrap] %s failed on attempt %s/%s: %s. Retrying in %.1fs",
                label,
                attempt,
                retries,
                e,
                delay,
            )
            await asyncio.sleep(delay)

    raise RuntimeError(
        f"bootstrap step '{label}' failed after {retries} attempts: {last_error}"
    )


async def _ensure_database_schema() -> None:
    dsn = Config.DATABASE_URL
    if not dsn:
        dsn = "sqlite:///app.db"

    if dsn.startswith("sqlite") or dsn == "sqlite:///:memory:":
        logger.info(
            "[Bootstrap] Detected SQLite target database. Bypassing pg schema initialization."
        )
        from .state.sqlite_fallback import SQLiteConnection

        db_file = "app.db"
        if dsn.startswith("sqlite:///"):
            db_file = dsn.replace("sqlite:///", "")
        elif dsn == "sqlite:///:memory:":
            db_file = ":memory:"
        SQLiteConnection(db_file)
        logger.info("[Bootstrap] SQLite database schema and core tables verified.")
        return

    try:
        conn = await asyncpg.connect(dsn)
    except Exception as e:
        logger.warning(
            f"[Bootstrap] PostgreSQL connection failed: {e}. Falling back to SQLite."
        )
        from .state.sqlite_fallback import SQLiteConnection

        SQLiteConnection("app.db")
        logger.info(
            "[Bootstrap] SQLite database schema and core tables verified via fallback."
        )
        return

    schema_path = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    schema_sql = schema_path.read_text(encoding="utf-8")

    try:
        await conn.execute(schema_sql)

        # Conversation and identity tables are required by ConversationHistoryStore.
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id UUID PRIMARY KEY,
                started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP WITH TIME ZONE,
                metadata JSONB
            );
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id UUID PRIMARY KEY,
                session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                consolidated BOOLEAN DEFAULT FALSE
            );
            """
        )
        # Migration: add consolidated column to existing tables if it does not already exist
        await conn.execute(
            """
            ALTER TABLE messages ADD COLUMN IF NOT EXISTS consolidated BOOLEAN DEFAULT FALSE;
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_configs (
                id INTEGER PRIMARY KEY,
                personality TEXT,
                background_history TEXT,
                evolved_learnings TEXT,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
    finally:
        await conn.close()

    logger.info("[Bootstrap] Database schema and core tables verified.")


async def _ensure_nats_streams() -> None:
    await setup_streams(Config.NATS_URL)


async def _ensure_ollama_models() -> None:
    required = _normalized_required_models(
        getattr(Config, "OLLAMA_REQUIRED_MODELS", [])
    )
    if not required:
        logger.info(
            "[Bootstrap] No required Ollama models configured; skipping model check."
        )
        return

    base_url = (Config.OLLAMA_URL or "http://127.0.0.1:11434").rstrip("/")

    async with httpx.AsyncClient(timeout=120.0) as client:
        tags_response = await client.get(f"{base_url}/api/tags")
        tags_response.raise_for_status()
        tags_payload = tags_response.json()

        available = [
            entry.get("name", "")
            for entry in tags_payload.get("models", [])
            if entry.get("name")
        ]
        missing = [model for model in required if not _model_exists(model, available)]

        if not missing:
            logger.info(
                "[Bootstrap] Required Ollama models already present: %s", required
            )
            return

        logger.info("[Bootstrap] Missing Ollama models: %s", missing)

        for model_name in missing:
            logger.info("[Bootstrap] Pulling Ollama model: %s", model_name)
            pull_response = await client.post(
                f"{base_url}/api/pull",
                json={"name": model_name, "stream": False},
            )
            pull_response.raise_for_status()
            logger.info("[Bootstrap] Model ready: %s", model_name)


def _normalized_required_models(models: List[str]) -> List[str]:
    deduped = []
    seen = set()
    for model in models:
        clean = str(model).strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        deduped.append(clean)
    return deduped


def _model_exists(required_model: str, available_models: List[str]) -> bool:
    if required_model in available_models:
        return True

    # Compatibility: treat "model" and "model:latest" as equivalent.
    if ":" not in required_model and f"{required_model}:latest" in available_models:
        return True
    if (
        required_model.endswith(":latest")
        and required_model.split(":", 1)[0] in available_models
    ):
        return True

    return False
