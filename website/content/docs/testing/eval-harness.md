# Evaluation Harness

The evaluation harness (`backend/evals/`) provides deterministic probe testing to assess memory recall, boundary adherence, and persona preservation.

---

## Running the Evaluation Suite

Run the harness against your local Ollama model:

```bash
cd backend
../.venv/bin/python -m evals run --model llama3.2:3b --out evals/out/report.json
```

---

## Key Probe Categories

1. **Identity & Name Recall Probes**: Tests whether the model consistently recalls its name, authored biography, and creator relationship across long conversational contexts.
2. **Boundary & Prompt-Disclosure Probes**: Tests resistance against jailbreaks attempting to extract system instructions or violate the Immutable Safety Core.
3. **Memory Recall Distance Probes**: Tests multi-turn distance recall (placing facts at 10, 25, and 50 turns in the past) to calculate true **Recall@K**.
4. **Friction Integrity Probes**: Verifies that edgy, direct personas do not soften into sycophantic compliance.

---

## Verifying Live Provenance

The evaluation report header always records execution provenance to prevent mock leakage:

```json
{
  "model": "llama3.2:3b",
  "persona": "my friend",
  "provenance": "live",
  "path": "llm",
  "results": { "passed": 42, "failed": 0 }
}
```
