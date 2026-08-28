# Voice training & other GPU work

Recording an 8-second clip (see [Quickstart](/docs/getting-started/quickstart))
gets your friend talking in a rough approximation of your voice
immediately. Fine-tuning GPT-SoVITS on a larger set of your own recordings
gets a real clone, and that's genuinely GPU-heavy work a laptop either
can't do at all, or can only do slowly and hot — so it lives in a Colab
notebook instead.

## The three notebooks

| Notebook | What it does | Needs a GPU? |
| :--- | :--- | :--- |
| `ai_friend_voice_training.ipynb` | Fine-tunes a GPT-SoVITS voice clone from your own recordings | Yes, hard requirement |
| `ai_friend_eval_harness.ipynb` | Runs the behavioral eval gate against real Ollama models | Helps a lot, not required |
| `ai_friend_llm_benchmark.ipynb` | Measures raw generation throughput/latency/VRAM across model sizes | Yes, that's the point |

All three are self-contained — open the Colab badge, run top to bottom,
download the result, close the tab. None of them need Docker, Postgres,
Neo4j, or NATS running anywhere. Full walkthrough and runtime estimates:
[`notebooks/README.md`](https://github.com/Aniket-a14/AI_friend/blob/main/notebooks/README.md)
on GitHub.

## What's deliberately not a notebook

`backend/tools/measure/` (the live-infrastructure latency/pressure harness)
and `scripts/research/` (a simulated cognitive benchmarking suite) both
need the full Postgres/Neo4j/Qdrant/NATS mesh actually running, which
Colab's own container can't reliably nest. A notebook claiming to run
either would either silently measure something smaller than advertised, or
just fail — worse than not having one. If you need those numbers, run them
locally.
