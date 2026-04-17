# Refactor Guidelines

## Safe Refactoring Rules

- Preserve externally visible behavior unless change is intentional.
- Add or confirm characterization tests before risky refactors.
- Refactor in small, behavior-preserving increments.
- Keep each increment reversible.
- Verify each increment with local checks.

## Sequencing Rules

- Separate behavior changes from structural refactors whenever possible.
- If separation is impossible, isolate intent with small commits and explicit notes.
- Move/rename first, then change logic.
- Avoid broad renames and logic rewrites in one step.

## Anti-Patterns to Avoid

- Premature abstraction.
- Deep utility dumping (`utils/common/shared`) without ownership.
- Mixing architecture migration with feature delivery in one step.
- Large renames plus behavior changes without clear isolation.
- Mechanical churn that does not improve readability, boundaries, or correctness.
