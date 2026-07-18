"""Parity tests for the Personalized PageRank hot loop port to Rust.

The PPR power method that drives HippoRAG-style graph spreading activation was
moved from an in-Python loop into the cognitive_rust extension (the crate that
already owns the ACT-R scoring loop). This is a behavior-preserving move: the
Rust path, the pure-Python fallback, and a faithful copy of the *original*
set-based loop must all agree bit-for-bit -- including the two subtle legacy
behaviors: probability-mass leakage through neighbors absent from entity_names,
and dangling-node redistribution to the seed set.
"""

import random

import pytest
from unittest.mock import patch

from app.state.memory_store import MemoryStore, PPR_DAMPING


def _py_reference(entity_names, adj, seeds, damping, iterations):
    """Verbatim reproduction of the pre-port in-Python PPR loop, used as the
    independent ground truth for both the Rust and fallback code paths."""
    n = len(entity_names)
    if not seeds:
        return [0.0] * n
    p_0 = [0.0] * n
    val = 1.0 / len(seeds)
    for s_idx in seeds:
        p_0[s_idx] = val
    p = list(p_0)
    node_to_idx = {name: idx for idx, name in enumerate(entity_names)}
    d = damping
    for _ in range(iterations):
        p_next = [0.0] * n
        for i in range(n):
            node_name = entity_names[i]
            neighbors = adj.get(node_name, set())
            if neighbors:
                v = p[i] / len(neighbors)
                for nb in neighbors:
                    n_idx = node_to_idx.get(nb)
                    if n_idx is not None:
                        p_next[n_idx] += v
            else:
                for idx in seeds:
                    p_next[idx] += p[i] / len(seeds)
        for i in range(n):
            p_next[i] = d * p_next[i] + (1 - d) * p_0[i]
        p = p_next
    return p


def _assert_matches(entity_names, adj, seeds, iterations=3):
    expected = _py_reference(entity_names, adj, seeds, PPR_DAMPING, iterations)

    rust = MemoryStore._personalized_pagerank(
        entity_names, adj, seeds, PPR_DAMPING, iterations
    )
    assert rust == pytest.approx(expected, abs=1e-12)

    # Force the pure-Python fallback by making the Rust call raise.
    with patch(
        "cognitive_rust.personalized_pagerank", side_effect=RuntimeError("boom")
    ):
        fallback = MemoryStore._personalized_pagerank(
            entity_names, adj, seeds, PPR_DAMPING, iterations
        )
    assert fallback == pytest.approx(expected, abs=1e-12)
    return rust


class TestPprParity:
    def test_single_seed_ring(self):
        names = ["a", "b", "c"]
        adj = {"a": {"b", "c"}, "b": {"a"}, "c": {"a"}}
        _assert_matches(names, adj, {0})

    def test_multiple_seeds(self):
        names = ["a", "b", "c", "d"]
        adj = {"a": {"b"}, "b": {"a", "c"}, "c": {"b", "d"}, "d": {"c"}}
        _assert_matches(names, adj, {0, 3})

    def test_dangling_node_redistributes_to_seeds(self):
        # "a" has no adjacency entry -> dangling; its mass returns to the seeds.
        names = ["a", "b"]
        adj = {"b": {"a"}}
        _assert_matches(names, adj, {0})

    def test_empty_seeds_is_zero_vector(self):
        names = ["a", "b"]
        adj = {"a": {"b"}, "b": {"a"}}
        result = MemoryStore._personalized_pagerank(names, adj, set(), PPR_DAMPING, 3)
        assert result == [0.0, 0.0]

    def test_neighbor_outside_entity_set_leaks_mass(self):
        # "ghost" is a real graph edge but not a candidate entity: node "a" has
        # degree 2, yet only "b" resolves, so half of a's mass leaks away.
        names = ["a", "b"]
        adj = {"a": {"b", "ghost"}, "b": {"a"}}
        leaked = _assert_matches(names, adj, {0})

        # Same topology without the phantom edge (degree 1) must score "b"
        # strictly higher -- proving the original degree is honored, not the
        # count of resolved neighbors.
        no_ghost = MemoryStore._personalized_pagerank(
            names, {"a": {"b"}, "b": {"a"}}, {0}, PPR_DAMPING, 3
        )
        assert no_ghost[1] > leaked[1]

    def test_matches_across_random_graphs(self):
        rng = random.Random(1234)
        for _ in range(25):
            n = rng.randint(2, 12)
            names = [f"n{i}" for i in range(n)]
            adj = {}
            for i in range(n):
                degree = rng.randint(0, n - 1)
                nbrs = set(rng.sample(range(n), degree)) - {i}
                if nbrs:
                    adj[names[i]] = {names[j] for j in nbrs}
                # Occasionally inject an out-of-set neighbor to exercise leakage.
                if rng.random() < 0.3:
                    adj.setdefault(names[i], set()).add("phantom")
            seed_count = rng.randint(1, n)
            seeds = set(rng.sample(range(n), seed_count))
            _assert_matches(names, adj, seeds)
