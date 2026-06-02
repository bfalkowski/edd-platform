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

This repo is currently a skeleton. The first implementation step is moving the
existing React console and platform API into `apps/web` and `apps/api`.

```bash
./scripts/dev.sh
./scripts/test.sh
```

