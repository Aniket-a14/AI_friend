# Functional Core and Imperative Shell

## Outcome

Business rules are deterministic and side effects are isolated.

## Core Rules

- Keep core logic pure: deterministic input -> output transformations.
- Do not perform I/O, logging, env reads, time/random calls, or network in core functions.
- Pass external values (time, IDs, configuration, randomness) into the core as parameters.
- Return plain data and decisions from the core; avoid framework-bound return types.

## Shell Rules

- Shell code adapts external input into core input.
- Shell orchestrates side effects: persistence, network, logging, messaging.
- Shell applies effects produced by core decisions.
- Shell should translate and route; core should decide.

## Testing Split

- Unit-test core logic heavily with no mocks by default.
- Keep shell tests thin and focused on integration contracts.
- Verify boundary adapters preserve context and type expectations.
