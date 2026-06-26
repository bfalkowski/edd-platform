# HLD Coverage Matrix

## Status

Draft

## Purpose

This matrix shows whether the current HLD set covers the product spine clearly
enough to implement without drift.

Statuses:

- `covered`: clear enough to implement
- `partial`: concept exists, but implementation details are incomplete
- `gap`: missing or too vague

## Matrix

| Capability | Primary HLD | API contract | UI model | Status | Notes |
|---|---|---|---|---|---|
| Clean-room consolidation | HLD-000 | n/a | n/a | covered | Establishes one repo, one UI, one API. |
| Requirements and constraints | Architecture readiness brief, Requirements and constraints | n/a | n/a | covered | Product users, functional requirements, non-functional requirements, assumptions, and success criteria are documented. |
| System tradeoffs | System tradeoffs | n/a | n/a | covered | Core architecture tradeoffs are documented for artifacts, contracts, checks, tools, Langfuse, repo shape, and async growth. |
| Operability and failure modes | Operability and failure modes | partial | partial | covered | Expected behavior is documented for provider failures, trace sync failures, invalid tools, regressions, stale context, and cost spikes. |
| Architecture deep dives | Architecture deep dives | partial | partial | covered | Eval evidence pipeline, tool governance, evidence context, and promotion readiness have expanded design notes. |
| Evidence artifacts | HLD-001, HLD-002 | covered | partial | covered | Artifact list/search/detail/link exist. |
| Evidence context packs | HLD-001 | covered | partial | covered | Purpose-specific deterministic context packs exist for prompt review, fix proposal generation, gate review, and version comparison. |
| Evidence summaries | HLD-001 | covered | gap | partial | Deterministic and optional live summaries exist with cache and token/cost telemetry; UI display is missing. |
| Agent design | HLD-002, HLD-003 | covered | covered | covered | Create/list/delete and left-nav UI exist. |
| Platform tools | HLD-002, HLD-004 | covered | partial | partial | Tool definitions, approval, search/filter, draft creation, agent allowlists, schema-first adapter contracts, and runner adapters exist; broader UI polish remains partial. |
| Agent versions | HLD-001, HLD-004 | partial | partial | partial | Baseline and candidate versions are created through the proof loop; broader version management UI is still planned. |
| Scenarios | HLD-003, HLD-004 | partial | partial | partial | Scenario APIs exist and the UI creates scenario-backed test cases with single-turn, conversation, and trace-replay shapes. |
| Eval contracts | HLD-003, HLD-004 | partial | partial | partial | The UI creates contracts for rubric judge, tool-use, and exact-text checks; richer contract editing is still planned. |
| Runs | HLD-002, HLD-003, HLD-004 | partial | partial | partial | Project-scoped runs and proof-loop run actions exist; run history and broader replay UI are still planned. |
| Tool call evidence | HLD-004 | partial | partial | covered | Tool calls and tool results are emitted as first-class evidence artifacts and shown in related evidence. |
| Eval results | HLD-003, HLD-004 | partial | partial | covered | Contract-driven run evaluation exists for deterministic checks and optional live judges. |
| Judge prompts | HLD-002, HLD-003, HLD-004 | covered | partial | partial | Prompt templates are stored as artifacts and can be linked to eval contracts; direct prompt-template management UI is still planned. |
| Judge outputs | HLD-001, HLD-004 | partial | partial | covered | Deterministic and optional live judge output artifacts are created during run evaluation and linked into evidence. |
| Failure packets | HLD-001, HLD-003, HLD-004 | partial | partial | partial | API and automatic failed-eval creation exist; the proof loop supports open-coded failure notes, while full taxonomy/error-analysis views are planned. |
| Fix proposals | HLD-001, HLD-003, HLD-004 | partial | partial | partial | API, evidence links, and proof-loop actions exist; richer editing/version management is still planned. |
| Comparisons | HLD-001, HLD-004 | partial | partial | partial | API and proof-loop comparison artifacts exist; broader comparison review UI is still planned. |
| Gates | HLD-002, HLD-003 | covered | partial | partial | Gate definitions are stored as artifacts and can be created from the readiness view. |
| Gate decisions | HLD-001, HLD-002 | covered | partial | partial | Gate decisions create readiness artifacts linked to gate and supporting evidence. |
| Langfuse trace refs | HLD-001, HLD-002 | covered | partial | covered | Trace refs are stored as artifacts with Open trace links; live agent runs create Langfuse agent observations with child generation observations for raw OpenAI calls. |
| Frontend design language | Frontend guide | n/a | covered | covered | Use `docs/design/FRONTEND_GUIDE.md`. |
| AI-agent development guardrails | Engineering guide | n/a | n/a | covered | Use `docs/engineering/AI_AGENT_DEVELOPMENT.md`. |

## Immediate Planning Gaps

The Phase 2 EDD backbone is now covered by HLD and OpenAPI contracts. The next
gaps are broader run/replay views, evidence-summary UI, public docs migration,
and eventual async execution design for long-running run/eval workloads.

## Rule

When a capability is marked `gap`, implementation work should start with an HLD
or API contract update, not UI polish.
