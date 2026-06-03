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
| Evidence context packs | HLD-001 | covered | partial | covered | Basic context packs exist; richer purposes remain later. |
| Agent design | HLD-002, HLD-003 | covered | covered | covered | Create/list/delete and left-nav UI exist. |
| Platform tools | HLD-002, HLD-004 | partial | partial | partial | Tool definitions exist; editing/governance UI is missing. |
| Agent versions | HLD-001, HLD-004 | planned | gap | gap | Planned in `API_CONTRACT.md`; implementation missing. |
| Scenarios | HLD-003, HLD-004 | planned | partial | partial | Scenario input exists in playground; scenario artifact/API implementation is not first-class yet. |
| Eval contracts | HLD-003, HLD-004 | planned | gap | gap | Planned in `API_CONTRACT.md`; central next dependency. |
| Runs | HLD-002, HLD-003, HLD-004 | planned | partial | partial | Agent-scoped run endpoint exists; canonical project-scoped run API is planned. |
| Tool call evidence | HLD-004 | partial | partial | partial | Stored in run artifact body; should become first-class evidence. |
| Eval results | HLD-003, HLD-004 | planned | partial | partial | Eval endpoint exists, but checks are hardcoded; contract-driven API is planned. |
| Judge prompts | HLD-002, HLD-003, HLD-004 | gap | gap | gap | Mentioned in docs, not modeled in API yet. |
| Judge outputs | HLD-001, HLD-004 | planned | gap | gap | Need implementation and linked artifact shape. |
| Failure packets | HLD-001, HLD-003, HLD-004 | planned | gap | gap | Planned in `API_CONTRACT.md`; needed for EDD proof loop. |
| Fix proposals | HLD-001, HLD-003, HLD-004 | planned | gap | gap | Planned in `API_CONTRACT.md`; needed for bounded improvement. |
| Comparisons | HLD-001, HLD-004 | planned | gap | gap | Planned in `API_CONTRACT.md`; needed for v0/v1 proof. |
| Gates | HLD-002, HLD-003 | gap | gap | partial | Concept exists, implementation is later. |
| Gate decisions | HLD-001, HLD-002 | gap | gap | partial | Later readiness milestone. |
| Langfuse trace refs | HLD-001, HLD-002 | gap | gap | partial | Boundary is clear; adapter remains future work. |
| Frontend design language | Frontend guide | n/a | covered | covered | Use `docs/design/FRONTEND_GUIDE.md`. |
| AI-agent development guardrails | Engineering guide | n/a | n/a | covered | Use `docs/engineering/AI_AGENT_DEVELOPMENT.md`. |

## Immediate Planning Gaps

The repo should not add more workflow feature code until these gaps are covered
by HLD and OpenAPI contracts:

1. implement `EvalContract` API
2. implement `Scenario` API
3. implement first-class `Run` API
4. implement contract-driven `EvalResult`
5. implement `JudgeOutput` artifacts
6. implement `FailurePacket` API
7. implement `FixProposal` API
8. implement `AgentVersion` API
9. implement `Comparison` API

## Rule

When a capability is marked `gap`, implementation work should start with an HLD
or API contract update, not UI polish.
