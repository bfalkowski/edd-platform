# Architecture Readiness Brief

## Purpose

This brief summarizes the EDD Platform architecture in a form that can be used
to explain, review, and extend the system without depending on implementation
details.

The platform is designed around one product idea:

> Help teams design, run, evaluate, fix, compare, and promote AI agents using
> durable evidence.

## Users

### AI Engineer

Builds or revises an agent and needs to know whether a new version behaves
better than the previous one.

Needs:

- repeatable scenarios;
- explicit expectations;
- run and tool evidence;
- failure diagnosis;
- comparison across versions.

### Evaluation Lead

Owns quality criteria for agent behavior and reviews whether failures,
regressions, and fixes are supported by evidence.

Needs:

- reusable eval contracts;
- judge outputs and deterministic checks;
- linked failure packets;
- gate decisions with supporting evidence;
- cost and trace visibility for live evals.

### Platform Owner

Owns tool governance, safe runtime defaults, and operational confidence.

Needs:

- approved tool definitions;
- agent-level tool allowlists;
- deterministic local and CI behavior;
- optional live provider execution;
- clear separation between product state and observability systems.

## Success Criteria

The platform is successful when a team can:

1. define what good agent behavior means before or during iteration;
2. run a baseline agent version against a scenario;
3. evaluate the run against explicit expectations;
4. turn failures into actionable evidence;
5. propose a bounded fix;
6. create and run a candidate version;
7. compare baseline and candidate results;
8. make a promotion decision from linked evidence.

The key product outcome is not a single good answer. The key outcome is a
reviewable improvement loop.

## Functional Requirements

- Create and manage project-scoped agent designs.
- Define agent versions so baselines and candidates remain distinguishable.
- Define scenarios that can be rerun against different versions.
- Define eval contracts as data, not hardcoded checks.
- Run scenarios in deterministic and optional live modes.
- Capture run output, tool calls, tool results, and trace references.
- Evaluate runs with deterministic checks and optional LLM judges.
- Create failure packets from failed eval checks.
- Create bounded fix proposals linked to failures.
- Compare versions with fixed, new, and remaining failures.
- Create gate decisions with supporting evidence.
- Assemble evidence context packs for review and fix workflows.

## Non-Functional Requirements

### Determinism

Local development and CI must pass without model-provider credentials. Mock
runs and deterministic checks are the default reliability baseline.

### Traceability

Every meaningful generated or reviewed output should become an artifact or link
to one. The product must be able to explain why a version improved, regressed,
or is ready for promotion.

### Governance

Agents may only use platform-approved tools that are allowed for that agent or
scenario. Tool calls and tool results must be captured as evidence.

### Cost Control

Live model calls and LLM-as-judge calls are optional. Deterministic checks run
first. Live judge outputs record token and cost telemetry.

### Reliability

Provider outages, trace sync failures, and judge instability should not corrupt
platform state. The durable platform record is the API-owned product store.

### Reviewability

Users should be able to inspect the records behind every important decision:
run output, check result, judge output, failure packet, fix proposal,
comparison, and gate decision.

## High-Level Design

```text
React Console
  |
  | HTTP JSON
  v
Platform API
  |
  +-- Product Store
  |     projects, agents, versions, scenarios, contracts, runs,
  |     eval results, artifacts, links, gates
  |
  +-- Runner Package
  |     deterministic runs, optional live runs, approved tools,
  |     tool events, trace metadata
  |
  +-- Eval and Judge Services
  |     deterministic checks, optional LLM judges, failure packets
  |
  +-- Evidence Context
  |     artifact search, artifact links, context packs, summaries
  |
  +-- Langfuse Adapter
        trace references, scores, comments, observability links
```

## Core Data Flow

```text
AgentDesign
  -> AgentVersion
  -> Scenario
  -> Run
  -> EvalContract
  -> EvalResult / JudgeOutput
  -> FailurePacket
  -> FixProposal
  -> Candidate AgentVersion
  -> Comparison
  -> GateDecision
```

The run proves what happened. The eval explains whether it met expectations.
The failure packet explains what needs to change. The comparison explains
whether the change helped.

## Key Boundaries

| Component | Owns | Does not own |
|---|---|---|
| React console | product workflows, review surfaces, evidence navigation | durable product state |
| Platform API | state, artifacts, links, contracts, judges, gates | raw framework tool-loop mechanics |
| Runner package | scenario execution, tool adapters, mock/live run behavior | promotion decisions |
| Domain package | shared vocabulary and schema concepts | persistence or runtime policy |
| Langfuse adapter | external trace references and observability sync | source-of-truth product records |

## Primary Deep Dives

The two strongest technical areas to explain in depth are:

1. **Eval evidence pipeline**
   Scenario execution creates run evidence, eval results, failure packets, fix
   proposals, candidate versions, comparisons, and gate decisions.

2. **Tool governance boundary**
   Platform-owned tool definitions, approval state, and allowlists are adapted
   into runner-compatible tools while preserving tool-call evidence.

A third useful area is evidence context: artifacts remain the durable memory,
while context packs provide deterministic, purpose-specific assembled views.

## Open Scale Path

The current design is intentionally product-first and deterministic. As usage
grows, the clean extension points are:

- move long-running runs and evals to background workers;
- introduce queue-backed execution with idempotent run records;
- add database indexes for project, artifact type, run, and version queries;
- add object storage for large trace or artifact payloads;
- cache context packs and summaries by artifact revision;
- enforce tenant isolation and role-based permissions;
- introduce stricter OpenAPI linting and generated clients.

