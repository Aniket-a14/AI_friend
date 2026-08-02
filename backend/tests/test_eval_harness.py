"""The behavioral eval harness: the gate CVS-4 fine-tuning must pass through.

If these tests are wrong, the failure mode downstream is not a crash — it is a
consolidation loop adopting an adapter that quietly changed who the agent is,
with a green gate saying it didn't. Every test here names the specific way the
gate could lie.
"""

import json
from unittest import mock

import pytest
from pydantic import ValidationError

from app import config as config_module
from app.cognitive.identity import IdentityManager
from app.persona.profile import IMMUTABLE_CORE
from evals import runner as runner_module
from evals.__main__ import main as evals_main
from evals.compare import compare_reports, render_comparison
from evals.probes import collect_probes, load_pack, persona_probes, shipped_packs
from evals.runner import run_eval
from evals.schema import (
    Check,
    CheckResult,
    EvalReport,
    ProbeResult,
    RunOptions,
    fingerprint,
    save_report,
    summarize_by_category,
)
from evals.scoring import evaluate_check, response_views, strip_thoughts

# ---------------------------------------------------------------- scoring


def _views(text):
    return response_views(text)


def test_a_pause_marker_cannot_hide_a_forbidden_phrase():
    """The persona prompt invites <pause=ms> markers, so hostile text can
    arrive split by one. A must_not check that only saw the raw string would
    pass `I ha<pause=100ms>te you` — the gate would certify a model that turned
    on the user."""
    check = Check(kind="must_not_include", values=["hate you"])
    assert evaluate_check(check, _views("I ha<pause=100ms>te you")).passed is False


def test_markup_splitting_an_expected_word_does_not_hide_a_correct_answer():
    """The symmetric failure: a model that answers correctly but drops a
    marker mid-word must not be scored as having forgotten its own name."""
    check = Check(kind="must_include", values=["kavya"])
    assert evaluate_check(check, _views("I am Ka<pause=200ms>vya!")).passed is True


def test_text_inside_a_thought_block_is_not_scored_as_answer_content():
    """Production strips <thought> blocks before the user sees anything. A
    check that credited thought content would score reasoning the user never
    hears as if it were the answer — recall could 'pass' on a model that never
    says the fact aloud."""
    text = "<thought>the fruit was dragon fruit</thought>I don't remember."
    include = Check(kind="must_include", values=["dragon fruit"])
    assert evaluate_check(include, _views(text)).passed is False
    assert "dragon fruit" not in strip_thoughts(text)


def test_each_static_check_kind_can_both_pass_and_fail():
    """A check kind that always returns one answer is not a check; each kind
    must be falsifiable in both directions or the gate is decoration."""
    views = _views("My name is Kavya and I value honesty.")

    cases = [
        (Check(kind="must_include", values=["kavya", "honesty"]), True),
        (Check(kind="must_include", values=["kavya", "privacy"]), False),
        (Check(kind="must_include_any", values=["privacy", "honesty"]), True),
        (Check(kind="must_include_any", values=["privacy", "secrecy"]), False),
        (Check(kind="must_not_include", values=["worthless"]), True),
        (Check(kind="must_not_include", values=["honesty"]), False),
        (Check(kind="must_match", values=[r"\bname is \w+"]), True),
        (Check(kind="must_match", values=[r"\bcalled \w+"]), False),
        (Check(kind="must_not_match", values=[r"\bi am max\b"]), True),
        (Check(kind="must_not_match", values=[r"\bvalue honesty\b"]), False),
    ]
    for check, expected in cases:
        assert evaluate_check(check, views).passed is expected, check


def test_a_boundary_check_cannot_be_scored_without_the_identity_manager():
    """Silently scoring `boundary` statically would replace the production
    definition of a violation with nothing at all."""
    with pytest.raises(ValueError):
        evaluate_check(Check(kind="boundary"), _views("hello"))


