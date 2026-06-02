# EDD Platform Work Plan

This is the working checklist for the clean-room consolidated EDD Platform repo.

The product direction is one React console, one platform API, runner packages
behind the API, and evidence artifacts as the durable memory of the workflow.

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
- [ ] Add artifact link model.
- [ ] Add artifact link create/read endpoints.
- [ ] Show related artifacts in the UI.
- [ ] Persist state beyond in-memory storage.

## Phase 2: Agent Design Workflow

- [ ] Synthesize `HLD-003: Eval-Driven Agent Design Workflow`.
- [ ] Add target/design artifact sections.
- [ ] Add behavior rules artifacts.
- [ ] Add judge prompt artifacts.
- [ ] Add gate artifacts.
- [ ] Add edit/save support for artifact sections.
- [ ] Add add/remove controls for repeatable sections.
- [ ] Keep every generated or edited output represented as an artifact.

## Phase 3: Runner Integration

- [ ] Synthesize `HLD-004: Runner, Mock Mode, and Live Mode`.
- [ ] Add deterministic runner package.
- [ ] Run a mock scenario from a selected agent design.
- [ ] Store run evidence artifacts.
- [ ] Store eval result artifacts.
- [ ] Display run/eval evidence in context packs.

## Phase 4: Judges and Gates

- [ ] Synthesize `HLD-005: Judges, Gates, and Failure Packets`.
- [ ] Fold rubric-driven agent improvement into `HLD-005`.
- [ ] Store judge prompts in the platform.
- [ ] Add mock judge execution for local/CI mode.
- [ ] Add optional LLM-as-judge execution for live mode.
- [ ] Add gate definitions.
- [ ] Add gate decision artifacts.
- [ ] Track token and cost telemetry for live judge calls.

## Phase 5: Langfuse Adapter

- [ ] Define trace reference artifact shape.
- [ ] Add Langfuse adapter package implementation.
- [ ] Import or link Langfuse traces as evidence artifacts.
- [ ] Show trace links inside evidence context.
- [ ] Keep platform artifacts as the source of truth.

## Phase 6: Context Intelligence

- [ ] Add richer context pack purposes.
- [ ] Add deterministic context assembly strategies per purpose.
- [ ] Add optional LLM evidence summaries.
- [ ] Cache evidence summaries for unchanged context packs.
- [ ] Record summary token usage and cost telemetry.

## Phase 7: Portfolio Polish

- [ ] Add GitHub Actions CI.
- [ ] Add README screenshot.
- [ ] Add a public demo-ready customer triage example.
- [ ] Add seeded sample data for local demo mode.
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

The UI is not yet a full EDD workflow. It does not yet edit artifact sections,
run scenarios, evaluate runs, create gates, link Langfuse traces, or persist to
Postgres.
