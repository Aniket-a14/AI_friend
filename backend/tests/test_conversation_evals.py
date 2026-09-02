"""Tests for the multi-turn recall harness.

This suite measures whether a fact survives the distance to the question it
answers -- the problem the whole memory architecture exists to solve. The
failure that matters most is not a probe returning the wrong verdict; it is a
probe that returns a *confident* verdict while measuring nothing, because the
planted fact was never in the context, or the filler contained the answer, or
two strategies collided under one id. A broken instrument reads as a result.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from evals.conversation import (
    DEFAULT_STRATEGIES,
    FullHistory,
    RecentWindow,
    Turn,
    build_transcript,
    context_fits,
    estimate_tokens,
    load_conversation_pack,
    render_context,
    run_conversation_eval,
    run_conversation_probe,
    shipped_conversation_pack,
)
from evals.schema import Check, ConversationProbe, RunOptions

FILLER = [
    ("what's the weather doing", "grey. same as yesterday."),
    ("did you eat yet", "not yet. probably later."),
]


def make_probe(**overrides) -> ConversationProbe:
    base = {
        "id": "recall_name",
        "plant": "my youngest sister is called Wren.",
        "plant_reply": "Wren. noted.",
        "filler_turns": 4,
        "recall_prompt": "what's my youngest sister called again?",
        "checks": [Check(kind="must_include", values=["wren"])],
    }
    base.update(overrides)
    return ConversationProbe(**base)


class TestTheTranscriptIsReproducible:
    def test_filler_cycles_rather_than_samples(self):
        """Two runs of one probe must produce byte-identical context.

        Random filler would make every rerun a different measurement, so a
        score change between two model versions -- the only thing this harness
        exists to detect -- could not be attributed to the model.
        """
        probe = make_probe(filler_turns=6)
        first = build_transcript(probe, FILLER)
        second = build_transcript(probe, FILLER)
        assert first == second

    def test_the_plant_comes_first(self):
        """A fact planted after the filler has no distance to survive."""
        turns = build_transcript(make_probe(), FILLER)
        assert turns[0] == Turn("user", "my youngest sister is called Wren.")

    def test_distance_is_what_the_probe_varies(self):
        """filler_turns is the independent variable of the entire suite."""
        near = build_transcript(make_probe(filler_turns=2), FILLER)
        far = build_transcript(make_probe(filler_turns=20), FILLER)
        assert len(far) - len(near) == 36  # 18 extra exchanges, two turns each

    def test_a_pack_with_no_filler_is_rejected(self):
        """Silently producing a zero-distance transcript would score as recall.

        Every probe would pass, at every stated distance, and the report would
        claim the model remembers everything.
        """
        with pytest.raises(ValueError):
            build_transcript(make_probe(), [])


class TestContextStrategies:
    @pytest.mark.asyncio
    async def test_full_history_shows_the_plant(self):
        turns = build_transcript(make_probe(filler_turns=50), FILLER)
        visible = await FullHistory().select(turns, "q")
        assert any("Wren" in turn.text for turn in visible)

    @pytest.mark.asyncio
    async def test_a_narrow_window_drops_the_plant(self):
        """The control condition, and it is supposed to fail.

        Once the plant falls outside the window the fact is genuinely absent,
        so a pass under this strategy means the model guessed the answer and
        the probe is measuring the prior, not recall.
        """
        turns = build_transcript(make_probe(filler_turns=50), FILLER)
        visible = await RecentWindow(6).select(turns, "q")
        assert len(visible) == 6
        assert not any("Wren" in turn.text for turn in visible)

    @pytest.mark.asyncio
    async def test_a_window_wider_than_the_conversation_keeps_everything(self):
        turns = build_transcript(make_probe(filler_turns=1), FILLER)
        assert await RecentWindow(100).select(turns, "q") == turns

    def test_a_zero_width_window_is_rejected(self):
        """An empty context scores the model's prior with no conversation at all."""
        with pytest.raises(ValueError):
            RecentWindow(0)

    def test_strategies_are_named_distinctly(self):
        """Names become part of probe ids, so a collision merges two conditions."""
        names = [strategy.name for strategy in DEFAULT_STRATEGIES]
        assert len(names) == len(set(names))


