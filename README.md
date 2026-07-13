# EDD Platform

EDD Platform is a product workspace for designing, running, evaluating, and
improving AI agents with durable evidence.

The platform is not a generic chat UI and not a trace browser. It is an
evidence system for improving agent behavior. Teams define explicit test cases
and eval contracts, run agent versions against them, review traces for failure
patterns, name recurring failure modes, and make promotion decisions from linked
artifacts — not from intuition.

EDD Platform turns agent traces into failure modes, failure modes into evals,
evals into bounded fixes, and fixes into evidence-backed promotion decisions.

## Live demo: syncing a Langfuse trace comment into the app

![Commenting on a trace in Langfuse and syncing it back into the platform as evidence](./docs/assets/error-analysis-langfuse-sync-demo.gif)

1. Open the trace for a failed run in Langfuse.
2. Add a comment noting what went wrong.
3. Back in the app, click "Sync Langfuse comments."
4. The comment appears as an annotation on that trace, ready to be assigned a
   failure mode.

## The workspace

Each agent gets five tabs: **Agent**, **Proof loop**, **Error analysis**,
**Evidence**, and **Readiness**.

### Agent tab

Define the agent's name, core instruction, and enabled tools. The warm card
layout keeps the design surface clean against the sidebar.

![EDD Platform Agent tab showing the Sentiment Observer agent design](./docs/assets/sentiment-observer-agent.webp)

### Proof loop tab

Select a saved test, run the agent live against Anthropic, evaluate the output,
and iterate. The proof loop shows the selected test (scenario input, judge
method, latest result) and a next-action card that guides the evaluator toward
the right step — run, fix, compare, or done.

![EDD Platform Proof loop showing a passed Sentiment Observer test](./docs/assets/sentiment-observer-proof-loop.webp)

### Error analysis tab — 4-step wizard

Error analysis is a guided 4-step wizard for turning raw traces into a named
failure mode taxonomy:

1. **Build review set** — pull in live runs as a corpus of traces to review.
   A data table shows each item with its source, status, and note count.

![EDD Platform Error analysis step 1 — build review set table](./docs/assets/error-analysis-build-corpus.webp)

2. **Review & code** — open each trace in Langfuse and add comments there.
   Reviewers annotate directly in Langfuse — not in a shallow copy inside the
   platform.

![Langfuse trace with live judge span and tool calls for Sentiment Observer](./docs/assets/langfuse-live-judge-trace.webp)

   Then sync those comments back into the platform with one click. Synced
   comments appear inline per trace with an "Assign failure mode" dropdown.

![EDD Platform Error analysis step 2 — synced Langfuse comments with failure mode assignment](./docs/assets/error-analysis-review-code.webp)

3. **Confirm modes** — promote recurring annotations to named failure modes.
4. **Done** — the taxonomy is ready to inform test cases and fix proposals in
   the Proof loop.

## Evaluation-Driven Design Loop

```text
Observe -> Analyze -> Measure -> Improve -> Compare -> Gate
```

**Observe** — produce or import traces from live agent runs linked to Langfuse.

**Analyze** — review traces in Langfuse, add comments, sync them into the
platform, and name recurring failure modes through the Error analysis wizard.

**Measure** — turn failure modes into eval contracts: deterministic checks,
rubric dimensions, or LLM-as-judge prompts. The Proof loop runs these against
live Anthropic and stores `RUN_RESULT`, `EVAL_RESULT`, and `JUDGE_OUTPUT`
evidence.

**Improve** — propose bounded prompt, tool, or workflow changes linked to
specific failure packets.

**Compare** — rerun baseline and candidate versions against the same scenarios
and compare scores, fixed failures, and new regressions.

**Gate** — promote only when the evidence supports the decision.

## Product Thesis

Most AI eval tooling starts with scores. EDD starts one step earlier: before a
team can know what to measure, it needs to understand how the agent fails.

```text
review traces
  -> name failure modes
  -> encode eval contracts
  -> run repeatable checks
  -> propose bounded fixes
  -> compare versions
  -> gate promotion
```

This makes evaluation part of the design process, not just a dashboard after
the fact.

## Product Spine

```text
Project
  -> AgentDesign
  -> AgentVersion
  -> Scenario
  -> EvalContract
  -> Run
  -> EvalResult / JudgeOutput
  -> FailurePacket
  -> FixProposal
  -> Comparison
  -> GateDecision
  -> ReviewCorpus -> ReviewItem -> ReviewAnnotation -> FailureMode
  -> EvidenceContext
```

The canonical product language is in
[`docs/PRODUCT_SPINE.md`](docs/PRODUCT_SPINE.md).

## Repository Shape

```text
apps/web
  React product console (main.tsx, Wizard.tsx, styles.css)

apps/api
  FastAPI platform API — state, evidence, judges, gates, promotion,
  Langfuse comment sync

packages/runner
  Live runner layer for agent execution against Anthropic

packages/domain
  Shared product language and domain package scaffold

packages/langfuse-adapter
  Langfuse trace reference helpers
```

## What Works Now

