# Product Spine

## Status

Current — canonical product vocabulary for the implemented product slice.

## Purpose

This document defines the canonical product backbone for EDD Platform.

It exists to prevent drift. Before adding feature code, UI surfaces, or runner
behavior, the work should map to one or more objects in this spine.

## Product Thesis

EDD Platform helps users design, run, evaluate, fix, and compare agents using
durable evidence.

The platform is not a generic chat UI. It is not a trace browser. It is not a
local demo workbench. It is an evidence system for improving agent behavior.

## Spine

```text
Project
  -> AgentDesign
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

## Objects

### Project

A project is the workspace boundary.

Owns:

- agent designs
- tools
- eval contracts
- runs
- artifacts
- links
- gates

### AgentDesign

An agent design is the user-facing agent workspace.

It starts with a name and intent, but it should grow into a structured design
surface with scenarios, tool policy, expectations, runs, failures, fixes, and
versions.

### AgentVersion

An agent version is a specific candidate behavior for an agent design.

Versions make improvement measurable. A fix should create or target a candidate
version instead of mutating all history in place.

Expected examples:

- `v0` baseline
- `v1` first bounded fix
- `v2` later improvement

### Scenario

A scenario defines what the runner executes.

It should describe:

- input
- setup context
- available fixtures
- expected evidence
- relevant eval contract

The UI presents scenarios as test cases. A test case can be a single-turn
prompt, a conversation turn with prior messages, or a trace replay seed. The
current implementation stores that UI shape in `setup_context` while the runner
continues to execute the scenario `input`.

Scenarios must support deterministic local/CI execution and optional live
provider execution.

### EvalContract

An eval contract is the first-class place where expectations live.

It should describe arbitrary agent behavior, not one hardcoded demo:

- expected behavior
- required evidence
- tool expectations
- forbidden behavior
- output shape
- deterministic checks
- judge prompt reference
- pass/fail gate criteria

Contracts are product data. They should not live only in code.

### Run

A run records what happened when a selected agent version handled a scenario.

It should capture:

- agent design and version
- scenario
- mode (`mock` — deterministic, CI/test only, never exposed in the console;
  `live` — the only mode reachable from the wizard)
- provider/model if live
- tool calls and tool results
- output text
- trace references when available

### EvalResult

An eval result records how a run performed against an eval contract.

It should capture:

- contract id/version
- run id
- deterministic check results
- judge output references
- pass/fail decision
- score when applicable

### JudgeOutput

A judge output is the raw or structured result from a deterministic judge or
LLM-as-judge.

It should be linked to:

- eval contract
- judge prompt template
- run
- eval result

### FailurePacket

A failure packet turns a failed eval into actionable evidence.

It should answer:

- what failed?
- what evidence proves it failed?
- which contract check or judge criterion failed?
- why does it matter?
- what kind of fix should be attempted?

### FixProposal

A fix proposal is a bounded change intended to address one or more failure
packets.

It should identify:

- target agent/version
- addressed failures
- proposed behavior change
- affected prompt/tool/contract/scenario surface
- validation plan

### Comparison

A comparison explains whether a candidate version improved, regressed, or stayed
flat relative to a baseline.

It should reference:

- baseline run/eval
- candidate run/eval
- fixed failures
- new regressions
- remaining weaknesses

### GateDecision

A gate decision converts evidence into readiness.

It should not be inferred silently from a score. It should link to the runs,
evals, comparisons, failures, and approvals that justify the decision.

### EvidenceContext

Evidence context is an assembled view over existing artifacts.

It is not a separate memory system. Artifacts are the memory; retrieval and
context packs make them usable.

## Implementation Rule

For every new product feature, answer these questions before coding:

1. Which spine object does this create, read, update, or link?
2. Is the object represented in OpenAPI?
3. Is the object represented as durable evidence?
4. Does the UI reveal the evidence relationship?
5. Can local/CI mode run without provider keys?

If the answer is unclear, update planning docs before writing feature code.
