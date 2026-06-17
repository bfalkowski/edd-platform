# System Tradeoffs

## Purpose

This document captures the architectural tradeoffs behind EDD Platform's core
design choices.

The goal is to make the system easier to reason about as the product grows.

## Artifact Spine Before Specialized Tables

### Decision

Store every meaningful output as an artifact and link artifacts together, while
adding specialized tables for high-value objects such as agent designs,
scenarios, runs, eval results, and gate decisions.

### Benefits

- Creates one evidence surface across the workflow.
- Makes review, search, context packs, and links consistent.
- Avoids losing product meaning in isolated feature tables.
- Lets new artifact types be introduced without a schema redesign every time.

### Costs

- Some data is represented both as typed records and artifacts.
- The platform needs discipline around artifact creation and linking.
- Querying can become more complex as artifact volume grows.

### Why It Fits

EDD Platform's main product value is traceable evidence. A shared artifact
spine makes evidence review a first-class system behavior instead of an
afterthought.

## Eval Contracts as Data

### Decision

Represent expectations as `EvalContract` records instead of hardcoded eval
branches.

### Benefits

- Users can inspect and edit what good behavior means.
- Runs can be re-evaluated against explicit versions of expectations.
- Contracts can describe arbitrary agent behavior, not just one demo workflow.
- Comparisons remain explainable because both versions were judged against the
  same contract.

### Costs

- Contract editing needs a careful UI.
- Validation must prevent vague or invalid contract shapes.
- Deterministic checks need a stable schema and execution model.

### Why It Fits

The platform is about improving behavior against stated expectations. If those
expectations live only in code, the product cannot explain its own decisions.

## Deterministic Checks Before LLM Judges

### Decision

Run deterministic checks first and use LLM judges only when they add value.

### Benefits

- Keeps CI provider-key-free.
- Reduces cost.
- Makes simple failures easy to reproduce.
- Improves trust in the eval loop.

### Costs

- Some qualitative behavior cannot be fully evaluated deterministically.
- Check schemas need to be expressive enough for common cases.
- Users may still need rubric judges for nuanced judgment.

### Why It Fits

Determinism gives the platform a stable baseline. LLM judges are useful, but
they should be bounded and attributable rather than hidden inside every eval.

## Platform-Owned Tool Governance

### Decision

Keep tool definitions, approval status, and agent allowlists in the platform.
Adapt approved tools into runner/framework primitives at execution time.

### Benefits

- Prevents agents from using arbitrary tools without review.
- Makes tool policy visible to users.
- Lets eval contracts check required and forbidden tool behavior.
- Captures tool calls and results as evidence.

### Costs

- Requires adapters for multiple tool execution models.
- Tool schemas and mock behavior need validation.
- The platform must handle draft, approved, and disabled tool states.

### Why It Fits

Agent behavior depends heavily on tools. Tool policy therefore belongs in the
same product record as evals, runs, and promotion decisions.

## Langfuse as Observability, Not Source of Truth

### Decision

Use Langfuse for optional trace observability and linked evidence, while keeping
product state in the platform API and store.

### Benefits

- The product remains portable across observability providers.
- Platform records remain available even if trace sync fails.
- Trace references can support review without replacing normalized evidence.
- Langfuse can be adopted gradually.

### Costs

- Some trace details live outside the platform.
- Sync failures need clear status and retry behavior.
- Users may need to jump between product evidence and external traces.

### Why It Fits

Langfuse is valuable for observing live behavior, but EDD Platform's product
model is the evidence loop. The platform must own that loop.

## Monorepo With Package Boundaries

### Decision

Keep one product repo with clear package boundaries: `apps/web`, `apps/api`,
`packages/domain`, `packages/runner`, and `packages/langfuse-adapter`.

### Benefits

- Keeps the product easy to develop locally.
- Preserves one canonical frontend and API.
- Makes shared vocabulary available without early service extraction.
- Allows packages to become independently deployable later if needed.

### Costs

- Requires discipline to avoid cross-package leakage.
- Larger builds may eventually need more targeted CI.
- Service ownership boundaries are logical before they are physical.

### Why It Fits

The current challenge is product coherence, not independent service scaling.
Logical boundaries are enough until runtime scale forces extraction.

## Synchronous First, Asynchronous Later

### Decision

Start with direct API-triggered run and eval flows, while designing records so
long-running work can move to queues and workers later.

### Benefits

- Keeps the first product slice simple.
- Makes local development easier.
- Avoids premature distributed-system complexity.
- Still preserves run and eval status fields for later async execution.

### Costs

- Live runs and live judges can block longer than ideal.
- Retries and cancellation need stronger semantics as usage grows.
- Worker orchestration will eventually be needed for heavy workloads.

### Why It Fits

The platform first needs a correct evidence model. Once the model is stable,
background execution can scale it without changing the product vocabulary.

