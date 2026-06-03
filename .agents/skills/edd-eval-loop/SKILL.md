---
name: edd-eval-loop
description: Build or review the EDD improvement loop for agents. Use when working on Scenario, EvalContract, Run, EvalResult, JudgeOutput, FailurePacket, FixProposal, AgentVersion, Comparison, GateDecision, baseline vs candidate evaluation, failure diagnosis, bounded fixes, or proving eval-driven design.
---

# EDD Eval Loop

Use this skill when implementing or reviewing the agent improvement loop.

## Canonical Loop

```text
AgentDesign
  -> AgentVersion
  -> Scenario
  -> EvalContract
  -> Run
  -> EvalResult / JudgeOutput
  -> FailurePacket
  -> FixProposal
  -> candidate AgentVersion
  -> Comparison
  -> GateDecision
```

## Workflow

1. Start from the selected agent design and version.
2. Make the scenario explicit; do not rely on hidden playground text.
3. Make expectations explicit in an `EvalContract`.
4. Run the version against the scenario and store run evidence.
5. Evaluate against the contract, producing `EvalResult` and `JudgeOutput`.
6. When checks fail, create `FailurePacket` evidence.
7. Propose bounded fixes that link to failure packets.
8. Create a candidate version from the fix.
9. Compare baseline and candidate evidence.
10. Preserve artifacts and artifact links so the user can explain why improvement did or did not happen.

## Guardrails

- Treat tools, traces, judge outputs, and failure packets as evidence.
- Prefer deterministic checks before LLM-as-judge behavior.
- Keep live LLM calls optional and excluded from CI; provider-key env vars such as `OPENAI_API_KEY` must never be required for tests.
- Compare against a baseline; a single good run does not prove improvement.
- Record human feedback as evidence when automated checks miss quality issues.
- Do not jump directly to broad prompt rewriting; create evidence-backed failure packets and bounded fixes first.
