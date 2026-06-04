---
name: edd-docs-hld
description: Update EDD Platform planning docs, HLDs, product spine, roadmap, or coverage matrix. Use when the user asks whether the plan is aligned, whether HLDs are complete, what to build next, how to avoid drift, or when adding/changing product architecture without feature code.
---

# EDD Docs And HLD

Use this skill for planning and architecture work.

## Required Reading

Start with:

- `docs/PRODUCT_SPINE.md`
- `docs/HLD_COVERAGE_MATRIX.md`
- `docs/WORK_PLAN.md`
- `docs/hld/README.md`

Read the relevant HLD after identifying the product area.

## Use Case References

- checking whether HLDs are aligned: `references/hld-alignment.md`
- creating or updating an HLD: `references/hld-authoring.md`

## Workflow

1. Map the question to the product spine.
2. Check whether the capability is covered, partial, planned, or a gap in `docs/HLD_COVERAGE_MATRIX.md`.
3. Update or create the smallest doc needed to remove ambiguity.
4. Map human feedback to evidence artifacts or the eval loop before adding new concepts.
5. Keep HLD language aligned with the consolidated repo:
   - React console, not separate Lab UI.
   - Runner package, not product frontend.
   - Evidence context, not generic memory.
   - Agent design/version, not local draft.
   - Langfuse observability, not Langfuse as the EDD source of truth.
6. Update `docs/WORK_PLAN.md` only for active, executable milestones.
7. Avoid feature code during planning hardening unless the user asks to build.

## Guardrails

- Do not preserve obsolete history for its own sake.
- Do not create broad TODO lists detached from HLD/API/UI evidence.
- Keep private context out of public docs.
- Do not require provider-key env vars such as `OPENAI_API_KEY` in CI or deterministic docs/examples.
- Keep docs portfolio-safe and product-focused.
