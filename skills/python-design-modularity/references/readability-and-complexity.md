# Readability and Complexity

## Outcome

Implementations are simple to explain, review, and evolve.

## Readability Rules

- Prefer explicit over implicit behavior.
- Keep control flow flat where possible; extract helpers when nesting obscures intent.
- Favor one obvious implementation path over multiple equivalent styles in the same module.
- Use names that expose business meaning, not framework or transport details.

## Simplicity and Defense

- Start with the minimal golden path that satisfies the contract.
- Add defensive checks when failure modes are realistic and tested.
- Avoid speculative abstractions for hypothetical reuse.
- If a design is hard to explain in a short review comment, simplify before extending.

## Reuse and Composition

- Prefer composition for combining capabilities.
- Use inheritance when true subtype substitution improves usability and reduces glue code.
- Avoid heavy decorator layers when plain functions, context managers, or partials are clearer.