class TestScoringAProbe:
    @pytest.fixture
    def manager(self):
        manager = MagicMock()
        manager.validate_response = AsyncMock(return_value=(True, ""))
        return manager

    async def _run(self, manager, response: str, strategy, probe=None):
        client = AsyncMock()
        client.generate.return_value = response
        return await run_conversation_probe(
            client,
            manager,
            probe or make_probe(filler_turns=50),
            FILLER,
            strategy,
            "system",
            "model",
            RunOptions(),
        )

    @pytest.mark.asyncio
    async def test_recalling_the_fact_passes(self, manager):
        result = await self._run(manager, "Wren, right?", FullHistory())
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_missing_the_fact_fails(self, manager):
        result = await self._run(manager, "I don't think you said.", FullHistory())
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_the_probe_id_records_the_strategy(self, manager):
        """Unqualified ids collide inside one report.

        `compare` aligns two reports by probe_id. If the same probe ran under
        two strategies with one id, the comparison would diff the wrong pair
        and report a regression that never happened.
        """
        result = await self._run(manager, "Wren.", RecentWindow(6))
        assert result.probe_id == "recall_name@recent_window_6"

    @pytest.mark.asyncio
    async def test_a_pass_without_the_fact_is_flagged_unsound(self, manager):
        """The one result that must never be counted as recall.

        With the plant outside the window the model cannot have remembered
        anything; a pass means it guessed a common name. Recording
        plant_visible is what lets the report say so instead of banking it.
        """
        result = await self._run(manager, "Wren.", RecentWindow(6))
        assert result.passed is True
        assert result.plant_visible is False

    @pytest.mark.asyncio
    async def test_the_context_reaches_the_model(self, manager):
        """The transcript has to actually be in the prompt.

        If the harness generated from the recall question alone, every probe
        would be scoring the model's prior over sister names and the distance
        column would be decorative.
        """
        client = AsyncMock()
        client.generate.return_value = "Wren."
        await run_conversation_probe(
            client,
            manager,
            make_probe(filler_turns=4),
            FILLER,
            FullHistory(),
            "system",
            "model",
            RunOptions(),
        )
        prompt = client.generate.await_args.kwargs["prompt"]
        assert "Wren" in prompt
        assert prompt.rstrip().endswith("Assistant:")


class TestAPackCannotCollideWithItself:
    def test_two_probes_sharing_an_id_are_rejected_at_load(self, tmp_path):
        """`compare_reports` keys on `id@strategy`, so a duplicate id makes one
        result overwrite the other and the comparison silently diffs the wrong
        pair. The single-turn loader already refuses this; a pack arriving
        through --pack must not be the way it gets in."""
        pack = tmp_path / "dupes.json"
        probe = {
            "id": "recall_name",
            "plant": "my sister is Wren.",
            "filler_turns": 2,
            "recall_prompt": "what is her name?",
            "checks": [{"kind": "must_include", "values": ["wren"]}],
        }
        pack.write_text(
            json.dumps({"filler": [["a", "b"]], "probes": [probe, probe]}),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="duplicate probe id"):
            load_conversation_pack(pack)


class TestTheRunStartsFromAKnownState:
    @pytest.fixture
    def manager(self):
        manager = MagicMock()
        manager.validate_response = AsyncMock(return_value=(True, ""))
        manager.get_persona_prompt.return_value = "SYSTEM"
        manager.persona.name = "Kavya"
        return manager

    @pytest.mark.asyncio
    async def test_the_suite_warms_the_model_before_the_first_probe(self, manager):
        """This suite is where the cold-start difference was measured: three
        identical runs, one cold and two warm, agreed byte-for-byte on the warm
        pair and diverged on three of sixteen probes in the cold one. Without
        the warm-up, whether the model happened to be resident becomes an
        unrecorded input to every recall number.
        """
        client = AsyncMock()
        client.generate.return_value = "Wren."
        client.model = "scripted:test"
        # No address, so the reset skips the unload rather than trying to
        # reach a real Ollama from a unit test.
        client.base_url = None

        report = await run_conversation_eval(
            client,
            manager,
            [make_probe(filler_turns=4)],
            FILLER,
            strategies=(FullHistory(),),
        )

        first_prompt = client.generate.await_args_list[0].kwargs["prompt"]
        assert "Warm-up" in first_prompt
        # One warm-up plus one generation per probe-strategy pair, and the
        # discarded one must not reach the report.
        assert client.generate.await_count == 2
        assert len(report.results) == 1


