"""Persistent records for model adapters and their evaluation provenance."""

from pathlib import Path

from pydantic import BaseModel


class AdapterRecord(BaseModel):
    version: str
    training_set_hash: str
    base_model_hash: str
    regression_report_path: str
    rollback_pointer: str | None = None


def save_adapter_record(record: AdapterRecord, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(record.model_dump_json(indent=2), encoding="utf-8")


def load_adapter_record(path: str | Path) -> AdapterRecord:
    return AdapterRecord.model_validate_json(Path(path).read_text(encoding="utf-8"))