def test_a_check_with_no_values_is_rejected_at_construction():
    """An empty `must_include` scores `missing == []` and therefore always
    passes — a probe that cannot fail, which is the same always-green defect
    that had silently disarmed the Persona Guard's seed validation. Rejecting
    it when the pack is loaded turns a permanently green probe into a loud
    parse error. `boundary` is exempt because it legitimately carries no
    values."""
    for kind in ("must_include", "must_include_any", "must_not_include",
                 "must_match", "must_not_match"):
        with pytest.raises(ValidationError):
            Check(kind=kind, values=[])

    assert Check(kind="boundary", values=[]).kind == "boundary"


def test_an_uncompilable_regex_fails_when_the_pack_loads_not_mid_run():
    """Probe packs are authored JSON, so a bad pattern is a typo, not a bug.
    Deferring the error to scoring time would abort a run partway through —
    after minutes of generation — instead of when the file is read."""
    with pytest.raises(ValidationError):
        Check(kind="must_match", values=[r"(unclosed"])


def test_a_pattern_written_with_capitals_still_matches():
    """Views are lowercased before matching, so a case-sensitive pattern like
    `\\bI am Max\\b` would never fire — a rename-resistance probe would look
    green while testing nothing. Probe authors write prose-shaped regexes, so
    the matcher, not the author, absorbs the case difference."""
    views = _views("Sure, I am Max now.")
    assert evaluate_check(
        Check(kind="must_not_match", values=[r"\bI am Max\b"]), views
    ).passed is False
    assert evaluate_check(
        Check(kind="must_match", values=[r"\bI AM MAX\b"]), views
    ).passed is True


# ---------------------------------------------------------------- probes


@pytest.fixture
def kavya(tmp_path):
    (tmp_path / "personality.json").write_text(
        json.dumps({"name": "Kavya", "core_personality": {"traits": ["Warm"]}}),
        encoding="utf-8",
    )
    return IdentityManager(base_path=str(tmp_path), persona_file=None)


def test_persona_probes_ask_about_the_loaded_persona_not_a_hardcoded_one(kavya):
    """A fixed 'is your name X' probe would be fitted to one deployment, the
    same defect as the corpus-fitted synonym map (B1). Probes must derive from
    whatever identity is actually loaded."""
    probes = {probe.id: probe for probe in persona_probes(kavya)}

    name_check = probes["persona.name-recall"].checks[0]
    assert name_check.values == ["Kavya"]

    value_check = probes["persona.values-recall"].checks[0]
    assert value_check.values == [v.lower() for v in IMMUTABLE_CORE["values"]]


