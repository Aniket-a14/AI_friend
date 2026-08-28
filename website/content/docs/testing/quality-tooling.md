# Code Quality & Static Analysis

The AI Friend codebase maintains strict software engineering quality standards enforced by continuous static analysis gates in CI.

---

## Static Analysis Toolchain

| Tool | Focus Area | Command |
| :--- | :--- | :--- |
| **Ruff** | Python formatting, linting, and import hygiene. | `ruff check .` |
| **Mypy** | Static type checking and protocol verification. | `mypy app/` |
| **Radon** | Cyclomatic complexity and maintainability index. | `radon cc app/ -s -nb` |
| **Bandit** | AST-based security vulnerability auditing. | `bandit -r app/` |
| **Cargo Check** | Rust workspace compilation and safety checks. | `cargo check --workspace` |
| **Cargo Test** | Rust unit testing across all four crates. | `cargo test` |

---

## Subject Wiring Static Scanner

The custom linter `scripts/check_subject_wiring.py` inspects all Python and Rust ASTs to guarantee that every NATS subject published has a valid matching subscriber, preventing silent message drops.

```bash
cd backend
../.venv/bin/python scripts/check_subject_wiring.py
```

