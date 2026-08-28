# Code Quality & Static Analysis

The AI Friend codebase maintains strict software engineering quality standards, most enforced by blocking CI gates — a few deliberately still report-only until they've earned a real baseline to gate against.

---

## Static Analysis Toolchain

| Tool | Focus Area | Command | CI Status |
| :--- | :--- | :--- | :--- |
| **Ruff** | Python formatting, linting, and import hygiene. | `ruff check .` | Blocking |
| **Mypy** | Static type checking and protocol verification. | `mypy app/` | Blocking |
| **Radon (D/E/F tier)** | Cyclomatic complexity, worst-offender functions. | `radon cc app/ --min D -s` | Blocking |
| **Radon (C tier + maintainability index)** | Remaining complexity findings and MI score. | `radon cc app/ -s -nb`, `radon mi app/` | Report-only |
| **Bandit** | AST-based security vulnerability auditing. | `bandit -r app/` | Blocking |
| **Cargo Check** | Rust workspace compilation and safety checks. | `cargo check --workspace` | Blocking |
| **Cargo Test** | Rust unit testing across all four crates. | `cargo test` | Blocking |

Radon's C-tier complexity findings and maintainability index stay report-only on purpose: the D/E/F tier got a dedicated fix pass and a clean baseline to gate against, but the C-tier findings haven't, and blocking on them now would gate against noise nobody has earned the right to call a regression yet.

---

## Subject Wiring Static Scanner

The custom linter `scripts/check_subject_wiring.py` inspects all Python and Rust ASTs to guarantee that every NATS subject published has a valid matching subscriber, preventing silent message drops.

```bash
cd backend
../.venv/bin/python scripts/check_subject_wiring.py
```