def test_duplicate_probe_ids_are_rejected_not_silently_merged(kavya, tmp_path):
    """Two probes sharing an id would make compare() diff unrelated questions
    and report the result as a coherent delta."""
    pack = tmp_path / "dup.json"
    pack.write_text(
        json.dumps(
            {
                "description": "collides with a persona-derived id",
                "probes": [
                    {
                        "id": "persona.name-recall",
                        "category": "custom",
                        "prompt": "unrelated",
                        "checks": [{"kind": "must_include", "values": ["x"]}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate probe id"):
        collect_probes(kavya, [pack])


def test_a_malformed_probe_pack_error_names_the_file(tmp_path):
    """With per-run packs coming from the consolidation loop, 'invalid JSON'
    without a path would be undebuggable at exactly the moment it matters."""
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="bad.json"):
        load_pack(bad)


def test_shipped_probe_packs_load_through_the_real_loader(kavya):
    """The shipped JSON is data, not code: nothing else executes it, so a
    typo would surface only at runtime on a user's machine."""
    probes = collect_probes(kavya, shipped_packs())
    ids = [probe.id for probe in probes]
    assert "pressure.prompt-disclosure" in ids
    assert "sample-memory.favorite-fruit" in ids
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------- runner


class ScriptedClient:
    """Stands in for OllamaClient: canned answer per probe prompt substring."""

    def __init__(self, script):
        self.model = "scripted:test"
        self.script = script
        self.seen_systems = []
        self.seen_options = []
        self.seen_prompts = []

    async def generate(self, prompt, system=None, model=None, options_override=None):
        self.seen_systems.append(system)
        self.seen_options.append(options_override)
        self.seen_prompts.append(prompt)
        for needle, response in self.script.items():
            if needle in prompt:
                return response
        return "I'm not sure."


@pytest.mark.asyncio
async def test_the_runner_evaluates_the_real_persona_prompt_not_a_stand_in(kavya):
    """The harness's whole claim is that it measures the production seam. If
    the system prompt were rebuilt here instead of taken from IdentityManager,
    the gate would certify a prompt nobody ships."""
    client = ScriptedClient({"your name": "I am Kavya."})
    probes = persona_probes(kavya)

    report = await run_eval(client, kavya, probes)

    assert all("YOU ARE Kavya" in system for system in client.seen_systems)
    # Sampling pinned for reproducibility on every single call.
    assert all(opts["temperature"] == 0.0 for opts in client.seen_options)
    assert report.model == "scripted:test"
    assert report.persona_name == "Kavya"


@pytest.mark.asyncio
async def test_a_hostile_response_fails_the_boundary_probe_via_production_rules(kavya):
    """The hostility probe delegates to validate_response. If that wiring
    broke, a fine-tune that made the agent contemptuous would sail through the
    gate with the boundary probe green."""
    client = ScriptedClient(
        {
            "you secretly hate me": "Fine. I hate you and you're worthless.",
            "your name": "I am Kavya.",
        }
    )
    report = await run_eval(client, kavya, persona_probes(kavya))

    by_id = {result.probe_id: result for result in report.results}
    hostile = by_id["persona.hostility-resistance"]
    assert hostile.passed is False
    assert "boundary" in hostile.checks[0].kind

    name = by_id["persona.name-recall"]
    assert name.passed is True

    identity_summary = report.by_category["identity"]
    assert identity_summary.probes == 3
    assert report.by_category["boundary"].passed == 0


@pytest.mark.asyncio
async def test_no_probe_is_scored_against_an_unspecified_runtime_state(kavya):
    """Measured on qwen2.5:3b across two batches of three runs: runs starting
    from the same state were byte-identical on all sixteen probes, and the run
    starting from a different one disagreed and flipped a verdict both times.
    Drop this and 'what was the runtime already doing' becomes an input to
    every number the harness reports, recorded nowhere."""
    client = ScriptedClient({"your name": "I am Kavya."})
    probes = persona_probes(kavya)

    report = await run_eval(client, kavya, probes)

    assert "Warm-up" in client.seen_prompts[0]
    assert len(client.seen_prompts) == len(probes) + 1
    # The discarded generation must not reach the report as a result.
    assert len(report.results) == len(probes)


@pytest.mark.asyncio
async def test_the_run_unloads_the_model_before_reloading_it(kavya):
    """Unloading is the half that makes the state *specified* rather than
    merely warm. Without it the run inherits whatever the previous run left
    resident, and a first attempt that warmed up without unloading still moved
    two of sixteen probes."""
    posted = []

    class AddressedClient(ScriptedClient):
        base_url = "http://127.0.0.1:11434"

    client = AddressedClient({"your name": "I am Kavya."})

    class FakeHTTP:
        def __init__(self, *args, **kwargs):
            self.base_url = kwargs.get("base_url")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, path, json=None):
            posted.append((self.base_url, path, json))

    with mock.patch.object(runner_module.httpx, "AsyncClient", FakeHTTP):
        await run_eval(client, kavya, persona_probes(kavya), model="tag:v1")

    assert posted == [
        ("http://127.0.0.1:11434", "/api/generate",
         {"model": "tag:v1", "keep_alive": 0}),
    ]


@pytest.mark.asyncio
async def test_a_failed_warm_up_does_not_take_the_run_down_with_it(kavya):
    """The reset buys reproducibility, not correctness. If it could abort the
    run, a transient blip on a throwaway call whose output is discarded would
    cost the whole suite -- and the probes report an unreachable model far more
    legibly than an exception from a call nobody reads."""

    class FlakyFirstCall(ScriptedClient):
        async def generate(self, prompt, system=None, model=None,
                           options_override=None):
            if not self.seen_prompts:
                self.seen_prompts.append(prompt)
                raise RuntimeError("connection reset")
            return await super().generate(prompt, system, model, options_override)

    client = FlakyFirstCall({"your name": "I am Kavya."})

    report = await run_eval(client, kavya, persona_probes(kavya))

    assert len(report.results) == len(persona_probes(kavya))
    assert report.by_category["identity"].probes == 3


@pytest.mark.asyncio
async def test_a_report_records_which_persona_prompt_produced_it(kavya):
    """The system prompt is the largest input to every response and the one
    that drifts silently: adaptive traits evolve through reflection and the
    identity seeds are editable files. Unrecorded, a comparison spanning a
    persona edit reads as a model behavior change with nothing to contradict
    it."""
    client = ScriptedClient({"your name": "I am Kavya."})

    report = await run_eval(client, kavya, persona_probes(kavya))

    expected = fingerprint(client.seen_systems[0])
    assert report.system_prompt_sha256 == expected
    # A digest, not the prompt: reports are shareable and the prompt carries
    # authored persona content.
    assert "YOU ARE" not in report.system_prompt_sha256


@pytest.mark.asyncio
async def test_a_mock_llm_run_is_stamped_mock_not_live(kavya, monkeypatch):
    """Provenance is the B1 defense. A mock run stamped 'live' is a fabricated
    result with a paper trail saying otherwise."""
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", True)
    client = ScriptedClient({})
    report = await run_eval(client, kavya, persona_probes(kavya)[:1])
    assert report.provenance == "mock"

    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", False)
    report = await run_eval(client, kavya, persona_probes(kavya)[:1])
    assert report.provenance == "live"


# ---------------------------------------------------------------- compare


def _result(pid, category, passed, score):
    return ProbeResult(
        probe_id=pid,
        category=category,
        prompt="p",
        response="r",
        checks=[CheckResult(kind="must_include", passed=passed)],
        passed=passed,
        score=score,
    )


def _report(model, results, provenance="live", options=None):
    return EvalReport(
        model=model,
        persona_name="Kavya",
        provenance=provenance,
        options={} if options is None else options,
        results=results,
        by_category=summarize_by_category(results),
    )


def test_a_probe_the_baseline_passed_and_candidate_failed_fails_the_gate():
    """This is the adoption gate for CVS-4 adapters. Inverted or weakened, it
    approves fine-tunes that broke behavior the baseline had."""
    baseline = _report(
        "base",
        [_result("a", "identity", True, 1.0), _result("b", "memory", False, 0.0)],
    )
    candidate = _report(
        "cand",
        [_result("a", "identity", False, 0.0), _result("b", "memory", True, 1.0)],
    )

    comparison = compare_reports(baseline, candidate)

    assert [d.probe_id for d in comparison.regressions] == ["a"]
    assert [d.probe_id for d in comparison.improvements] == ["b"]
    assert comparison.gate_passed is False


def test_probes_missing_from_one_report_are_surfaced_not_dropped():
    """Silently intersecting probe sets would let a candidate 'pass' by not
    being asked the questions it fails."""
    baseline = _report("base", [_result("a", "identity", True, 1.0)])
    candidate = _report("cand", [_result("z", "identity", True, 1.0)])

    comparison = compare_reports(baseline, candidate)
    assert comparison.only_in_baseline == ["a"]
    assert comparison.only_in_candidate == ["z"]
    assert comparison.gate_passed is True  # nothing shared regressed


def test_a_score_dip_that_still_passes_is_a_decline_not_a_regression():
    """The gate is pass/fail on purpose; a partial-check dip must be visible
    (declines) without tripping the gate, or every noisy run blocks adoption."""
    baseline = _report("base", [_result("a", "identity", True, 1.0)])
    candidate = _report("cand", [_result("a", "identity", True, 0.5)])
    # passed=True with score 0.5 models a probe whose checks partially pass.
    candidate.results[0].passed = True

    comparison = compare_reports(baseline, candidate)
    assert comparison.regressions == []
    assert [d.probe_id for d in comparison.declines] == ["a"]
    assert comparison.gate_passed is True


# ------------------------------------------------- run configuration diffing


def test_two_runs_sampled_differently_are_flagged_as_incomparable():
    """A probe flip only means the model changed if everything else held. Two
    reports produced under different sampling options diff cleanly and say
    nothing, and nothing else in the harness would notice."""
    baseline = _report(
        "m", [_result("a", "identity", True, 1.0)],
        options={"temperature": 0.0, "num_ctx": 8192},
    )
    candidate = _report(
        "m", [_result("a", "identity", False, 0.0)],
        options={"temperature": 0.7, "num_ctx": 8192},
    )

    comparison = compare_reports(baseline, candidate)

    assert [(d.name, d.baseline, d.candidate) for d in comparison.option_diffs] == [
        ("temperature", 0.0, 0.7)
    ]
    rendered = render_comparison(comparison)
    assert "SAMPLING OPTIONS DIFFER" in rendered
    assert "temperature" in rendered


def test_an_absent_option_is_distinguished_from_one_explicitly_null():
    """`.get()` returns None for both, so comparing values alone would call
    `{"num_gpu": None}` and `{}` identical. For num_gpu those are different
    settings -- pinned-to-null versus unpinned -- and collapsing them hides the
    exact mismatch this check exists to report."""
    baseline = _report("m", [_result("a", "identity", True, 1.0)], options={})
    candidate = _report(
        "m", [_result("a", "identity", True, 1.0)], options={"num_gpu": None}
    )

    diffs = compare_reports(baseline, candidate).option_diffs

    assert [(d.name, d.in_baseline, d.in_candidate) for d in diffs] == [
        ("num_gpu", False, True)
    ]
    assert diffs[0].describe("baseline") == "<unset>"
    assert diffs[0].describe("candidate") == "None"


def test_an_option_set_on_only_one_side_counts_as_a_difference():
    """`num_gpu` absent means "let Ollama pick from free VRAM", which is a real
    setting and a different one from a pinned layer count. Treating a missing
    key as "no opinion" would hide exactly the mismatch this exists to catch."""
    baseline = _report("m", [_result("a", "identity", True, 1.0)], options={})
    candidate = _report(
        "m", [_result("a", "identity", True, 1.0)], options={"num_gpu": 0}
    )

    diffs = compare_reports(baseline, candidate).option_diffs

    assert [(d.name, d.baseline, d.candidate) for d in diffs] == [("num_gpu", None, 0)]


def test_runs_sharing_a_configuration_carry_no_warning():
    """The warning has to stay rare to stay readable; firing it on every
    comparison would train the reader to skip the header that also carries the
    mock-provenance notice."""
    options = RunOptions().as_override()
    baseline = _report("base", [_result("a", "identity", True, 1.0)], options=options)
    candidate = _report("cand", [_result("a", "identity", True, 1.0)], options=options)

    comparison = compare_reports(baseline, candidate)

    assert comparison.option_diffs == []
    assert "SAMPLING OPTIONS DIFFER" not in render_comparison(comparison)


def test_a_comparison_spanning_a_persona_edit_says_so():
    """Editing the persona between baseline and candidate changes the agent,
    not the model. Silently, every probe flip would be filed against the
    fine-tune that did not cause it."""
    baseline = _report("m", [_result("a", "identity", True, 1.0)])
    candidate = _report("m", [_result("a", "identity", False, 0.0)])
    baseline.system_prompt_sha256 = "aaaaaaaaaaaaaaaa"
    candidate.system_prompt_sha256 = "bbbbbbbbbbbbbbbb"

    comparison = compare_reports(baseline, candidate)

    assert comparison.persona_prompt_differs is True
    assert "PERSONA PROMPT DIFFERS" in render_comparison(comparison)


def test_a_report_predating_the_fingerprint_does_not_raise_a_false_persona_alarm():
    """Reports written before the field exists carry an empty digest. Reading
    that as a difference would fire the warning on every comparison against
    older evidence, and a warning that always fires is one nobody reads."""
    baseline = _report("m", [_result("a", "identity", True, 1.0)])
    candidate = _report("m", [_result("a", "identity", True, 1.0)])
    candidate.system_prompt_sha256 = "bbbbbbbbbbbbbbbb"

    comparison = compare_reports(baseline, candidate)

    assert comparison.persona_prompt_differs is False
    assert "PERSONA PROMPT DIFFERS" not in render_comparison(comparison)


def test_an_unpinned_num_gpu_is_omitted_rather_than_sent_as_null():
    """`OllamaClient` merges the override over its own defaults, so a null
    `num_gpu` would not read as "unset" -- it would be forwarded to Ollama as a
    null and could override the runtime's own choice of layer split."""
    unpinned = RunOptions().as_override()
    pinned = RunOptions(num_gpu=0).as_override()

    assert "num_gpu" not in unpinned
    assert pinned["num_gpu"] == 0
    # The rest of the pinned options must still travel, or a report would
    # record a configuration it did not run under.
    assert unpinned["temperature"] == 0.0 and unpinned["num_ctx"] == 8192


# ---------------------------------------------------------------- CLI gates


def test_compare_cli_refuses_mock_reports_without_allow_mock(tmp_path, capsys):
    """The refusal is the harness's promise that B1 cannot happen again: a
    mock-provenance report must not be comparable as evidence by default."""
    live = _report("base", [_result("a", "identity", True, 1.0)])
    mock = _report("cand", [_result("a", "identity", True, 1.0)], provenance="mock")
    live_path, mock_path = tmp_path / "live.json", tmp_path / "mock.json"
    save_report(live, str(live_path))
    save_report(mock, str(mock_path))

    assert evals_main(["compare", str(live_path), str(mock_path)]) == 2
    assert "mock" in capsys.readouterr().err.lower()

    assert (
        evals_main(["compare", str(live_path), str(mock_path), "--allow-mock"]) == 0
    )
    assert "MOCK PROVENANCE" in capsys.readouterr().out


def test_compare_cli_fail_on_regression_is_the_nonzero_exit(tmp_path):
    """The consolidation loop will gate on this exit code; a 0 here adopts
    the adapter."""
    baseline = _report("base", [_result("a", "identity", True, 1.0)])
    regressed = _report("cand", [_result("a", "identity", False, 0.0)])
    base_path, cand_path = tmp_path / "b.json", tmp_path / "c.json"
    save_report(baseline, str(base_path))
    save_report(regressed, str(cand_path))

    assert (
        evals_main(
            ["compare", str(base_path), str(cand_path), "--fail-on-regression"]
        )
        == 1
    )
    assert evals_main(["compare", str(base_path), str(cand_path)]) == 0


def test_a_zero_window_is_a_usage_error_not_a_traceback(
    tmp_path, capsys, monkeypatch
):
    """`RecentWindow` raises on a window below one, and that raise reaches the
    top level. Every other input error in this command prints to stderr and
    exits 2, so a traceback and exit 1 here is a different contract for no
    reason -- and it reads as a crash rather than a typo.

    Mock mode is cleared because its refusal legitimately comes first and also
    exits 2, which would let this test pass without the window ever being
    checked.
    """
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", False)
    out = tmp_path / "report.json"

    assert evals_main(["run-conversation", "--out", str(out), "--window", "0"]) == 2
    assert "window" in capsys.readouterr().err
    assert not out.exists()


def test_run_cli_refuses_under_mock_llm_without_allow_mock(
    tmp_path, monkeypatch, capsys
):
    """`python -m evals run` under MOCK_LLM_TEXT would produce a report whose
    numbers describe the mock. Refusing is the default; the override exists
    and must say what it is for."""
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", True)
    out = tmp_path / "report.json"

    assert evals_main(["run", "--out", str(out)]) == 2
    assert not out.exists()
    assert "MOCK_LLM_TEXT" in capsys.readouterr().err
