# HLD-006: Agentic Investigation Evaluation Harness

## Status

Draft

## Goal

Extend EDD Platform with a flagship example vertical: an **Agentic Investigation Evaluation Harness**. The purpose is to exercise how EDD Platform evaluates a long-horizon AI agent that investigates cases, gathers evidence, uses tools, classifies risk, and recommends an action.

This vertical makes EDD Platform directly applicable to real-world agent evaluation problems: long-horizon behavior, tool use, investigation quality, coverage gaps, regression gates, human review, and policy-expert authoring.

All cases are **safe and synthetic**. No real abuse data, operational misuse instructions, real security incidents, or sensitive policy-enforcement data.

---

## Product Framing

EDD Platform's existing loop:

```
Observe -> Analyze -> Measure -> Improve -> Compare -> Gate
```

Applied to an investigation agent:

```
Case data / synthetic review item
        -> investigation agent run
        -> trajectory evidence
        -> grading / eval result
        -> failure packet
        -> coverage analysis
        -> bounded fix proposal
        -> candidate version
        -> comparison
        -> release gate
```

**Central question this vertical answers:**
> How do we know an agentic investigation system catches what it should, avoids over-enforcement, gathers the right evidence, and stays reliable as prompts, tools, models, and cases change?

---

## Example Vertical: Policy Investigation Agent

A synthetic **Policy Investigation Agent** receives a case that may require review. It must inspect evidence, use approved tools, decide whether the case is benign, suspicious, violating, or ambiguous, and recommend a next action.

**Synthetic case categories:**
- account abuse
- spam-like behavior
- phishing-like behavior
- policy ambiguity
- benign false positive
- missing evidence
- unsafe escalation

**Example agent task:**
```
A user account triggered a policy review because recent messages matched a suspicious
activity pattern. Investigate the case, gather relevant evidence, determine whether
the case is benign, suspicious, violating, or ambiguous, and recommend the next action.
```

**Agent output schema:**
```json
{
  "classification": "benign | suspicious | violating | ambiguous",
  "confidence": "low | medium | high",
  "evidence_summary": ["..."],
  "policy_refs": ["..."],
  "recommended_action": "allow | monitor | escalate | enforce",
  "reasoning_summary": "..."
}
```

---

## Tools

Synthetic platform-owned tools with mock responses. Fit the existing tool governance model (`implementation_kind = mock`, `status = approved`).

| Tool | Description |
|------|-------------|
| `get_case_metadata` | Fetch case ID, policy area, risk severity |
| `fetch_recent_messages` | Retrieve synthetic message history for the account |
| `retrieve_policy_section` | Look up relevant policy text by section ID |
| `lookup_prior_reviews` | Check prior review history for this account |
| `summarize_evidence` | Condense gathered evidence into a structured summary |
| `create_escalation_report` | Generate escalation artifact for human review |

Each tool has: `name`, `description`, `input_schema`, `output_schema`, `output_description`, `implementation_kind`, `mock_response`, `status`.

---

## Eval Dimensions

Grades both **outcome quality** and **trajectory quality**.

| Dimension | What it measures |
|-----------|-----------------|
| `classification_accuracy` | Correct benign/suspicious/violating/ambiguous label |
| `evidence_completeness` | Required evidence items gathered |
| `policy_grounding` | Relevant policy sections referenced |
| `false_positive_control` | Benign cases not over-enforced |
| `escalation_quality` | Escalation triggered when and only when warranted |
| `tool_use_quality` | Appropriate tools used, no hallucinated tool calls |
| `investigation_trajectory_quality` | Coherent step-by-step reasoning before conclusion |
| `unsupported_claim_avoidance` | No claims without evidence backing |

Each eval result surfaces: what passed, what failed, supporting evidence, and which failure packet to create on failure.

---

## Dataset / Case Model

Conceptual objects (can be represented via existing `Scenario` + `EvalContract` + seeded metadata for the first slice):

```
EvalDataset
EvalCase
PolicyArea
RiskSeverity
ExpectedDecision
GradingRubric
CoverageReport
```

**Case fields:**
```
case_id, title, policy_area, risk_severity, input, available_evidence,
expected_classification, expected_action, required_evidence, rubric_notes, known_trickiness
```

**Seed cases:**
1. Obvious synthetic violation
2. Benign false positive
3. Ambiguous case requiring escalation
4. Missing evidence — agent should ask for more or escalate
5. Suspicious pattern with insufficient confidence

---

## Coverage Analysis

Shows whether the eval suite covers the right areas and where measurement gaps exist.

