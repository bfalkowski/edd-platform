# EDD Platform

EDD Platform is a product workspace for designing, running, evaluating, fixing,
comparing, and promoting AI agents with durable evidence.

The platform is not a generic chat UI and not a trace browser. It is an evidence
system for improving agent behavior. Users define explicit scenarios and eval
contracts, run agent versions against them, inspect failures, propose bounded
fixes, compare candidates, and make promotion decisions from linked artifacts.

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
  -> EvidenceContext
```

The canonical product language is in
[`docs/PRODUCT_SPINE.md`](docs/PRODUCT_SPINE.md).

## Repository Shape

```text
apps/web
  React product console

apps/api
  FastAPI platform API for state, evidence, judges, gates, and promotion

packages/runner
  Deterministic and live runner layer for agent execution

packages/domain
  Shared product language and domain package scaffold

packages/langfuse-adapter
  Optional Langfuse trace reference helpers
```

## What Works Now

The current app supports the full eval-driven proof loop:

1. Create an agent design.
2. Define a scenario and eval contract.
3. Run a baseline version in mock or live mode.
4. Evaluate the run with deterministic checks or an optional live judge.
5. Store `RUN_RESULT`, `EVAL_RESULT`, and `JUDGE_OUTPUT` evidence.
6. Create failure packets when checks fail.
7. Propose bounded fixes linked to failures.
8. Create candidate agent versions.
9. Run and evaluate candidates against the same contract.
10. Compare baseline and candidate evidence.
11. Create gate definitions and gate decisions.
12. Assemble evidence context packs and optional evidence summaries.

The platform also supports:

- project-scoped persistence through Postgres;
- platform-owned tool definitions, approval status, and agent allowlists;
- built-in and mock tool execution through the runner;
- first-class tool call and tool result evidence;
- optional OpenAI live agent runs and live judge calls;
- optional Langfuse trace refs, scenario dataset refs, and eval score refs;
- deterministic seeded demo data for portfolio and local walkthroughs.

Langfuse remains observability and experiment infrastructure. Platform artifacts
remain the source of truth.

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

The API runs on:

```text
http://127.0.0.1:8001
```

The React console runs on Vite's reported local URL, usually:

```text
http://localhost:5173
```

By default, the API connects to:

```text
postgresql://edd_platform:edd_platform@127.0.0.1:15432/edd_platform
```

Set `EDD_PLATFORM_DATABASE_URL` to use a different Postgres database. Tests use
memory storage, so CI and local verification do not require a database service.

## Live Mode

Live agent runs and live judge calls are opt-in. Put secrets in `.env.local` or
`.env`, not in committed files:

```bash
cp .env.example .env.local
```

Set:

```text
OPENAI_API_KEY=...
EDD_OPENAI_MODEL=gpt-5-nano
```

Then start:

```bash
./scripts/dev.sh
```

## Langfuse

Local Langfuse is optional. If it is already running on
`http://localhost:3001`, `./scripts/dev.sh` uses the seeded local keys.

To start Langfuse and the app together:

```bash
./scripts/dev_langfuse.sh
```

Langfuse runs at `http://localhost:3001` with seeded local credentials:

```text
admin@local.dev / local-demo-password
LANGFUSE_PUBLIC_KEY=pk-lf-local-demo
LANGFUSE_SECRET_KEY=sk-lf-local-demo
```

When Langfuse credentials are configured:

- live project runs can create linked `TRACE_REF` artifacts;
- scenario creation keeps planned dataset refs by default;
- `EDD_PLATFORM_LANGFUSE_DATASET_SYNC=live` creates Langfuse datasets and
  dataset items for scenarios;
- `EDD_PLATFORM_LANGFUSE_SCORE_SYNC=live` writes eval pass-rate scores for
  live run evaluations and stores score refs on eval and judge artifacts.
- `EDD_PLATFORM_LANGFUSE_COMMENT_SYNC=live` mirrors platform review notes to
  Langfuse comments on linked traces or prompts.

Langfuse dataset, score, and comment writes are explicit opt-in paths.
Deterministic local and CI behavior do not require Langfuse credentials.

Langfuse comments are lightweight trace or prompt notes. Annotation queues are
separate structured human-evaluation workflows and are not part of the default
comment sync path.

## Verification

Run all local checks:

```bash
./scripts/test.sh
```

This runs:

- secret scan;
- API tests;
- Langfuse adapter tests;
- OpenAPI contract lint;
- React build.

Seed deterministic demo data after the app is running:

```bash
python scripts/seed_customer_triage_demo.py
```

Run the live OpenAI plus local Langfuse smoke script after
`./scripts/dev_langfuse.sh` is running. If you use `.env.local`, load it into
your shell first:

```bash
set -a; source .env.local; set +a
python scripts/live_langfuse_e2e.py
```

The script prints the platform run id, eval result id, score, Langfuse trace id,
and Langfuse trace URL.

## Canonical Docs

- [`docs/HAPPY_PATH_WALKTHROUGH.md`](docs/HAPPY_PATH_WALKTHROUGH.md) is the
  manual proof-loop smoke script.
- [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) explains the generated OpenAPI
  contract and contract-first rules.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) contains architecture diagrams.
- [`docs/WORK_PLAN.md`](docs/WORK_PLAN.md) tracks active implementation
  milestones.
- [`docs/HLD_COVERAGE_MATRIX.md`](docs/HLD_COVERAGE_MATRIX.md) tracks HLD
  coverage and gaps.
- [`docs/hld/`](docs/hld) contains high-level design docs.
- [`docs/design/FRONTEND_GUIDE.md`](docs/design/FRONTEND_GUIDE.md) defines
  frontend conventions.
- [`docs/engineering/AI_AGENT_DEVELOPMENT.md`](docs/engineering/AI_AGENT_DEVELOPMENT.md)
  defines AI-assisted development guardrails.

## Current Limits

- Tool definitions exist, but adapters for `http`, `mcp`, and `python`
  implementation kinds are still planned.
- Evidence summaries are available through the API, but UI display is still
  planned.
- README screenshot and external public docs are still portfolio-polish tasks.
