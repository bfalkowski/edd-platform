# EDD Platform Work Plan

This document is the public milestone map for the consolidated EDD Platform
repo.

Beads is the operational task tracker. Use Beads for active ownership,
dependencies, blockers, resume state, and verification notes. Update this file
only when milestone state, product direction, or public planning anchors change.

Last Beads reconciliation: 2026-06-17.

At reconciliation time, Beads reported 15 total issues: 9 closed, 1 in
progress, and 5 open.

## Product Direction

EDD Platform is one React console, one platform API, runner packages behind the
API, and evidence artifacts as the durable memory of the workflow.

The product proves evaluation-driven agent design:

```text
AgentDesign
  -> AgentVersion
  -> Scenario
  -> EvalContract
  -> Run
  -> EvalResult / JudgeOutput
  -> FailurePacket
  -> FixProposal
  -> Comparison
  -> GateDecision
  -> EvidenceContext
```

## Planning Anchors

- [`PRODUCT_SPINE.md`](PRODUCT_SPINE.md) defines the canonical product objects.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) summarizes the implemented system shape.
- [`ARCHITECTURE_READINESS_BRIEF.md`](ARCHITECTURE_READINESS_BRIEF.md) defines
  users, requirements, constraints, boundaries, and scale path.
- [`REQUIREMENTS_AND_CONSTRAINTS.md`](REQUIREMENTS_AND_CONSTRAINTS.md),
  [`SYSTEM_TRADEOFFS.md`](SYSTEM_TRADEOFFS.md),
  [`OPERABILITY_AND_FAILURE_MODES.md`](OPERABILITY_AND_FAILURE_MODES.md), and
  [`ARCHITECTURE_DEEP_DIVES.md`](ARCHITECTURE_DEEP_DIVES.md) capture the
  architecture reasoning that guides implementation.
- [`HLD_COVERAGE_MATRIX.md`](HLD_COVERAGE_MATRIX.md) tracks planning coverage
  before feature code.
- [`hld/HLD-004-eval-contracts-runs-judges-and-fixes.md`](hld/HLD-004-eval-contracts-runs-judges-and-fixes.md)
  defines the eval-driven implementation backbone.
- [`API_CONTRACT.md`](API_CONTRACT.md) defines API contract rules and OpenAPI
  generation.
- [`HAPPY_PATH_WALKTHROUGH.md`](HAPPY_PATH_WALKTHROUGH.md) is the canonical
  manual smoke script for validating the product flow.
- [`engineering/TASK_TRACKING.md`](engineering/TASK_TRACKING.md) defines how
  this file and Beads work together.
- [`PUBLIC_DOCS_REPO.md`](PUBLIC_DOCS_REPO.md) links the public documentation
  repo and tracks the initial migration checklist.

## Completed Milestones

### Repo Foundation

Complete.

Includes the monorepo scaffold, React console, FastAPI API, domain package,
local dev/test scripts, GitHub Actions CI, OpenAPI export/lint/tests, design
guide, architecture overview, architecture reasoning docs, and AI-assisted
development guardrails.

### Evidence Spine

Complete.

Includes project-scoped agent designs, artifacts, artifact search, artifact
detail, artifact links, deterministic context packs, related-evidence UI, and
persistent state beyond in-memory storage.

### Eval Contract Backbone

Substantially complete.

Includes deterministic and live runner paths, scenario records, eval contracts,
agent versions, project-scoped runs, contract-driven eval results, judge
outputs, failure packets, fix proposals, comparisons, tool-call/tool-result
evidence, and generated OpenAPI coverage for the backbone.

Remaining backbone hardening is tracked in Beads, especially API module
refactoring.

### Builder UI for the EDD Loop

Complete for the current proof-loop vertical slice.

The React console can create/select agents, edit agent profile and tool
allowlists, create scenarios and eval contracts, run/evaluate baseline and
candidate versions, inspect failure packets and fix proposals, create candidate
versions, compare versions, reconstruct the proof loop after refresh, and keep
generated or edited outputs represented as artifacts.

### Judges and Gates

Complete for the current product slice.

Includes platform-stored judge prompts, mock judge execution, optional live
LLM-as-judge execution, gate definitions, gate decision artifacts, token/cost
telemetry for live judge calls, and readiness views backed by gate decisions.

### Langfuse Adapter

Complete for the current product slice.

Includes trace reference artifacts, adapter package implementation, trace links
inside evidence context, live agent trace capture, raw OpenAI Responses
generation observations, scenario dataset sync, eval score refs, prompt links,
review-note comment mirroring, surfaced Langfuse refs in context packs and the
review panel, and a live E2E script.

### Context Intelligence

Complete for the current product slice.

Includes richer context pack purposes, deterministic context assembly
strategies, optional LLM evidence summaries, summary caching, and summary
token/cost telemetry.

### Discovery Loop Workbench

Complete for the current product slice.

Includes first-class review corpora, trace/artifact review items, open-coded
annotations, FailureMode records, agent suggestions, Langfuse queue/score import
landing zones, breadth/depth/recoding sampling, promotion of accepted findings
into proof-loop evidence, and a Polars read-side analysis plane for corpus
coverage and failure-rate summaries.

## Beads Queue At Last Reconciliation

Use `bd ready` and `bd list` for the source of truth. At the 2026-06-17
reconciliation, open work was:

| Bead | Priority | Status | Scope |
|---|---|---|---|
| `edd-wnt` | P1 | open epic | Prove eval-driven design for arbitrary agents. |
| `edd-e9d` | P1 | open epic | Langfuse-backed eval data plane. |
| `edd-wnt.4` | P2 | in progress | Refactor `apps/api/edd_platform_api/main.py` into focused modules without changing public API behavior. |
| `edd-wnt.6` | P2 | open | Finish schema-first tool registry adapters. |
| `edd-e9d.5` | P2 | open | Surface Langfuse evidence in UI and context packs. |
| `edd-wnt.5` | P3 | open | Populate the dedicated public docs repo. |

## Current UI Status

The UI supports the proof-loop vertical slice:

1. Start the app with `./scripts/dev.sh`.
2. Open `http://localhost:5173`.
3. Create or select an agent from the left rail.
4. Edit the agent profile and tool allowlist from the Agent tab and right-side
   tool manager.
5. In Proof loop, create a test case from the right panel.
6. Choose a test shape: single turn, conversation, or trace replay.
7. Choose a judge method: rubric judge, tool use, or exact text.
8. Run and evaluate the baseline version in mock or live mode.
9. Open failed checks, add review notes, propose a bounded fix, create a
   candidate version, rerun, reevaluate, and compare.
10. Inspect evidence artifacts, related evidence, and Langfuse trace links from
    the right review panel.
11. Use the Error analysis tab for trace review, open-coded notes, failure
    taxonomy, sampling suggestions, promotion into proof-loop evidence, and
    corpus analytics.
12. Use the Readiness tab to create gates and gate decisions.

## Next Product Hardening

Keep the next work aligned with the active Beads queue:

- refactor the API main module into focused route, model, service, storage, and
  app-wiring modules;
- improve evidence-summary display and broader run/replay views;
- migrate the public docs checklist into the dedicated docs repo.
