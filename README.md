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
- The platform owns tool governance: definitions, approval status, agent allowlists,
  and tool-call evidence.
- LangChain/LangGraph should provide the agent/tool execution loop; the runner
  adapts approved platform tools into that loop and returns evidence.
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
7. Keep local state across API restarts with Postgres-backed storage.
8. Run a deterministic mock scenario from the selected agent.
9. Store the scenario output as a `RUN_RESULT` evidence artifact.
10. Evaluate the run and store deterministic `EVAL_RESULT` evidence.
11. Optionally switch the playground to live OpenAI mode and store provider
    output as the same `RUN_RESULT` evidence shape.
12. Give new agents an approved `get_weather` tool from the platform registry;
    live runs adapt that approved tool into a LangChain/LangGraph tool loop.

This is intentionally small. The next layers are editable tool allowlists,
judge prompts, gates, failure packets, and richer evidence context.

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
docker compose up -d postgres
./scripts/dev.sh
```

The API runs on `http://127.0.0.1:8001`. The web console runs on Vite's
reported local URL, usually `http://localhost:5173`.

By default, the API connects to
`postgresql://edd_platform:edd_platform@127.0.0.1:5432/edd_platform`.
Set `EDD_PLATFORM_DATABASE_URL` to point at a different Postgres database.
Tests use `EDD_PLATFORM_STORAGE_BACKEND=memory` so CI does not require a
database service.

Live OpenAI runs are opt-in. Set `OPENAI_API_KEY` before starting the API, then
choose `Live OpenAI` in the playground. The default model is `gpt-5-nano`; set
`EDD_OPENAI_MODEL` to use a different OpenAI model.

Run tests and build checks:

```bash
./scripts/test.sh
```
