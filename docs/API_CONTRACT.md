# API Contract

The platform API contract is generated from FastAPI's OpenAPI schema.

The generated contract lives at:

- [`docs/openapi.json`](openapi.json)

Regenerate it with:

```bash
npm run api:openapi
```

Lint it with:

```bash
npm run api:lint-openapi
```

The repo test script runs the OpenAPI lint through API tests. The current lint
checks:

- OpenAPI 3.x schema
- expected API title
- required project-scoped paths
- operation ids on every route
- unique operation ids
- summaries on every route

This is intentionally lightweight for the first slice. As the API grows, the
lint can become stricter or move to a dedicated OpenAPI linter in CI.

## Stubbing Rule

Stub APIs sparingly.

Do not stub every future endpoint. Stub only contract-defining APIs that are
part of the next two work-plan phases or are needed to stabilize UI/domain
design.

Stubbed APIs must:

- return `501 Not Implemented`
- define request and response shapes in OpenAPI
- have a contract test
- be marked clearly as planned behavior, not working behavior

Current near-term candidates are limited to the Phase 2 EDD backbone:

- eval contracts
- scenarios
- agent versions
- runs
- run evaluation
- failure packets
- fix proposals
- comparisons

Do not stub Langfuse, live LLM routing, broad gate workflows, or unrelated
admin surfaces until they are close enough to implementation to validate the
contract.

## Phase 2 API Backbone

The next implementation milestone is contract-first. The API should expose the
objects needed to prove eval-driven design before the UI adds more workflow
surface.

The backbone is:

```text
EvalContract
  -> Scenario
  -> AgentVersion
  -> Run
  -> EvalResult / JudgeOutput
  -> FailurePacket
  -> FixProposal
  -> Comparison
```

### Agent Designs

Agent designs hold the user intent and the platform-approved tool policy that
future versions inherit.

```text
GET    /api/projects/{project_id}/agent-designs
POST   /api/projects/{project_id}/agent-designs
GET    /api/projects/{project_id}/agent-designs/{agent_design_id}
PATCH  /api/projects/{project_id}/agent-designs/{agent_design_id}
DELETE /api/projects/{project_id}/agent-designs/{agent_design_id}
```

Minimum response fields:

```text
id
project_id
name
intent
status
allowed_tool_names
langfuse_prompt_name
langfuse_prompt_version
langfuse_prompt_label
created_at
updated_at
```

### Tool Definitions

Tool definitions are platform-owned. Agents may only use approved tools in
their allowlists, but the registry can hold draft tools while their schemas,
mock behavior, and execution policy are still being designed.

```text
GET   /api/projects/{project_id}/tools
POST  /api/projects/{project_id}/tools
PATCH /api/projects/{project_id}/tools/{tool_id}
```

Create request:

```json
{
  "name": "lookup_ticket",
  "description": "Look up a support ticket by id.",
  "input_schema": {
    "type": "object",
    "properties": {
      "ticket_id": {
        "type": "string",
        "description": "External ticket identifier."
      },
      "customer_since": {
        "type": "string",
        "format": "date"
      },
      "retry_count": {
        "type": "integer",
        "minimum": 0
      },
      "confidence": {
        "type": "number",
        "minimum": 0,
        "maximum": 1
      },
      "priority": {
        "type": "string",
        "enum": ["low", "medium", "high"]
      },
      "include_history": {
        "type": "boolean"
      }
    },
    "required": ["ticket_id"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "summary": {
        "type": "string"
      },
      "status": {
        "type": "string",
        "enum": ["open", "blocked", "resolved"]
      },
      "age_days": {
        "type": "integer"
      },
      "last_updated": {
        "type": "string",
        "format": "date-time"
      },
      "recommended_actions": {
        "type": "array",
        "items": {
          "type": "string"
        }
      }
    },
    "required": ["status", "summary"]
  },
  "output_description": "Ticket status and summary.",
  "implementation_kind": "mock",
  "implementation_key": "mock.lookup_ticket",
  "config_schema": {
    "type": "object",
    "properties": {}
  },
  "mock_response": "Ticket is open and awaiting customer logs.",
  "status": "draft"
}
```

Status update request:

```json
{
  "status": "approved"
}
```

Minimum response fields:

```text
id
project_id
name
description
input_schema
output_schema
output_description
implementation_kind
implementation_key
config_schema
mock_response
status
created_at
updated_at
```

### Eval Contracts

Eval contracts are where expectations live.

```text
GET    /api/projects/{project_id}/eval-contracts
POST   /api/projects/{project_id}/eval-contracts
GET    /api/projects/{project_id}/eval-contracts/{contract_id}
PATCH  /api/projects/{project_id}/eval-contracts/{contract_id}
```

