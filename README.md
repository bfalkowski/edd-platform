# EDD Platform

EDD Platform is a product workspace for designing, evaluating, improving, and
promoting AI agents with evidence.

This repo is a clean-room consolidation of the useful ideas from the earlier
platform and lab repos. It starts fresh: new history, one product UI, one
backend, one runner layer, and no legacy frontend split.

## Product Shape

```text
apps/web
  React product console

apps/api
  Platform API, persistence, judges, gates, evidence, promotion

packages/domain
  Shared EDD object schemas and product language

packages/runner
  LangGraph runner, mock tools, scenarios, deterministic execution harness

packages/langfuse-adapter
  Optional trace evidence integration
```

## Core Principles

- The React console is the only product UI.
- The platform owns agent designs, judge prompts, gates, evidence context, and promotion.
- The runner executes agent implementations and returns evidence.
- Langfuse is an optional trace evidence layer, not the workflow source of truth.
- Local development and CI must work without model-provider keys.
- Useful old code should be copied intentionally, renamed as needed, and simplified.

## Current Slice

The repo now has a minimal local product loop:

1. Start the API and web console.
2. Create an agent design from name and intent.
3. Persist the design through the API.
4. Create an initial `AGENT_DESIGN` evidence artifact.
5. List agent designs for the active project in the left nav.
6. Select a design and inspect its deterministic evidence context pack.

This is intentionally small. The next layers are judge prompts, gates,
deterministic runner evidence, and evidence context.

The evidence context design is captured in
[`docs/hld/HLD-001-artifact-retrieval-and-evidence-context.md`](docs/hld/HLD-001-artifact-retrieval-and-evidence-context.md).

The product architecture and data model are captured in
[`docs/hld/HLD-002-product-architecture-and-data-model.md`](docs/hld/HLD-002-product-architecture-and-data-model.md).

The architecture overview and diagrams are in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

The API contract is generated from OpenAPI and documented in
[`docs/API_CONTRACT.md`](docs/API_CONTRACT.md).

The active implementation checklist is tracked in
[`docs/WORK_PLAN.md`](docs/WORK_PLAN.md).

Frontend conventions are defined in
[`docs/design/FRONTEND_GUIDE.md`](docs/design/FRONTEND_GUIDE.md).

AI-assisted development practices are documented in
[`docs/engineering/AI_AGENT_DEVELOPMENT.md`](docs/engineering/AI_AGENT_DEVELOPMENT.md).

## Initial Milestone

The first useful loop is:

1. Create an agent design in the React console.
2. Persist the target and design artifacts through the API.
3. Bind a judge prompt and gate.
4. Run deterministic mock execution through the runner.
5. Store run/eval evidence.
6. Show evidence context in the UI.
7. Link to Langfuse traces when enabled.

## Local Development

Install the web dependencies once:

```bash
cd apps/web
npm install
```

Run the local product:

```bash
./scripts/dev.sh
```

The API runs on `http://127.0.0.1:8001`. The web console runs on Vite's
reported local URL, usually `http://localhost:5173`.

Run tests and build checks:

```bash
./scripts/test.sh
```
