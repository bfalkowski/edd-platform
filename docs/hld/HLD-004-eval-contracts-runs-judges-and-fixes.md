# HLD-004: Eval Contracts, Runs, Judges, and Fixes

## Status

Draft

## Purpose

This HLD defines the implementation backbone for proving eval-driven design in
EDD Platform.

The current platform can create agent designs, execute mock/live runs, and store
evidence artifacts. The missing piece is a first-class definition of what the
agent was expected to do and a durable loop for evaluating, failing, fixing,
versioning, and comparing behavior.

This HLD covers:

- `EvalContract`
- `Scenario`
- `Run`
- `EvalResult`
- `JudgeOutput`
- `FailurePacket`
- `FixProposal`
- `AgentVersion`
- `Comparison`

## Core Thesis

An agent is not improved because it produced a nicer answer once.

An agent is improved when a candidate version performs better against explicit,
durable expectations using linked evidence.

```text
EvalContract
  -> Run
  -> EvalResult / JudgeOutput
  -> FailurePacket
  -> FixProposal
  -> AgentVersion
  -> Comparison
```

## Non-Goals

This HLD does not define:

- a generic chatbot product
- a one-off weather-agent workflow
- a hidden middleware-only rubric system
- unrestricted autonomous self-improvement
- full Langfuse ingestion
- production-grade model routing

The platform should support arbitrary agents. Small demo scenarios are smoke
fixtures, not the product model.

## Design Principles

- Expectations are data, not code branches.
- Every run and eval must link back to the contract used to judge it.
- Deterministic checks come before LLM-as-judge calls.
- LLM judges are optional, bounded, attributable, and cost tracked.
- Failed checks should create actionable failure packets.
- Fixes should be bounded and linked to the failures they address.
- Version comparisons should explain improvement, regression, and remaining
  weakness with evidence.
- CI must pass without model-provider credentials.

## Domain Objects

### EvalContract

An eval contract defines what good behavior means for a scenario or capability.

It can describe customer triage, document review, research support, coding
assistance, tool use, or any other runnable agent behavior.

```text
EvalContract
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

Checks should support deterministic types first:

- `output_contains`
- `output_not_contains`
- `tool_called`
- `tool_not_called`
- `tool_argument_equals`
- `tool_result_referenced`
- `json_path_exists`
- `regex_match`
- `manual_review_required`

Later, checks can include LLM-as-judge criteria.

### Scenario

A scenario defines what the runner executes.

```text
Scenario
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

Scenarios are first-class because users need to run the same agent version
against the same input before and after a fix.

In the React console, scenarios appear as test cases. The current UI supports
three input shapes:

- `single_turn`: one isolated user prompt;
- `conversation`: prior messages plus the next user turn;
- `trace_replay`: selected or pasted prior spans/messages/evidence used as the
  starting context for a replay.

The API keeps this shape in `setup_context` while the runner executes `input`.
Future trace replay work can replace pasted replay seeds with first-class trace
span selection without changing the core `Scenario -> Run -> EvalResult` loop.

### AgentVersion

An agent version is a candidate behavior snapshot.

```text
AgentVersion
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

The platform can start with simple versions derived from an agent design. The
important requirement is that v0 and v1 are distinguishable in evidence.

### Run

A run records what happened when a version handled a scenario.

```text
Run
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
```

Runs should create or link evidence artifacts:

- `RUN_RESULT`
- `TOOL_CALL`
- `TOOL_RESULT`
- `TRACE_REF`

When Langfuse is configured for a live raw OpenAI Responses call, the runner
should record the outer agent observation and a child `openai.responses`
generation observation with model input, output, response id, status, and token
usage. The platform still stores only the normalized run evidence and trace
reference as product state.

### EvalResult

An eval result records contract performance for one run.

```text
EvalResult
  id
  project_id
  run_id
  eval_contract_id
  judge_prompt_template_id
  mode
  score
  passed
  checks
  created_at
```

Each check should capture:

```text
EvalCheckResult
  check_id
  check_type
  passed
  observed
  expected
  evidence_artifact_ids
  comment
```

### JudgeOutput

A judge output stores deterministic or LLM judge details.

```text
JudgeOutput
  id
  project_id
  eval_result_id
  judge_prompt_template_id
  mode
  model
  input_summary
  output
  token_usage
  cost_estimate
  created_at
```

Deterministic evals can still create judge outputs when the output is useful for
evidence and debugging.

### FailurePacket

A failure packet turns a failed eval into actionable diagnosis.

```text
FailurePacket
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

Expected links:

- `FAILURE_PACKET GENERATED_FROM EVAL_RESULT`
- `FAILURE_PACKET SUPPORTED_BY RUN_RESULT`
- `FAILURE_PACKET SUPPORTED_BY JUDGE_OUTPUT`
- `FAILURE_PACKET SUPPORTED_BY TOOL_CALL`

### FixProposal

A fix proposal describes a bounded change.

```text
FixProposal
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

Expected links:

- `FIX_PROPOSAL ADDRESSES FAILURE_PACKET`
- `FIX_PROPOSAL TARGETS AGENT_VERSION`

### Comparison

A comparison explains whether a candidate improved against a baseline.

```text
Comparison
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
  created_at
