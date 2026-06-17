# Requirements and Constraints

## Purpose

This document defines the requirements and constraints that shape EDD Platform's
architecture.

It is intentionally separate from implementation notes so product behavior,
system boundaries, and operational expectations can be reviewed without reading
code.

## Product Problem

Teams building AI agents often struggle to answer:

- What was the agent expected to do?
- What did it actually do?
- Which evidence proves a failure?
- What change was made to fix it?
- Did the candidate version improve without introducing regressions?
- Is the agent ready to promote?

EDD Platform turns those questions into product records.

## Assumptions

- A project is the main workspace boundary.
- Teams need deterministic local and CI behavior before live provider behavior.
- Live model calls and live judge calls are useful, but optional.
- Agent quality needs evidence, not just chat transcripts.
- Tool use must be governed by platform policy.
- Langfuse is useful observability, but product state must remain platform-owned.
- Early implementations can favor clear product records over premature scale
  infrastructure.

## Users and Jobs

| User | Job |
|---|---|
| AI engineer | Build and revise agent behavior based on failed evals. |
| Evaluation lead | Define expectations, review evidence, and approve gates. |
| Platform owner | Govern tools, runtime modes, provider usage, and traceability. |
| Reviewer | Inspect why a version passed, failed, improved, or regressed. |

## Functional Requirements

### Agent Design

- Users can create project-scoped agent designs.
- Agent designs capture intent and tool policy.
- Agent designs can produce versions so history remains reviewable.

### Scenarios

- Users can define reusable test cases.
- Scenarios can model single-turn, conversation, and trace-replay inputs.
- The same scenario can be run against multiple versions.

### Eval Contracts

- Users can define expectations as product data.
- Contracts can require tools, forbid tools, require evidence, define output
  requirements, and include deterministic checks.
- Contracts can optionally reference judge prompt templates.

### Runs

- Users can run an agent version against a scenario.
- Runs record input, output, mode, provider/model metadata, tool calls, tool
  results, and trace references when available.
- Runs can execute in mock, local, platform, or auto mode.

### Evaluations

- Users can evaluate a run against an eval contract.
- Deterministic checks execute before optional LLM judges.
- Eval results record pass/fail state, score, observed evidence, expected
  criteria, and linked artifacts.

### Failure and Fix Loop

- Failed checks can create failure packets.
- Fix proposals must link to the failure packets they address.
- Candidate versions can be created from fix proposals.
- Comparisons show fixed failures, new failures, and remaining failures.

### Gates

- Gate decisions convert evidence into readiness decisions.
- Gate decisions must link to supporting runs, evals, comparisons, failures,
  and approvals.

### Evidence Context

- Users can search and inspect artifacts.
- The platform can assemble deterministic context packs for review, fixing,
  comparison, and gate decisions.
- Context packs are assembled views, not a separate source of truth.

## Non-Functional Requirements

### Latency

Interactive UI operations should return quickly for product records and
evidence review. Long-running live runs, live judges, and future replay jobs
can move to asynchronous execution.

### Consistency

The platform should prioritize consistent evidence records over optimistic UI
shortcuts. A run or eval should not appear complete unless its durable evidence
has been written.

### Reliability

Mock mode and deterministic checks provide a reliable baseline. Optional
provider or observability failures should degrade gracefully and leave an
inspectable platform record.

### Cost

Live calls are opt-in. Deterministic checks run first. Token usage and cost
telemetry are recorded for live judge calls and summaries.

### Security and Governance

Tool definitions are platform-owned. Tools require approval before use. Agent
allowlists determine which approved tools can be used by a specific agent.

### Auditability

Promotion and comparison decisions must be explainable from linked artifacts,
not inferred from the latest score alone.

### Portability

Core product records should not depend on a single external observability tool
or provider. Trace references and provider metadata are linked evidence, not
the system of record.

## Explicit Non-Goals

- Generic chatbot UI.
- General-purpose memory system.
- Langfuse trace browser.
- Unbounded autonomous self-improvement.
- Hidden eval logic that only exists in code.
- CI that depends on provider credentials.
- A separate product frontend outside `apps/web`.

## Success Metrics

The architecture should support these measurable outcomes:

- A baseline and candidate version can be compared against the same scenario
  and contract.
- Every failed eval check can be traced to run evidence.
- Every fix proposal identifies the failures it addresses.
- Every promotion decision links to supporting evidence.
- Local tests and builds pass without provider keys.
- Live provider usage records token and cost telemetry where applicable.

