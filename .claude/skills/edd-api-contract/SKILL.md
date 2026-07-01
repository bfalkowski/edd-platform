---
name: edd-api-contract
description: Implement or update EDD Platform API contracts. Use when adding FastAPI routes, Pydantic request/response models, OpenAPI paths, contract tests, eval contracts, scenarios, runs, eval results, failure packets, fix proposals, comparisons, or when the user says contract-first, OpenAPI, API backbone, or Phase 2 API.
---

# EDD API Contract

Use this skill for contract-first backend work in EDD Platform.

## Required Reading

Read these before coding:

- `docs/PRODUCT_SPINE.md`
- `docs/API_CONTRACT.md`
- `docs/hld/HLD-004-eval-contracts-runs-judges-and-fixes.md`
- `docs/WORK_PLAN.md`

## Use Case References

- adding or changing API contracts: `references/contract-first-api.md`
- managing OpenAPI drift: `references/openapi-drift.md`

## Workflow

1. Identify the product spine object being changed.
2. Confirm the API shape in `docs/API_CONTRACT.md`; update docs first if the shape is unclear.
3. Implement the smallest useful FastAPI/Pydantic slice in `apps/api/edd_platform_api/main.py`.
4. Persist records through the existing JSON store collections.
5. Create or link evidence artifacts when the endpoint creates meaningful EDD state.
6. Add focused API tests in `apps/api/tests/test_agent_designs.py` or a more specific test file.
7. Update `scripts/lint_openapi.py` required paths for new route families.
8. Regenerate `docs/openapi.json` with `npm run api:openapi`.
9. Run `./scripts/test.sh`.
10. Update `docs/WORK_PLAN.md` only for completed work.

## Guardrails

- Keep routes project-scoped.
- Keep CI deterministic and provider-key free; provider API keys must never be required for tests.
- Do not hide expectations in code-only constants.
- When API work touches Langfuse traces, prompts, datasets, or scores, use
  `.claude/skills/langfuse/SKILL.md` and keep mutations explicit and reviewable.
- Do not add UI until the API/evidence shape is clear.
- Do not create mock UI from API work; define the contract and evidence shape first.
- Do not mark the whole Phase 2 backbone done when only one object is implemented.
