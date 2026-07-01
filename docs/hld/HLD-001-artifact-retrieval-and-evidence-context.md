# HLD-001: Artifact Retrieval and Evidence Context

## Status

Implemented for the current product slice. See `docs/ARCHITECTURE.md` and `docs/WORK_PLAN.md` for current implementation detail and remaining gaps.

## Purpose

This HLD defines the artifact intelligence layer for EDD Platform.

The platform already treats artifacts as the durable record of the evaluation
driven design workflow: agent designs, versions, eval suites, eval runs, judge
outputs, traces, failure packets, fix proposals, gates, and design decisions.
Those artifacts are the product's memory.

The missing capability is not another memory system. The missing capability is
the ability to retrieve, link, and assemble those artifacts into useful context
when a user, UI, runner, or agent needs to make a decision.

## Core Thesis

Artifacts are the memory.

Retrieval makes them usable.

Context packs make them agent-readable.

EDD Platform should not introduce a separate brain, note store, or
general-purpose memory database. It should build an intelligence layer over the
artifacts it already owns.

```text
EDD Platform
  owns:
    projects
    agent designs
    agent versions
    eval suites
    eval runs
    judge outputs
    traces
    failure packets
    fix proposals
    gates
    design decisions
    comparison notes
  adds:
    artifact retrieval
    artifact linking
    evidence context assembly
```

## Problem

Artifacts can exist as separate records without becoming useful evidence. The
platform needs to answer higher-level questions:

- Why did v0 fail?
- What exact evidence supports promoting v1?
- Have we seen this failure before?
- Which failure packets did this fix address?
- Which judge outputs explain the score delta?
- What design decision changed the rubric?
- What context should an agent receive before proposing a fix?
- What known weaknesses remain in the candidate version?

Without retrieval and linking, artifacts are records.

With retrieval and linking, artifacts become working evidence.

## Goals

1. Search across project artifacts.
2. Link related artifacts together.
3. Build evidence context packs for users, UIs, runners, and agents.
4. Explain why one agent version improved or regressed.
5. Provide context for future fix-generation and review agents.
6. Preserve artifacts as the source of truth.

## Non-Goals

This HLD does not propose:

- a general-purpose personal memory system
- continuous autonomous reflection
- email, calendar, or document ingestion
- a separate memory database unrelated to EDD artifacts
- LLM enrichment on every trace or message
- a full knowledge graph for all product data
- replacing existing artifact tables

The platform should stay evaluation-centered.

## Design Principle

Prefer deterministic artifact relationships first. Use LLMs only when synthesis
adds clear value.

Cheap path:

```text
store artifact
link artifact
index artifact
retrieve artifact
assemble context
```

Expensive path:

```text
summarize evidence
compare versions
explain score changes
generate fix proposals
draft gate rationale
```

The LLM sits at the edge of the workflow, not inside every internal platform
operation.

## Existing Artifact Model

The platform should treat these objects as the primary source of truth:

- Project
- AgentDesign
- AgentVersion
- EvalSuite
- EvalCase
- EvalRun
- EvalResult
- JudgeOutput
- Trace
- FailurePacket
- FixProposal
- Gate
- GateDecision
- DesignDecision
- VersionComparison

The new layer should not duplicate their content into a separate memory object
unless needed for indexing.

## Proposed Components

### Artifact Search Service

`ArtifactSearchService` provides project-scoped search across artifacts.

Initial search should be simple keyword search. Embeddings can come later.

```text
ArtifactSearchService
  search(projectId, query, filters)
  searchFailures(projectId, query, filters)
  searchDecisions(projectId, query, filters)
  searchEvalEvidence(projectId, query, filters)
```

First implementation requirements:

- project-scoped search
- artifact type filtering
- version filtering
- eval suite filtering
- failure status filtering
- basic keyword matching

### Artifact Linking Service

`ArtifactLinkingService` creates and reads relationships between artifacts.

Examples:

- FailurePacket `GENERATED_FROM` EvalResult
- FailurePacket `SUPPORTED_BY` JudgeOutput
- FailurePacket `SUPPORTED_BY` Trace
- FixProposal `ADDRESSES` FailurePacket
- FixProposal `TARGETS` AgentVersion
- GateDecision `SUPPORTED_BY` EvalRun
- GateDecision `JUSTIFIED_BY` FailurePacket
- DesignDecision `APPLIES_TO` EvalSuite
- VersionComparison `GENERATED_FROM` EvalRun

A generic relationship table is preferable to hardcoding every relationship in
each artifact table.

```sql
CREATE TABLE artifact_links (
  id UUID PRIMARY KEY,
  project_id UUID NOT NULL,
  source_artifact_type TEXT NOT NULL,
  source_artifact_id UUID NOT NULL,
  target_artifact_type TEXT NOT NULL,
  target_artifact_id UUID NOT NULL,
  relationship_type TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT now()
);
```

