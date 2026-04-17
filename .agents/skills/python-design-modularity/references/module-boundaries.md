# Module Boundaries and Ownership

## Outcome

Modules remain independently understandable and safely evolvable.

## Ownership Rules

- Each module owns its data, invariants, and internal structures.
- Keep persistence models and storage details private to the owning module.
- Cross-module interaction must use explicit public interfaces.

## Data Sharing Rules

- Share only the minimum data required for the use case.
- Prefer immutable DTO/value-style payloads for cross-module exchange.
- Do not expose mutable internal state across boundaries.

## Consistency Rules

- Treat each module as the unit of immediate consistency.
- Do not span transactions across module boundaries.
- Use events, jobs, or queued commands for cross-module workflows.
- Design cross-module flows for eventual consistency by default.

## Service Interaction Rules

- Avoid direct service-to-service domain call chains in request handling.
- During request handling, allow orchestration interactions only:
  - event publication
  - job/command enqueueing
  - infrastructure services (auth, logging, metrics)
- Keep business decisions local to the handling module.

## Architectural Intent

- Prefer a modular monolith with strict boundaries over premature microservice splits.
- Use service decomposition only when team/org scaling needs exceed module-level separation.