Minimum response fields:

```text
id
project_id
agent_design_id
name
description
scenario_id
version
expected_behavior
required_evidence
required_tools
forbidden_tools
forbidden_behavior
output_requirements
checks
judge_prompt_template_id
pass_criteria
status
created_at
updated_at
```

### Judge Prompt Templates

Judge prompt templates are platform-owned prompts used by optional judge
execution. Eval contracts reference them by id.

```text
GET  /api/projects/{project_id}/judge-prompt-templates
POST /api/projects/{project_id}/judge-prompt-templates
GET  /api/projects/{project_id}/judge-prompt-templates/{judge_prompt_template_id}
```

Minimum response fields:

```text
id
project_id
name
description
template
version
status
langfuse_prompt_name
langfuse_prompt_version
langfuse_prompt_label
created_at
updated_at
```

### Gates

Gates define promotion/readiness criteria over stored evidence artifacts.

```text
GET  /api/projects/{project_id}/gates
POST /api/projects/{project_id}/gates
GET  /api/projects/{project_id}/gates/{gate_id}
```

Minimum response fields:

```text
id
project_id
agent_design_id
name
criteria
required_artifact_types
threshold
blocking_failure_statuses
approval_mode
status
created_at
updated_at
```

### Gate Decisions

Gate decisions evaluate a gate against current evidence and create a durable
readiness artifact.

```text
GET  /api/projects/{project_id}/gate-decisions
POST /api/projects/{project_id}/gates/{gate_id}/decisions
GET  /api/projects/{project_id}/gate-decisions/{decision_id}
```

Minimum response fields:

```text
id
project_id
gate_id
agent_design_id
eval_result_id
comparison_id
decision
rationale
missing_artifact_types
blocking_failure_packet_ids
evidence_artifact_ids
decided_by
created_at
```

### Discovery Error Analysis

Discovery error analysis turns messy traces, runs, and artifacts into structured
failure evidence before the proof loop proposes fixes.

The minimum durable objects are:

- `ReviewCorpus`: a project-scoped set of review items for one agent design.
- `ReviewItem`: a trace, Langfuse generation observation, run, eval result, or
  artifact selected for review.
- `ReviewAnnotation`: a free-text human or agent note on a review item.
- `FailureMode`: a first-class taxonomy category discovered from annotations.
- `AgentSuggestion`: a proposed annotation or mode match that requires human
  accept/dismiss before it influences confirmed evidence.

```text
GET   /api/projects/{project_id}/review-corpora
POST  /api/projects/{project_id}/review-corpora
GET   /api/projects/{project_id}/review-corpora/{corpus_id}
PATCH /api/projects/{project_id}/review-corpora/{corpus_id}
GET   /api/projects/{project_id}/review-corpora/{corpus_id}/sampling-plan
POST  /api/projects/{project_id}/review-corpora/{corpus_id}/langfuse-items
POST  /api/projects/{project_id}/review-corpora/{corpus_id}/langfuse-annotations

GET   /api/projects/{project_id}/review-items
POST  /api/projects/{project_id}/review-items
GET   /api/projects/{project_id}/review-items/{review_item_id}
PATCH /api/projects/{project_id}/review-items/{review_item_id}

GET   /api/projects/{project_id}/review-annotations
POST  /api/projects/{project_id}/review-annotations
GET   /api/projects/{project_id}/review-annotations/{annotation_id}
PATCH /api/projects/{project_id}/review-annotations/{annotation_id}

GET   /api/projects/{project_id}/failure-modes
POST  /api/projects/{project_id}/failure-modes
GET   /api/projects/{project_id}/failure-modes/{failure_mode_id}
PATCH /api/projects/{project_id}/failure-modes/{failure_mode_id}

GET   /api/projects/{project_id}/agent-suggestions
POST  /api/projects/{project_id}/agent-suggestions
GET   /api/projects/{project_id}/agent-suggestions/{suggestion_id}
PATCH /api/projects/{project_id}/agent-suggestions/{suggestion_id}
```

Langfuse integration is represented through refs on corpus/items/annotations:

```text
langfuse_queue_id
langfuse_score_config_ids
langfuse_ref.trace_id
langfuse_ref.observation_id
langfuse_ref.object_type
langfuse_ref.score_ids
langfuse_score_id
```

For OpenTelemetry traces, `ReviewItem.langfuse_ref.object_type` may be
`OBSERVATION` so the UI can target a Langfuse generation observation when
trace-level input/output is empty. EDD stores these refs as evidence links; live
Langfuse queue and score mutations stay explicit and opt-in.

The Langfuse import endpoints are deterministic landing zones for live sync
workflows:

