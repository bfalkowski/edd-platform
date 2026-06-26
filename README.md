# EDD Platform

EDD Platform is a product workspace for designing, running, evaluating, fixing,
comparing, and promoting AI agents with durable evidence.

The platform is not a generic chat UI and not a trace browser. It is an evidence
system for improving agent behavior. Users define explicit scenarios and eval
contracts, run agent versions against them, inspect failures, propose bounded
fixes, compare candidates, and make promotion decisions from linked artifacts.

The platform starts from a simple belief: reliable AI products improve when
teams study real behavior, name recurring failure modes, measure those failures,
and make design changes from evidence instead of vibes.

EDD Platform turns agent traces into failure modes, failure modes into evals,
evals into bounded fixes, and fixes into evidence-backed promotion decisions.

![EDD Platform showing the seeded Sentiment Observer agent](./docs/assets/sentiment-observer-agent.png)

## Demo Flow

The seeded Sentiment Observer demo shows more than an agent designer. It walks
through the EDD loop: select a conversation test, run the current agent version,
judge the output, and keep every decision tied to durable evidence.

![EDD Platform Proof loop showing a Sentiment Observer conversation test](./docs/assets/sentiment-observer-proof-loop.png)

The Evidence tab collects the proof artifacts for the selected agent: trace
refs, success criteria, agent versions, and agent designs. This keeps the
platform decision visible even when the raw trace lives in Langfuse.

![EDD Platform Evidence tab showing linked proof artifacts for Sentiment Observer](./docs/assets/sentiment-observer-evidence.png)

The live demo also links platform evidence to Langfuse observability. Agent
runs, tool spans, and live judge calls appear on the same trace so a reviewer
can see both the product decision and the model evidence behind it.

![Langfuse trace showing the live judge generation for a Sentiment Observer eval](./docs/assets/langfuse-live-judge-trace.png)

## Evaluation-Driven Design Loop

EDD Platform operationalizes an evidence loop for improving AI agents:

```text
Observe -> Analyze -> Measure -> Improve -> Compare -> Gate
```

Observe: produce or import traces from agent runs, local runners, Langfuse, or
other observability systems.

Analyze: inspect representative runs and traces to understand how the agent
fails. Human review notes, failure packets, and emerging failure modes capture
the first evidence of what needs to improve.

Measure: turn recurring failure modes into eval contracts, deterministic
checks, rubric dimensions, or LLM-as-judge prompts. The goal is to quantify
failure rates, severity, and regression risk.

Improve: propose bounded prompt, tool, retrieval, or workflow changes linked to
specific failures.

Compare: rerun baseline and candidate versions against the same scenarios and
eval contracts, then compare scores, fixed failures, remaining failures, and
new regressions.

Gate: promote only when the evidence supports the decision.

In short: traces reveal failure modes; failure modes become evals; evals drive
fixes; fixes are promoted only when comparison and gate evidence support them.

## Product Thesis

Most AI eval tooling starts with scores. EDD starts one step earlier. Before a
team can know what to measure, it needs to understand how the agent fails.
EDD Platform helps teams move from qualitative evidence to quantitative
evaluation:

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
  -> EvidenceContext
```

The canonical product language is in
[`docs/PRODUCT_SPINE.md`](docs/PRODUCT_SPINE.md).

Public-facing documentation should be published from
[bfalkowski/edd-platform-docs](https://github.com/bfalkowski/edd-platform-docs).
The initial migration checklist is tracked in
[`docs/PUBLIC_DOCS_REPO.md`](docs/PUBLIC_DOCS_REPO.md).

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
2. Define a test case backed by a scenario and eval contract.
3. Run a baseline version in mock or live mode.
4. Evaluate the run with deterministic checks or an optional live judge.
5. Store `RUN_RESULT`, `EVAL_RESULT`, and `JUDGE_OUTPUT` evidence.
6. Create failure packets when checks fail.
7. Add review notes that open-code failure modes before proposing fixes.
8. Propose bounded fixes linked to failures.
9. Create candidate agent versions.
10. Run and evaluate candidates against the same contract.
11. Compare baseline and candidate evidence.
12. Create gate definitions and gate decisions.
13. Assemble evidence context packs for the proof loop.

The platform also supports:

- project-scoped persistence through Postgres;
- platform-owned tool definitions, approval status, and agent allowlists;
- built-in and mock tool execution through the runner;
- first-class tool call and tool result evidence;
- single-turn, conversation, and trace-replay test case shapes;
- optional OpenAI live agent runs and live judge calls;
- optional evidence summaries through the API;
- optional Langfuse trace refs, generation observations, scenario dataset refs,
  and eval score refs;
- optional Langfuse comment mirroring for review notes on linked traces or
  prompts;
- deterministic seeded demo data for public and local walkthroughs,
  including a ready-to-run Sentiment Observer agent with its monitoring tools
  enabled.

Langfuse remains observability and experiment infrastructure. Platform artifacts
remain the source of truth.

The current proof loop is strongest in the Measure -> Improve -> Compare ->
Gate portion of the workflow. The planned error-analysis workflow strengthens
the front of the loop by making human trace review, open-coded notes,
failure-mode taxonomy, and failure-mode regression first-class platform
concepts.

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

### Langfuse Boundary

Langfuse is treated as observability and experiment infrastructure. It can
provide traces, spans, datasets, scores, and deep links into raw execution
detail.

EDD Platform owns the evaluation-driven workflow:

```text
trace evidence
  -> failure packets
  -> failure modes
  -> eval contracts
  -> fix proposals
  -> comparisons
  -> gate decisions
  -> evidence context
```

The normal workflow should keep users in the EDD Platform UI. Langfuse is a
source of evidence and a deep-link target when raw trace detail is needed, not
the primary workspace for error analysis, fix proposals, comparisons, or
promotion decisions.

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

Seed the Sentiment Observer conversation-monitoring example:

```bash
python scripts/seed_sentiment_observer_demo.py
```

See `examples/customer-triage` and `examples/sentiment-observer` for the demo
walkthroughs.

Run the live OpenAI plus local Langfuse smoke script after
`./scripts/dev_langfuse.sh` is running. If you use `.env.local`, load it into
your shell first:

```bash
set -a; source .env.local; set +a
python scripts/live_langfuse_e2e.py
```

The script prints the platform run id, eval result id, score, Langfuse trace id,
and Langfuse trace URL.
For raw OpenAI Responses calls, the linked Langfuse trace should include an
`openai.responses` generation observation under the agent run observation.

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
- Error analysis is currently represented through failure packets, review
  notes, evidence artifacts, and an Error analysis tab placeholder. A dedicated
  trace review queue, open-coded human notes, failure-mode taxonomy, and
  failure-mode regression views are planned.
- Langfuse trace references, dataset refs, score refs, and comment refs exist
  as integration points. Production-grade trace import is still planned.
