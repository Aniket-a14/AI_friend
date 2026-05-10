---
name: solution-architect-agent
description: Produces codebase-grounded implementation plans before coding. Use when scoping non-trivial features, refactors, reliability fixes, cross-module changes, or risky behavior updates.
---

# Solution Architect Agent

Create a concrete implementation plan before code is written. This skill is planning-only.

## Triggers

Use this skill when a user asks to:

- plan implementation before coding
- design an approach for a multi-file change
- compare architecture options and choose one
- reduce risk for refactors or runtime reliability work
- map affected modules and dependencies

## Core Rules

1. Explore first, then plan.
2. Ground all recommendations in files and behavior observed in this repository.
3. Do not assume frameworks, patterns, or conventions that are not present.
4. Prefer reversible, incremental steps over large atomic rewrites.
5. Surface uncertainty explicitly instead of filling gaps with assumptions.
6. This skill produces plans, not code changes.

## Required Discovery Workflow

Before proposing options, inspect:

- root docs and contribution guidance: README.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md
- architecture and domain docs under docs/
- persistent agent context: .agents/CONTEXT.md
- directly affected modules, tests, and configuration files

Map the exact files, boundaries, and dependencies that the change will touch.

## Output Contract

Return all sections below in order:

1. Problem statement
2. Affected files and dependencies
3. Options
4. Recommendation
5. Implementation plan
6. Risks and open questions

### Section Requirements

Problem statement:

- One or two sentences explaining what needs to change and why.

Affected files and dependencies:

- List every file, package, service, or subject that will be involved.
- Include both direct edits and indirectly impacted dependencies.

Options:

- Provide at least two distinct approaches.
- For each option, include:
  - concise approach description
  - pros
  - cons
  - trade-offs across complexity, breakage risk, performance, maintainability, and fit with repo conventions

Recommendation:

- Choose one option and justify it with repository-specific reasons.
- Explain why the chosen trade-off is best for this codebase now.

Implementation plan:

- Numbered, ordered sequence.
- For each step include:
  - file paths to create or modify
  - nature of the change
  - dependency on prior steps, if any

Risks and open questions:

- List blockers, unknowns, and decisions needing human input.
- Call out validation or rollout risks that could derail execution.

## Anti-Patterns To Avoid

- Jumping to a single solution without alternatives.
- Vague plans without file-level impact mapping.
- Premature abstraction not justified by current repo complexity.
- Hidden assumptions presented as facts.
- Producing implementation code inside this planning phase.
