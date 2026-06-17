# Architecture Deep Dives

## Purpose

This document expands the most important EDD Platform architecture areas for
technical review and future implementation planning.

The goal is to identify where the system has meaningful backend depth and where
the next implementation choices should stay disciplined.

## Deep Dive 1: Eval Evidence Pipeline

### Problem

An agent can produce a plausible answer once without becoming a reliable
candidate for promotion. The platform needs to preserve the path from expected
behavior to observed behavior to diagnosis to fix to comparison.

### Flow

```text
Scenario
  -> Run
  -> ToolCall / ToolResult artifacts
  -> EvalContract
  -> EvalResult
  -> JudgeOutput
  -> FailurePacket
  -> FixProposal
  -> Candidate AgentVersion
  -> Candidate Run
  -> Candidate EvalResult
  -> Comparison
  -> GateDecision
```

### Component Responsibilities

| Component | Responsibility |
|---|---|
| React console | starts runs/evals and displays evidence |
| Platform API | owns records, links, and eval orchestration |
| Runner package | executes scenario and returns output/tool events |
| Eval service | applies deterministic checks and optional judges |
| Evidence store | persists artifacts and relationships |

### Key Invariants

- A run references the agent version and scenario it executed.
- An eval result references the run and eval contract used.
- Failed checks identify observed and expected behavior.
- Failure packets reference the evidence that proves the failure.
- Fix proposals link to the failure packets they address.
- Comparisons reference both baseline and candidate evidence.

### Tradeoffs

The platform stores both typed records and artifacts. Typed records make API
behavior clear. Artifacts make evidence review, linking, and context assembly
consistent.

### Failure Handling

- If a run fails, preserve status and error evidence.
- If evaluation fails, do not infer pass/fail from missing results.
- If a candidate regresses, keep it separate from the baseline and show the
  regression in comparison evidence.

## Deep Dive 2: Tool Governance Boundary

### Problem

Agent tool use is powerful but risky. The platform needs to let agents use
tools while preserving reviewability, schema discipline, and approval policy.

### Flow

```text
ToolDefinition
  -> approval status
  -> agent allowlist
  -> runner adapter
  -> tool call
  -> tool result
  -> run evidence
  -> eval contract checks
```

### Component Responsibilities

| Component | Responsibility |
|---|---|
| Platform API | stores tool definitions, status, schemas, allowlists |
| Runner package | adapts approved tools to LangChain/LangGraph or mock tools |
| Eval contract | defines required and forbidden tool behavior |
| Evidence store | records tool calls and tool results |

### Key Invariants

- Draft tools are not executable by default.
- Disabled tools are not executable.
- An agent can only use tools approved by the platform and allowed for that
  agent.
- Tool calls and results are evidence artifacts.
- Eval contracts can fail a run for missing required tools or using forbidden
  tools.

### Tradeoffs

Keeping tool governance in the platform adds schema and adapter work, but it
prevents the runner from becoming an opaque tool-execution island.

### Failure Handling

- Invalid schema keeps a tool in draft or invalid state.
- Unapproved tool calls are blocked and can become failure evidence.
- Tool adapter errors should fail the run with inspectable status.

## Deep Dive 3: Evidence Context

### Problem

Artifacts are useful only if users and agents can retrieve the right evidence
at the right time.

### Flow

```text
Artifacts
  -> ArtifactLinks
  -> Search / filtering
  -> ContextPack
  -> UI review, fix proposal, comparison, gate decision
```

### Component Responsibilities

| Component | Responsibility |
|---|---|
| Artifact search | project-scoped retrieval |
| Artifact links | explain relationships between evidence |
| Context pack builder | assembles task-specific evidence |
| React console | displays context and related artifacts |

### Key Invariants

- Context packs reference artifacts instead of replacing them.
- Context pack purposes are explicit.
- Summaries are optional derived evidence.
- Cached summaries must be invalidated when underlying evidence changes.

### Tradeoffs

Keyword and structured retrieval are simpler and deterministic. Embeddings can
improve recall later, but they should not replace explicit artifact links.

### Failure Handling

- If a context pack is incomplete, show missing evidence rather than inventing
  rationale.
- If summaries are unavailable, fall back to raw artifacts.
- If artifact links are sparse, search can still provide a basic review path.

## Deep Dive 4: Promotion Readiness

### Problem

A passing score alone is not enough to promote an agent version. Promotion
should be tied to evidence, checks, regressions, and explicit gate decisions.

### Flow

```text
GateDefinition
  -> supporting runs/evals/comparisons
  -> gate review context pack
  -> GateDecision artifact
```

### Component Responsibilities

| Component | Responsibility |
|---|---|
| Platform API | stores gates and gate decisions |
| Evidence context | assembles supporting artifacts |
| React console | exposes readiness review |
| Langfuse adapter | links optional trace and score evidence |

### Key Invariants

- Gate decisions are explicit artifacts.
- A decision links to supporting evidence.
- Scores do not silently imply readiness.
- Regressions and unresolved failures remain visible.

### Tradeoffs

Explicit gate decisions add workflow steps, but they make readiness auditable
and prevent accidental promotion based on a single passing run.

