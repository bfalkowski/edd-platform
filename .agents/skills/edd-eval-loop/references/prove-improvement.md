# Prove Improvement

Use this reference when building or reviewing an eval-driven improvement slice.

## Goal

Prove that a candidate agent version improved against explicit expectations,
not merely that one run looked good.

## Required Shape

```text
Scenario
  -> EvalContract
  -> baseline Run
  -> EvalResult / JudgeOutput
  -> FailurePacket
  -> FixProposal
  -> candidate AgentVersion
  -> candidate Run
  -> candidate EvalResult / JudgeOutput
  -> Comparison
  -> GateDecision when promotion is in scope
```

## Workflow

1. Choose the scenario and make its input explicit.
2. Define the eval contract before judging output.
3. Run the baseline version and store evidence.
4. Evaluate the baseline against the contract.
5. Create failure packets for failed checks.
6. Create bounded fix proposals linked to failure evidence.
7. Create a candidate version from the selected fix.
8. Run the candidate against the same scenario and contract.
9. Compare baseline and candidate evidence.
10. Record whether the fix resolved failures, introduced regressions, or left
    gaps.

## Acceptance Criteria

- The baseline and candidate are both represented.
- The same contract is used for comparison unless the purpose is contract
  evolution.
- Failure packets link back to failed checks, run evidence, and judge output.
- Fix proposals link to failure packets.
- Comparison evidence explains the improvement or regression.

## Avoid

- declaring success from a single candidate run;
- broad prompt rewrites without failure packets;
- hidden expectations in code;
- judge-only decisions without deterministic checks where possible.
