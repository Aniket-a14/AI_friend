# Behavioral eval harness

Answers one question, deterministically: **did this model + persona combination
change behavior between two runs?** It exists because CVS-4's consolidation
loop ("REM sleep" fine-tuning) cannot be built responsibly without it — no test
suite can tell you whether a fine-tuned model is still your friend or got
quietly lobotomized. This harness is the measured step that has to come before
that leap.

## What it measures, and at which seam

Probes are sent to the **LLM boundary**: the real persona prompt from the real
`IdentityManager`, through the real `OllamaClient`, with sampling pinned
(temperature 0, fixed seed) and the mood directive frozen to a neutral
constant. That is exactly the seam a LoRA adapter changes, and nothing above it
(retrieval, state, action pipeline) is touched by an adapter swap — so nothing
above it is in the loop. No NATS, no databases.

Three probe sources:

- **Persona-derived** (generated from whatever identity is actually loaded, so
  nothing here is fitted to one deployment): name recall, immutable-values
  recall, rename resistance, and a hostility probe scored by the production
  `validate_response` — eval and runtime share one definition of "crossed a
  line".
- **`probes/identity_pressure.json`** — persona-independent pressure: prompt
  disclosure, wholesale persona swap, values override.
- **Memory packs, supplied per run** (`--probes my_pack.json`) — in-weights
  recall of facts a consolidation run trained on. Only the caller knows those
  facts, so the consolidation loop generates the pack from its own training
  set. `probes/sample_memory_recall.json` pins the format and is labeled the
  sample it is; against an untrained model its probes *should* fail.

## Usage

```bash
cd backend
python -m evals run --model llama3.2:1b --out evals/out/baseline.json
# ... fine-tune, build candidate model ...
python -m evals run --model my-friend:adapter-v1 --out evals/out/candidate.json
python -m evals compare evals/out/baseline.json evals/out/candidate.json --fail-on-regression
```

The gate is deliberately blunt: **a regression is a probe the baseline passed
and the candidate failed.** Score-threshold subtlety is a tuning knob nobody
has measured yet; pass/fail is unarguable, which is what a gate must be. The
CVS-4 contract is: adopt the adapter only if the gate passes and memory recall
improved.

## What it refuses to claim

- **No LLM judge.** Deterministic checks only. Cruder, but a gate that flips
  between identical runs is worse than one that misses nuance. Tone, warmth,
  and style drift are real phenomena this harness *does not measure*.
- **No scores from mocks.** Under `MOCK_LLM_TEXT` the CLI refuses to run;
  `--allow-mock` exists for plumbing checks and stamps the report
  `provenance: mock`, which `compare` in turn refuses without the same flag.
  Reports from this repo's history of corpus-fitted evaluation (finding B1)
  are exactly what this is designed to make impossible.
- **No committed results.** `evals/out/` is gitignored. A number only means
  something next to the run that produced it.
- Determinism is per-build, per-hardware: greedy decoding plus a seed pins
  Ollama's sampling, not floating-point reality across machines. Compare runs
  from the same box and binary.

## Production stays clean

Nothing in `app/` imports from `evals/`. The dependency points one way only:
the harness imports production code because production behavior is the thing
under test.