- `sampling-plan` returns coverage counts, breadth candidates, depth candidates,
  and recoding prompts. With `create_suggestions=true`, deterministic candidate
  matches become pending `AgentSuggestion` records that still require human
  accept/dismiss.
- `langfuse-items` imports selected queue items or trace/generation observation
  rows into EDD review items and skips duplicates by source, trace, or
  observation id.
- `langfuse-annotations` imports open-coding/pass-fail/category score rows into
  accepted EDD review annotations and creates candidate `FailureMode` records
  for new category labels.

### Review Notes

Review notes are platform-owned human comments on evidence artifacts. They can
optionally mirror to Langfuse comments when the target artifact carries a
Langfuse trace or prompt reference.

```text
GET  /api/projects/{project_id}/review-notes
POST /api/projects/{project_id}/review-notes
GET  /api/projects/{project_id}/review-notes/{review_note_id}
```

Create request:

```json
{
  "target_artifact_id": "artifact_123",
  "body": "This trace shows the agent skipped escalation evidence.",
  "author": "reviewer@example.com",
  "metadata": {
    "review_type": "trace_diagnosis"
  }
}
```

Minimum response fields:

```text
id
project_id
target_artifact_id
body
author
metadata
artifact_ids
created_at
```

Langfuse comments are for lightweight discussion and trace/prompt notes. They
are distinct from Langfuse annotation queues, which are a later workflow for
structured human evaluation over many traces or sessions.

### Scenarios

Scenarios define what a runner executes.

The React console presents scenarios as test cases. The current UI stores the
selected input shape in `setup_context` using `test_shape:{value}`, where value
is one of `single_turn`, `conversation`, or `trace_replay`. This keeps the API
model stable while letting the UI distinguish isolated prompts, conversation
turns, and future trace-replay starts.

```text
GET    /api/projects/{project_id}/scenarios
POST   /api/projects/{project_id}/scenarios
GET    /api/projects/{project_id}/scenarios/{scenario_id}
PATCH  /api/projects/{project_id}/scenarios/{scenario_id}
```

Minimum response fields:

```text
id
project_id
agent_design_id
name
input
setup_context
fixture_refs
default_eval_contract_id
status
created_at
updated_at
```

### Agent Versions

Agent versions separate baseline behavior from candidate fixes.

```text
GET   /api/projects/{project_id}/agent-designs/{agent_design_id}/versions
POST  /api/projects/{project_id}/agent-designs/{agent_design_id}/versions
GET   /api/projects/{project_id}/agent-designs/{agent_design_id}/versions/{version_id}
```

Minimum response fields:

```text
id
project_id
agent_design_id
version_label
parent_version_id
instructions
tool_policy
source_fix_proposal_id
status
langfuse_prompt_name
langfuse_prompt_version
langfuse_prompt_label
created_at
updated_at
```

### Runs

Runs execute a version against a scenario and optional eval contract.

```text
GET   /api/projects/{project_id}/runs
POST  /api/projects/{project_id}/runs
GET   /api/projects/{project_id}/runs/{run_id}
```

Run request:

```json
{
  "agentDesignId": "agent_123",
  "agentVersionId": "version_v0",
  "scenarioId": "scenario_123",
  "evalContractId": "contract_123",
  "mode": "mock"
}
```

Minimum response fields:

```text
id
project_id
agent_design_id
agent_version_id
scenario_id
eval_contract_id
mode
provider
model
input
output
status
started_at
completed_at
artifact_ids
```

The existing agent-scoped run endpoint can remain temporarily as a convenience,
but the project-scoped run contract is the canonical direction.

### Trace References

Trace references link platform run/eval evidence to Langfuse or another
observability source. Langfuse remains the source of truth for raw traces; the
platform stores references and evidence links.

```text
GET  /api/projects/{project_id}/trace-refs
POST /api/projects/{project_id}/trace-refs
GET  /api/projects/{project_id}/trace-refs/{trace_ref_id}
```

Minimum response fields:

```text
id
project_id
agent_design_id
provider
external_trace_id
run_id
url
metadata
artifact_ids
created_at
```

### Context Packs

Context packs assemble project evidence for a specific workflow purpose. They
are deterministic by default and do not call an LLM.

```text
POST /api/projects/{project_id}/context-packs
```

Context pack request:

```json
{
  "purpose": "AGENT_PROMPT_REVIEW",
  "agentDesignId": "agent_123"
}
```

Supported purposes:

```text
AGENT_PROMPT_REVIEW
SIDE_BY_SIDE_VERSION_COMPARISON
FIX_PROPOSAL_GENERATION
GATE_DECISION_REVIEW
```

Purpose-specific assembly filters the artifact set so each workflow receives
the evidence it can actually use:

