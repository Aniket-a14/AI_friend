"""Retrieval-backed context strategies: the seam that measures the memory layer.

`full_history` and `recent_window` are bounds, not systems. These strategies are
what turns "our memory architecture helps" from a claim into a number, so the
way they can lie is specific: give retrieval a bigger context than the control
and any win is just extra room; let one probe's transcript answer another's
question and the distance axis stops meaning anything; match retrieved turns by
value against filler that repeats verbatim and a budget of six silently becomes
sixty.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from test_conversation_evals import FILLER, make_probe

from evals.conversation import (
    Retrieved,
    Turn,
    WindowPlusRetrieved,
    build_transcript,
)
from evals.retrieval import (
    EVAL_WING,
    LexicalRetriever,
    MemoryStoreRetriever,
    transcript_fingerprint,
)

pytestmark = pytest.mark.asyncio


class TestTheLexicalControl:
    async def test_it_surfaces_the_planted_turn_over_filler(self):
        """The control has to actually work, or it is not a control.

        If BM25 could not find a fact it was shown, a memory layer beating it
        would prove nothing -- the comparison would be against a broken
        baseline rather than against retrieval.
        """
        turns = build_transcript(make_probe(filler_turns=40), FILLER)
        retriever = LexicalRetriever()
        await retriever.index(turns)

        hits = await retriever.search("what is my youngest sister called?", 6)

        assert any("Wren" in turn.text for turn in hits)

    async def test_it_returns_nothing_rather_than_noise_for_an_unmatched_query(self):
        """A retriever that always fills its budget hands the model six
        irrelevant turns and calls it recall. Empty is the honest answer when
        nothing matches, and it makes `plant out` visible in the report."""
        turns = [Turn("user", "the bus was late"), Turn("assistant", "again?")]
        retriever = LexicalRetriever()
        await retriever.index(turns)

        assert await retriever.search("quantum chromodynamics", 6) == []

    async def test_reindexing_the_same_transcript_is_skipped(self):
        """Two strategies share one retriever. Without the skip, every
        transcript is embedded and written twice -- doubling the cost of the
        expensive retriever for no change in result."""
        turns = build_transcript(make_probe(filler_turns=4), FILLER)
        retriever = LexicalRetriever()
        await retriever.index(turns)

        # Identity of the rebuilt state, not the fingerprint. Comparing
        # fingerprints proves nothing: without the skip, `index` recomputes the
        # same value and reassigns it, and the assertion still holds. The
        # observable consequence of skipping is that the work is not redone.
        docs_before = retriever._docs

        await retriever.index(turns)
        assert retriever._docs is docs_before

        other = build_transcript(make_probe(filler_turns=6), FILLER)
        await retriever.index(other)
        assert retriever._docs is not docs_before

    async def test_a_different_transcript_replaces_the_index(self):
        """Probes must not pool their evidence. If indexing accumulated, a fact
        planted for the 4-turn probe would still be retrievable during the
        240-turn probe and every distance would look survivable."""
        first = [Turn("user", "my sister is called Wren.")]
        second = [Turn("user", "the bus was late again.")]
        retriever = LexicalRetriever()

        await retriever.index(first)
        await retriever.index(second)

        assert await retriever.search("wren", 5) == []


class TestTheBudgetIsMatched:
    async def test_retrieved_never_exceeds_its_turn_budget(self):
        """The budget is the experiment. Given more turns than the window
        control, a win is attributable to context size rather than to
        selection, and the comparison answers a question nobody asked.

        The stub deliberately returns more than it was asked for: BM25 caps
        itself, so testing against it would prove the *retriever* honest and
        say nothing about whether the strategy enforces its own budget. A
        retriever that over-returns is exactly what this has to survive --
        `search_memories` takes `limit` as one input among several.
        """
        turns = build_transcript(make_probe(filler_turns=60), FILLER)
        retriever = AsyncMock()
        retriever.name = "stub"
        retriever.search.return_value = list(turns[:20])

        visible = await Retrieved(retriever, 6).select(turns, "q")

        assert len(visible) == 6

    async def test_the_lexical_control_also_respects_the_budget(self):
        turns = build_transcript(make_probe(filler_turns=60), FILLER)
        strategy = Retrieved(LexicalRetriever(), 6)

        visible = await strategy.select(turns, "what is my sister called?")

        assert len(visible) <= 6

    async def test_repeated_filler_cannot_inflate_the_budget(self):
        """Filler repeats verbatim every few exchanges. Matching hits by value
        would let one retrieved turn claim all of its duplicates, so a budget
        of two could return twenty turns and quietly become a second
        full_history."""
        repeated = Turn("user", "what's the weather doing")
        turns = [repeated] * 20 + [Turn("user", "my sister is called Wren.")]

        retriever = AsyncMock()
        retriever.name = "stub"
        retriever.search.return_value = [repeated, repeated]
        strategy = Retrieved(retriever, 2)

        visible = await strategy.select(turns, "weather")

        assert len(visible) == 2

    async def test_a_zero_budget_is_rejected(self):
        """An empty context scores the model's prior with no conversation."""
        with pytest.raises(ValueError):
            Retrieved(LexicalRetriever(), 0)

    async def test_selected_turns_are_returned_in_transcript_order(self):
        """Relevance order would hand the model a conversation that jumps
        around in time, which is a different comprehension task than the
        controls face and would confound the comparison."""
        turns = [
            Turn("user", "my sister is called Wren."),
            Turn("assistant", "noted."),
            Turn("user", "the bus was late."),
        ]
        retriever = AsyncMock()
        retriever.name = "stub"
        retriever.search.return_value = [turns[2], turns[0]]

        visible = await Retrieved(retriever, 3).select(turns, "q")

        assert visible == [turns[0], turns[2]]


