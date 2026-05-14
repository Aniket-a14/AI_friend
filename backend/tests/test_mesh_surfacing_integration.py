import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.agents.surfacing_agent import SurfacingAgent
from app.state.memory_store import MemoryStore


class _FakeConn:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, query, *args):
        normalized = " ".join(query.split()).lower()

        if normalized.startswith("insert into memories"):
            # New Arg Order: content, raw_val, wing, room, vector_str, importance, emotion...
            self.rows.append(
                {
                    "content": args[0],
                    "raw_content": args[1],
                    "wing": args[2],
                    "room": args[3],
                    "importance_score": float(args[5]),
                    "emotional_weight": float(args[6]),
                    "last_recalled_at": datetime.now(timezone.utc),
                }
            )
            return "INSERT 0 1"

        if normalized.startswith("update memories set last_recalled_at"):
            contents = set(args[0] if args else [])
            now = datetime.now(timezone.utc)
            for row in self.rows:
                if row["content"] in contents:
                    row["last_recalled_at"] = now
            return "UPDATE"

        return "OK"

    async def fetch(self, _query, *args):
        # New Params: vector_str, wing, [room], limit
        limit_idx = len(args) - 1
        limit = int(args[limit_idx]) if len(args) > 0 else len(self.rows)
        results = []
        for row in self.rows[:limit]:
            results.append(
                {
                    "content": row["content"],
                    "raw_content": row.get("raw_content", row["content"]),
                    "wing": row.get("wing", "personal"),
                    "room": row.get("room"),
                    "importance_score": row["importance_score"],
                    "emotional_weight": row["emotional_weight"],
                    "valence": row.get("valence", 0.0),
                    "recall_count": row.get("recall_count", 1),
                    "created_at": row.get("created_at", datetime.now(timezone.utc)),
                    "last_recalled_at": row["last_recalled_at"],
                    "metadata": row.get("metadata", {}),
                    "similarity": 0.99,
                }
            )
        return results


class _AcquireContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self):
        self._rows = []
        self._conn = _FakeConn(self._rows)

    def acquire(self):
        return _AcquireContext(self._conn)


class _InMemoryMesh:
    def __init__(self):
        self.subscribers = {}
        self.events = []
        self.payloads = {}

    async def subscribe(self, subject, callback):
        self.subscribers.setdefault(subject, []).append(callback)

    async def publish(self, subject, data):
        self.events.append(subject)
        self.payloads.setdefault(subject, []).append(data)
        for callback in self.subscribers.get(subject, []):
            await callback(data)


@pytest.mark.asyncio
async def test_surfacing_mesh_regression_emits_system_tick_and_memory_surfaced():
    pool = _FakePool()
    memory_store = MemoryStore(pool=pool, ollama_base_url="http://mock-ollama")
    memory_store.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])

    seeded = await memory_store.add_memory(
        content="You mentioned exam stress yesterday.",
        importance=0.9,
        emotion=0.4,
    )
    assert seeded is True
    memory_store.search_memories = AsyncMock(
        return_value=[
            {"content": "You mentioned exam stress yesterday.", "score": 0.95}
        ]
    )

    mesh = _InMemoryMesh()

    agent = SurfacingAgent(memory_store=memory_store)
    agent.connect = AsyncMock()

    async def _subscribe(subject, callback, **_kwargs):
        await mesh.subscribe(subject, callback)

    async def _publish(subject, data, metadata=None):
        payload = dict(data)
        if metadata:
            payload["latency_metadata"] = metadata
        await mesh.publish(subject, payload)

    agent.subscribe = _subscribe
    agent.publish = _publish

    await agent.start()

    # Avoid immediate chat-triggered surfacing; force tick-driven surfacing path.
    agent.last_surfaced_time = time.time()
    agent.surfacing_cooldown = -1

    await mesh.publish("chat.input", {"text": "I am still worried about my exam."})
    await mesh.publish(
        "system.tick",
        {
            "timestamp": time.time(),
            "latency_metadata": {"start_time": time.time() - 0.05},
        },
    )

    assert "system.tick" in mesh.events
    assert "memory.surfaced" in mesh.events
    surfaced_payload = mesh.payloads["memory.surfaced"][0]
    assert "exam stress" in surfaced_payload["memories"][0]["content"].lower()
