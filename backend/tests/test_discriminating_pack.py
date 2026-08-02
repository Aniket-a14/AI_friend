"""Tests for multi-plant probes and the pack written to separate two retrievers.

The shipped recall pack found this project's memory layer tied with a
fifty-line BM25 control. That was not a result about the architecture: every
question in that pack repeats the words of its own plant, so both retrievers
were being asked the same easy thing. The pack tested here is the instrument
built to tell them apart, and the failure that matters is the same one the
rest of the harness guards against -- an instrument that reads confidently
while measuring nothing.

Two specific ways that could happen here, both covered below: a plant placed
where the probe does not claim it is (so the stated distance is a fiction),
and a question whose words appear in its own plant (so the "oblique" probe is
not oblique and a lexical retriever passes it for free).
"""

import json
import re

import pytest
from pydantic import ValidationError
from test_conversation_evals import FILLER, make_probe

from evals.conversation import (
    Turn,
    build_transcript,
    load_conversation_pack,
    run_conversation_probe,
    shipped_discriminating_pack,
)
from evals.retrieval import LexicalRetriever
from evals.schema import Check, ConversationProbe, Plant, RunOptions

# The pack's own stop words. Overlap on "i" or "the" is not a lexical handle a
# retriever can rank on -- BM25 gives a term appearing in nearly every turn an
# idf near zero -- so the obliqueness check ignores them rather than reporting
# a failure the retriever could never exploit.
_TOO_COMMON = frozenset(
    {
        "a", "am", "an", "and", "are", "as", "at", "be", "been", "but", "by",
        "can", "cant", "do", "does", "doing", "dont", "for", "from", "get",
        "got", "had", "has", "have", "how", "i", "id", "if", "ill", "im", "in",
        "is", "it", "its", "ive", "just", "me", "most", "my", "no", "not",
        "of", "on", "or", "out", "should", "so", "than", "that", "the",
        "their", "them", "these", "they", "this", "to", "up", "us", "was",
        "we", "what", "when", "where", "which", "who", "why", "will", "with",
        "you", "your",
    }
)


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in _TOO_COMMON}


@pytest.fixture(scope="module")
def pack():
    probes, filler = load_conversation_pack(shipped_discriminating_pack())
    return probes, filler


class TestPlacingMoreThanOneFact:
    def test_a_plant_lands_after_exactly_the_filler_it_names(self):
        """`after_filler` is the probe's claim about when the fact was said.

        A contradiction probe is only a contradiction if the correction comes
        later than the fact it corrects. If placement drifted, the transcript
        would read in some other order and the probe would score the model on
        a conversation nobody wrote.
        """
        probe = ConversationProbe(
            id="two",
            plants=[
                Plant(text="first fact", reply="ok", after_filler=0, answers=False),
                Plant(text="second fact", reply="ok", after_filler=3),
            ],
            filler_turns=6,
            recall_prompt="which?",
            checks=[Check(kind="must_include", values=["second"])],
        )
        turns = build_transcript(probe, FILLER)
        texts = [turn.text for turn in turns]
        # The first plant's two turns, then three filler exchanges of two.
        assert texts.index("second fact") - texts.index("first fact") == 2 + 6

    def test_plants_do_not_add_to_the_stated_distance(self):
        """Filler is one running sequence that plants interrupt.

        If inserting a plant restarted the filler count, a probe declaring 24
        exchanges of distance would emit more than 24, and the distance axis --
        the thing every recall number is reported against -- would mean a
        different amount of text for every probe.
        """
        one = ConversationProbe(
            id="one", plant="fact", filler_turns=8,
            recall_prompt="q", checks=[Check(kind="must_include", values=["f"])],
        )
        many = ConversationProbe(
            id="many",
            plants=[
                Plant(text="a", after_filler=0),
                Plant(text="b", after_filler=2),
                Plant(text="c", after_filler=5),
            ],
            filler_turns=8,
            recall_prompt="q",
            checks=[Check(kind="must_include", values=["a"])],
        )
        filler_only = [
            turn for turn in build_transcript(many, FILLER)
            if turn.text not in {"a", "b", "c", "Got it."}
        ]
        assert len(filler_only) == len(build_transcript(one, FILLER)) - 2

    def test_depth_decides_the_order_not_the_order_they_were_written_in(self):
        """`after_filler` is the only thing that places a plant.

        A pack lists an update next to the fact it corrects because that is
        how it reads; if list order won, the correction could be emitted
        before the thing it corrects and the probe would be testing whether
        the model prefers the *older* answer.
        """
        probe = ConversationProbe(
            id="out-of-order",
            plants=[
                Plant(text="the correction", after_filler=3),
                Plant(text="the original", after_filler=1, answers=False),
            ],
            filler_turns=6,
            recall_prompt="q",
            checks=[Check(kind="must_include", values=["correction"])],
        )
        texts = [turn.text for turn in build_transcript(probe, FILLER)]
        assert texts.index("the original") < texts.index("the correction")

    def test_a_single_plant_transcript_is_unchanged(self):
        """The multi-plant path must not move the probes already measured.

        Reports from the shipped pack are compared against future runs. A
        transcript that shifted by even one turn would make every one of those
        comparisons a diff of two different experiments.
        """
        probe = make_probe(filler_turns=12)
        turns = build_transcript(probe, FILLER)
        assert turns[0] == Turn("user", probe.plant)
        assert turns[1] == Turn("assistant", probe.plant_reply)
        assert len(turns) == 2 + 24