class TestTheProductionShapedStrategy:
    async def test_the_recent_window_is_always_present(self):
        """This strategy exists to mirror what the running system does: recent
        context is never dropped, memories arrive alongside it."""
        turns = build_transcript(make_probe(filler_turns=40), FILLER)
        retriever = AsyncMock()
        retriever.name = "stub"
        retriever.search.return_value = []

        visible = await WindowPlusRetrieved(retriever, 6, 6).select(turns, "q")

        assert visible == turns[-6:]

    async def test_a_retrieved_turn_already_in_the_window_is_not_duplicated(self):
        """Paying twice for the same turn spends the retrieval budget on
        context the model already had."""
        turns = build_transcript(make_probe(filler_turns=20), FILLER)
        retriever = AsyncMock()
        retriever.name = "stub"
        retriever.search.return_value = [turns[-1]]

        visible = await WindowPlusRetrieved(retriever, 6, 6).select(turns, "q")

        assert len(visible) == len({id(t) for t in visible})
        assert len(visible) == 6

    async def test_an_over_returning_retriever_cannot_grow_the_context(self):
        """This strategy is not budget-matched, but it is still bounded.
        `search_memories` treats `limit` as one input among several and may
        return more; unbounded, "window plus six" becomes "window plus
        everything", which is `full_history` under another name -- and the
        comparison against `full_history` then compares it to itself.
        """
        # Every turn distinct on purpose. Built from the shipped filler, the
        # early turns repeat the window's text verbatim and are dropped as
        # already-visible before the cap is ever reached -- so the test would
        # pass with the cap removed and prove nothing.
        turns = [Turn("user", f"line {index}") for index in range(46)]
        retriever = AsyncMock()
        retriever.name = "stub"
        # Far more than asked for, all from outside the window.
        retriever.search.return_value = list(turns[:40])

        visible = await WindowPlusRetrieved(retriever, 6, 6).select(turns, "q")

        assert len(visible) == 12

    async def test_it_reaches_past_the_window_for_the_plant(self):
        """The whole point: the fact is outside the window, so `recent_window`
        must fail and this must not."""
        turns = build_transcript(make_probe(filler_turns=40), FILLER)
        strategy = WindowPlusRetrieved(LexicalRetriever(), 6, 6)

        visible = await strategy.select(turns, "what is my sister called?")

        assert any("Wren" in turn.text for turn in visible)


