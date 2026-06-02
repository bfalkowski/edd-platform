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
