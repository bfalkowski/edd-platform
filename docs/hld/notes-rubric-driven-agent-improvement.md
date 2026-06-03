# Note: Rubric-Driven Agent Improvement

LangChain's RubricMiddleware announcement is useful market validation for the
EDD Platform direction.

Reference:

- [Introducing Rubrics: Build Agents that Evaluate and Correct Their Work](https://www.langchain.com/blog/introducing-rubrics-for-deepagents)

Useful idea to preserve:

```text
explicit rubric
  -> grader / judge
  -> per-criterion verdict
  -> targeted feedback
  -> retry or bounded fix
  -> stop on pass, max iterations, failure, or grader error
```

EDD Platform should model this as durable evidence artifacts rather than hidden
middleware state:

- `BehaviorRule` and `EvalContract` define the rubric.
- `JudgePromptTemplate` defines the grader.
- `EvalResult` stores per-criterion verdicts.
- `FailurePacket` stores actionable feedback.
- `FixProposal` or runner retry applies bounded correction.
- `GateDecision` records whether the result is acceptable.

This is now represented in
[`HLD-004: Eval Contracts, Runs, Judges, and Fixes`](HLD-004-eval-contracts-runs-judges-and-fixes.md).
Revisit this note when implementing optional LLM-as-judge behavior.

Do not copy a framework-specific implementation wholesale. The product value is
the platform-native evidence model around rubric-driven improvement.