class TestTheMemoryStoreRetrieverDoesNotPolluteTheAgent:
    def _store(self):
        store = MagicMock()
        store.add_memory = AsyncMock(return_value=True)
        store.search_memories = AsyncMock(return_value=[])
        return store

    async def test_every_write_is_scoped_to_the_eval_wing(self):
        """This suite writes hundreds of scripted filler lines into the same
        database the agent uses to remember its user. Unscoped, "the bus was
        late again" becomes indistinguishable from something the user said,
        and the cleanup at the end has nothing to key on."""
        store = self._store()
        retriever = MemoryStoreRetriever(store)

        await retriever.index([Turn("user", "my sister is called Wren.")])

        assert store.add_memory.await_count == 1
        assert store.add_memory.await_args.kwargs["wing"] == EVAL_WING
        assert EVAL_WING != "personal"

    async def test_indexing_a_new_transcript_purges_the_previous_one_first(self):
        """`add_memory` deduplicates on content across the whole table, not
        within a room. Probes share filler verbatim, so without a purge the
        second probe's writes are swallowed as duplicates of the first probe's
        rows -- which sit in the first probe's room. Its own room comes up
        empty and the report shows the memory layer returning nothing.

        That is not hypothetical: it happened, and it made a live run read as a
        memory-layer failure that was entirely this retriever's fault.
        """
        conn = AsyncMock()
        conn.fetch.return_value = []
        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        store = self._store()
        store.pool = pool
        store.graph_db = None
        store.qdrant_store = MagicMock(client=None, collection_name=None)
        retriever = MemoryStoreRetriever(store)

        await retriever.index([Turn("user", "probe one")])
        await retriever.index([Turn("user", "probe two")])

        deletes = [
            call.args[0] for call in conn.execute.await_args_list
            if "DELETE" in call.args[0]
        ]
        assert len(deletes) == 2, "each index must purge before it writes"

    async def test_each_transcript_gets_its_own_room(self):
        """Probes share a database but must not share evidence: a fact planted
        for the 4-turn probe answering the 240-turn probe would make every
        distance look survivable."""
        store = self._store()
        retriever = MemoryStoreRetriever(store)

        await retriever.index([Turn("user", "one")])
        first = retriever._room
        await retriever.index([Turn("user", "two")])

        assert first and retriever._room != first
        assert retriever._room.startswith("probe_")

    async def test_a_write_that_silently_failed_is_counted_not_swallowed(self):
        """`add_memory` reports failure by returning False rather than raising.
        Unchecked, a probe whose transcript never reached the store returns
        nothing and the report reads it as a memory layer that could not
        recall -- which is exactly how the previous run was invalidated."""
        store = self._store()
        store.add_memory = AsyncMock(side_effect=[True, False, True])
        retriever = MemoryStoreRetriever(store)

        await retriever.index(
            [Turn("user", "a"), Turn("user", "b"), Turn("user", "c")]
        )

        assert retriever.indexed == 2
        assert retriever.index_failures == 1

    async def test_the_search_is_scoped_to_the_indexed_room(self):
        """An unscoped search reads every probe's turns and the room is
        decoration."""
        store = self._store()
        retriever = MemoryStoreRetriever(store)
        await retriever.index([Turn("user", "my sister is called Wren.")])

        await retriever.search("sister", 5)

        kwargs = store.search_memories.await_args.kwargs
        assert kwargs["wing"] == EVAL_WING
        assert kwargs["room"] == retriever._room

    async def test_searching_does_not_strengthen_what_it_retrieves(self):
        """Retrieval must not reshape the store the next probe is scored against.

        `search_memories` normally takes `recall_count + 1` on every hit, which
        is right for an agent living its life -- what you think about, you
        think about more easily. It is wrong for an instrument. Four strategies
        ask the same room the same question, so with the refresh on, strategy
        four ranks against a store the first three have already rewritten, and
        the ranking depends on the order the suite happened to run in.

        Not a theoretical worry: the ln(frequency) term is worth more than the
        entire spread of the similarity term at these scales, so one extra
        recall is enough to reorder the results.
        """
        store = self._store()
        retriever = MemoryStoreRetriever(store)
        await retriever.index([Turn("user", "my sister is called Wren.")])

        await retriever.search("sister", 5)

        assert store.search_memories.await_args.kwargs["refresh_on_recall"] is False

    async def test_results_map_back_to_turns_by_content(self):
        store = self._store()
        turn = Turn("user", "my sister is called Wren.")
        store.search_memories = AsyncMock(
            return_value=[{"content": "my sister is called Wren."}]
        )
        retriever = MemoryStoreRetriever(store)
        await retriever.index([turn])

        assert await retriever.search("sister", 5) == [turn]

    async def test_cleanup_reads_ids_before_deleting_them(self):
        """The vector tier is keyed by the same id the relational tier holds.
        Deleting rows first would leave Qdrant answering queries from records
        that no longer exist, and nothing left to identify them by."""
        conn = AsyncMock()
        conn.fetch.return_value = [{"id": "abc"}]
        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        store = self._store()
        store.pool = pool
        store.graph_db = None
        store.qdrant_store = MagicMock(client=MagicMock(), collection_name="m")

        await MemoryStoreRetriever(store).close()

        assert "SELECT id" in conn.fetch.await_args.args[0]
        assert "DELETE" in conn.execute.await_args.args[0]
        assert conn.execute.await_args.args[1] == EVAL_WING
        store.qdrant_store.client.delete.assert_called_once()

        # Order is the entire claim, and asserting on the calls individually
        # does not check it: a `_purge` that deleted first and read ids
        # afterwards would satisfy every assertion above while leaving Qdrant
        # holding vectors it can no longer identify. Both land on one
        # connection mock, so `mock_calls` records which ran first.
        sequence = [
            call[0] for call in conn.mock_calls if call[0] in ("fetch", "execute")
        ]
        assert sequence == ["fetch", "execute"]


class TestTheFingerprint:
    async def test_reordering_turns_changes_it(self):
        """Same turns in a different order is a different conversation, and a
        retriever that skipped re-indexing it would answer from the old one."""
        a = [Turn("user", "one"), Turn("user", "two")]
        b = [Turn("user", "two"), Turn("user", "one")]
        assert transcript_fingerprint(a) != transcript_fingerprint(b)

    async def test_it_does_not_collide_across_a_field_boundary(self):
        """Concatenating fields without a separator makes ("ab","c") and
        ("a","bc") the same transcript."""
        a = [Turn("ab", "c")]
        b = [Turn("a", "bc")]
        assert transcript_fingerprint(a) != transcript_fingerprint(b)
