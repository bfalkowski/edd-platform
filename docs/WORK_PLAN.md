# EDD Platform Work Plan

This document is the public milestone map for the consolidated EDD Platform
repo.

Beads is the operational task tracker. Use Beads for active ownership,
dependencies, blockers, resume state, and verification notes. Update this file
only when milestone state, product direction, or public planning anchors change.

Last Beads reconciliation: 2026-07-01.

At reconciliation time, Beads reported 41 total issues: 40 closed, 0 in
progress, and 1 open (1 ready to work).

Note: work between 2026-06-26 and 2026-07-01 (19 commits hardening the wizard
and rebuilding error analysis) was tracked in a local scratch checklist during
active development and reconciled into Beads afterward as the closed
`edd-ddd` epic below. Beads is best suited to epic/milestone-level tracking;
reconcile fast iteration bursts back into it promptly once they land.

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
- [`ARCHITECTURE.md`](ARCHITECTURE.md) defines the implemented system shape,
  requirements, component deep dives, and operability/failure-mode behavior.
- [`SYSTEM_TRADEOFFS.md`](SYSTEM_TRADEOFFS.md) records the reasoning behind
  the core architecture decisions.
- [`hld/HLD-004-eval-contracts-runs-judges-and-fixes.md`](hld/HLD-004-eval-contracts-runs-judges-and-fixes.md)
  defines the eval-driven implementation backbone.
- [`hld/HLD-005-relational-metadata-and-polars-analysis-plane.md`](hld/HLD-005-relational-metadata-and-polars-analysis-plane.md)
  defines the Postgres metadata store plus Polars trace/corpus analysis plane.
- [`API_CONTRACT.md`](API_CONTRACT.md) defines API contract rules and OpenAPI
  generation.
- [`HAPPY_PATH_WALKTHROUGH.md`](HAPPY_PATH_WALKTHROUGH.md) is the canonical
  manual smoke script for validating the product flow.
- [`engineering/TASK_TRACKING.md`](engineering/TASK_TRACKING.md) defines how
  this file and Beads work together.

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

Complete for the current product slice.

Includes deterministic and live runner paths, scenario records, eval contracts,
agent versions, project-scoped runs, contract-driven eval results, judge
outputs, failure packets, fix proposals, comparisons, tool-call/tool-result
evidence, and generated OpenAPI coverage for the backbone.

Final backbone hardening included extracting API schemas, state/bootstrap,
lookup helpers, eval checks, evidence context, tool adapter contracts, storage,
and service status into focused modules.

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

### Wizard Hardening and Error-Analysis Rebuild

Complete for the current product slice.

Includes iteration context carried into the failure step after a failed
compare, a model selector (haiku/sonnet/opus) in the wizard run step, inline
error recovery with retry on mid-wizard failures, a fix for the wizard
dismissing itself mid-flow, sidebar re-entry that reopens the wizard at the
agent's current evidence-state step (or the workspace directly for a
complete agent), and a full rebuild of Error analysis into the 4-step wizard
(Build review set -> Review & code -> Confirm modes -> Done) with Langfuse
comment sync (`POST .../sync-langfuse-comments`) replacing the open-coded
in-platform annotation flow. Langfuse is now required, not optional, for
error analysis. Runs are live-only (mock mode removed).

One item from this slice remains open: the wizard's done state still uses a
separate "View evidence" button rather than an inline evidence chain
(`edd-1z6`).

## Beads Queue At Last Reconciliation

Use `bd ready` and `bd list` for the source of truth. At the 2026-07-01
reconciliation, one task was open and ready. Recently completed epics and
final hardening tasks were:

| Bead | Priority | Status | Scope |
|---|---|---|---|
| `edd-wnt` | P1 | closed epic | Prove eval-driven design for arbitrary agents. |
| `edd-e9d` | P1 | closed epic | Langfuse-backed eval data plane. |
| `edd-wnt.4` | P2 | closed | Refactor `apps/api/edd_platform_api/main.py` into focused modules without changing public API behavior. |
| `edd-wnt.6` | P2 | closed | Finish schema-first tool registry adapters. |
| `edd-e9d.5` | P2 | closed | Surface Langfuse evidence in UI and context packs. |
| `edd-wnt.5` | P3 | closed | Populate the dedicated public docs repo. |
| `edd-6dn` | P2 | closed | Design relational metadata plus Polars trace analysis plane. |
| `edd-eoa` | P2 | closed | Implement first Polars analysis snapshot materializer. |
| `edd-ddd` | P1 | closed epic | Wizard hardening and error-analysis rebuild (retroactive reconciliation of the 2026-06-28 to 2026-07-01 burst). |
| `edd-1z6` | P2 | **open, ready** | Wizard done state: show evidence inline instead of the separate "View evidence" button. |

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
11. Use the Error analysis tab's 4-step wizard (Build review set -> Review &
    code -> Confirm modes -> Done) to pull live runs into a review corpus,
    annotate traces in Langfuse, sync comments back with one click, assign
    failure modes inline, and promote recurring modes into the taxonomy.
    Langfuse must be running for this tab.
12. Use the Readiness tab to create gates and gate decisions.

## Next Product Hardening

Create the next Beads task before starting implementation work. Candidate
hardening areas are:

- close `edd-1z6`: show evidence inline in the wizard done state instead of
  the separate "View evidence" button;
- visual redesign (Anthropic-style tokens, typography, wizard shell) tracked
  in `TODO.md`;
- improve evidence-summary display;
- broaden run history and trace replay views;
- harden async execution design for long-running run/eval workloads.
