"""`evals rate-pairwise`: blinded pairwise human rating between two reports'
answers to the same probes -- HUMANOID_ARCHITECTURE_RESEARCH.md §17's
"Character voice... blinded human pairwise rating" requirement specifically,
which a single absolute score cannot substitute for. Driven through
`_cmd_rate_pairwise`'s injectable `input_fn`, no real stdin or live model.
"""

import argparse
import json

from evals.__main__ import _cmd_rate_pairwise
from evals.schema import EvalReport, ProbeResult, save_report


def _report(path, model, probe_id="p1", response="a response"):
    report = EvalReport(
        model=model,
        persona_name="Kavya",
        provenance="live",
        suite="single_turn",
        options={},
        results=[
            ProbeResult(
                probe_id=probe_id,
                category="custom",
                prompt="prompt",
                response=response,
                checks=[],
                passed=True,
                score=1.0,
            )
        ],
        by_category={},
    )
    save_report(report, str(path))
    return report


def _args(report_a, report_b, out, rater_id="tester", seed=None):
    return argparse.Namespace(
        report_a=str(report_a),
        report_b=str(report_b),
        out=str(out),
        rater_id=rater_id,
        seed=seed,
    )


def test_preference_maps_back_to_the_correct_report_despite_order_randomization(
    tmp_path,
):
    """The rater only ever sees "Response 1"/"Response 2", randomized per
    probe -- this is the core correctness property: whichever physical
    report the rater actually preferred must be the one recorded, not
    whichever slot happened to be shown first."""
    report_a = tmp_path / "a.json"
    report_b = tmp_path / "b.json"
    _report(report_a, "model-a", response="response from A")
    _report(report_b, "model-b", response="response from B")
    out = tmp_path / "pairwise.json"

    # Try many seeds so both presentation orders are exercised across runs.
    for seed in range(20):
        exit_code = _cmd_rate_pairwise(
            _args(report_a, report_b, out, seed=seed),
            input_fn=lambda _: "1",  # always prefer whichever is shown first
        )
        assert exit_code == 0

    recorded = json.loads(out.read_text())
    preferences = {rating["preferred"] for rating in recorded}
    # "1" was chosen every time, but which underlying report was shown as
    # "1" varies by seed -- both "a" and "b" must appear if order truly
    # randomizes, proving the mapping is order-aware, not always-"a".
    assert preferences == {"a", "b"}


def test_the_rater_never_sees_either_model_name(tmp_path, capsys):
    report_a = tmp_path / "a.json"
    report_b = tmp_path / "b.json"
    _report(report_a, "identifiable-model-a")
    _report(report_b, "identifiable-model-b")
    out = tmp_path / "pairwise.json"

    _cmd_rate_pairwise(
        _args(report_a, report_b, out, seed=0), input_fn=lambda _: ""
    )

    printed = capsys.readouterr().out
    assert "identifiable-model-a" not in printed
    assert "identifiable-model-b" not in printed


def test_tie_is_recorded_as_tie_not_forced_to_a_side(tmp_path):
    report_a = tmp_path / "a.json"
    report_b = tmp_path / "b.json"
    _report(report_a, "model-a")
    _report(report_b, "model-b")
    out = tmp_path / "pairwise.json"
    answers = iter(["tie", "no real difference"])

    _cmd_rate_pairwise(
        _args(report_a, report_b, out, seed=0), input_fn=lambda _: next(answers)
    )

    recorded = json.loads(out.read_text())
    assert recorded[0]["preferred"] == "tie"


def test_neither_input_report_is_modified(tmp_path):
    report_a = tmp_path / "a.json"
    report_b = tmp_path / "b.json"
    _report(report_a, "model-a")
    _report(report_b, "model-b")
    before_a = report_a.read_text()
    before_b = report_b.read_text()
    out = tmp_path / "pairwise.json"

    _cmd_rate_pairwise(
        _args(report_a, report_b, out, seed=0), input_fn=lambda _: "1"
    )

    assert report_a.read_text() == before_a
    assert report_b.read_text() == before_b


def test_ratings_append_to_an_existing_out_file_rather_than_overwriting(tmp_path):
    report_a = tmp_path / "a.json"
    report_b = tmp_path / "b.json"
    _report(report_a, "model-a", probe_id="p1")
    _report(report_b, "model-b", probe_id="p1")
    out = tmp_path / "pairwise.json"
    out.write_text(json.dumps([{"probe_id": "pre-existing", "preferred": "a"}]))

    _cmd_rate_pairwise(
        _args(report_a, report_b, out, seed=0), input_fn=lambda _: "1"
    )

    recorded = json.loads(out.read_text())
    assert len(recorded) == 2
    assert recorded[0]["probe_id"] == "pre-existing"


def test_only_shared_probe_ids_are_rated(tmp_path):
    report_a = tmp_path / "a.json"
    report_b = tmp_path / "b.json"
    _report(report_a, "model-a", probe_id="only-in-a")
    _report(report_b, "model-b", probe_id="only-in-b")
    out = tmp_path / "pairwise.json"

    exit_code = _cmd_rate_pairwise(
        _args(report_a, report_b, out, seed=0), input_fn=lambda _: "1"
    )

    assert exit_code == 2
    assert not out.exists()


def test_an_interrupted_session_still_saves_ratings_collected_so_far(tmp_path):
    report_a = tmp_path / "a.json"
    report_b = tmp_path / "b.json"
    r1 = _report(report_a, "model-a", probe_id="p1")
    save_report(
            EvalReport(
                model="model-a",
                persona_name="Kavya",
                provenance="live",
                suite="single_turn",
            options={},
            results=[
                *r1.results,
                ProbeResult(
                    probe_id="p2",
                    category="custom",
                    prompt="prompt2",
                    response="resp2",
                    checks=[],
                    passed=True,
                    score=1.0,
                ),
            ],
            by_category={},
        ),
        str(report_a),
    )
    r2 = _report(report_b, "model-b", probe_id="p1")
    save_report(
        EvalReport(
                model="model-b",
                persona_name="Kavya",
                provenance="live",
                suite="single_turn",
            options={},
            results=[
                *r2.results,
                ProbeResult(
                    probe_id="p2",
                    category="custom",
                    prompt="prompt2",
                    response="resp2-b",
                    checks=[],
                    passed=True,
                    score=1.0,
                ),
            ],
            by_category={},
        ),
        str(report_b),
    )
    out = tmp_path / "pairwise.json"
    answers = iter(["1"])  # only enough for the first shared probe

    def input_fn(_prompt):
        try:
            return next(answers)
        except StopIteration:
            raise EOFError from None

    exit_code = _cmd_rate_pairwise(
        _args(report_a, report_b, out, seed=0), input_fn=input_fn
    )

    assert exit_code == 0
    recorded = json.loads(out.read_text())
    assert len(recorded) == 1
