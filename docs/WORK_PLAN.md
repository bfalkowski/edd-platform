# EDD Platform Work Plan

This is the working checklist for the clean-room consolidated EDD Platform repo.

The product direction is one React console, one platform API, runner packages
behind the API, and evidence artifacts as the durable memory of the workflow.

Planning anchors:

- [`PRODUCT_SPINE.md`](PRODUCT_SPINE.md) defines the canonical product objects.
- [`HLD_COVERAGE_MATRIX.md`](HLD_COVERAGE_MATRIX.md) tracks planning coverage
  before feature code.
- [`hld/HLD-004-eval-contracts-runs-judges-and-fixes.md`](hld/HLD-004-eval-contracts-runs-judges-and-fixes.md)
  defines the next implementation backbone.
- [`API_CONTRACT.md`](API_CONTRACT.md) defines the Phase 2 API backbone to
  implement through FastAPI/OpenAPI.
- [`HAPPY_PATH_WALKTHROUGH.md`](HAPPY_PATH_WALKTHROUGH.md) is the canonical
  manual smoke script for validating the product flow.

## Phase 0: Repo Foundation

- [x] Create clean public repo with fresh history.
- [x] Add repo rule banning `Co-authored-by` commit trailers.
- [x] Add canonical frontend design guide.
- [x] Add AI-assisted development guardrails.
- [x] Add architectural decision record directory.
- [x] Add architecture overview diagrams.
- [x] Add OpenAPI export, lint, and contract tests.
- [x] Add monorepo folder structure.
- [x] Add React app scaffold in `apps/web`.
- [x] Add FastAPI app scaffold in `apps/api`.
- [x] Add shared domain package scaffold in `packages/domain`.
- [x] Add local dev script.
- [x] Add local test/build script.
- [x] Verify API tests and web build.
- [x] Browser-smoke the first UI slice.

## Phase 1: Evidence Spine

- [x] Add `AgentDesign` create/list API.
- [x] Add first `AGENT_DESIGN` artifact when an agent design is created.
- [x] Add project artifact list endpoint.
- [x] Add project artifact keyword search endpoint.
- [x] Add deterministic context pack endpoint.
- [x] Display context-pack-backed evidence in the UI.
- [x] Replace hardcoded `project_default` with a real `Project` model.
- [x] Add artifact detail endpoint.
- [x] Add artifact link model.
- [x] Add artifact link create/read endpoints.
- [x] Show related artifacts in the UI.
- [x] Persist state beyond in-memory storage.

## Phase 2: Eval Contract Backbone

This phase defines the missing API and data contracts for eval-driven design.
Do this before adding more workflow UI.

- [x] Add deterministic runner package.
- [x] Run a mock scenario from a selected agent design.
- [x] Run a live OpenAI scenario from a selected agent design.
- [x] Store run evidence artifacts.
- [x] Add platform-owned tool definitions and approval status.
- [x] Add agent-level approved tool allowlists.
- [x] Adapt approved platform tools into LangChain/LangGraph tool primitives.
- [x] Store tool calls and tool results as run evidence.
- [ ] Build a schema-first tool registry so user-created tools define input
      JSON Schema, output schema or output description, implementation kind
      (`http`, `python`, `mcp`, `builtin`, `mock`), auth/config requirements,
      deterministic mock behavior, approval status, and adapters for
      LangChain/LangGraph, OpenAI tool calling, MCP, OpenAPI docs, and eval
      validation.
- [x] Synthesize `HLD-004: Eval Contracts, Runs, Judges, and Fixes`.
- [x] Define planned OpenAPI contracts for `EvalContract`, `Run`, `EvalResult`,
      `FailurePacket`, `FixProposal`, `AgentVersion`, and `Comparison`.
- [x] Implement the Phase 2 API contracts in FastAPI and generated OpenAPI.
- [x] Implement `Scenario` API contracts.
- [x] Implement `EvalContract` API contracts.
- [x] Implement `AgentVersion` API contracts.
- [x] Implement canonical project-scoped `Run` API contracts.
- [x] Implement contract-driven `EvalResult` API contracts.
- [x] Implement `FailurePacket` API contracts.
- [x] Implement `FixProposal` API contracts.
- [x] Implement `Comparison` API contracts.
- [ ] Add `EvalContract` artifacts as the first-class place where agent
      expectations live.
- [ ] Add scenario-specific contracts that can describe any agent behavior,
      required evidence, tool expectations, output shape, forbidden behavior,
      and pass/fail criteria.
- [ ] Add run records that reference agent design/version, scenario, mode,
      tools, and optional eval contract.
- [ ] Split tool calls and tool results into first-class evidence artifacts.
- [ ] Replace hardcoded eval checks with contract-driven deterministic checks.
- [x] Store eval results and judge outputs as evidence artifacts linked to runs
      and contracts.
