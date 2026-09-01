---
name: qdrant-vector-search
description: Qdrant vector database patterns -- collection/payload design, HNSW and quantization tuning, filtered search, and how to slot a vector store into a multi-source fusion retrieval pipeline (vector + graph + relational + reranking). Use when touching Qdrant client code, a memory/retrieval system's vector backend, or tuning embedding search recall/latency (this repo: state/memory_store.py's vector leg of search_memories).
---

# Qdrant vector search patterns

This repo's `memory_store.py` fuses Qdrant vector search with an L1 cache, a Neo4j graph boost,
Postgres/SQLite candidate lookups, PageRank, and cue expansion, behind a dual-backend
(`Postgres` in production, `SQLite` in tests/local dev) abstraction. The patterns below cover
Qdrant itself plus how to reason about it as one leg of that kind of fusion system -- general
Qdrant knowledge, flagged where it is, versus this repo's specific shape, flagged separately.

## Collection and payload design

- **Payload, not a second lookup table, for anything you filter or boost on.** Qdrant supports
  filtering *during* the vector search (not just post-filtering results), so metadata you need
  to constrain search by (user/session ID, memory type, a timestamp range, an importance score)
  belongs in the point's payload, indexed (`create_payload_index`) if it's filtered on
  frequently -- an unindexed payload filter still works but degrades to a linear scan over
  candidates within the search, which erodes the whole point of an ANN index at scale.
- **Named vectors** (multiple vector fields per point, e.g. a dense embedding plus a sparse
  keyword vector) are the standard way to do hybrid dense+sparse search in one collection,
  rather than maintaining two separate collections and merging client-side.

## HNSW and quantization tuning

- `m` (graph connectivity) and `ef_construct` (build-time search breadth) trade index build
  time and memory against recall; `ef` (query-time search breadth, called `hnsw_ef` in some
  client versions) trades query latency against recall and can be tuned per-query without
  rebuilding the index -- raise it for a query where recall matters more than the last few ms
  of latency, rather than raising the collection-wide default.
- **Qdrant ships built-in scalar, binary, and product quantization** -- if VRAM/RAM footprint
  for a vector store is a real constraint, reach for this before reaching for a custom
  quantization scheme. Scalar quantization (int8) is the safe default recall/memory tradeoff;
  binary quantization is far more aggressive (larger recall cost) but appropriate when the
  embedding model was specifically designed to tolerate it. Don't build a bespoke
  compression scheme for a problem the vector database you're already running solves natively.
- Quantization changes recall characteristics; re-measure recall@K after enabling it rather than
  assuming the default rescore/oversampling settings are already tuned for your embedding
  distribution.

## Filtered and hybrid search

- A `must`/`should`/`must_not` filter combined with the vector query is the normal way to scope
  search (e.g. "only this user's memories," "only memories tagged episodic") -- prefer this over
  fetching a broad top-K and filtering client-side, which both wastes the ANN index's own pruning
  and can return fewer results than K after filtering if the pre-filter candidate pool was too
  narrow.
- For hybrid dense+sparse (keyword) retrieval, Qdrant's native multi-vector query lets both
  scores combine server-side; if instead fusing scores from *separate* systems (a Qdrant vector
  score alongside, say, a graph-database boost and a relational-candidate score, as this repo
  does), keep the fusion weights and normalization explicit and inspectable -- a fusion score
  that silently lets one signal dominate because its raw scale is larger than the others is a
  common, hard-to-notice retrieval quality bug.

## Slotting a vector store into a multi-source fusion pipeline

When a vector store is one leg of several (cache → vector → graph → relational → rerank, this
repo's actual shape), a few things matter more than any single leg's own tuning:

- **Know what each leg is actually for**, so a regression in one doesn't get misattributed to
  another. A vector leg finds semantic/embedding-similarity neighbors; a graph leg finds
  structurally/relationally connected items a pure embedding distance would miss; a relational
  leg is usually exact-match/recency-filtered candidates. If overall retrieval quality drops,
  isolate which leg's *output* changed before assuming the fusion/reranking stage is at fault.
- **A cache in front of the fusion (an L1 cache keyed on query/context) needs an explicit
  invalidation story.** A cache that never expires or invalidates on a write to any of the
  underlying stores will serve stale fused results indefinitely -- decide up front whether it's
  TTL-based, invalidated on write, or accepted as eventually-consistent, and test that decision
  explicitly rather than discovering it in production.
- **A dual-backend abstraction (e.g. Postgres in prod, SQLite in tests) needs its own dialect
  boundary tested, not just assumed identical.** Nearly every query on such a system needs a
  branch for the two backends' SQL dialect differences; a test suite that only ever exercises
  one backend (commonly SQLite, for speed) can pass while the Postgres branch has drifted or
  never ran. If the abstraction exposes a "which backend am I" property, treat it as read-only
  and force the *other* backend in tests via a real connection object of that type, not by
  assigning to the property -- a property with no setter is usually that way on purpose, to stop
  exactly this kind of test-only override from silently diverging from how it's actually
  selected in production.
