"""`evals rate`: blinded absolute human rating of one report's responses
(HUMANOID_ARCHITECTURE_RESEARCH.md Phase 0 / §17's human-rating requirement).
Driven through `_cmd_rate`'s injectable `input_fn` rather than real stdin,
the same reason a stand-in client is injectable elsewhere in this harness --
these tests run with no terminal and no live model.
"""

import argparse

from evals.__main__ import _cmd_rate
from evals.schema import EvalReport, ProbeResult, load_report, save_report


def _report(path, model="secret-model-name", probe_ids=("p1", "p2")):
    report = EvalReport(
        model=model,
        persona_name="Kavya",
        provenance="live",
        options={},
        results=[
            ProbeResult(
                probe_id=pid,
                category="custom",
                prompt=f"prompt for {pid}",
                response=f"response for {pid}",
                checks=[],
                passed=True,
                score=1.0,
            )
            for pid in probe_ids
        ],
        by_category={},
    )
    save_report(report, str(path))
    return report


def _args(report_path, rater_id="tester"):
    return argparse.Namespace(report=str(report_path), rater_id=rater_id)


def test_rating_is_written_back_to_the_same_report(tmp_path):
    path = tmp_path / "report.json"
    _report(path)
    answers = iter(["5", "great", "3", "so-so"])

    exit_code = _cmd_rate(_args(path), input_fn=lambda _: next(answers))

    assert exit_code == 0
    restored = load_report(str(path))
    assert len(restored.human_ratings) == 2
    assert restored.human_ratings[0].character_fidelity == 5
    assert restored.human_ratings[0].notes == "great"
    assert restored.human_ratings[1].character_fidelity == 3


def test_the_rater_never_sees_the_model_name(tmp_path, capsys):
    path = tmp_path / "report.json"
    _report(path, model="a-very-identifiable-model-tag")
    answers = iter(["", ""])  # skip both probes

    _cmd_rate(_args(path), input_fn=lambda _: next(answers))

    out = capsys.readouterr().out
    assert "a-very-identifiable-model-tag" not in out


def test_blank_input_skips_a_probe_without_recording_anything(tmp_path):
    path = tmp_path / "report.json"
    _report(path)
    answers = iter(["", "4", "note"])

    _cmd_rate(_args(path), input_fn=lambda _: next(answers))

    restored = load_report(str(path))
    assert len(restored.human_ratings) == 1
    assert restored.human_ratings[0].probe_id == "p2"


def test_an_out_of_range_score_skips_the_probe_rather_than_raising(tmp_path):
    path = tmp_path / "report.json"
    _report(path, probe_ids=("p1",))
    answers = iter(["9"])

    exit_code = _cmd_rate(_args(path), input_fn=lambda _: next(answers))

    assert exit_code == 0
    restored = load_report(str(path))
    assert restored.human_ratings == []


def test_a_non_integer_score_skips_the_probe_rather_than_raising(tmp_path):
    path = tmp_path / "report.json"
    _report(path, probe_ids=("p1",))
    answers = iter(["five"])

    exit_code = _cmd_rate(_args(path), input_fn=lambda _: next(answers))

    assert exit_code == 0
    restored = load_report(str(path))
    assert restored.human_ratings == []


def test_an_interrupted_session_still_saves_ratings_collected_so_far(tmp_path):
    """A real session is far more often interrupted (Ctrl-D/Ctrl-C) than run
    to completion. Losing already-collected ratings to an uncaught EOFError
    would defeat the whole point of rating incrementally."""
    path = tmp_path / "report.json"
    _report(path, probe_ids=("p1", "p2", "p3"))

    answers = iter(["5", "first rating"])  # exhausted before p2's prompt

    def input_fn(_prompt):
        # Real `input()` raises EOFError on exhausted stdin, not
        # StopIteration -- match that exactly, since that's the real
        # exception `_cmd_rate` has to survive.
        try:
            return next(answers)
        except StopIteration:
            raise EOFError from None

    exit_code = _cmd_rate(_args(path), input_fn=input_fn)

    assert exit_code == 0
    restored = load_report(str(path))
    assert len(restored.human_ratings) == 1
    assert restored.human_ratings[0].probe_id == "p1"


def test_a_session_interrupted_during_the_notes_prompt_still_saves_the_score(
    tmp_path,
):
    """A finer-grained case than a whole-probe interrupt: the score was
    already given, and only the *notes* prompt that follows it gets cut off.
    That score must not be thrown away along with the notes it never got --
    the rater already did the part that matters."""
    path = tmp_path / "report.json"
    _report(path, probe_ids=("p1",))
    answers = iter(["5"])  # score given; notes prompt has nothing left

    def input_fn(_prompt):
        try:
            return next(answers)
        except StopIteration:
            raise EOFError from None

    exit_code = _cmd_rate(_args(path), input_fn=input_fn)

    assert exit_code == 0
    restored = load_report(str(path))
    assert len(restored.human_ratings) == 1
    assert restored.human_ratings[0].character_fidelity == 5
    assert restored.human_ratings[0].notes == ""


def test_rater_id_is_stamped_from_the_cli_argument(tmp_path):
    path = tmp_path / "report.json"
    _report(path, probe_ids=("p1",))
    answers = iter(["5", ""])

    _cmd_rate(_args(path, rater_id="specific-rater"), input_fn=lambda _: next(answers))

    restored = load_report(str(path))
    assert restored.human_ratings[0].rater_id == "specific-rater"
