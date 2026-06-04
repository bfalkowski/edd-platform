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
| Evidence artifacts | HLD-001, HLD-002 | covered | partial | covered | Artifact list/search/detail/link exist. |
| Evidence context packs | HLD-001 | covered | partial | covered | Purpose-specific deterministic context packs exist for prompt review, fix proposal generation, gate review, and version comparison. |
| Evidence summaries | HLD-001 | covered | gap | partial | Deterministic and optional live summaries exist with cache and token/cost telemetry; UI display is missing. |
| Agent design | HLD-002, HLD-003 | covered | covered | covered | Create/list/delete and left-nav UI exist. |
| Platform tools | HLD-002, HLD-004 | partial | partial | partial | Tool definitions exist; editing/governance UI is missing. |
| Agent versions | HLD-001, HLD-004 | partial | gap | partial | Create/list/get API exists; versioned runs and comparison are missing. |
| Scenarios | HLD-003, HLD-004 | partial | partial | partial | Create/list/get API exists; playground is not yet driven by scenario records. |
| Eval contracts | HLD-003, HLD-004 | partial | gap | partial | Create/list/get API exists; evaluation does not yet consume contracts. |
| Runs | HLD-002, HLD-003, HLD-004 | partial | partial | partial | Canonical project-scoped run API exists; contract-driven evaluation is missing. |
| Tool call evidence | HLD-004 | partial | partial | partial | Stored in run artifact body; should become first-class evidence. |
| Eval results | HLD-003, HLD-004 | partial | partial | partial | Contract-driven run evaluation API exists; failure packets are next. |
| Judge prompts | HLD-002, HLD-003, HLD-004 | covered | gap | partial | Prompt templates are stored as artifacts and can be linked to eval contracts. |
| Judge outputs | HLD-001, HLD-004 | partial | gap | partial | Deterministic and optional live judge output artifacts are created during run evaluation. |
| Failure packets | HLD-001, HLD-003, HLD-004 | partial | gap | partial | API and automatic failed-eval creation exist; UI is missing. |
| Fix proposals | HLD-001, HLD-003, HLD-004 | partial | gap | partial | API and evidence artifact links exist; UI is missing. |
| Comparisons | HLD-001, HLD-004 | partial | gap | partial | API and comparison artifacts exist; UI is missing. |
| Gates | HLD-002, HLD-003 | covered | partial | partial | Gate definitions are stored as artifacts and can be created from the EDD loop. |
| Gate decisions | HLD-001, HLD-002 | covered | partial | partial | Gate decisions create readiness artifacts linked to gate and supporting evidence. |
| Langfuse trace refs | HLD-001, HLD-002 | covered | partial | covered | Trace refs are stored as artifacts with links to external Langfuse traces; adapter package builds platform payloads. |
| Frontend design language | Frontend guide | n/a | covered | covered | Use `docs/design/FRONTEND_GUIDE.md`. |
| AI-agent development guardrails | Engineering guide | n/a | n/a | covered | Use `docs/engineering/AI_AGENT_DEVELOPMENT.md`. |

## Immediate Planning Gaps

The Phase 2 EDD backbone is now covered by HLD and OpenAPI contracts. The next
gaps are workflow UI and deeper judge/tool evidence modeling.

## Rule

When a capability is marked `gap`, implementation work should start with an HLD
or API contract update, not UI polish.
