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

### Scenarios

Scenarios define what a runner executes.

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
