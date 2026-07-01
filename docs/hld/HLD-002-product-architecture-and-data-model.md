# HLD-002: Product Architecture and Data Model

## Status

Implemented for the current product slice. See `docs/ARCHITECTURE.md` and `docs/WORK_PLAN.md` for current implementation detail and remaining gaps.

## Purpose

This HLD defines the product architecture and core data model for the
clean-room EDD Platform repo.

The goal is to preserve the strongest later design direction from the prior
platform and lab repos while removing the confusion of two product frontends,
two starting points, and old local-only workflow state.

## Core Decision

EDD Platform is a product monorepo with one canonical UI and one canonical API.

```text
EDD Platform
  apps/web
    React console

  apps/api
    Platform API and product state

  packages/domain
    Shared object vocabulary

  packages/runner
    Deterministic and live execution harness

  packages/langfuse-adapter
    Trace evidence integration
```

The React console is the only product UI.

The API owns platform state.

The runner executes scenarios and returns evidence.

Langfuse supplies trace evidence, not product state.

## Product Boundary

The product is not:

- a generic chatbot
- a Langfuse trace browser
- a Streamlit demo app
- a local YAML workbench
- a general-purpose memory system

The product is:

> An evaluation-driven agent development platform that turns ambiguous AI
> behavior into measurable, reviewable, linked evidence artifacts.

## Architecture

```text
React console
  |
  | HTTP JSON / streaming events
  v
Platform API
  |
  +--> product storage
  |      projects
  |      agent designs
  |      artifacts
  |      artifact links
  |      context packs
  |      judge prompts
  |      gates
  |      runs
  |      eval results
  |
  +--> runner package
  |      deterministic mock runs
  |      optional live/provider runs
  |
  +--> langfuse adapter
         trace refs
         run links
         observability metadata
```

## Current Repo Shape

The current implementation has the first slice:

- project-scoped API routes
- `AgentDesign` create/list
- automatic `AGENT_DESIGN` artifact creation
- artifact list/search
- deterministic context pack generation
- React left rail and evidence panel
- local API tests and web build

This slice is intentionally small. It establishes the product spine before
adding runners, judges, gates, or persistence.

## Ownership Model

| Capability | Owner |
|---|---|
| Product UI | `apps/web` |
| Product state | `apps/api` |
| Agent design records | `apps/api` |
| Evidence artifacts | `apps/api` |
| Context packs | `apps/api` |
| Judge prompt templates | `apps/api` |
| Gate decisions | `apps/api` |
| Runner execution | `packages/runner` |
| Mock tools and scenarios | `packages/runner` and `examples/` |
| Langfuse trace integration | `packages/langfuse-adapter` |
| Shared vocabulary | `packages/domain` |

## Runtime Modes

Original design draft (superseded — see below): four runtime modes, `mock`,
`local`, `platform`, and `auto`, distinguished by provider-key requirements
and state ownership.

The implementation collapsed this to two modes: `mock` (deterministic,
test/CI only, never exposed in the console) and `live` (the only mode the
console can trigger). See `docs/ARCHITECTURE.md`'s Runtime Modes section for
the current model.

CI must pass without model-provider credentials.

Live model behavior is opt-in. The default path should remain deterministic.

## Core Domain Objects

### Project

A project is the product workspace that owns agent designs and evidence.

```text
Project
  id
  name
  description
  created_at
  updated_at
```

### AgentDesign

An agent design is the user-facing design workspace created from intent.

It is not merely a prompt and not merely code. It is the container for target,
rules, judges, gates, runs, failures, fixes, and evidence.

```text
AgentDesign
  id
  project_id
  name
  intent
  status
  created_at
  updated_at
```

### Artifact

Artifacts are the durable memory of the workflow.

Examples:

- `AGENT_DESIGN`
- `AGENT_TARGET`
- `BEHAVIOR_RULE`
- `JUDGE_PROMPT_TEMPLATE`
- `EVAL_CONTRACT`
- `GATE`
- `SCENARIO`
- `RUN_RESULT`
- `EVAL_RESULT`
- `TRACE_REF`
- `FAILURE_PACKET`
- `FIX_PROPOSAL`
- `VERSION_COMPARISON`
- `GATE_DECISION`
- `DESIGN_DECISION`

Initial shape:

```text
Artifact
  id
  project_id
  artifact_type
  artifact_id
  title
  body
  source
  agent_design_id
  created_at
  updated_at
```

Dedicated tables can be added later for high-value artifact types. The artifact
spine should exist first so all meaningful outputs have a common evidence
surface.

### ArtifactLink

Artifact links explain relationships between evidence.

```text
ArtifactLink
  id
  project_id
  source_artifact_type
  source_artifact_id
  target_artifact_type
  target_artifact_id
  relationship_type
  created_at
```

Common relationship types:

- `GENERATED_FROM`
- `SUPPORTED_BY`
- `ADDRESSES`
- `TARGETS`
- `JUSTIFIED_BY`
- `IMPROVED_FROM`
- `REGRESSED_FROM`
- `SUPERSEDES`
- `RELATED_TO`

