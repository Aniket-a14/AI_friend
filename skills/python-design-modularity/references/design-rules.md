# Code Design and Readability

## Outcome

Code that is easy to reason about, modify, and test under change.

## Primary Rules

- Prefer explicit control flow and explicit data movement.
- Keep naming domain-first and keep functions narrowly purposeful.
- Keep module boundaries strict; avoid architectural leakage and shared "common/utils" dumping.
- Bias toward simple, golden-path implementations before adding defensive complexity.

## Reference Map

- `readability-and-complexity.md`
- `module-boundaries.md`
- `functional-core-shell.md`
- `refactor-guidelines.md`