- `AGENT_PROMPT_REVIEW` emphasizes agent design, versions, contracts, judge
  prompt templates, gates, and trace references.
- `SIDE_BY_SIDE_VERSION_COMPARISON` emphasizes comparisons, runs, eval results,
  judge outputs, failure packets, fix proposals, and trace references.
- `FIX_PROPOSAL_GENERATION` emphasizes open evidence from runs, evals, judge
  outputs, failure packets, existing fixes, contracts, and trace references.
- `GATE_DECISION_REVIEW` emphasizes gate definitions, gate decisions,
  comparisons, eval evidence, failures, judge outputs, and trace references.

Unknown purposes currently fall back to the full project-scoped artifact set.

Minimum response fields:

```text
id
project_id
purpose
agent_design_id
artifacts
created_at
```

### Evidence Summaries

Evidence summaries synthesize a bounded context pack. Deterministic mode is
available for CI and local development without provider keys. Live mode is
optional and calls OpenAI only when explicitly requested.

```text
POST /api/projects/{project_id}/evidence-summaries
```

Evidence summary request:

```json
{
  "purpose": "FIX_PROPOSAL_GENERATION",
  "agentDesignId": "agent_123",
  "summaryType": "WHAT_FAILURES_REMAIN",
  "mode": "deterministic"
}
```

Minimum response fields:

```text
id
project_id
purpose
agent_design_id
summary_type
mode
provider
model
summary
supporting_artifact_ids
token_usage
cost_estimate
cache_key
cache_hit
created_at
```

The cache key is derived from project id, agent id, purpose, summary type, mode,
and the selected artifact ids/update times. Repeated requests for an unchanged
context return the cached summary with `cache_hit=true`. Live summaries record
token usage and cost estimates when cost-rate environment variables are set.

### Evaluation

Evaluation judges a run against an eval contract.

```text
POST  /api/projects/{project_id}/runs/{run_id}/evaluate
GET   /api/projects/{project_id}/eval-results/{eval_result_id}
```

Evaluation request:

```json
{
  "evalContractId": "contract_123",
  "judgeMode": "deterministic | live"
}
```

Live judge mode records provider token usage on the judge output. Cost estimates
are calculated only when `EDD_OPENAI_INPUT_COST_PER_1M` and
`EDD_OPENAI_OUTPUT_COST_PER_1M` are configured.

Minimum response fields:

```text
id
project_id
run_id
eval_contract_id
judge_prompt_template_id
mode
score
passed
checks
judge_output_ids
artifact_ids
created_at
```

### Failure Packets

Failure packets turn failed checks into diagnosis.

```text
GET    /api/projects/{project_id}/failure-packets
POST   /api/projects/{project_id}/failure-packets
GET    /api/projects/{project_id}/failure-packets/{failure_packet_id}
PATCH  /api/projects/{project_id}/failure-packets/{failure_packet_id}
```

Minimum response fields:

```text
id
project_id
agent_design_id
agent_version_id
run_id
eval_result_id
eval_contract_id
failed_check_ids
title
diagnosis
severity
evidence_artifact_ids
recommended_fix
status
created_at
updated_at
```

### Fix Proposals

Fix proposals describe bounded changes.

```text
GET    /api/projects/{project_id}/fix-proposals
POST   /api/projects/{project_id}/fix-proposals
GET    /api/projects/{project_id}/fix-proposals/{fix_proposal_id}
PATCH  /api/projects/{project_id}/fix-proposals/{fix_proposal_id}
```

Minimum response fields:

```text
id
project_id
agent_design_id
target_version_id
title
rationale
proposed_changes
addressed_failure_packet_ids
validation_contract_ids
status
created_at
updated_at
```

### Comparisons

Comparisons show whether a candidate improved against a baseline.

```text
POST  /api/projects/{project_id}/comparisons
GET   /api/projects/{project_id}/comparisons/{comparison_id}
```

Comparison request:

```json
{
  "baselineRunId": "run_v0",
  "candidateRunId": "run_v1",
  "evalContractId": "contract_123"
}
```

Minimum response fields:

```text
id
project_id
agent_design_id
baseline_version_id
candidate_version_id
baseline_run_id
candidate_run_id
baseline_eval_result_id
candidate_eval_result_id
fixed_failure_packet_ids
new_failure_packet_ids
remaining_failure_packet_ids
summary
artifact_ids
created_at
```

## Contract Acceptance

Each Phase 2 API addition should have:

- Pydantic request and response models;
- OpenAPI export coverage;
- route summary and operation id;
- contract tests for success and basic project scoping;
- deterministic behavior that does not require provider keys;
- artifact creation or artifact links when the endpoint creates evidence.