Initial relationship types:

- `GENERATED_FROM`
- `SUPPORTED_BY`
- `ADDRESSES`
- `TARGETS`
- `REGRESSED_FROM`
- `IMPROVED_FROM`
- `BLOCKED_BY`
- `JUSTIFIED_BY`
- `SUPERSEDES`
- `RELATED_TO`

### Context Pack Builder

`ContextPackBuilder` assembles relevant artifacts into a compact object that can
be shown in the React console or passed to a runner, tool, or future agent.

A context pack is not a new source of truth. It is a temporary assembled view
over existing evidence.

```json
{
  "projectId": "project_123",
  "purpose": "SIDE_BY_SIDE_VERSION_COMPARISON",
  "baselineVersionId": "v0",
  "candidateVersionId": "v1",
  "evalSuiteId": "suite_456",
  "evidence": {
    "openFailurePackets": [],
    "resolvedFailurePackets": [],
    "relevantJudgeOutputs": [],
    "fixProposals": [],
    "designDecisions": [],
    "gateRules": [],
    "traceRefs": []
  }
}
```

Initial context pack purposes:

- `SIDE_BY_SIDE_VERSION_COMPARISON`
- `FIX_PROPOSAL_GENERATION`
- `GATE_DECISION_REVIEW`
- `FAILURE_TRIAGE`
- `VERSION_RELEASE_SUMMARY`
- `AGENT_PROMPT_REVIEW`

Each purpose should have its own deterministic assembly strategy.

### Evidence Summary Service

`EvidenceSummaryService` uses a context pack to generate human-readable
explanations.

This is where LLM usage makes sense.

Example outputs:

- why v1 improved
- why v1 regressed
- why this gate passed
- why this gate failed
- what failures remain
- what fix should be attempted next

The service should not search the entire system directly. It should operate on
a bounded context pack assembled by the platform.

```text
Artifacts
  -> ArtifactSearchService
  -> ContextPackBuilder
  -> EvidenceSummaryService
  -> React console / runner / agent / gate explanation
```

## Data Model Additions

```python
ArtifactType = Literal[
    "PROJECT",
    "AGENT_DESIGN",
    "AGENT_VERSION",
    "EVAL_SUITE",
    "EVAL_CASE",
    "EVAL_RUN",
    "EVAL_RESULT",
    "JUDGE_OUTPUT",
    "TRACE",
    "FAILURE_PACKET",
    "FIX_PROPOSAL",
    "GATE",
    "GATE_DECISION",
    "DESIGN_DECISION",
    "VERSION_COMPARISON",
]

RelationshipType = Literal[
    "GENERATED_FROM",
    "SUPPORTED_BY",
    "ADDRESSES",
    "TARGETS",
    "REGRESSED_FROM",
    "IMPROVED_FROM",
    "BLOCKED_BY",
    "JUSTIFIED_BY",
    "SUPERSEDES",
    "RELATED_TO",
]
```

### Artifact Search Index

The first version can use a simple table populated from artifact text.

```python
class ArtifactSearchIndex(BaseModel):
    id: str
    project_id: str
    artifact_type: ArtifactType
    artifact_id: str
    title: str
    body: str
    agent_version_id: str | None = None
    eval_suite_id: str | None = None
    eval_run_id: str | None = None
    created_at: datetime
    updated_at: datetime
```

Embeddings should not be required for the first milestone.

### Context Pack

Context packs can be generated dynamically and optionally stored for important
gate decisions or debugging.

```python
class ContextPackArtifact(BaseModel):
    artifact_type: ArtifactType
    artifact_id: str
    title: str
    summary: str | None = None
    relevance_reason: str | None = None
    relationship_path: list[str] = []


class ContextPack(BaseModel):
    id: str | None = None
    project_id: str
    purpose: ContextPackPurpose
    baseline_version_id: str | None = None
    candidate_version_id: str | None = None
    eval_suite_id: str | None = None
    eval_run_id: str | None = None
    artifacts: list[ContextPackArtifact]
    created_at: datetime
```

## API Design

Initial endpoints:

```text
GET  /api/projects/{project_id}/artifacts/search
POST /api/projects/{project_id}/artifact-links
GET  /api/projects/{project_id}/artifacts/{artifact_type}/{artifact_id}/links
POST /api/projects/{project_id}/context-packs
POST /api/projects/{project_id}/evidence-summary
```

The first implementation should make search, links, and context packs work
without requiring an LLM provider key.

## UI Integration

The React console should expose this layer as **Evidence** or **Evidence
Context**, not generic memory.

Evidence views should include:

- open failures
- resolved failures
- recent fix proposals
- recent design decisions
- gate decisions
- version comparisons
- search

