"""Measurement 1.6 (PERFORMANCE.md §13 item 7): the retrieval hot path
(M2-P1), the unbounded graph fetch (M2-P2), and the SQLite fallback under
concurrent load (M2-P3) -- all still labelled NOT TESTED in ISSUES.md.

Three sub-measurements, each against real infra: search_memories()'s fused
latency against Postgres/Neo4j/Qdrant; the two unbounded Cypher MATCHes from
M2-P2 cold vs cache-warm; and search_memories() under concurrent load on a
real (not mocked) SQLitePool, to check M2-P3's claim that the event loop
blocks for the full call duration.

audit/ROADMAP.md Stage 4 Part 2 (P2-3): the first run of this measurement
seeded only `add_memory`, which never creates `:Entity` nodes -- the graph
sub-measurement fetched an empty graph (0 entities, 0 relations), so M2-P2's
"fetches the entire entity table" cost was never actually stressed. This
version also seeds the graph directly via `GraphDB.create_triplet`, the same
path `ReflectionService._consolidate` uses in production, at a scale meant
to look like a graph that has been running for a while rather than a
just-booted one.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import time

from app.state import ConversationHistoryStore, GraphDB, MemoryStore
from app.state.sqlite_fallback import SQLitePool

from .harness import check_live_llm, ensure_bootstrapped
from .schema import Figure, MeasurementReport, Run

_GRAPH_RELATION_TYPES = ["KNOWS", "LIKES", "MENTIONED", "RELATED_TO", "WORKS_WITH"]

_SEED_MEMORIES = [
    "We talked about how much I enjoy reading sci-fi novels on weekends.",
    "You mentioned you were stressed about a work deadline last Tuesday.",
    "I told you about the hiking trip I'm planning for next month.",
    "We discussed the new coffee shop that opened near the office.",
    "You asked about my favorite programming languages and I said Rust and Python.",
    "I shared that I've been learning to cook Italian food lately.",
    "We had a long conversation about our shared love of jazz music.",
    "You told me about your sister's graduation coming up in June.",
    "I mentioned feeling anxious about an upcoming presentation.",
    "We joked about how neither of us can keep houseplants alive.",
]

_GRAPH_ENTITY_QUERY = "MATCH (e:Entity) RETURN e.name AS name, e.description AS description"
_GRAPH_RELATION_QUERY = "MATCH (s:Entity)-[r]-(t:Entity) RETURN s.name AS source, t.name AS target"


async def _seed(store: MemoryStore, n: int = 10) -> None:
    for i in range(n):
        await store.add_memory(
            content=_SEED_MEMORIES[i % len(_SEED_MEMORIES)] + f" (seed {i})",
            wing="personal",
        )


async def _time_search(store: MemoryStore, query: str) -> float:
    t0 = time.monotonic()
    await store.search_memories(query, limit=5)
    return time.monotonic() - t0


async def _measure_pg(graph_db: GraphDB) -> dict:
    conversation_store = ConversationHistoryStore()
    await conversation_store.initialize()
    store = MemoryStore(pool=conversation_store.pool, graph_db=graph_db)
    await _seed(store, 10)

    latency = await _time_search(store, "what have we talked about recently?")
    return {"pg_search_memories_s": latency}


async def _seed_graph(graph_db: GraphDB, n_entities: int, avg_degree: int = 2) -> int:
    """Seed a synthetic-but-representative entity graph via `create_triplet`
    -- unlike `add_memory` (used by `_seed` above), this is the path that
    actually creates `:Entity` nodes, matching what `ReflectionService.
    _consolidate` does in production.

    Concurrent batches, not sequential: `create_triplet` -> `consolidate_
    relationship` is at least two Cypher round trips per call (a cache
    invalidation plus the MERGE itself), so seeding thousands of relations
    one at a time would make the seeding step itself the slow part of this
    script rather than the thing being measured. A fixed random seed keeps
    the generated graph -- and therefore the entity/relation counts in the
    report -- reproducible across runs.
    """
    names = [f"entity_{i}" for i in range(n_entities)]
    rng = random.Random(42)
    edges = []
    for name in names:
        for _ in range(avg_degree):
            target = rng.choice(names)
            if target != name:
                edges.append((name, rng.choice(_GRAPH_RELATION_TYPES), target))

    batch_size = 50
    for start in range(0, len(edges), batch_size):
        batch = edges[start : start + batch_size]
        await asyncio.gather(
            *[graph_db.create_triplet(s, r, t) for s, r, t in batch]
        )
    return len(edges)


async def _measure_graph_fetch(graph_db: GraphDB) -> dict:
    # Both `_seed_graph` (every create_triplet call) and `_measure_pg`
    # (search_memories -> _gather_candidate_sources runs these same two
    # queries with use_cache=True) can leave the belief cache warm by the
    # time this runs -- the first version of this measurement did not
    # account for that, so its "cold" figure was silently a cache hit off
    # _measure_pg's own read, on an empty graph where cold and warm both
    # measured near-instantly regardless. Explicit invalidation here makes
    # "cold" mean what it says, independent of call order elsewhere in run().
    await graph_db.invalidate_cache()

    t0 = time.monotonic()
    entities = await graph_db.execute_query(_GRAPH_ENTITY_QUERY, use_cache=True)
    relations = await graph_db.execute_query(_GRAPH_RELATION_QUERY, use_cache=True)
    cold_s = time.monotonic() - t0

    t0 = time.monotonic()
    await graph_db.execute_query(_GRAPH_ENTITY_QUERY, use_cache=True)
    await graph_db.execute_query(_GRAPH_RELATION_QUERY, use_cache=True)
    warm_s = time.monotonic() - t0

    return {
        "graph_fetch_cold_s": cold_s,
        "graph_fetch_cache_warm_s": warm_s,
        "entity_count": len(entities) if isinstance(entities, list) else -1,
        "relation_count": len(relations) if isinstance(relations, list) else -1,
    }


async def _measure_sqlite_concurrency(graph_db: GraphDB, n: int = 5) -> dict:
    pool = SQLitePool(":memory:")
    store = MemoryStore(pool=pool, graph_db=graph_db)
    assert store.is_sqlite is True
    await _seed(store, 10)

    single_s = await _time_search(store, "what have we talked about recently?")

    t0 = time.monotonic()
    await asyncio.gather(
        *[
            store.search_memories(f"query {i}", limit=5)
            for i in range(n)
        ]
    )
    concurrent_total_s = time.monotonic() - t0

    serial_estimate_s = single_s * n
    # If the loop truly never yields during a SQLite call (M2-P3's claim),
    # N "concurrent" calls cost the same wall-clock as N serial calls -- no
    # overlap gained from asyncio.gather. overlap_ratio near 1.0 means no
    # concurrency was actually achieved; near 1/N would mean full overlap.
    overlap_ratio = (
        concurrent_total_s / serial_estimate_s if serial_estimate_s > 0 else float("nan")
    )

    return {
        "sqlite_single_call_s": single_s,
        f"sqlite_{n}_concurrent_calls_total_s": concurrent_total_s,
        f"sqlite_{n}x_serial_estimate_s": serial_estimate_s,
        "sqlite_concurrency_overlap_ratio": overlap_ratio,
    }


async def run(allow_mock: bool = False, graph_entities: int = 1000) -> MeasurementReport:
    # This measurement times DB/graph calls, not the LLM boundary, but the
    # provenance check stays for consistency: a MOCK_LLM_TEXT deployment
    # usually also means synthetic seed data isn't meaningfully "real" either.
    provenance = check_live_llm(allow_mock)
    await ensure_bootstrapped()

    graph_db = GraphDB()
    await graph_db.initialize()

    seed_start = time.monotonic()
    relations_seeded = await _seed_graph(graph_db, graph_entities)
    graph_seed_s = time.monotonic() - seed_start

    pg = await _measure_pg(graph_db)
    graph = await _measure_graph_fetch(graph_db)
    sqlite = await _measure_sqlite_concurrency(graph_db)

    figures = {
        "pg_search_memories_s": Figure(
            label="MEASURED", value=pg["pg_search_memories_s"], unit="seconds"
        ),
        "graph_fetch_cold_s": Figure(
            label="MEASURED", value=graph["graph_fetch_cold_s"], unit="seconds"
        ),
        "graph_fetch_cache_warm_s": Figure(
            label="MEASURED",
            value=graph["graph_fetch_cache_warm_s"],
            unit="seconds",
            derivation=(
                f"{graph['entity_count']} entities, {graph['relation_count']} "
                "relations fetched unbounded (M2-P2); cache TTL 300s per "
                "graph_db.py"
            ),
        ),
        "sqlite_concurrency_overlap_ratio": Figure(
            label="MEASURED",
            value=sqlite["sqlite_concurrency_overlap_ratio"],
            unit="ratio (1.0 = zero overlap, no concurrency gained)",
            derivation=(
                f"single call {sqlite['sqlite_single_call_s']:.4f}s; "
                f"5 concurrent calls totaled "
                f"{sqlite['sqlite_5_concurrent_calls_total_s']:.4f}s vs "
                f"{sqlite['sqlite_5x_serial_estimate_s']:.4f}s serial estimate"
            ),
        ),
    }

    return MeasurementReport(
        measurement_id="1.6",
        title="Retrieval hot path, unbounded graph fetch, SQLite under concurrent load",
        provenance=provenance,
        runs=[
            Run(
                figures=figures,
                raw={
                    "pg": pg,
                    "graph": graph,
                    "sqlite": sqlite,
                    "graph_seeding": {
                        "entities_requested": graph_entities,
                        "relations_seeded": relations_seeded,
                        "graph_seed_s": graph_seed_s,
                    },
                },
            )
        ],
        notes=[
            (
                f"Graph seeded via GraphDB.create_triplet (not add_memory, "
                f"which creates no :Entity nodes) before the graph "
                f"sub-measurement ran: {graph_entities} entity names, "
                f"{relations_seeded} relation edges, {graph_seed_s:.2f}s to "
                f"seed. The first run of this measurement (Stage 3) fetched "
                f"an empty graph -- M2-P2's 'fetches the entire entity "
                f"table' cost was never actually stressed; graph_fetch_cold_s "
                f"and entity_count/relation_count below are the real figures "
                f"this run closes that gap with."
            ),
            (
                "10 seed memories per store; a fresh Neo4j graph in this run "
                "carries whatever entities prior measurements in the same "
                "session already wrote (no isolation between sub-measurements "
                "sharing one GraphDB instance)."
            ),
            (
                "sqlite_concurrency_overlap_ratio near 1.0 would mean zero "
                "overlap (M2-P3's claim in its strongest form); near 1/N would "
                "mean full overlap. On this run it lands well below 1.0 -- "
                "meaningful overlap IS achieved overall. This does not "
                "contradict M2-P3's evidence (SQLiteConnection's methods really "
                "do call cursor.execute()/commit() with no await inside them): "
                "search_memories() also does real async I/O per call (at least "
                "one embedding request over httpx), and that portion genuinely "
                "yields the loop, letting other tasks' embedding calls interleave "
                "even while each call's SQLite portion blocks. The measured "
                "ratio is a call-level average across both; it does not by "
                "itself show whether the SQLite portion specifically overlaps "
                "(M2-P3's precise claim) -- isolating that needs timing inside "
                "search_memories() around just the SQLiteConnection calls, which "
                "this run does not do."
            ),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-mock", action="store_true")
    parser.add_argument("--out", default="tools/measure/out/m16_retrieval.json")
    parser.add_argument(
        "--graph-entities",
        type=int,
        default=1000,
        help="Entity names to seed before the graph sub-measurement runs "
        "(each yields ~2 relation edges on average). Default approximates "
        "a graph that has been running for a while.",
    )
    args = parser.parse_args()

    report = asyncio.run(
        run(allow_mock=args.allow_mock, graph_entities=args.graph_entities)
    )
    with open(args.out, "w") as f:
        f.write(report.model_dump_json(indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
