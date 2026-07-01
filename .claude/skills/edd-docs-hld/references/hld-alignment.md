# HLD Alignment

Use this reference when checking whether docs still match the product direction.

## Workflow

1. Start from `docs/PRODUCT_SPINE.md`.
2. Read the HLD for the product area under discussion, starting with its
   `## Status` line (implemented, implemented-with-gaps, or draft).
3. Cross-reference `docs/WORK_PLAN.md`'s Completed Milestones for what has
   actually shipped, since HLD status can lag real implementation.
4. Compare the HLD against the actual repo direction:
   - one React console;
   - API-owned platform state;
   - runner package behind the API;
   - platform artifacts as source of truth;
   - Langfuse as observability and trace evidence;
   - evidence context, not generic memory.
5. Update the smallest doc that removes ambiguity.
6. Update `docs/WORK_PLAN.md` only for executable milestones.

## Output Shape

When reporting alignment, separate:

- aligned;
- partial;
- out of date;
- missing;
- recommended next doc change.

## Avoid

- preserving obsolete history for its own sake;
- broad planning churn;
- adding feature code during a docs-alignment pass.