**Example coverage report:**

| Policy Area | Cases | Pass Rate | False Negatives | False Positives | Saturation |
|-------------|-------|-----------|-----------------|-----------------|------------|
| Spam-like behavior | 12 | 0.83 | 1 | 2 | Medium |
| Account abuse | 10 | 0.70 | 3 | 0 | Low |
| Policy ambiguity | 8 | 0.62 | n/a | n/a | Low |
| Benign edge cases | 10 | 0.80 | n/a | 2 | Medium |

**Saturation heuristic:**
- High = pass rate very high, no recent failures → evals may be saturated
- Medium = mixed signal
- Low = still producing useful failures → keep investing

**Proposed endpoint:**
```
GET /api/projects/{project_id}/agent-designs/{agent_design_id}/coverage
```

Returns: coverage by policy area, coverage by severity, pass rates by dimension, failure modes, measurement gaps, saturation hints, recommended next cases.

---

## Release Gate

**Gate name:** Investigation Agent Release Gate

**Gate criteria:**
- No critical failure packets remain open
- High-severity recall ≥ configured threshold
- Benign false-positive rate ≤ configured threshold
- Policy grounding checks pass
- Required evidence coverage exists
- Candidate does not regress against baseline

Uses existing `GateDecision` objects. First implementation can use deterministic mock scores.

---

## Human / Policy Expert Authoring

Lightweight first version: a seeded form or documented workflow letting a policy expert define:

```
policy area
risk severity
case description
expected decision
required evidence
escalation rule
rubric notes
known tricky behavior
```

EDD converts this into a `Scenario` + `EvalContract`. Maps to the product goal: **domain experts can author, run, and iterate on evaluations without engineering support.**

---

## Mapping to Existing EDD Spine

Do not replace the spine — extend it.

| Investigation concept | EDD spine object |
|-----------------------|-----------------|
| Investigation case | `Scenario` |
| Expected behavior | `EvalContract` |
| Agent execution | `Run` |
| Trajectory / tool evidence | `ArtifactRecord` / `TraceRef` |
| Grading result | `EvalResult` / `JudgeOutput` |
| Named issue | `FailurePacket` / `FailureMode` |
| Dataset coverage | `CoverageReport` artifact |
| Candidate improvement | `FixProposal` / `AgentVersion` |
| Release readiness | `Comparison` / `GateDecision` |

**Prefer working coherently over large schema expansion.** Use existing artifacts and metadata first.

---

## Implementation Phases

### Phase 1 — Seeded investigation example

```
examples/agentic-investigation-evals/
  README.md
  cases.json
  policy.md
  seed_demo.py
```

Seed script creates: agent design, baseline agent version, approved investigation tools, eval cases as scenarios, eval contracts/rubrics, gate definition, example artifacts.

### Phase 2 — Run and evaluate investigation cases

Use existing runner/eval infrastructure. Support:
- Run baseline agent on selected case
- Evaluate result against investigation rubric
- Store run + eval artifacts
- Create judge output if applicable
- Create failure packet on failure
- Show evidence chain

Mock mode must work without provider keys.

### Phase 3 — Coverage analysis

New endpoint + UI panel. Simple deterministic implementation acceptable for first slice.

### Phase 4 — Release gate

Seed a gate that blocks promotion when the investigation agent regresses. Demonstrate: baseline vs candidate comparison, open critical failure packet blocks promotion, missing coverage blocks promotion, candidate improvement passes when evidence supports it.

### Phase 5 — Docs

Update README and `docs/HAPPY_PATH_WALKTHROUGH.md` with investigation vertical section. Update `ARCHITECTURE.md` and `PRODUCT_SPINE.md` only where necessary.

---

## Acceptance Criteria

A user can:

1. Start the local platform
2. Run `seed_demo.py`
3. Open the investigation agent in the UI
4. Select a synthetic investigation case
5. Run the baseline agent
6. Evaluate the result
7. See run evidence, tool evidence, and eval evidence
8. See a failure packet when the agent misses required evidence or misclassifies
9. View a coverage report (policy areas, severity, pass/fail rates, gaps)
10. Create or view a candidate version
11. Compare baseline vs candidate
12. See a release gate pass or block based on evidence

---

## Non-Goals

- Real abuse detection
- Real cyber/bio/influence-operation examples
- Jailbreak payload libraries
- Evasion guidance
- Production trust-and-safety workflows
- Auth / multi-tenancy
- Large-scale distributed eval processing
- Full RL training infrastructure
