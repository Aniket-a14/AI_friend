# Mutation Testing Discipline

To ensure that unit tests verify actual runtime behavior rather than merely exercising code coverage, all critical cognitive boundaries are **mutation tested** using `mutmut`.

---

## What is Mutation Testing?

Mutation testing systematically introduces artificial bugs (mutants) into the source code (e.g. changing `>` to `<`, flipping booleans, returning `None` early) and runs the test suite against each mutation:
* **Killed Mutant**: The test suite fails as expected. (Test is effective).
* **Survived Mutant**: The test suite passes despite the broken code. (Test is weak or testing implementation details rather than behavior).

---

## Running Mutation Tests

Run targeted mutation testing on core decision and appraisal modules:

```bash
cd backend
../.venv/bin/mutmut run --paths-to-mutate app/cognitive/appraisal.py
```

Inspect mutation survival reports:
```bash
../.venv/bin/mutmut results
```

---

## Golden Rule for Contributions
Every new test contributed to the repository must be mutation-verified: manually break the code being covered, confirm the test fails with a clear message, restore the code, and confirm the test passes.

