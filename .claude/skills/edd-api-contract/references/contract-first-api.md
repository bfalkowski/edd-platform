# Contract-First API

Use this reference when adding or changing EDD Platform API behavior.

## Goal

Keep the platform API aligned with the product spine, OpenAPI contract, tests,
and evidence model. API work should make the system easier to explain, not just
add endpoints.

## Workflow

1. Identify the product object: project, agent design, version, scenario,
   eval contract, run, eval result, judge output, failure packet, fix proposal,
   comparison, gate decision, artifact, artifact link, context pack, or trace
   ref.
2. Read the current contract in `docs/API_CONTRACT.md`.
3. If the API shape is missing or ambiguous, update the docs before code.
4. Add the smallest Pydantic request/response models that make the object
   explicit.
5. Keep routes project-scoped unless the object is intentionally global.
6. Persist through the store abstraction; do not bypass platform storage.
7. Create or link evidence artifacts when the endpoint changes EDD state.
8. Add focused tests for success behavior and important failure behavior.
9. Update OpenAPI lint required paths when adding route families.
10. Regenerate `docs/openapi.json` and verify it is current.

## Evidence Discipline

Endpoint side effects should be visible as artifacts when they matter to the
EDD loop.

Examples:

- creating an agent design creates `AGENT_DESIGN` evidence;
- running an agent creates run evidence;
- evaluating a run creates `EVAL_RESULT` and `JUDGE_OUTPUT` evidence;
- failed checks create `FAILURE_PACKET` evidence;
- bounded repair ideas create `FIX_PROPOSAL` evidence;
- live traces create `TRACE_REF` evidence.

## Avoid

- endpoints that only mutate hidden state;
- behavior expectations stored only as code constants;
- UI changes before API/evidence shape is stable;
- provider-key requirements in deterministic API tests;
- broad route families without OpenAPI and test coverage.
