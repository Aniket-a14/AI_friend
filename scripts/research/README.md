# 🧪 Research & Measurement Scripts

Real, runnable tools for observing the live mesh and measuring its actual
behavior — latency, PAD/endocrine trajectories, and human-realism/paralinguistic
data. Everything in this directory writes to `scripts/results/` and is either
directly cited as the source of a real, measured number already in this
repo's docs, or usable to produce one.

**Not here anymore:** the corpus-fitted benchmark-generation suite
(`hard_benchmark.py`, `corpus_builder.py`, `generate_seeding_corpus.py`,
`cognitive_engine.py`, `cognitive_metrics_eval.py`, `extended_benchmarks_eval.py`,
`benchmark_visualizer.py`, `build_intent_cache.py`) and its methodology doc
(`paper_results_guide.md`) moved to `_archive/research/`. `CLAUDE.md`'s
integrity constraints already flag that cluster's whole approach — running
against a synthetic, procedurally-generated corpus and reporting the result
as if measured against real data — as finding B1, and those tools were
already documented as "deliberately not run." They also generated a
fabricated academic-paper PDF (fake SOTA comparisons framed as "CVS-3.5
(Ours)" beating named real systems) that had no place staying in live,
user-facing tooling. See `_archive/research/` if you need the old code for
reference.

---

## What's here, and what it measures

| Script | What it does | Feeds into |
| :--- | :--- | :--- |
| `monitor.py` | Subscribes to `chat.input`/`chat.output`/`audio.perception` and computes real cognitive-turnaround latency and multimodal jitter from live NATS traffic. | Manual observation, or a CSV/log you build around it. |
| `injector.py` | Publishes standardized `chat.input` messages to the mesh, so latency numbers aren't confounded by human typing/thinking time. | Pair with `monitor.py`. |
| `collector.py` | Subscribes to `state.update` and logs the agent's live PAD trajectory to `scripts/results/research_pad_trajectory.csv`. | `visualizer.py`. |
| `visualizer.py` | Renders the collected PAD/ToM trajectory CSV into a publication-grade plot. | Reads `collector.py`'s output. |
| `human_fidelity_test.py` | Drives a structured, live human-realism/emotional-stimuli scenario over NATS. | Pairs with `collector.py` as a background daemon. |
| `human_realism_eval.py` | Runs real infrastructure (live agents, real DB queries) and writes `scripts/results/human_realism_results.json` — the file `docs/ARCHITECTURE.md`/`docs/ROBOTICS_ANALYSIS.md` cite for the real "5.44 ms sub-LLM pathway overhead" figure. | Cited directly in this repo's docs. |
| `estimate_realtime_latency.py` | Measures real infrastructure latency without a synthetic corpus — the one script in the old suite `academic_benchmarks/documentation/experimental_methodology.md` records as actually run. | Cited directly in `academic_benchmarks/documentation/`. |
| `resource_profiler.py` | Measures real CPU/RAM footprint of the live agent mesh during active inference. | Standalone. |
| `reset_cognitive_db.py` | Resets Postgres/pgvector and Neo4j to a clean schema before a measurement run. | Prerequisite for a clean run of anything above. |
| `db_seeding.py` / `test_db_queries.py` | Database seeding/query utilities, independent of the archived benchmark suite. | Standalone. |
| `metrics_eval.py` | Sentiment-scoring helper using the NRC-VAD lexicon (see setup below). | Used by `human_realism_eval.py`/`human_fidelity_test.py`. |

`scripts/visualization/visualize_affect.py` (a sibling directory, not this
one) plots a sample PAD trajectory chart — see `docs/RESEARCH_GUIDE.md`.

---

## Setup

```bash
pip install matplotlib numpy pandas nats-py python-dotenv scipy asyncpg neo4j vaderSentiment
```

### NRC-VAD Lexicon (needed by `metrics_eval.py`)

Due to distribution licensing, this file is excluded from Git and must be
set up locally:

```bash
python -c "import urllib.request, zipfile, io, os; url = 'https://saifmohammad.com/WebDocs/Lexicons/NRC-VAD-Lexicon.zip'; headers = {'User-Agent': 'Mozilla/5.0'}; req = urllib.request.Request(url, headers=headers); target_dir = 'scripts/research/NRC-VAD-Lexicon'; os.makedirs(target_dir, exist_ok=True); response = urllib.request.urlopen(req); zip_data = response.read(); z = zipfile.ZipFile(io.BytesIO(zip_data)); [open(os.path.join(target_dir, 'NRC-VAD-Lexicon.txt'), 'wb').write(z.read(n)) for n in z.namelist() if n.endswith('NRC-VAD-Lexicon.txt')]; print('done')"
```

Or manually: download from the URL above and place
`NRC-VAD-Lexicon.txt` in `scripts/research/NRC-VAD-Lexicon/`.

---

## A real measurement session

```bash
# 1. Bring up infra
docker compose up -d

# 2. Clean slate
python scripts/research/reset_cognitive_db.py

# 3. Latency profiling (two terminals)
python scripts/research/monitor.py
python scripts/research/injector.py

# 4. PAD/human-realism telemetry (two terminals)
python scripts/research/collector.py
python scripts/research/human_fidelity_test.py
# Ctrl+C the collector when done -- CSV is in scripts/results/research_pad_trajectory.csv

# 5. Plots
python scripts/research/visualizer.py

# 6. Real human-realism/paralinguistic numbers
python scripts/research/human_realism_eval.py
```

For provenance-tracked measurements meant to back a specific claim in this
repo, prefer `backend/tools/measure/` (the `m11`-`m17` registered
measurements) and `backend/evals/` over these scripts — see
`CLAUDE.md`'s "Behavioral eval harness" section and
`docs/RESEARCH_GUIDE.md`. The scripts here are lower-ceremony and good for
exploratory observation; `tools/measure`/`evals` are what actually goes
into a documented claim.
