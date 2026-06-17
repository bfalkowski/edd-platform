# High-Level Design

This directory contains the HLDs for the consolidated EDD Platform product.

The historical platform/lab repos had useful design work, but this repo should
not copy their history wholesale. HLDs brought into this repo should be updated
to use the consolidated product language:

- **Agent design**, not draft
- **Runner**, not Lab as a product frontend
- **Evidence context**, not generic memory
- **React console**, not Streamlit or a separate Lab UI
- **Langfuse adapter**, not Langfuse as product state

## Initial HLD Set

| ID | Title | Status |
|---|---|---|
| [HLD-000](HLD-000-clean-room-consolidation.md) | Clean-Room Consolidation Plan | Draft |
| [HLD-001](HLD-001-artifact-retrieval-and-evidence-context.md) | Artifact Retrieval and Evidence Context | Draft |
| [HLD-002](HLD-002-product-architecture-and-data-model.md) | Product Architecture and Data Model | Draft |
| [HLD-003](HLD-003-eval-driven-agent-design-workflow.md) | Eval-Driven Agent Design Workflow | Draft |
| [HLD-004](HLD-004-eval-contracts-runs-judges-and-fixes.md) | Eval Contracts, Runs, Judges, and Fixes | Draft |

## Notes

- [Rubric-driven agent improvement](notes-rubric-driven-agent-improvement.md)
  is captured by `HLD-004` and should be revisited when implementing optional
  LLM-as-judge behavior.

## Architecture Companions

The HLD set is supported by product architecture docs at the repo root:

- [`../ARCHITECTURE_READINESS_BRIEF.md`](../ARCHITECTURE_READINESS_BRIEF.md)
  summarizes users, requirements, constraints, boundaries, and scale path.
- [`../REQUIREMENTS_AND_CONSTRAINTS.md`](../REQUIREMENTS_AND_CONSTRAINTS.md)
  defines functional and non-functional requirements.
- [`../SYSTEM_TRADEOFFS.md`](../SYSTEM_TRADEOFFS.md) records architecture
  tradeoffs.
- [`../OPERABILITY_AND_FAILURE_MODES.md`](../OPERABILITY_AND_FAILURE_MODES.md)
  describes failure modes and recovery behavior.
- [`../ARCHITECTURE_DEEP_DIVES.md`](../ARCHITECTURE_DEEP_DIVES.md) expands the
  eval evidence, tool governance, context, and readiness flows.