- [x] Create failure packet artifacts when contract checks fail.
- [x] Add bounded fix proposal artifacts linked to failure packets.
- [ ] Add agent versions so fixes can produce v1, v2, v3, and later candidates.
- [x] Add comparison artifacts/API for baseline vs candidate runs.
- [ ] Keep all new API shapes covered by OpenAPI export, lint, and contract
      tests.

### Phase 2 Vertical Slice: Prove Eval-Driven Design

The first Phase 2 demo should prove this loop end to end:

```text
v0 run
  -> evaluate against explicit EvalContract
  -> create failure packet
  -> create bounded fix
  -> run v1
  -> evaluate against the same EvalContract
  -> compare whether the fix improved the agent
```

The product model must support arbitrary agents. A contract should be able to
describe expectations for customer triage, document review, research support,
coding assistance, weather lookup, or any other runnable behavior. Contracts
should be data, not code branches.

For any scenario, the expectation contract should be able to verify that an
agent:

- uses required tools when the contract requires tool use;
- avoids tools that are not approved for the agent or scenario;
- grounds the final answer in the available evidence;
- follows required output shape and safety constraints;
- avoids contract-specific forbidden behavior;
- records tool calls and judge results as evidence artifacts.

The current weather/tool scenario is only an implementation smoke test because
it is easy to verify. It should not become the canonical product workflow.

## Phase 3: Builder UI for the EDD Loop

This phase makes the backbone usable without hiding the system model.

- [x] Add React console scaffold.
- [x] Add left-nav agent creation and selection.
- [x] Display context-pack-backed evidence in the UI.
- [x] Show related artifacts in the UI.
- [x] Show run/eval evidence in context packs.
- [x] Show the selected eval contract beside the playground run controls.
- [x] Add UI to create scenario inputs.
- [x] Add UI to create eval contracts.
- [x] Add UI to edit agent tool allowlists.
- [x] Add UI to run v0 against a selected contract.
- [x] Add UI to evaluate a selected run against a selected contract.
- [x] Add UI to inspect failure packets and bounded fix proposals.
- [x] Add UI to create a candidate version from a fix proposal.
- [x] Add UI to run/evaluate candidate versions.
- [x] Add a v0/v1 comparison view that shows run evidence, eval checks,
      failure packets, fixes, and pass/fail movement.
- [x] Reconstruct the selected agent's EDD loop from platform records after
      refresh or agent switch.
- [x] Keep every generated or edited output represented as an artifact.

## Phase 4: Judges and Gates

- [x] Store judge prompts in the platform and link them to contracts.
- [x] Add mock judge execution for local/CI mode.
- [x] Add optional LLM-as-judge execution for live mode.
- [x] Add gate definitions.
- [x] Add gate decision artifacts.
- [x] Track token and cost telemetry for live judge calls.
- [x] Add promotion readiness views backed by gate decisions.

## Phase 5: Langfuse Adapter

- [x] Define trace reference artifact shape.
- [x] Add Langfuse adapter package implementation.
- [x] Import or link Langfuse traces as evidence artifacts.
- [x] Show trace links inside evidence context.
- [x] Instrument canonical live agent runs with Langfuse trace capture.
- [x] Auto-create trace references for traced live runs.
- [x] Add live E2E script for agent creation, live run, live eval, and trace lookup.
- [x] Keep platform artifacts as the source of truth.

## Phase 6: Context Intelligence

- [x] Add richer context pack purposes.
- [x] Add deterministic context assembly strategies per purpose.
- [x] Add optional LLM evidence summaries.
- [x] Cache evidence summaries for unchanged context packs.
- [x] Record summary token usage and cost telemetry.

## Phase 7: Portfolio Polish

- [x] Add GitHub Actions CI.
- [ ] Add README screenshot.
- [ ] Create a dedicated documentation repo, modeled after a product docs site
      such as `langfuse/langfuse-docs`, for guides, concepts, API references,
      architecture notes, and portfolio-ready walkthroughs.
- [x] Add a public demo-ready customer triage example.
- [x] Add seeded sample data for local demo mode.
- [ ] Refactor `apps/api/edd_platform_api/main.py` into focused modules instead
      of keeping routes, models, services, and app wiring in one file.
- [ ] Keep HLD index aligned with implementation.

## Current UI Status

The UI works for the first vertical slice:

1. Start the app with `./scripts/dev.sh`.
2. Open `http://localhost:5173`.
3. Create an agent with a name and intent.
4. The agent appears in the left nav.
5. The API creates an `AGENT_DESIGN` artifact.
6. The Evidence panel displays a deterministic `AGENT_PROMPT_REVIEW` context
   pack containing that artifact.
7. Local API state persists to Postgres across restarts.
8. A selected agent can run a deterministic mock scenario from the playground.
9. The API stores the run output as a `RUN_RESULT` artifact.
10. The UI can evaluate a run and store deterministic `EVAL_RESULT` evidence.

The UI is not yet a full EDD workflow. It does not yet edit artifact sections,
create gates, or link Langfuse traces.
