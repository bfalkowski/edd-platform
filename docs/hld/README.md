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
| [HLD-000](HLD-000-clean-room-consolidation.md) | Clean-Room Consolidation Plan | Implemented |
| [HLD-001](HLD-001-artifact-retrieval-and-evidence-context.md) | Artifact Retrieval and Evidence Context | Implemented for the current product slice |
| [HLD-002](HLD-002-product-architecture-and-data-model.md) | Product Architecture and Data Model | Implemented for the current product slice |
| [HLD-003](HLD-003-eval-driven-agent-design-workflow.md) | Eval-Driven Agent Design Workflow | Implemented for the current product slice |
| [HLD-004](HLD-004-eval-contracts-runs-judges-and-fixes.md) | Eval Contracts, Runs, Judges, and Fixes | Implemented for the current product slice |
| [HLD-005](HLD-005-relational-metadata-and-polars-analysis-plane.md) | Relational Metadata and Polars Analysis Plane | Implemented for the current product slice |
| [HLD-006](HLD-006-agentic-investigation-evaluation-harness.md) | Agentic Investigation Evaluation Harness | Draft |

## Notes

- [Rubric-driven agent improvement](notes-rubric-driven-agent-improvement.md)
  is captured by `HLD-004` and should be revisited when implementing optional
  LLM-as-judge behavior.

## Architecture Companions

The HLD set is supported by two product architecture docs at the repo root:

- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) defines users, requirements,
  system shape, component deep dives, boundaries, operability/failure-mode
  behavior, and the scale path.
- [`../SYSTEM_TRADEOFFS.md`](../SYSTEM_TRADEOFFS.md) records the reasoning
  behind the core architecture decisions.