class TestProbesThatCouldNotMeasureWhatTheyClaim:
    def test_a_plant_deeper_than_the_filler_is_rejected(self):
        """It would be emitted next to the question it must be recalled across.

        The probe would report a distance of 24 while the fact sat one turn
        from the prompt, and pass everywhere.
        """
        with pytest.raises(ValidationError):
            ConversationProbe(
                id="past-the-end",
                plants=[Plant(text="late", after_filler=9)],
                filler_turns=4,
                recall_prompt="q",
                checks=[Check(kind="must_include", values=["late"])],
            )

    def test_a_probe_with_only_distractors_is_rejected(self):
        """Nothing in the transcript answers, so `plant_visible` is vacuous.

        Every strategy would report the fact as present regardless of what it
        selected, which is the exact signal the flag exists to give.
        """
        with pytest.raises(ValidationError):
            ConversationProbe(
                id="no-answer",
                plants=[Plant(text="a distractor", answers=False)],
                filler_turns=4,
                recall_prompt="q",
                checks=[Check(kind="must_include", values=["x"])],
            )

    def test_writing_a_probe_both_ways_is_rejected(self):
        """One of the two would be silently dropped from the transcript."""
        with pytest.raises(ValidationError):
            ConversationProbe(
                id="both",
                plant="single",
                plants=[Plant(text="listed")],
                filler_turns=4,
                recall_prompt="q",
                checks=[Check(kind="must_include", values=["x"])],
            )

    def test_a_probe_planting_nothing_is_rejected(self):
        with pytest.raises(ValidationError):
            ConversationProbe(
                id="empty",
                filler_turns=4,
                recall_prompt="q",
                checks=[Check(kind="must_include", values=["x"])],
            )


class TestWhetherTheAnswerReachedTheModel:
    @pytest.fixture
    def manager(self):
        from unittest.mock import AsyncMock, MagicMock

        manager = MagicMock()
        manager.validate_response = AsyncMock(return_value=(True, ""))
        return manager

    def _update_probe(self):
        return ConversationProbe(
            id="update",
            plants=[
                Plant(text="i work at the bookshop.", after_filler=0, answers=False),
                Plant(text="i'm at the museum now.", after_filler=2, answers=True),
            ],
            filler_turns=8,
            recall_prompt="where do i work now?",
            checks=[Check(kind="must_include", values=["museum"])],
        )

    async def _run(self, manager, probe, strategy):
        from unittest.mock import AsyncMock

        client = AsyncMock()
        client.generate.return_value = "the museum."
        return await run_conversation_probe(
            client, manager, probe, FILLER, strategy,
            "system", "model", RunOptions(),
        )

    @pytest.mark.asyncio
    async def test_half_of_a_two_part_answer_reports_the_plant_dropped(
        self, manager
    ):
        """An answer split across two facts needs both of them on screen.

        With only one shown the question is unanswerable, and the probe
        produces a clean FAIL that reads as a memory-layer weakness when the
        harness simply never put the answer in front of the model. This is why
        the flag asks whether *every* answering plant arrived, not whether one
        did.
        """
        probe = ConversationProbe(
            id="two-part",
            plants=[
                Plant(text="my sister is called wren.", after_filler=0),
                Plant(text="wren moved to oslo last year.", after_filler=2),
            ],
            filler_turns=8,
            recall_prompt="where does my sister live?",
            checks=[Check(kind="must_include", values=["oslo"])],
        )

        class OnlyTheFirstHalf:
            name = "only_first"

            async def select(self, transcript, query):
                return [t for t in transcript if "called wren" in t.text]

        result = await self._run(manager, probe, OnlyTheFirstHalf())
        assert result.plant_visible is False

    @pytest.mark.asyncio
    async def test_a_dropped_distractor_does_not_invalidate_the_probe(self, manager):
        """Distractors are supposed to compete; losing one makes it easier.

        Counting them would mark every honest retrieval result as "measured
        nothing", because picking the answer over the distractors is precisely
        what the probe asks a retriever to do.
        """
        probe = self._update_probe()

        class OnlyTheUpdate:
            name = "only_new"

            async def select(self, transcript, query):
                return [t for t in transcript if "museum" in t.text]

        result = await self._run(manager, probe, OnlyTheUpdate())
        assert result.plant_visible is True


