# HLD-003: Eval-Driven Agent Design Workflow

## Status

Implemented for the current product slice. See `docs/ARCHITECTURE.md` and `docs/WORK_PLAN.md` for current implementation detail and remaining gaps.

## Purpose

This HLD defines the first user-facing workflow in EDD Platform: turning an
agent idea into reviewable design artifacts that can be run, judged, fixed, and
promoted with evidence.

The workflow starts before code. A useful agent design needs a target, behavior
rules, judge prompts, gates, scenarios, and evidence links. The platform should
make those pieces explicit instead of hiding them in one prompt blob or a local
YAML file.

## Core Thesis

Agent design is an evidence workflow, not a form wizard.

The platform should let a user:

1. Describe intent.
2. Generate or edit structured design artifacts.
3. Review every artifact in context.
4. Run deterministic or live scenarios.
5. Evaluate behavior against stored judge prompts and gates.
6. Create failure packets and bounded fixes.
7. Promote only when evidence supports the decision.

Every meaningful output should become an artifact. Every artifact should be
searchable, linkable, and usable in context packs.

## Product Boundary

The React console owns the workflow surface.

The API owns durable design state.

The runner executes scenarios and returns evidence.

The platform does not depend on a separate Lab UI, local YAML workspace, or
manual file editing loop.

## Design Principles

- Keep the first design loop understandable without model-provider keys.
- Treat generated content as draft evidence until reviewed.
- Put actions near the artifact or workflow stage they affect.
- Avoid disconnected step buttons and non-clickable breadcrumbs.
- Prefer artifact cards and right-panel review over raw filenames.
- Keep repeated sections editable, addable, and removable.
- Store judge prompts and gates as platform artifacts, not code-only constants.
- Make mock/local/live mode visible in run and eval evidence.

## Workflow Stages

### 1. Intent

The user creates an `AgentDesign` with:

- name
- intent
- project
- status

The API also creates the first `AGENT_DESIGN` artifact.

### 2. Target

The target defines what the agent is supposed to accomplish.

Artifact type:

- `AGENT_TARGET`

Recommended sections:

- purpose
- intended users
- primary goals
- non-goals
- assumptions
- allowed tool categories
- risk tolerance
- expected output format
- example scenarios

The target is the anchor for later judge prompts and gates.

### 3. Behavior Rules

Behavior rules define constraints that the agent must follow.

Artifact type:

- `BEHAVIOR_RULE`

Recommended fields:

- rule id
- severity
- description
- rationale
- status

Rules should be repeatable sections. Users need to add, edit, and remove them
from the review panel.

### 4. Judge Prompts

Judge prompts define how behavior is evaluated.

Artifact type:

- `JUDGE_PROMPT_TEMPLATE`

Recommended fields:

- prompt id
- purpose
- rubric
- scoring scale
- pass threshold
- required evidence
- failure signals
- version

Judge prompts are product records. They should not live only in test code or
runner implementation.

### 5. Gates

Gates define promotion criteria.

Artifact type:

- `GATE`

Recommended fields:

- gate id
- name
- criteria
- required artifacts
- threshold
- blocking failures
- approval mode

Gate decisions later become their own artifacts linked back to runs, evals,
judge outputs, and failure packets.

### 6. Scenarios

Scenarios define what the runner executes.

Artifact type:

- `SCENARIO`

Recommended fields:

- scenario id
- user input
- setup context
- tool fixtures
- expected evidence
- expected constraints

Scenarios must run in deterministic mock mode for CI and public demos.

### 7. Runs And Evals

The runner executes scenarios and returns run evidence to the API.

Artifact types:

- `RUN_RESULT`
- `EVAL_RESULT`
- `JUDGE_OUTPUT`
- `TRACE_REF`

The platform links these artifacts back to the design artifacts that shaped
them.

### 8. Failures And Fixes

When an eval fails, the platform creates a failure packet and a bounded fix
proposal.

Artifact types:

- `FAILURE_PACKET`
- `FIX_PROPOSAL`

Expected links:

- `FAILURE_PACKET GENERATED_FROM EVAL_RESULT`
- `FAILURE_PACKET SUPPORTED_BY JUDGE_OUTPUT`
- `FIX_PROPOSAL ADDRESSES FAILURE_PACKET`
- `FIX_PROPOSAL TARGETS AGENT_VERSION`

Fixes should be specific enough to implement and narrow enough to evaluate.

## UI Model

The main workspace should show a selected agent design with artifact-backed
workflow sections:

