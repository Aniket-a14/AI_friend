import json

from app.llm.adapter_registry import (
    AdapterRecord,
    load_adapter_record,
    save_adapter_record,
)
from evals.compare import compare_reports
from evals.schema import CheckResult, EvalReport, ProbeResult, summarize_by_category


def _report(model: str, passed: bool = True) -> EvalReport:
    result = ProbeResult(
        probe_id="probe-1",
        category="identity",
        prompt="hello",
        response="hi",
        checks=[CheckResult(kind="must_include", passed=passed)],
        passed=passed,
        score=1.0 if passed else 0.0,
    )
    return EvalReport(
        model=model,
        persona_name="Kavya",
        provenance="live",
        suite="single_turn",
        options={},
        results=[result],
        by_category=summarize_by_category([result]),
    )


def test_adapter_record_round_trips_as_json(tmp_path):
    record = AdapterRecord(
        version="adapter-v1",
        training_set_hash="train-sha",
        base_model_hash="base-sha",
        regression_report_path="evals/out/adapter-v1.json",
        rollback_pointer="base-model",
    )
    path = tmp_path / "registry" / "adapter-v1.json"

    save_adapter_record(record, path)

    assert json.loads(path.read_text(encoding="utf-8")) == record.model_dump()
    assert load_adapter_record(path) == record


def test_optional_adapter_record_does_not_change_gate_without_record():
    baseline = _report("base")
    candidate = _report("candidate")

    without_record = compare_reports(baseline, candidate)
    with_none = compare_reports(baseline, candidate, adapter_record=None)

    assert with_none.gate_passed == without_record.gate_passed
    assert with_none.adapter_record is None


def test_gate_stamps_the_evaluated_adapter_record():
    record = AdapterRecord(
        version="adapter-v2",
        training_set_hash="train-sha",
        base_model_hash="base-sha",
        regression_report_path="evals/out/adapter-v2.json",
    )

    comparison = compare_reports(_report("base"), _report("candidate"), record)

    assert comparison.adapter_record == record