class TestTheShippedPack:
    def test_the_pack_loads(self):
        probes, filler = load_conversation_pack(shipped_conversation_pack())
        assert probes and filler

    def test_the_filler_never_contains_an_answer(self):
        """A probe that the filler answers is not measuring recall at all.

        This is the quietest way for the suite to become worthless: the model
        reads the answer out of nearby chatter, every probe passes at every
        distance, and the report says memory is solved.
        """
        probes, filler = load_conversation_pack(shipped_conversation_pack())
        filler_text = " ".join(
            f"{user} {assistant}" for user, assistant in filler
        ).lower()
        for probe in probes:
            for check in probe.checks:
                for value in check.values:
                    assert value.lower() not in filler_text, (
                        f"{probe.id}: filler contains the answer {value!r}"
                    )

    def test_the_pack_spans_distances(self):
        """One distance gives a pass/fail; several give the point it breaks."""
        probes, _ = load_conversation_pack(shipped_conversation_pack())
        assert len({probe.filler_turns for probe in probes}) >= 3

    def test_probes_are_stamped_with_their_pack(self):
        """A report has to be auditable without the pack files at hand."""
        probes, _ = load_conversation_pack(shipped_conversation_pack())
        assert all(probe.source == "conversation_recall.json" for probe in probes)

    def test_probe_ids_are_unique(self):
        """Duplicate ids silently overwrite each other in a comparison."""
        probes, _ = load_conversation_pack(shipped_conversation_pack())
        ids = [probe.id for probe in probes]
        assert len(ids) == len(set(ids))

    def test_every_probe_guards_against_a_disclaimed_answer(self):
        """A substring check alone scores a denial of recall as recall.

        Observed on a live 3B run: asked what the user could not eat, the model
        replied "I'm not sure what you're referring to, but if you mentioned
        walnuts earlier..." -- containing the answer while denying knowing it.
        `must_include` passed, and the suite reported memory the model did not
        have. Every recall probe needs the negative guard, or the number it
        produces is an artifact of the phrasing.
        """
        probes, _ = load_conversation_pack(shipped_conversation_pack())
        for probe in probes:
            kinds = {check.kind for check in probe.checks}
            assert "must_not_match" in kinds, (
                f"{probe.id} can pass on a disclaimed answer"
            )

    def test_the_disclaimer_guard_catches_the_observed_false_pass(self):
        """Pin the exact response that got through, so the guard cannot regress."""
        from evals.scoring import evaluate_check, response_views

        probes, _ = load_conversation_pack(shipped_conversation_pack())
        probe = next(p for p in probes if p.id == "recall_detail_d240")
        observed = (
            "I'm not sure what you're referring to, but if you have specific "
            "dietary restrictions or allergies, I'd be happy to help address "
            "those. For instance, if you mentioned walnuts earlier, we've "
            "already discussed that."
        )
        views = response_views(observed)
        assert not all(evaluate_check(check, views).passed for check in probe.checks)

    def test_a_typographic_apostrophe_does_not_slip_past_the_guard(self):
        """Small models emit both apostrophe forms, and this one was observed
        doing it: two runs of the same probe produced "What's her name?" and
        "What’s her name?" from identical input. A guard written with a bare
        `'?` makes only U+0027 optional, so the U+2019 spelling of the very
        same disclaimer walks through and the probe reports recall the model
        explicitly denied."""
        from evals.scoring import evaluate_check, response_views

        probes, _ = load_conversation_pack(shipped_conversation_pack())
        probe = next(p for p in probes if p.id == "recall_detail_d240")
        # Deliberately phrased so the *only* guard that can fire is one
        # carrying an apostrophe: "if you mentioned" and the other guards have
        # none, and would catch this sentence whatever the apostrophe class
        # does. It still contains "walnut", so must_include passes and the
        # probe hangs entirely on the negative guard.
        curly = "I don’t recall walnuts coming up."
        straight = "I don't recall walnuts coming up."

        for text in (curly, straight):
            views = response_views(text)
            assert not all(
                evaluate_check(check, views).passed for check in probe.checks
            ), f"disclaimer slipped through: {text!r}"

    def test_the_single_turn_loader_does_not_see_conversation_packs(self):
        """The two suites share a directory tree but not a file format.

        `shipped_packs()` globs ``probes/*.json`` and validates every hit as a
        single-turn `ProbePack`. A conversation pack sitting beside them makes
        the *other* suite fail at load time -- `python -m evals run` stops
        working entirely, for a file it never wanted.
        """
        from evals.probes import shipped_packs

        assert shipped_conversation_pack() not in shipped_packs()
        assert all("conversation" not in path.name for path in shipped_packs())


