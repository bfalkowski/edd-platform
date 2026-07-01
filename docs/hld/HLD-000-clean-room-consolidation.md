# HLD-000: Clean-Room Consolidation Plan

## Status

Implemented. See `docs/ARCHITECTURE.md` and `docs/WORK_PLAN.md` for current implementation detail.

## Purpose

This HLD defines the starting shape for the consolidated EDD Platform repo.

The goal is to build a new product repo without importing old repo history or
bulk-copying legacy structure. Useful implementation pieces may be copied later,
but each copied piece should be intentional, renamed into the new product model,
and tested in the new repo.

## Decision

Create a new repo with one product UI and one backend.

```text
EDD Platform
  React console
  Platform API
  Domain package
  Runner package
  Langfuse adapter
```

Do not preserve two product UIs.

Do not preserve Streamlit as a product surface.

Do not preserve Agent Lab as a separate frontend.

## Target Structure

```text
apps/
  web/
  api/

packages/
  domain/
  runner/
  langfuse-adapter/

examples/
  customer-triage/

docs/
  hld/

scripts/
```

## Migration Order

1. Create clean skeleton.
2. Move the React console into `apps/web`.
3. Move the platform API into `apps/api`.
4. Move shared schemas into `packages/domain`.
5. Move runnable LangGraph code into `packages/runner`.
6. Move Langfuse integration into `packages/langfuse-adapter` or `apps/api`.
7. Wire one deterministic mock execution loop.
8. Add evidence context.

## Copy Rules

Every imported file must answer:

- Is this still part of the new product?
- Does its naming match the new product language?
- Does it avoid legacy UI assumptions?
- Can it be tested in the new repo?

If not, rewrite it or leave it behind.

## Product Language

| Old language | New language |
|---|---|
| Lab UI | Historical debug UI |
| Lab | Runner |
| Draft | Agent design |
| Publish | Return evidence / import evidence |
| Streamlit console | Historical MVP console |
| Platform console | React product console |

## First Acceptance Criteria

- Repo has one product README.
- Repo has the target folder structure.
- Repo has no copied legacy implementation.
- Repo has an initial git commit with no co-author trailer.
- Next work can move React console and API intentionally.

