# Operability and Failure Modes

## Purpose

This document describes how EDD Platform should behave when dependencies fail,
records are incomplete, or eval outcomes are ambiguous.

The platform should prefer durable, inspectable records over silent success.

## Operating Principles

- Platform artifacts are the source of truth.
- Optional integrations should degrade gracefully.
- Failed or partial work should leave reviewable status.
- Live provider behavior should not be required for local or CI confidence.
- Promotion decisions should be explicit and evidence-backed.

## Runtime Modes

| Mode | Purpose | Failure posture |
|---|---|---|
| `mock` | Deterministic local and CI execution | should be stable and provider-free |
| `local` | Developer provider experiments | may fail due to local credentials or provider access |
| `platform` | Canonical live routing | should record provider metadata and failures |
| `auto` | Prefer live when configured, otherwise mock | should clearly report selected mode |

## Failure Modes

### Live Provider Unavailable

Risk:

- A live run or live judge cannot complete.

Expected behavior:

- Mark the run or judge output as failed.
- Preserve input, mode, provider/model metadata, and error summary.
- Do not create a successful eval result from missing output.
- Allow deterministic mock mode to continue working.

### Langfuse Sync Fails

Risk:

- A run succeeds, but trace creation, score sync, or comment mirroring fails.

Expected behavior:

- Preserve normalized run and eval artifacts in platform state.
- Record trace sync status or missing trace reference clearly.
- Do not block the core evidence loop on observability sync.

### Tool Schema Invalid

Risk:

- A tool definition cannot be safely adapted into runner/framework primitives.

Expected behavior:

- Keep the tool in draft or invalid state.
- Do not allow the tool in agent execution.
- Surface validation errors near the tool definition.
- Prevent eval contracts from requiring unavailable tools without warning.

### Agent Calls Unapproved Tool

Risk:

- The agent attempts a tool call outside its allowlist or outside approved
  platform policy.

Expected behavior:

- Block the tool execution.
- Record the attempted call as evidence when possible.
- Fail relevant eval checks.
- Create or support a failure packet that identifies the policy violation.

### Run Succeeds But Evidence Write Fails

Risk:

- The runner returns output, but the API cannot persist run evidence.

Expected behavior:

- Treat the product operation as incomplete.
- Do not report a complete run unless durable evidence exists.
- Preserve enough error information for retry or review.

### Judge Output Is Inconsistent

Risk:

- An LLM judge returns malformed output, contradicts deterministic checks, or
  produces low-confidence reasoning.

Expected behavior:

- Prefer deterministic check results where applicable.
- Store malformed or low-confidence judge output as failed judge evidence.
- Avoid silent score changes.
- Require review or rerun when pass/fail cannot be trusted.

### Candidate Fix Introduces Regression

Risk:

- A candidate version fixes one failure but fails another requirement.

Expected behavior:

- Comparison should show fixed, new, and remaining failures.
- Gate decisions should consider regressions explicitly.
- The candidate should not silently replace baseline behavior.

### Stale Context Pack

Risk:

- A context pack was assembled before new artifacts or links were created.

Expected behavior:

- Context packs should be rebuildable from current artifacts.
- Summaries should be cacheable only when underlying artifact revisions have
  not changed.
- UI should favor fresh context for gate decisions and fix proposals.

### Cost Spike From Live Evaluation

Risk:

- Repeated live runs, LLM judges, or summaries create unexpected cost.

Expected behavior:

- Live behavior remains opt-in.
- Token usage and cost telemetry are stored for live judge and summary calls.
- Deterministic checks run first to avoid unnecessary judge calls.

### Partial Comparison Inputs

Risk:

- Baseline or candidate runs exist without corresponding eval results.

Expected behavior:

- Comparison should report missing inputs instead of inferring improvement.
- The UI should guide the user to run or evaluate the missing side.
- Gate decisions should require complete supporting evidence.

## Observability

The platform should expose enough metadata for operators and reviewers to
answer:

- Which runtime mode was used?
- Which provider and model were called?
- Which tools were available?
- Which tools were actually called?
- Which eval contract version was used?
- Which judge prompt version was used?
- Which artifacts support the decision?
- Was trace sync available?

## Recovery Paths

| Failure | Recovery |
|---|---|
| Provider unavailable | rerun in mock mode or retry live later |
| Langfuse sync failure | keep platform evidence, retry trace sync when supported |
| Invalid tool schema | edit schema, keep tool draft until approved |
| Failed eval | inspect failure packet, propose bounded fix |
| Regression | keep candidate separate, compare against baseline |
| Missing evidence | rebuild context pack or rerun incomplete operation |

## Reliability Priorities

1. Keep platform records durable and project-scoped.
2. Keep local and CI paths deterministic.
3. Keep live integrations optional.
4. Keep evidence links explicit.
5. Keep promotion decisions reviewable.

