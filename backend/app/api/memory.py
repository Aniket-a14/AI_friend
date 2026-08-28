"""Memory browse over HTTP (roadmap Phase 5.1).

Read-only, and deliberately not routed through `state/memory_store.py`'s
`MemoryStore` -- that class's constructor also wires Qdrant and Neo4j
dependencies a plain "list what's there" browse has no need of, and it is
already the largest, riskiest file in the codebase (CLAUDE.md). This opens
its own short-lived connection per request, the same pattern
`scripts/export_friend.py` already uses, rather than adding pool lifecycle
management to `main.py` for a single read endpoint.
"""

import asyncpg
from fastapi import APIRouter, HTTPException, Query

from ..config import Config

router = APIRouter(prefix="/api/memory", tags=["memory"])

_ALLOWED_SORT_COLUMNS = ("created_at", "importance_score", "last_recalled_at")


@router.get("/recent")
async def list_recent_memories(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at"),
):
    if sort_by not in _ALLOWED_SORT_COLUMNS:
        raise HTTPException(
            status_code=400,
            detail=f"sort_by must be one of {_ALLOWED_SORT_COLUMNS}",
        )
    dsn = Config.DATABASE_URL
    if not dsn:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured")

    try:
        conn = await asyncpg.connect(dsn)
    except OSError as exc:
        raise HTTPException(
            status_code=503, detail=f"Could not reach the database: {exc}"
        ) from exc

    try:
        rows = await conn.fetch(
            """
            SELECT id, content, importance_score, emotional_weight, valence,
                   recall_count, last_recalled_at, created_at, wing, modality
            FROM memories
            ORDER BY """
            f"{sort_by}"  # nosec B608 - sort_by is checked against _ALLOWED_SORT_COLUMNS above
            """ DESC NULLS LAST
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM memories")
    finally:
        await conn.close()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "memories": [dict(row) for row in rows],
    }
