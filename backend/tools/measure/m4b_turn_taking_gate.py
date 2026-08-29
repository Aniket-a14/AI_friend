"""Roadmap leftovers Item 4b verification: does turn_taking_probability
discriminate over the reachable state space, before it gets wired to
anything?

M3-D2 (audit/ISSUES.md): calculate_pacing_parameters returns
turn_taking_probability and no caller reads it. The plan's own
"verify the benefit, then wire" gate for this item requires proving the
gate would actually change proactive-speech behavior, not decorate it --
wiring a threshold that blocks 0% or 100% of reachable states is not a
feature, it is either a no-op or a silent regression that disables
proactive speech entirely.

Pure computation, no live services: this evaluates
0.5 + 0.3*D - 0.1*F + 0.2*V over the box the persona schema and the live
state's own clamp actually permit --
  V (valence)   in [-0.6, 0.6]   (PersonaProfile.baseline_valence bounds,
                                   profile.py:113)
  D (dominance) in [0.15, 0.85]  (PersonaProfile.baseline_dominance bounds,
                                   profile.py:115)
  F (fatigue)   in [0.0, 1.0]    (AgentState's own clamp,
                                   agent_state.py:1382, :1539)
sampled on a fine grid rather than at corners only, because the formula is
linear in each variable and a grid sweep is what actually answers "what
fraction of reachable states fall each side," not just the extremes.
"""

from __future__ import annotations

import argparse

from app.utils.conversational_runtime import ConversationalRuntime

from .schema import Figure, MeasurementReport, Run

V_BOUNDS = (-0.6, 0.6)
D_BOUNDS = (0.15, 0.85)
F_BOUNDS = (0.0, 1.0)
GRID_STEPS = 41  # 41^3 ~= 68,921 points; fine enough to resolve the formula's
# linear gradient without being expensive -- this is arithmetic, not inference.


def _linspace(lo: float, hi: float, n: int) -> list[float]:
    if n == 1:
        return [lo]
    step = (hi - lo) / (n - 1)
    return [lo + i * step for i in range(n)]


def sweep(threshold: float) -> dict:
    """Evaluate turn_taking_probability over the full V x D x F grid and
    report what fraction of reachable states the gate would block."""
    runtime = ConversationalRuntime()
    total = 0
    blocked = 0
    probs: list[float] = []

    for v in _linspace(*V_BOUNDS, GRID_STEPS):
        for d in _linspace(*D_BOUNDS, GRID_STEPS):
            for f in _linspace(*F_BOUNDS, GRID_STEPS):
                state_snap = {
                    "valence": v,
                    "arousal": 0.5,
                    "dominance": d,
                    "fatigue": f,
                }
                pacing = runtime.calculate_pacing_parameters(state_snap)
                p = pacing["turn_taking_probability"]
                probs.append(p)
                total += 1
                if p < threshold:
                    blocked += 1

    probs.sort()
    n = len(probs)
    median = probs[n // 2] if n % 2 else (probs[n // 2 - 1] + probs[n // 2]) / 2

    return {
        "total_states": total,
        "blocked_states": blocked,
        "blocked_fraction": blocked / total,
        "min_probability": probs[0],
        "max_probability": probs[-1],
        "median_probability": median,
    }


async def run(allow_mock: bool = False) -> MeasurementReport:
    # allow_mock is accepted for CLI/dispatcher symmetry with the other
    # measurements; this one has no live/mock distinction, since it computes
    # a pure function of its inputs with no external service involved.
    default_threshold = 0.5
    result = sweep(default_threshold)

    pass_low, pass_high = 0.15, 0.50
    gate_is_meaningful = pass_low <= result["blocked_fraction"] <= pass_high

    figures = {
        "blocked_fraction_at_default_threshold": Figure(
            label="MEASURED",
            value=round(result["blocked_fraction"], 4),
            unit="fraction of reachable (V,D,F) grid points",
            derivation=(
                f"{result['blocked_states']} of {result['total_states']} grid "
                f"points scored turn_taking_probability < {default_threshold} "
                f"(the formula's own nominal midpoint at D=0,F=0,V=0)"
            ),
        ),
        "gate_pass_criterion_met": Figure(
            label="MEASURED",
            value="yes" if gate_is_meaningful else "no",
            derivation=(
                f"pass band is [{pass_low}, {pass_high}] (a 'meaningful "
                "minority' of reachable states, per the plan's own criterion); "
                f"outside that band the gate is decoration -- always-open "
                "changes nothing, always-closed silently disables proactive "
                "speech entirely"
            ),
        ),
        "min_probability": Figure(
            label="MEASURED", value=round(result["min_probability"], 4)
        ),
        "max_probability": Figure(
            label="MEASURED", value=round(result["max_probability"], 4)
        ),
        "median_probability": Figure(
            label="MEASURED",
            value=round(result["median_probability"], 4),
            derivation=(
                "the re-siting candidate if the default 0.5 threshold fails "
                "the pass band -- the plan says to use the measured median of "
                "the reachable distribution rather than ship 0.5 as a guess"
            ),
        ),
    }

    notes = [
        (
            f"Grid: {GRID_STEPS}^3 = {GRID_STEPS**3} points over "
            f"V in {V_BOUNDS}, D in {D_BOUNDS}, F in {F_BOUNDS} -- the bounds "
            "PersonaProfile's schema and AgentState's own clamp actually "
            "permit, not the formula's unclamped range."
        ),
        (
            "This measures whether the GATE discriminates, not whether "
            "proactive speech itself is good -- that is a separate, "
            "qualitative check against the ledger's proactive-speech "
            "history, done by hand rather than computed here."
        ),
        (
            "arousal is held at 0.5 (neutral) throughout: it appears in "
            "calculate_pacing_parameters' silence_duration_ms computation but "
            "not in the turn_taking_probability formula itself, so it does "
            "not affect this sweep's result."
        ),
    ]

    return MeasurementReport(
        measurement_id="4b",
        title=(
            "Does turn_taking_probability discriminate over the reachable "
            "state space? (roadmap-leftovers Item 4b, pre-wiring verification)"
        ),
        provenance="live",
        runs=[Run(figures=figures, raw=result)],
        notes=notes,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-mock", action="store_true")
    parser.add_argument("--out", default="tools/measure/out/m4b_turn_taking_gate.json")
    args = parser.parse_args()

    import asyncio

    report = asyncio.run(run(allow_mock=args.allow_mock))
    with open(args.out, "w") as f:
        f.write(report.model_dump_json(indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
