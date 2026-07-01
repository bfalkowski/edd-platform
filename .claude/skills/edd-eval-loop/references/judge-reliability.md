# Judge Reliability

Use this reference when creating, changing, or trusting an LLM-as-judge.

## Principle

An LLM judge is another component that needs evaluation. One passing example is
not enough to trust it for gates or promotion decisions.

## Calibration Workflow

1. Define the label vocabulary or scoring scale.
2. Build a small labeled dataset from expected outputs or human decisions.
3. Keep expected outputs out of the judge prompt.
4. Run the judge against the dataset.
5. Start with exact-match or accuracy for a quick signal.
6. Use confusion-matrix metrics for higher-stakes automation.
7. Inspect disagreements qualitatively before changing the prompt.
8. Track judge prompt, model, dataset version, and metric output as evidence.

## Metrics

For binary decisions, compute:

- true positives;
- false positives;
- false negatives;
- true negatives;
- precision;
- recall;
- true positive rate;
- true negative rate.

## Guardrails

- Do not tune on the same examples used to claim final quality.
- Do not let the judge see ground-truth labels.
- Do not use judge output as the only evidence for a promotion gate.
- Keep live judge calls out of CI unless mocked.