The side-by-side comparison screen should include an evidence panel that shows:

- score delta
- relevant prior failure packets
- judge explanations
- linked traces
- fix proposals applied to the candidate version
- remaining open issues

## Agent Integration

Future agents and tools should access evidence through bounded endpoints:

- `search_project_artifacts`
- `get_open_failure_packets`
- `get_relevant_context_pack`
- `create_failure_packet`
- `create_fix_proposal`
- `create_design_decision`
- `link_artifacts`

Agents may draft design decisions, but accepted design decisions should require
user confirmation.

## LLM Usage

LLM calls should be optional and bounded.

Recommended initial LLM use cases:

- summarize a context pack
- explain version improvement or regression
- generate a fix proposal from selected failure packets
- draft a gate decision explanation
- cluster similar failure packets

Avoid:

- summarizing every trace automatically
- running reflection on every new artifact
- using LLMs to decide all artifact links
- generating embeddings before keyword search feels weak
- continuous background reflection

## Cost Control

Required safeguards:

- no LLM call during normal artifact creation by default
- no LLM call for simple search
- no background reflection loop
- explicit user or workflow trigger for synthesis
- cache summary outputs for unchanged context packs
- track token usage by operation

Telemetry fields:

- operation type
- project id
- context pack purpose
- input tokens
- output tokens
- model
- latency
- cost estimate
- cache hit

## Implementation Plan

### Phase 1: Artifact Indexing

Deliverables:

- artifact search index model
- indexing logic for failure packets
- indexing logic for fix proposals
- indexing logic for judge outputs
- indexing logic for design decisions
- basic project-scoped search API

Acceptance criteria:

- a user can search for a failure by keyword
- a user can filter search results by artifact type
- a user can search only within a project
- results include title, snippet, artifact type, and artifact id

### Phase 2: Artifact Links

Deliverables:

- artifact link model
- link creation API
- link read API
- automatic links for obvious workflow relationships
- manual link support

Acceptance criteria:

- a failure packet links back to the eval result and judge output that created it
- a fix proposal can link to one or more failure packets
- the UI can display related artifacts for a selected artifact

### Phase 3: Context Packs

Deliverables:

- `ContextPackBuilder`
- `SIDE_BY_SIDE_VERSION_COMPARISON` context pack
- `FIX_PROPOSAL_GENERATION` context pack
- `GATE_DECISION_REVIEW` context pack
- context pack API

Acceptance criteria:

- the platform can generate a context pack for v0 vs v1 comparison
- the pack includes relevant failures, judge outputs, fix proposals, and gate rules
- context pack generation is deterministic and does not require an LLM

### Phase 4: Evidence Panel

Deliverables:

- evidence panel in comparison UI
- turn-level relevant artifacts
- score delta explanation section
- remaining weaknesses section
- links back to underlying artifacts

Acceptance criteria:

- the user can see which artifacts explain a score delta
- the user can click from comparison evidence to the underlying artifact
- the UI distinguishes fixed failures from remaining failures

### Phase 5: Evidence Summaries

Deliverables:

- `EvidenceSummaryService`
- summary prompt templates
- summary caching
- token and cost telemetry
- summary display in comparison and gate review

Acceptance criteria:

- the platform can generate a bounded explanation of improvement or regression
- explanations cite supporting artifacts
- repeated requests reuse cached summaries when context has not changed
- token usage is recorded by operation

## Open Questions

1. Should context packs be persisted?

   Recommendation: generate dynamically first, then persist snapshots for
   important gate decisions.

2. Should artifact links be manual, automatic, or hybrid?

   Recommendation: hybrid. Automatically link obvious workflow artifacts and
   allow manual links for design decisions.

3. Should embeddings be included in the first implementation?

   Recommendation: no. Start with text search. Add embeddings once artifact
   volume makes keyword search weak.

4. Should the UI call this memory?

   Recommendation: no. Use Evidence, Artifacts, or Evidence Context.

## Risks

Risk: creating a second source of truth.

Mitigation: context packs reference artifacts; they do not duplicate artifact
content.

Risk: LLM costs grow silently.

Mitigation: no automatic synthesis by default. Add token telemetry and summary
caching.

Risk: search results become noisy.

Mitigation: use project, version, suite, artifact type, and status filters.

Risk: agents overfit to prior failures.

Mitigation: context packs should include both fixed failures and broader eval
suite goals.

Risk: artifact links become stale.

Mitigation: prefer immutable links. If artifacts are superseded, create
`SUPERSEDES` links rather than mutating history.

## Success Criteria

This HLD is successful when the platform can answer:

- What evidence explains this score?
- Why did this version improve?
- What failure packets does this fix address?
- What design decision explains this gate?
- What context should an agent use before proposing the next fix?

Before: the platform stores evidence.

After: the platform uses evidence.