```

Expected links:

- `VERSION_COMPARISON GENERATED_FROM EVAL_RESULT`
- `VERSION_COMPARISON IMPROVED_FROM AGENT_VERSION`
- `VERSION_COMPARISON REGRESSED_FROM AGENT_VERSION`
- `VERSION_COMPARISON JUSTIFIED_BY FAILURE_PACKET`

## API Contract Direction

The API should stay project-scoped.

### Eval Contracts

```text
GET  /api/projects/{project_id}/eval-contracts
POST /api/projects/{project_id}/eval-contracts
GET  /api/projects/{project_id}/eval-contracts/{contract_id}
PATCH /api/projects/{project_id}/eval-contracts/{contract_id}
```

### Scenarios

```text
GET  /api/projects/{project_id}/scenarios
POST /api/projects/{project_id}/scenarios
GET  /api/projects/{project_id}/scenarios/{scenario_id}
PATCH /api/projects/{project_id}/scenarios/{scenario_id}
```

### Versions

```text
GET  /api/projects/{project_id}/agent-designs/{agent_design_id}/versions
POST /api/projects/{project_id}/agent-designs/{agent_design_id}/versions
GET  /api/projects/{project_id}/agent-designs/{agent_design_id}/versions/{version_id}
```

### Runs

```text
GET  /api/projects/{project_id}/runs
POST /api/projects/{project_id}/runs
GET  /api/projects/{project_id}/runs/{run_id}
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

The existing agent-scoped run endpoint may remain as a convenience while the
project-scoped run contract becomes canonical.

### Evaluation

```text
POST /api/projects/{project_id}/runs/{run_id}/evaluate
GET  /api/projects/{project_id}/eval-results/{eval_result_id}
```

Evaluation request:

```json
{
  "evalContractId": "contract_123",
  "judgeMode": "deterministic"
}
```

### Failure Packets

```text
GET  /api/projects/{project_id}/failure-packets
POST /api/projects/{project_id}/failure-packets
GET  /api/projects/{project_id}/failure-packets/{failure_packet_id}
PATCH /api/projects/{project_id}/failure-packets/{failure_packet_id}
```

### Fix Proposals

```text
GET  /api/projects/{project_id}/fix-proposals
POST /api/projects/{project_id}/fix-proposals
GET  /api/projects/{project_id}/fix-proposals/{fix_proposal_id}
PATCH /api/projects/{project_id}/fix-proposals/{fix_proposal_id}
```

### Comparisons

```text
POST /api/projects/{project_id}/comparisons
GET  /api/projects/{project_id}/comparisons/{comparison_id}
```

## UI Requirements

The UI should make the EDD loop legible without showing every future feature at
once.

For a selected agent:

- show the active version;
- show runnable scenarios;
- show the selected eval contract and pass criteria;
- run the selected version against the selected scenario;
- evaluate the run against the selected contract;
- show failed checks as failure packets;
- show bounded fixes;
- create a candidate version from a fix;
- compare baseline and candidate evidence.

The UI should not hide expectations inside button labels or logs. The user
should be able to answer:

- What was the agent expected to do?
- What did it actually do?
- Which evidence supports the judgment?
- What fix was proposed?
- Did the candidate version improve?

## Deterministic Judge Path

The first implementation should use deterministic checks so CI and demos do not
need provider keys.

Flow:

```text
Run output + tool evidence + EvalContract
  -> deterministic check engine
  -> EvalResult
  -> FailurePacket if failed
```

The deterministic engine should inspect structured run evidence, not only raw
text.

## LLM-As-Judge Path

LLM judges should be optional.

Flow:

```text
Run evidence + EvalContract + JudgePromptTemplate
  -> bounded judge prompt
  -> JudgeOutput
  -> EvalResult
  -> FailurePacket if failed
```

Requirements:

- explicit user/workflow trigger;
- no CI dependency on provider keys;
- record model and prompt template version;
- record token/cost telemetry;
- cache or reuse summaries when possible.

## Relationship To Tools

Tool policy belongs to the platform.

Eval contracts can require or forbid tool use for a scenario, but the available
tool definitions and approval status are platform-owned.

Examples:

- a contract may require `get_weather` for a weather scenario;
- a contract may forbid web search for a closed-book scenario;
- a contract may require a retrieval tool for a document-review scenario.

The product model is arbitrary agent behavior. Tool checks are one type of
expectation, not the whole product.

## Implementation Plan

### Step 1: OpenAPI First

- Add request/response shapes for contracts, scenarios, runs, eval results,
  failure packets, fixes, versions, and comparisons.
- Add contract tests.
- Keep non-implemented endpoints as `501` only if they are needed to stabilize
  UI/domain design.

### Step 2: EvalContract Storage

- Store contracts as artifacts and structured records.
- Link contracts to scenarios and agent designs.
- Seed a small smoke contract for local validation.

### Step 3: Run Records

- Promote current run artifact behavior into a first-class run record.
- Store tool calls/tool results as structured evidence.
- Preserve the existing mock/live runner behavior.

### Step 4: Contract-Driven Eval

- Replace hardcoded text checks with contract-driven deterministic checks.
- Link eval results to run, contract, and evidence artifacts.

### Step 5: Failure Packets And Fixes

- Generate failure packets from failed check results.
- Create bounded fix proposals that address failure packets.

### Step 6: Versions And Comparison

- Add baseline/candidate versions.
- Create candidate versions from fixes.
- Compare v0/v1 runs and eval results.

### Step 7: UI Loop

- Make scenario, contract, run, eval, failure, fix, version, and comparison
  visible in the React console.

## Acceptance Criteria

This HLD is ready for implementation when:

1. The OpenAPI contract defines the core objects.
2. A user can see where expectations live.
3. A run references a scenario and eval contract.
4. An eval reads the contract instead of hidden code-only checks.
5. Failed checks create failure packets.
6. Fix proposals link to failure packets.
7. A candidate version can be compared with a baseline version.
8. The whole loop works in deterministic mode without provider keys.

## Success Criteria

The first implementation succeeds when a portfolio reviewer can see:

```text
v0 did X.
The contract expected Y.
The eval failed because of Z.
The platform created a failure packet.
The fix proposed a bounded change.
v1 was run against the same contract.
The comparison shows whether v1 improved.
```

That is the proof point for eval-driven design.