### ContextPack

A context pack is a deterministic assembled view over artifacts.

It is not a new source of truth. It references evidence and explains why that
evidence is relevant to a task.

```text
ContextPack
  id
  project_id
  purpose
  agent_design_id
  artifacts
  created_at
```

Initial purposes:

- `AGENT_PROMPT_REVIEW`
- `SIDE_BY_SIDE_VERSION_COMPARISON`
- `FIX_PROPOSAL_GENERATION`
- `GATE_DECISION_REVIEW`
- `FAILURE_TRIAGE`
- `VERSION_RELEASE_SUMMARY`

### JudgePromptTemplate

Judge prompts are platform assets, not hidden strings in runner code.

```text
JudgePromptTemplate
  id
  name
  version
  task_type
  input_schema
  output_schema
  prompt_text
  model_policy
  status
  created_at
  updated_at
```

Eval results should record the judge template id/version and model policy used
so score movement can be explained.

### Gate

Gates convert evidence into readiness decisions.

```text
Gate
  id
  project_id
  agent_design_id
  name
  condition
  status
```

Gate decisions should be explicit artifacts. Do not infer readiness only from
latest score.

### TraceRef

Trace refs link platform evidence to Langfuse or another observability system.

```text
TraceRef
  id
  project_id
  provider
  external_trace_id
  run_id
  url
  metadata
```

The platform stores trace references and normalized evidence. It does not copy
all trace details into product state.

## API Shape

The first public API shape should remain project-scoped.

```text
GET  /api/projects
GET  /api/projects/{project_id}

GET  /api/projects/{project_id}/agent-designs
POST /api/projects/{project_id}/agent-designs
GET  /api/projects/{project_id}/agent-designs/{agent_design_id}

GET  /api/projects/{project_id}/artifacts
GET  /api/projects/{project_id}/artifacts/search
GET  /api/projects/{project_id}/artifacts/{artifact_id}

POST /api/projects/{project_id}/artifact-links
GET  /api/projects/{project_id}/artifacts/{artifact_id}/links

POST /api/projects/{project_id}/context-packs
```

Future runner/judge endpoints:

```text
POST /api/projects/{project_id}/agent-designs/{agent_design_id}/run
POST /api/projects/{project_id}/agent-designs/{agent_design_id}/evaluate
POST /api/projects/{project_id}/agent-designs/{agent_design_id}/compare
POST /api/projects/{project_id}/agent-designs/{agent_design_id}/gate
```

Long-running operations should eventually stream workflow events to the UI.

## UI Shape

The frontend must follow `docs/design/FRONTEND_GUIDE.md`.

Canonical layout:

```text
left rail     main workspace               right review panel
projects      selected workflow/evidence    artifact detail/edit
agents
runs
search
```

The main UI should show:

- selected agent design
- evidence context
- artifact summaries
- local activity where work is happening
- review/edit panels for selected artifacts

Avoid:

- generic dashboard-card walls
- duplicated headers
- non-clickable breadcrumbs
- disconnected wizard action rows
- raw filenames as the main artifact surface

## Persistence Path

The current implementation uses in-memory storage.

The next persistence path should be:

1. Keep Pydantic/domain objects stable.
2. Add storage abstraction only when needed.
3. Add Postgres-backed persistence.
4. Preserve mock/local behavior for tests.
5. Migrate high-value artifact types to dedicated tables when their fields need
   querying.

Do not prematurely split every artifact type into a relational table before the
workflow proves which fields matter.

## Langfuse Boundary

Langfuse is an observability data plane.

EDD Platform owns:

- project
- agent design
- artifacts
- links
- context packs
- normalized eval evidence
- gate decisions

Langfuse owns:

- raw traces
- spans
- trace-level observability detail

The platform should store `TraceRef` artifacts that link to Langfuse evidence.

## Agent-Assisted Development Boundary

This repo intentionally uses AI coding agents, but product direction is governed
by steering files:

- `AGENTS.md`
- `docs/WORK_PLAN.md`
- `docs/design/FRONTEND_GUIDE.md`
- `docs/engineering/AI_AGENT_DEVELOPMENT.md`
- canonical HLDs

Agents may implement scoped changes. They should not silently redefine product
vocabulary, UI patterns, runtime modes, or persistence direction.

## Implementation Order

1. Project-scoped agent designs.
2. Evidence artifact creation.
3. Deterministic context packs.
4. Artifact detail and review panel.
5. Artifact links.
6. Behavior rules and judge prompt artifacts.
7. Deterministic runner.
8. Eval results and failure packets.
9. Gates and promotion.
10. Langfuse trace refs.
11. Optional LLM summaries over context packs.
12. Persistence.

## Success Criteria

This HLD is successful when the repo has:

- one canonical React UI
- project-scoped API routes
- platform-owned agent design state
- all meaningful outputs represented as artifacts
- deterministic context packs
- runner evidence returned to the platform
- judge prompt versions visible in eval evidence
- gate decisions backed by linked artifacts
- Langfuse traces linked as evidence
- local/CI checks that pass without provider keys