```text
left rail              main workspace                 right review panel
agents/projects        target/rules/judges/gates       selected artifact
search/runs            run/eval evidence               related evidence
```

The center workspace should not show every future step as a static checklist.
It should show useful current artifacts and their evidence status.

Each artifact card should include:

- human title
- short description
- artifact type
- status
- review action
- local activity if work is running

The right panel should support:

- review
- edit
- save
- add repeatable section
- remove repeatable section
- show related evidence

Destructive actions require confirmation once data is persisted.

## API Surface

The existing Phase 1 API supports:

- create/list agent designs
- artifact list/search/detail
- artifact links
- deterministic context packs

Phase 2 should add artifact editing rather than a separate workflow object.

Recommended next endpoints:

```text
PATCH /api/projects/{project_id}/artifacts/{artifact_id}
POST  /api/projects/{project_id}/agent-designs/{agent_design_id}/artifacts
DELETE /api/projects/{project_id}/artifacts/{artifact_id}
```

Deletion should be limited to user-created or generated draft artifacts. The
platform should preserve historical run/eval evidence unless a deliberate admin
cleanup path exists.

## Data Model Direction

The generic `ArtifactRecord` remains the first durable surface.

High-value artifact types can get dedicated tables later when the workflow
needs structured queries. Until then, structured artifact payloads can be stored
inside artifact bodies or future metadata fields while the common evidence
surface remains stable.

Near-term artifact types:

- `AGENT_TARGET`
- `BEHAVIOR_RULE`
- `JUDGE_PROMPT_TEMPLATE`
- `GATE`
- `SCENARIO`

Later artifact types:

- `RUN_RESULT`
- `EVAL_RESULT`
- `JUDGE_OUTPUT`
- `TRACE_REF`
- `FAILURE_PACKET`
- `FIX_PROPOSAL`
- `GATE_DECISION`
- `DESIGN_DECISION`

## LLM Usage

The platform may use an LLM to draft target, rules, judges, gates, or fixes.

LLM-generated artifacts must be:

- visibly draft
- editable
- attributable to generation mode
- deterministic in CI through mock generation
- stored as platform artifacts before downstream use

Live generation should be optional and provider keys should not be required for
tests or local demo mode.

## Acceptance Criteria

This workflow is useful when a user can:

1. Create an agent design from intent.
2. Generate or manually add target, rules, judge prompt, gate, and scenario
   artifacts.
3. Review and edit those artifacts in the right panel.
4. Add and remove repeatable sections such as behavior rules.
5. See related evidence for selected artifacts.
6. Run a deterministic scenario from the selected design.
7. Evaluate the run against stored judge prompts and gates.
8. See failure packets and bounded fixes linked to the evidence that created
   them.

## Implementation Plan

### Phase 2A: Design Artifact Editing

- Add artifact update endpoint.
- Add artifact create endpoint scoped to an agent design.
- Add draft artifact types for target, rules, judge prompt, gate, and scenario.
- Add right-panel edit/save support.
- Add add/remove controls for repeatable sections.

### Phase 2B: Design Artifact Generation

- Add deterministic mock generation for target/rules/judges/gates.
- Add optional live generation behind explicit mode.
- Store generation mode in artifact source or metadata.
- Show generation activity locally in the relevant panel.

### Phase 2C: Runner Preparation

- Define scenario artifact shape.
- Pass selected design artifacts to the runner package.
- Store run/eval outputs as artifacts.
- Link outputs back to the design artifacts that influenced them.

## Risks

Risk: The workflow becomes a wizard instead of an evidence workspace.

Mitigation: keep artifacts reviewable and actions local to the artifact they
affect.

Risk: The platform over-structures artifacts too early.

Mitigation: use the generic artifact spine first and promote fields into
dedicated tables only when query needs are proven.

Risk: Live generation becomes required for demos or CI.

Mitigation: deterministic mock generation and mock runner mode remain the
default.

Risk: Users cannot tell what is generated, edited, or evaluated.

Mitigation: store source, status, mode, and linked evidence on every meaningful
artifact.

## Success Criteria

HLD-003 is successful when the product can demonstrate the first recognizable
EDD loop:

```text
intent
  -> target
  -> rules, judges, gates, scenarios
  -> run
  -> eval
  -> failure packet
  -> bounded fix
  -> verified improvement
```

The user should be able to explain why an agent behaves the way it does because
the design, judge, gate, run, and fix evidence are all visible and linked.
