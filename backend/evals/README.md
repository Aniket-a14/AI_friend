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

## Multi-turn recall (`run-conversation`)

A second suite, answering a different question: **does a fact survive the
distance to the question it answers?** A fact is planted, buried under scripted
filler exchanges, then asked about. Distances span ~4 to ~240 turns so the
report shows *where* recall breaks rather than one pass/fail.

The variable under test is the **context strategy** — what the model is shown
at recall time. `full_history` is the naive baseline where lost-in-the-middle
is observable (the fact *is* present, so a miss is an attention failure).
`recent_window_N` is the control that is supposed to fail, since the plant
genuinely falls out. A retrieval-backed strategy fits the same seam, and the
gap between it and these two is the memory layer's contribution.

Only the final answer is generated; the plant, the filler and the assistant's
replies are scripted. That isolates distance from compounding model noise and
costs one generation per probe instead of hundreds — but it therefore measures
**retrieval from a context window, not conversational degradation**. A model
that would have derailed on its own output by turn thirty is not penalised.

Two ways a probe can return a confident verdict about nothing, both surfaced
and neither folded into the score:

- **`plant out`** — the strategy never showed the model the fact, so a pass is
  a guess against the model's prior.
- **`fits NO`** — the rendered context exceeded `num_ctx`. Ollama truncates
  from the *front*, which is exactly where the plant sits. `OllamaClient`
  defaults `num_ctx` to 2048, so the harness pins it explicitly. The budget
  counts prompt plus system plus **`num_predict`**, since generated tokens
  share the same window — leaving the reserve out yields a probe that fits on
  arrival and loses the plant partway through generation, reported as `fits
  yes`. The token estimate itself deliberately over-counts, because a false
  all-clear is far more expensive than a needless rerun.

Filler and probes live in JSON packs, not in code: what a conversation is
*about* is content, and content belongs to whoever authors the pack.

```bash
python -m evals run-conversation --model qwen2.5:3b --num-ctx 8192 \
    --out evals/out/recall_baseline.json
python -m evals run-conversation --pack my_pack.json --window 10 \
    --out evals/out/recall_candidate.json
```

Reports share the single-turn shape, so `compare` works across both suites.
Probe ids are qualified with the strategy (`recall_name_d96@full_history`) so
two conditions never collide inside one report.

### Retrieval strategies, and the control next to them

`--retrieval` adds strategies that *choose* what the model sees instead of
truncating to a rule:

- **`bm25`** — a fifty-line Okapi BM25 over the transcript. No embeddings, no
  database, no decay. It is the control, and it needs no infrastructure. A
  memory layer that cannot beat it has not yet earned what it costs to run.
- **`memory`** — the real `MemoryStore.search_memories`, built the way
  `brain_agent.main` builds it. **It needs Postgres, Qdrant and Neo4j up, and
  it writes every transcript turn into them**, into a dedicated `eval_harness`
  wing that it purges before each index and again at the end. Point it at the
  agent's live databases only if that is what you mean to do.

Each retriever yields two strategies: `Retrieved` is budget-matched to
`recent_window_N`, so a difference is attributable to *which* turns were chosen
rather than how many; `WindowPlusRetrieved` mirrors what the running system
does and is deliberately not budget-matched.

The eval retriever searches with `refresh_on_recall=False`. Retrieval normally
strengthens what it returns, which is right for an agent and wrong for an
instrument — four strategies query the same room, and the frequency term is
large enough to reorder results on its own, so leaving it on would make ranking
depend on the order the suite ran in.

### The discriminating pack

`probes/conversation/discriminating_recall.json` exists because the shipped
pack could not tell the two retrievers apart: every question in it repeats the
words of its own plant, which is close to the best case for BM25. Three
families, all written so literal overlap is absent or misleading — `oblique_*`
(the question names the topic and never the plant's words), `update_*` (a fact,
then its correction, distinguishable only by recency), and `similars_*` (seven
facts of identical shape, shipped in a lexical variant as the control and an
oblique variant as the test).

Probes there use `plants`, a list placing several facts at stated depths, with
`answers` marking the ones the question is about — so `plant out` still means
"the answer never reached the model" when distractors are present.

```bash
python -m evals run-conversation --model qwen2.5:3b --num-ctx 8192 \
    --pack evals/probes/conversation/discriminating_recall.json \
    --retrieval bm25 --retrieval memory \
    --out evals/out/discriminating.json
```

## What a report has to carry to be comparable

A probe flip means the model changed *only if everything else held*, so a
report records the everything else and `compare` checks it:

- **Sampling options**, diffed between the two reports. A mismatch prints a
  banner and taints every delta below it. It is surfaced, never gated on — the
  caller may have changed an option deliberately, and a gate that blocks a
  deliberate change just gets bypassed.
- **A digest of the system prompt.** The persona prompt is the largest single
  input to every response and the one that drifts silently: adaptive traits
  evolve through reflection and the identity seeds are editable files. A
  comparison spanning a persona edit would otherwise read as a model behavior
  change with nothing in the report to contradict it. A digest rather than the
  text, because reports are shareable and the prompt is authored character
  content.
- **`num_gpu`, if you pin it.** Unset, Ollama picks the layer split at load
  time from free VRAM, and the split *is* an input to the output — the same
  prompt all-CPU and part-GPU returns different text. It defaults to unset,
  because a layer count that does not fit the next machine's VRAM is worse
  than an honest unpinned run. Pin it for any A/B whose verdict matters.

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

- **No LLM judge.** Deterministic checks only. Cruder, but a scorer that
  returns two verdicts for one response is worse than one that misses nuance.
  This buys reproducible *scoring*, which is not the same as a reproducible
  *response* — see the cold-model bullet below. Tone, warmth, and style drift
  are real phenomena this harness *does not measure*.
- **No scores from mocks.** Under `MOCK_LLM_TEXT` the CLI refuses to run;
  `--allow-mock` exists for plumbing checks and stamps the report
  `provenance: mock`, which `compare` in turn refuses without the same flag.
  Reports from this repo's history of corpus-fitted evaluation (finding B1)
  are exactly what this is designed to make impossible.
- **No committed results.** `evals/out/` is gitignored. A number only means
  something next to the run that produced it.
- **Reproducibility is a property of the starting state, and it had to be
  bought.** `temperature=0` and a fixed seed were not enough. Two
  `run-conversation` runs with byte-identical prompts, options, model and
  persona differed on **3 of 16** probes and flipped two verdicts.

  The sampler was never the culprit. Ollama proved deterministic within a
  load, across three unload/reload cycles, and with a second model contending
  for VRAM. The CPU/GPU layer split does change the output but did not drift
  on its own here. What survived every experiment was narrower: **two runs
  that started from the same state agreed character for character, on all
  sixteen probes; runs that started differently did not.**

  So both suites now **unload the model, reload it, and burn one throwaway
  generation** before the first scored probe. Naming the starting state is
  what works — an earlier attempt that only warmed up, without unloading,
  still moved 2 of 16, because "freshly loaded" and "holding the last run's
  residue" are different places to start from. With the full reset, three
  consecutive runs were identical on every probe: **0 of 16 moved.**

  Re-measure this before quoting it. The flip rate is a property of a model on
  a machine, not of the harness, which is exactly why the options and the
  persona digest now travel inside the report instead of living in a comment.

## Production stays clean

Nothing in `app/` imports from `evals/`. The dependency points one way only:
the harness imports production code because production behavior is the thing
under test.