**Agent design**
- Outcome-based drafting is the primary creation flow — see
  [Step 1 of the walkthrough](docs/HAPPY_PATH_WALKTHROUGH.md#step-1--describe-your-agent).
- Create and edit agent designs directly with name, core instruction, and
  enabled tools.
- Platform-owned tool definitions with approval status and agent allowlists.

**Proof loop**
- Define test cases backed by scenarios and eval contracts.
- Run agent versions live against Anthropic (all runs are live — no mock mode).
- Evaluate with deterministic checks (tool use, exact text, forbidden behavior)
  or a live rubric judge.
- Store `RUN_RESULT`, `EVAL_RESULT`, and `JUDGE_OUTPUT` evidence per run.
- Wizard guides: Describe → Review → Run → Name failure → Fix → Compare → Done.
- Eval check labels are human-readable (e.g. "Rubric judge", not
  `requires_output_1`).
- "Output looks fine — approve anyway" button skips the fix flow on close calls.

**Error analysis**
- 4-step wizard: Build review set → Review & code → Confirm modes → Done.
- Review set filters to live runs only (TRACE_REF, RUN_RESULT, EVAL_RESULT,
  JUDGE_OUTPUT artifact types; no `:mock` sources).
- Langfuse comment sync: `POST .../sync-langfuse-comments` pulls trace comments
  into `ReviewAnnotation` records, deduped by `langfuse_comment_id`.
- Inline failure mode assignment per synced comment in step 2.
- Dismissible intro card explains the wizard purpose (persisted via
  localStorage).

**Evidence**
- Evidence tab collects all proof artifacts: trace refs, success criteria,
  agent versions, run outputs, eval results.
- Trace references include "Open trace" links into Langfuse when a URL exists.

**Langfuse integration**
- Live runs create linked `TRACE_REF` artifacts with Langfuse URLs.
- Judge calls appear as generation observations inside the agent run span.
- Comment sync: Langfuse comments on traces flow back into the platform as
  ReviewAnnotations.
- Optional: dataset sync, score sync, comment mirror (opt-in via env flags).

**Persistence**
- Project-scoped state through Postgres.
- Seeded demo data for local walkthroughs (Sentiment Observer, Customer Triage).

## Local Development

Install web dependencies once:

```bash
cd apps/web
npm install
```

Start local Postgres and the app:

```bash
docker compose up -d postgres
./scripts/dev.sh
```

The API runs on `http://127.0.0.1:8001`. The React console runs on Vite's
reported local URL, usually `http://localhost:5173`.

Default database:

```text
postgresql://edd_platform:edd_platform@127.0.0.1:15432/edd_platform
```

Set `EDD_PLATFORM_DATABASE_URL` to use a different Postgres database.

## Live Anthropic Runs

All agent runs use live Anthropic. Put your API key in `.env.local`:

```bash
cp .env.example .env.local
```

Set:

```text
ANTHROPIC_API_KEY=...
```

Then start:

```bash
./scripts/dev.sh
```

The default model is Claude Haiku. Override with `EDD_ANTHROPIC_MODEL`.

## Langfuse

Langfuse is required for error analysis. Start Langfuse and the app together:

```bash
./scripts/dev_langfuse.sh
```

Langfuse runs at `http://localhost:3001`:

```text
admin@local.dev / local-demo-password
LANGFUSE_PUBLIC_KEY=pk-lf-local-demo
LANGFUSE_SECRET_KEY=sk-lf-local-demo
```

### Langfuse Boundary

Langfuse is the review surface for traces. EDD Platform is the workflow layer:

```text
Langfuse trace comments
  -> ReviewAnnotations (synced by platform)
  -> FailureModes (named by evaluator)
  -> EvalContracts (encoded from modes)
  -> FixProposals (linked to failure packets)
  -> GateDecisions (backed by comparison evidence)
```

Langfuse is a source of evidence and a deep-link target. It is not the primary
workspace for failure mode taxonomy, fix proposals, comparisons, or promotion.

When Langfuse credentials are configured:

- live runs create linked `TRACE_REF` artifacts with trace URLs;
- `EDD_PLATFORM_LANGFUSE_DATASET_SYNC=live` creates Langfuse datasets for
  scenarios;
- `EDD_PLATFORM_LANGFUSE_SCORE_SYNC=live` writes eval pass-rate scores;
- `EDD_PLATFORM_LANGFUSE_COMMENT_SYNC=live` mirrors platform review notes to
  Langfuse comments.

## Verification

Run all local checks:

```bash
./scripts/test.sh
```

This runs: secret scan, API tests, Langfuse adapter tests, OpenAPI contract
lint, and React build.

Seed demo data after the app is running:

```bash
python scripts/seed_sentiment_observer_demo.py
python scripts/seed_customer_triage_demo.py
```

Run the live Anthropic + Langfuse smoke test:

```bash
set -a; source .env.local; set +a
python scripts/live_langfuse_e2e.py
```

## Canonical Docs

- [`docs/HAPPY_PATH_WALKTHROUGH.md`](docs/HAPPY_PATH_WALKTHROUGH.md) — manual
  proof-loop smoke script
- [`docs/design/FRONTEND_GUIDE.md`](docs/design/FRONTEND_GUIDE.md) — UI
  patterns, color tokens, wizard rules, Langfuse boundary
- [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) — generated OpenAPI contract
  and contract-first rules
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — architecture diagrams
- [`docs/PRODUCT_SPINE.md`](docs/PRODUCT_SPINE.md) — canonical product language
- [`docs/hld/`](docs/hld) — high-level design docs
- [`docs/engineering/AI_AGENT_DEVELOPMENT.md`](docs/engineering/AI_AGENT_DEVELOPMENT.md)
  — AI-assisted development guardrails

## Current Limits

- Tool adapters for `http`, `mcp`, and `python` implementation kinds are
  planned but not yet wired.
- Evidence summaries are available through the API; UI display is planned.
- Multiple test cases per agent (regression across N scenarios) is planned.
- Score delta / trend across iterations (beyond pass/fail) is planned.
