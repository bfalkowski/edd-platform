# HLD-005: Relational Metadata and Polars Analysis Plane

## Status

Implemented for the current product slice. See `docs/ARCHITECTURE.md` and `docs/WORK_PLAN.md` for current implementation detail and remaining gaps.

## Purpose

This HLD defines the next storage architecture direction for EDD Platform:
relational storage remains the source of truth for platform records, while a
columnar Polars analysis plane serves trace, span, review-corpus, and
failure-rate queries.

The goal is to support Braintrust/Langfuse-style separation between durable
workflow metadata and high-volume analytical trace data without turning Polars
into an operational database.

## Core Decision

Use two storage paths with clear ownership:

```text
Platform API
  -> relational metadata store
       projects
       agent designs
       scenarios
       eval contracts
       runs
       eval results
       failure packets
       fix proposals
       gates
       artifacts
       jobs

  -> columnar analysis plane
       trace events
       spans
       model generations
       tool events
       review items
       annotations
       failure-mode observations
       corpus summaries
```

Postgres should own product state, identity, permissions, workflow status,
idempotency, jobs, and artifact links.

Polars should own read-side analytics over batch-shaped data: trace corpus
coverage, failure rates, sampling queues, span-level drilldowns, and aggregate
comparison summaries.

## Non-Goals

This HLD does not introduce:

- Polars as the API's transactional store;
- a standalone Polars server that accepts arbitrary product queries;
- replacement of Langfuse trace observability;
- replacement of platform artifacts as durable evidence;
- a streaming event system before the synchronous product path needs it.

## Why This Split Fits

Relational storage is best for product invariants:

- a run belongs to one project, agent version, scenario, and eval contract;
- an eval result references a specific run and contract;
- failure packets and fix proposals link to stable evidence;
- gate decisions must be explicit, durable, and auditable;
- background jobs need status, retries, ownership, and idempotency.

Columnar analysis is best for corpus questions:

- Which failure modes dominate this corpus?
- Which tools are associated with failing traces?
- Which spans or observations should reviewers sample next?
- How does failure rate change by agent version, scenario shape, or model?
- Which traces have missing evals, annotations, scores, or evidence links?

Keeping those responsibilities separate prevents the analytical path from
weakening product consistency while avoiding slow relational scans for trace
analysis.

## Query Paths

### Product Queries

The React console calls the Platform API. The API reads from Postgres and
returns typed product records and evidence artifacts.

```text
React console
  -> Platform API
  -> Postgres
  -> typed records + artifacts
```

Examples:

- load an agent design;
- list scenarios and eval contracts;
- inspect a run, eval result, failure packet, or gate decision;
- create a fix proposal;
- update review status.

### Analysis Queries

The React console still calls the Platform API. The API runs bounded Polars
queries against columnar files or local analysis datasets and returns
product-shaped summaries.

```text
React console
  -> Platform API analysis endpoint
  -> Polars query over Parquet/Arrow/NDJSON snapshots
  -> summary rows linked back to product ids
```

Examples:

- corpus coverage summaries;
- failure-rate tables by failure mode, scenario, agent version, or model;
- sampling candidates for breadth/depth/recoding review;
- trace/span drilldowns linked back to run ids and artifact ids.

The API should not expose arbitrary SQL/DataFrame execution. Analysis endpoints
should stay product-specific and project-scoped.

### External Trace Queries

Langfuse remains optional observability. The platform stores trace refs and can
import or mirror selected trace metadata into the analysis plane.

```text
Langfuse
  -> adapter/import job
  -> platform trace refs in Postgres
  -> normalized trace/span rows in Polars-readable files
```

The product source of truth remains the platform. If Langfuse is unavailable,
existing platform evidence remains usable.

## Local and Containerized Access

Polars is a library, not a database service. The first containerized design
should therefore provide a repeatable analysis runtime rather than a Polars
daemon.

Recommended local shape:

```text
docker compose
  postgres
  api
  web
  analysis files volume
```

The API container includes the Polars dependency and reads project-scoped
analysis snapshots from a mounted volume such as:

```text
.local-data/analysis/
  projects/{project_id}/trace_events.parquet
  projects/{project_id}/spans.parquet
  projects/{project_id}/review_items.parquet
  projects/{project_id}/annotations.parquet
  projects/{project_id}/failure_modes.parquet
```

For heavier future usage, a worker container can materialize or compact these
files asynchronously. That worker would still write files or tables that the
API queries through product-specific endpoints.

## Sync Boundaries

The platform should write product records first, then update the analysis plane
as a derived read model.

```text
Run/eval/review mutation
  -> write Postgres source-of-truth records
  -> write evidence artifacts and links
  -> enqueue or perform analysis-plane materialization
  -> serve analytics from latest successful snapshot
```

If analysis materialization fails:

- the product mutation remains valid;
- the API surfaces stale or unavailable analysis status;
- deterministic local and CI behavior still works;
- retry can rebuild the analysis snapshot from Postgres records and imported
  trace rows.

## Minimal Data Model

The analysis plane should start with normalized rows that preserve product ids:

```text
trace_events
  project_id
  trace_id
  run_id
  agent_design_id
  agent_version_id
  scenario_id
  eval_contract_id
  provider
  model
  status
  started_at
  completed_at

spans
  project_id
  trace_id
  span_id
  parent_span_id
  run_id
  span_type
  name
  status
  input_preview
  output_preview
  token_count
  latency_ms
  started_at
  ended_at

review_observations
  project_id
  corpus_id
  review_item_id
  trace_id
  observation_id
  annotation_id
  failure_mode_id
  severity
  confidence
  status
  created_at
```

These rows are not a replacement for typed product records. They are an
analysis projection that can be deleted and rebuilt.

## API Surface Direction

Initial API endpoints should stay narrow:

```text
GET /api/projects/{project_id}/review-corpora/{corpus_id}/analysis
GET /api/projects/{project_id}/review-corpora/{corpus_id}/sampling-plan
GET /api/projects/{project_id}/analysis/failure-rates
GET /api/projects/{project_id}/analysis/trace-coverage
```

The current corpus analysis and sampling endpoints are the right product
shape. Future work should harden their backing store and materialization rather
than expose generic dataframe queries.

## Operational Invariants

- Product state is complete only after Postgres records and evidence artifacts
  are written.
- Analysis state is derived and rebuildable.
- Every analysis row that appears in the UI must link back to product ids or
  external trace refs.
- Analysis endpoints are project-scoped.
- CI must pass without provider keys, Langfuse credentials, or external
  analytical services.
- The API may return stale analysis with explicit snapshot metadata; it must
  not silently present stale analytics as fresh.

## Comparison to Braintrust and Langfuse

Braintrust and Langfuse both separate workflow metadata from trace/eval
analytics in practice: product concepts need durable identity and permissions,
while traces, spans, and scores need analytical scans.

EDD Platform should adopt that shape without copying provider-specific
ownership:

- Postgres owns the EDD product workflow.
- Langfuse can provide optional trace observations and external trace links.
- Polars provides local and CI-friendly analytical reads over normalized trace
  and review data.
- Artifacts remain the durable product evidence surface.

## First Implementation Slice

The first build slice should be intentionally small:

1. Define an analysis snapshot directory and file naming convention.
2. Add a materializer that exports review corpus rows to Parquet.
3. Keep existing analysis endpoints and switch their internals to load from
   the snapshot when available.
4. Fall back to current in-memory/Postgres-shaped records when no snapshot
   exists.
5. Return snapshot freshness metadata in analysis responses.

That slice proves the query path without requiring a new database service or a
large migration.
