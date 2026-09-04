"""Offline qualification and atomic activation for a fine-tuned adapter
(LoRA) or model-tag swap, per FINAL_HUMANOID_BRAIN_ARCHITECTURE.md Section
21's "optional offline model adaptation" learning channel and Section 40's
evaluation-framework provenance requirements.

Everything here is offline and deterministic: this module never runs a live
LLM or the behavioral eval harness itself. `backend/evals/` already owns
that (see its `compare` subcommand, which pass/fail-diffs a baseline and
candidate report), and CLAUDE.md's "nothing in `app/` may import from
`evals/`" rule means this gate cannot call it directly. Instead the caller
runs the held-out suite externally and hands `OfflineAdapterGate.qualify()`
the resulting per-probe pass/fail outcomes; this gate only judges them.

Three checks gate every qualification, mirroring the plan's requirements:
zero regression (no probe that passed under the incumbent and now fails),
the candidate's recorded prompt digest matching the prompt it would
actually run under if activated, and the same for a "constitution digest"
(a fingerprint of the immutable core plus every CONSTITUTIONAL-tier persona
field) -- so an adapter evaluated under one persona/safety configuration
can never be silently activated under a different one.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field

from ..persona.profile import PersonaProfile, Tier
from .adapter_registry import AdapterRecord


class AdapterQualificationRequest(BaseModel):
    adapter_id: str
    base_model_tag: str
    held_out_eval_file: str
    prompt_digest: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdapterQualificationResult(BaseModel):
    adapter_id: str
    qualified: bool
    pass_rate: float
    regression_detected: bool
    details: dict[str, Any] = Field(default_factory=dict)


def compute_prompt_digest(prompt_text: str) -> str:
    """Short digest identifying a system prompt without reproducing it, so
    reports and requests can carry provenance without embedding authored
    persona content."""
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16]


def compute_constitution_digest(persona: PersonaProfile) -> str:
    """Digest of everything Section 21 forbids a learning channel from
    touching: the immutable persona core plus every CONSTITUTIONAL-tier
    field's current value. Two configurations with the same digest are
    safety-and-temperament identical as far as an adapter's held-out
    evaluation is concerned; a different digest means the eval run this
    adapter qualified under no longer describes the configuration it would
    activate into."""
    payload = {
        "immutable_core": persona.immutable,
        "constitutional": {
            name: getattr(persona, name)
            for name in PersonaProfile.fields_in(Tier.CONSTITUTIONAL)
        },
    }
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class OfflineAdapterGate:
    """Tracks the currently active adapter/model configuration and judges
    candidates against it. One instance per running agent process (or per
    offline qualification run); `activate()` snapshots the incumbent so
    `rollback()` can restore it in a single step.
    """

    def __init__(
        self,
        incumbent_adapter_id: str,
        incumbent_base_model_tag: str,
        incumbent_prompt_digest: str,
        incumbent_constitution_digest: str,
        min_pass_rate: float = 0.0,
    ) -> None:
        if not 0.0 <= min_pass_rate <= 1.0:
            raise ValueError("min_pass_rate must be within [0.0, 1.0]")
        self._active = AdapterRecord(
            version=incumbent_adapter_id,
            training_set_hash="",
            base_model_hash=incumbent_base_model_tag,
            regression_report_path="",
            rollback_pointer=None,
        )
        self._active_prompt_digest = incumbent_prompt_digest
        self._active_constitution_digest = incumbent_constitution_digest
        self._min_pass_rate = min_pass_rate
        self._snapshot: AdapterRecord | None = None
        self._snapshot_digests: tuple[str, str] | None = None

    @property
    def active(self) -> AdapterRecord:
        return self._active

    def qualify(
        self,
        request: AdapterQualificationRequest,
        baseline_results: dict[str, bool],
        candidate_results: dict[str, bool],
        target_prompt_digest: str,
        target_constitution_digest: str,
    ) -> AdapterQualificationResult:
        """Judge one candidate adapter against the incumbent's held-out
        results and the live target configuration it would run under if
        activated. Pure -- never mutates the active/incumbent snapshot;
        only `activate()` does that, and only after this returns
        `qualified=True`.

        `baseline_results`/`candidate_results` map probe id -> passed, the
        same shape `evals/compare.py` reduces its reports to. Regression is
        pass/fail per probe, not a score threshold, matching that module's
        rationale: "a score delta ... is one check flipping; deciding how
        much of that is tolerable would be a tuning knob nobody has
        measured yet."
        """
        shared = sorted(set(baseline_results) & set(candidate_results))
        regressed = [
            probe_id
            for probe_id in shared
            if baseline_results[probe_id] and not candidate_results[probe_id]
        ]
        # No shared probes at all means zero regression cannot be
        # established one way or the other -- fail safe rather than treat
        # an empty intersection as a clean bill of health.
        regression_detected = bool(regressed) or not shared

        prompt_digest_ok = request.prompt_digest == target_prompt_digest
        constitution_digest_ok = (
            request.metadata.get("constitution_digest") == target_constitution_digest
        )

        total = len(candidate_results)
        passed = sum(1 for value in candidate_results.values() if value)
        pass_rate = (passed / total) if total else 0.0

        details: dict[str, Any] = {
            "shared_probe_count": len(shared),
            "candidate_probe_count": total,
            "regressed_probe_ids": regressed,
            "prompt_digest_matches_target": prompt_digest_ok,
            "constitution_digest_matches_target": constitution_digest_ok,
            "pass_rate_meets_minimum": pass_rate >= self._min_pass_rate,
        }

        qualified = (
            not regression_detected
            and prompt_digest_ok
            and constitution_digest_ok
            and pass_rate >= self._min_pass_rate
        )

        return AdapterQualificationResult(
            adapter_id=request.adapter_id,
            qualified=qualified,
            pass_rate=pass_rate,
            regression_detected=regression_detected,
            details=details,
        )

    def activate(
        self,
        request: AdapterQualificationRequest,
        result: AdapterQualificationResult,
        prompt_digest: str,
        constitution_digest: str,
    ) -> AdapterRecord:
        """Atomically swap the active configuration to a qualified
        candidate, snapshotting the incumbent first so `rollback()` can
        restore it in one step. Raises -- and changes nothing -- if
        `result.qualified` is False; activation only ever follows a green
        qualification, never a bypass of one."""
        if not result.qualified:
            raise ValueError(
                f"adapter {result.adapter_id!r} is not qualified "
                f"(pass_rate={result.pass_rate}, "
                f"regression_detected={result.regression_detected}); "
                "refusing to activate"
            )
        if result.adapter_id != request.adapter_id:
            raise ValueError("result.adapter_id does not match request.adapter_id")

        self._snapshot = self._active.model_copy(deep=True)
        self._snapshot_digests = (
            self._active_prompt_digest,
            self._active_constitution_digest,
        )
        self._active = AdapterRecord(
            version=request.adapter_id,
            training_set_hash=self._snapshot.training_set_hash,
            base_model_hash=request.base_model_tag,
            regression_report_path=request.held_out_eval_file,
            rollback_pointer=self._snapshot.version,
        )
        self._active_prompt_digest = prompt_digest
        self._active_constitution_digest = constitution_digest
        return self._active

    def rollback(self) -> AdapterRecord:
        """1-step atomic rollback: restore the incumbent snapshot taken by
        the most recent `activate()`. Raises if there is nothing to roll
        back to -- `activate()` was never called, or a prior `rollback()`
        already consumed the snapshot."""
        if self._snapshot is None or self._snapshot_digests is None:
            raise ValueError("no incumbent snapshot to roll back to")
        self._active = self._snapshot
        self._active_prompt_digest, self._active_constitution_digest = (
            self._snapshot_digests
        )
        self._snapshot = None
        self._snapshot_digests = None
        return self._active