class TestTheContextWindowIsAccountedFor:
    """The quietest way this harness could produce a wrong published number.

    Ollama truncates an over-long prompt from the *front* -- which for a
    recall probe is exactly where the planted fact sits. Without this
    accounting, a 240-turn probe would report a clean failure that says
    nothing about the model's memory, because the model never received the
    fact at all. The harness pins `num_ctx` explicitly rather than trusting
    `OllamaClient`'s own default (`Config.LLM_NUM_CTX`, 8192 as of Bucket
    6.1) precisely so this accounting can't be silently invalidated by a
    future deployment-config change.
    """

    def test_num_ctx_is_pinned_rather_than_inherited(self):
        """Leaving it unset would tie every probe's fit budget to whatever
        Config.LLM_NUM_CTX happens to be in the deployment running the
        harness, instead of a value the report can vouch for on its own."""
        assert RunOptions().num_ctx >= 8192
        assert "num_ctx" in RunOptions().as_override()

    def test_an_oversized_context_is_reported_as_not_fitting(self):
        big = "x" * 100_000
        assert context_fits(big, "", RunOptions(num_ctx=1024)) is False

    def test_an_ordinary_context_fits(self):
        assert context_fits("User: hi\nAssistant: hey", "sys", RunOptions()) is True

    def test_the_system_prompt_counts_against_the_window(self):
        """A long persona prompt is part of what crowds the plant out.

        Scoring only the transcript would call a context sound while the
        persona block pushed it past the limit.
        """
        transcript = "x" * 3000  # ~1000 estimated tokens
        options = RunOptions(num_ctx=4096, num_predict=192)
        assert context_fits(transcript, "", options) is True
        assert context_fits(transcript, "y" * 12_000, options) is False

    def test_the_generation_reserve_counts_against_the_window_too(self):
        """`num_predict` shares the window with the prompt.

        Omitting it gives the worst answer this check can give: a probe that
        fits on arrival, then loses the plant to front-truncation partway
        through generation, and reports `fits yes` while doing it. Sized so the
        prompt alone clears num_ctx and only the reserve pushes it over.
        """
        transcript = "x" * 3000  # ~1000 estimated tokens
        options = RunOptions(num_ctx=1100, num_predict=192)

        assert estimate_tokens(transcript) < options.num_ctx
        assert context_fits(transcript, "", options) is False
        # Same prompt, same window, no reserve to make room for: it fits.
        assert (
            context_fits(transcript, "", options.model_copy(update={"num_predict": 0}))
            is True
        )

    def test_the_token_estimate_errs_toward_too_long(self):
        """A false all-clear is the expensive direction of this error.

        Over-counting costs a rerun with a bigger window. Under-counting means
        publishing a recall figure the model was never given a chance to earn.
        """
        text = "a" * 400  # ~100 real tokens for English
        assert estimate_tokens(text) > 100

    @pytest.mark.asyncio
    async def test_a_truncated_probe_is_marked_on_the_result(self):
        manager = MagicMock()
        manager.validate_response = AsyncMock(return_value=(True, ""))
        client = AsyncMock()
        client.generate.return_value = "Wren."

        result = await run_conversation_probe(
            client,
            manager,
            make_probe(filler_turns=400),
            FILLER,
            FullHistory(),
            "system",
            "model",
            RunOptions(num_ctx=256),
        )
        assert result.context_fits is False


class TestRendering:
    def test_speakers_are_labelled(self):
        rendered = render_context([Turn("user", "hi"), Turn("assistant", "hey")])
        assert rendered == "User: hi\nAssistant: hey"


class TestAPackAuthorCanSupplyTheirOwn:
    def test_an_external_pack_is_stamped_with_its_own_name(self, tmp_path):
        """Content belongs to whoever authors the pack, not to this module.

        Filler and probes are data precisely so a different project can
        measure recall over its own conversations without editing production
        code.
        """
        pack = tmp_path / "mine.json"
        pack.write_text(
            json.dumps(
                {
                    "filler": [["a", "b"]],
                    "probes": [
                        {
                            "id": "p1",
                            "plant": "the code is 4417.",
                            "filler_turns": 1,
                            "recall_prompt": "what was the code?",
                            "checks": [{"kind": "must_include", "values": ["4417"]}],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        probes, filler = load_conversation_pack(pack)
        assert probes[0].source == "mine.json"
        assert filler == [("a", "b")]
