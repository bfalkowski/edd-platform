# Public Docs Repo

## Destination

Public product documentation should live in
[bfalkowski/edd-platform-docs](https://github.com/bfalkowski/edd-platform-docs).

This repo remains the implementation source of truth. The public docs repo
should carry user-facing concepts, guides, API references, architecture notes,
and demo walkthroughs that are safe to publish.

## Initial Population Checklist

- Product overview: migrate the public-safe thesis and demo flow from
  `README.md`.
- Product concepts: adapt `docs/PRODUCT_SPINE.md` into concise public pages for
  agent designs, scenarios, eval contracts, runs, eval results, failure packets,
  fix proposals, comparisons, gates, and evidence context.
- Getting started: adapt `docs/HAPPY_PATH_WALKTHROUGH.md` into a local demo
  guide with deterministic-first steps and optional live OpenAI/Langfuse setup.
- API reference: publish generated OpenAPI from `docs/openapi.json` and link to
  the contract rules in `docs/API_CONTRACT.md`.
- Architecture: adapt `docs/ARCHITECTURE.md`,
  `docs/ARCHITECTURE_READINESS_BRIEF.md`, `docs/SYSTEM_TRADEOFFS.md`,
  `docs/OPERABILITY_AND_FAILURE_MODES.md`, and
  `docs/ARCHITECTURE_DEEP_DIVES.md` into public-safe architecture pages.
- Error analysis: document the review corpus, annotations, FailureMode taxonomy,
  Langfuse import landing zones, sampling plan, promotion flow, and Polars
  analysis plane.
- Langfuse integration: document that Langfuse is observability and experiment
  infrastructure while EDD artifacts remain the source of truth.
- Tool governance: document platform-owned tool definitions, approval, schema
  contracts, adapter projections, agent allowlists, and eval validation.

## Migration Rules

- Keep private planning notes, local-only scratch files, credentials, and
  provider keys out of the public docs repo.
- Prefer product language from `docs/PRODUCT_SPINE.md`.
- Keep examples deterministic by default; mark OpenAI and Langfuse live flows as
  optional.
- Link back to this implementation repo for source code, local development, and
  generated API artifacts.