class TestThePackDiscriminates:
    def test_every_probe_id_is_unique(self, pack):
        """Ids qualify results, and `compare` keys its lookup on them."""
        probes, _ = pack
        ids = [probe.id for probe in probes]
        assert len(ids) == len(set(ids))

    def test_no_filler_line_contains_an_answer(self, pack):
        """A probe could otherwise pass without the fact ever being recalled.

        The whole pack is scored on `must_include`; an answer sitting in the
        filler makes every strategy look correct, including the ones designed
        to fail.
        """
        probes, filler = pack
        haystack = " ".join(a + " " + b for a, b in filler).lower()
        for probe in probes:
            for check in probe.checks:
                if check.kind not in ("must_include", "must_include_any"):
                    continue
                for value in check.values:
                    assert value.lower() not in haystack, (
                        f"{probe.id}: filler contains its own answer {value!r}"
                    )

    @pytest.mark.parametrize(
        "probe_id", ["oblique_activity_d24", "oblique_dislike_d24",
                     "similars_oblique_d48"],
    )
    def test_an_oblique_question_shares_no_content_word_with_its_answer(
        self, pack, probe_id
    ):
        """Obliqueness is the entire experimental manipulation.

        These probes exist to ask whether retrieval works by meaning. One
        content word shared between the question and the answering plant hands
        a lexical retriever the answer, and the pack goes back to measuring
        what the shipped one already measured -- which is how it produced a
        tie that looked like parity.
        """
        probes, _ = pack
        probe = next(p for p in probes if p.id == probe_id)
        question = _content_words(probe.recall_prompt)
        for plant in probe.resolved_plants:
            if not plant.answers:
                continue
            shared = question & _content_words(plant.text + " " + plant.reply)
            assert not shared, f"{probe_id} leaks {shared} to a lexical retriever"

    @pytest.mark.asyncio
    async def test_bm25_cannot_find_the_oblique_answer(self, pack):
        """The claim above, made against the actual control rather than a rule.

        The word-overlap test states the design intent; this states the
        consequence. If BM25 ranks the answering plant into a six-turn budget,
        the probe is not discriminating regardless of how its wording looks.
        """
        probes, filler = pack
        probe = next(p for p in probes if p.id == "oblique_dislike_d24")
        transcript = build_transcript(probe, filler)
        retriever = LexicalRetriever()
        await retriever.index(transcript)
        hits = await retriever.search(probe.recall_prompt, 6)
        assert not any("coriander" in hit.text for hit in hits)

    @pytest.mark.asyncio
    async def test_bm25_does_find_the_lexical_variant(self, pack):
        """The control that makes the oblique result attributable.

        Same seven near-identical facts, same distance, same budget -- only the
        wording of the question changes. Without this, a BM25 miss on the
        oblique probe could just as well mean a crowded field defeats it, and
        the comparison would say nothing about meaning.
        """
        probes, filler = pack
        probe = next(p for p in probes if p.id == "similars_lexical_d48")
        transcript = build_transcript(probe, filler)
        retriever = LexicalRetriever()
        await retriever.index(transcript)
        hits = await retriever.search(probe.recall_prompt, 6)
        assert any("halvard" in hit.text.lower() for hit in hits)

    def test_the_update_probes_place_the_correction_after_the_fact(self, pack):
        """Recency is the only thing that distinguishes them.

        Both plants name a job; if the correction were not strictly later, no
        retriever could be expected to prefer it and the probe would be asking
        for a coin flip.
        """
        probes, _ = pack
        for probe in probes:
            if not probe.id.startswith("update_"):
                continue
            answering = [p for p in probe.resolved_plants if p.answers]
            distractors = [p for p in probe.resolved_plants if not p.answers]
            assert answering and distractors
            assert min(p.after_filler for p in answering) > max(
                p.after_filler for p in distractors
            )

    def test_the_pack_is_valid_json_with_a_stated_rationale(self):
        """A pack whose probes cannot be justified will be misread as neutral."""
        data = json.loads(shipped_discriminating_pack().read_text(encoding="utf-8"))
        assert data["_comment"]
        assert data["filler"] and data["probes"]
