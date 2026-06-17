# Architecture

EDD Platform is a single product repo for evaluation-driven agent development.

The product has one React console, one platform API, shared domain objects, a
LangGraph-capable runner layer, and optional Langfuse trace evidence.

Planning companions:

- [`ARCHITECTURE_READINESS_BRIEF.md`](ARCHITECTURE_READINESS_BRIEF.md) summarizes users, requirements, constraints, and the system shape.
- [`REQUIREMENTS_AND_CONSTRAINTS.md`](REQUIREMENTS_AND_CONSTRAINTS.md) defines functional and non-functional requirements.
- [`SYSTEM_TRADEOFFS.md`](SYSTEM_TRADEOFFS.md) records the main architecture tradeoffs.
- [`OPERABILITY_AND_FAILURE_MODES.md`](OPERABILITY_AND_FAILURE_MODES.md) describes expected failure behavior and recovery paths.
- [`ARCHITECTURE_DEEP_DIVES.md`](ARCHITECTURE_DEEP_DIVES.md) expands the eval pipeline, tool governance, evidence context, and readiness flows.

## System Context

```mermaid
flowchart LR
  User["User / evaluator / researcher"]
  UI["React console<br/>apps/web"]
  API["Platform API<br/>apps/api"]
  Store["Project + evidence store<br/>projects, designs, artifacts, links, runs, evals, gates"]
  Tools["Tool governance<br/>definitions, approval, allowlists"]
  Runner["Runner package<br/>packages/runner"]
  LangGraph["LangChain / LangGraph<br/>agent + tool loop"]
  Langfuse["Langfuse<br/>trace observability"]

  User --> UI
  UI --> API
  API --> Store
  API --> Tools
  API --> Runner
  Tools --> Runner
  Runner --> LangGraph
  Runner --> API
  API --> Langfuse
  Langfuse --> API
```

## Product Shape

```mermaid
flowchart TB
  subgraph Repo["edd-platform"]
    subgraph Apps["apps"]
      Web["web<br/>React product console"]
      Api["api<br/>FastAPI platform backend"]
    end

    subgraph Packages["packages"]
      Domain["domain<br/>shared vocabulary"]
      RunnerPkg["runner<br/>LangGraph execution harness"]
      LangfuseAdapter["langfuse-adapter<br/>trace evidence integration"]
    end

    subgraph Examples["examples"]
      EvalScratch["eval-from-scratch"]
      Regression["regression-diagnosis"]
      Flaky["flaky-eval-pipeline"]
      Capability["research-capability-definition"]
    end
  end

  Web --> Api
  Api --> Domain
  Api --> RunnerPkg
  Api --> LangfuseAdapter
  Examples --> Api
  Examples --> RunnerPkg
```

## Shared Backend Model

Every example project uses the same backend model. The examples are seeded
projects, not separate apps.

```mermaid
flowchart TB
  Project["Project"]
  AgentDesign["AgentDesign"]
  Artifact["Artifact"]
  ArtifactLink["ArtifactLink"]
  ContextPack["ContextPack"]
  Run["RunResult"]
  Eval["EvalResult"]
  Failure["FailurePacket"]
  Gate["GateDecision"]
  Trace["TraceRef"]

  Project --> AgentDesign
  Project --> Artifact
  AgentDesign --> Artifact
  Artifact --> ArtifactLink
  ArtifactLink --> Artifact
  Artifact --> ContextPack
  Run --> Artifact
  Eval --> Artifact
  Failure --> Artifact
  Gate --> Artifact
  Trace --> Artifact
```

## Eval-Driven Workflow

```mermaid
sequenceDiagram
  participant U as User
  participant W as React Console
  participant A as Platform API
  participant R as LangGraph Runner
  participant S as Evidence Store
  participant L as Langfuse

  U->>W: Create agent design from intent
  W->>A: POST project agent design
  A->>S: Store AgentDesign + AGENT_DESIGN artifact
  A-->>W: Return design and artifact

  U->>W: Run test case
  W->>A: Request run
  A->>R: Execute graph with scenario
  R->>L: Record live agent trace and model generation when configured
  R-->>A: Return response, tool events, trace metadata
  A->>S: Store RUN_RESULT artifact
  A->>S: Store TRACE_REF artifact when trace metadata exists

  U->>W: Evaluate
  W->>A: Request eval
  A->>S: Load judge prompt, gates, run evidence
  A->>S: Store EVAL_RESULT and FAILURE_PACKET artifacts
  A-->>W: Return evidence context

  W->>A: Build context pack
  A->>S: Retrieve and assemble linked artifacts
  A-->>W: Return ContextPack
```

## Runtime Modes

```mermaid
flowchart LR
  Request["Run or evaluate request"]
  Mode{"Runtime mode"}
  Mock["mock<br/>deterministic CI/local"]
  Local["local<br/>developer provider experiments"]
  Platform["platform<br/>canonical live model routing"]
  Auto["auto<br/>platform/live when configured,<br/>otherwise mock"]
  Evidence["Evidence artifacts"]

  Request --> Mode
  Mode --> Mock
  Mode --> Local
  Mode --> Platform
  Mode --> Auto
  Mock --> Evidence
  Local --> Evidence
  Platform --> Evidence
  Auto --> Evidence
```

CI must pass without model-provider credentials. Live model behavior is opt-in.

## Tool Governance Boundary

Tool orchestration should use existing agent framework primitives instead of a
custom tool loop. LangChain/LangGraph should own the mechanics of model calls,
tool-call messages, tool execution, and continuing the graph until a final
response is produced.

The platform still owns governance:

- tool definitions and schemas
- tool approval status
- which tools are allowed for each agent design
- tool-call and tool-result evidence
- evals that judge tool selection and grounded use

The runner is the adapter between those responsibilities. It converts approved
platform tools into LangChain/LangGraph tools for a run, executes the graph, and
returns tool events and final responses to the platform as evidence artifacts.

## Example Projects

```mermaid
flowchart TB
  Platform["EDD Platform"]

  Eval["Eval From Scratch<br/>define task, dataset, scoring, dashboard"]
  Regression["Regression Diagnosis<br/>model vs harness vs data vs infra"]
  Flaky["Flaky Eval Pipeline<br/>retries, observability, deterministic replay"]
  Research["Capability Definition<br/>turn qualitative good into measurable artifacts"]

  Platform --> Eval
  Platform --> Regression
  Platform --> Flaky
  Platform --> Research
```

Each example should exercise the same platform services:

- project-scoped state
- artifacts
- artifact links
- context packs
- runner evidence
- eval results
- failure packets
- gates
- trace references

## Responsibility Boundaries

| Area | Responsibility |
|---|---|
| React console | product UI, review panels, evidence views, local activity |
| Platform API | product state, artifacts, links, context packs, judges, gates |
| Domain package | shared object vocabulary and schemas |
| Runner package | LangChain/LangGraph execution, platform-approved tools, scenarios, replay |
| Langfuse adapter | trace references and observability integration |
| Examples | seeded demo projects using the shared backend |

## Requirements Summary

The architecture is shaped by three primary users:

- AI engineers who need to prove that a candidate agent version improved;
- evaluation leads who need explicit expectations, failures, and gates;
- platform owners who need deterministic defaults, tool governance, and
  provider-cost control.

The main functional requirements are project-scoped agent designs, scenarios,
eval contracts, runs, eval results, failure packets, fix proposals, comparisons,
gate decisions, and evidence context packs.

The main non-functional requirements are deterministic local/CI execution,
traceable evidence, governed tool use, optional live-provider calls, bounded
judge cost, and reviewable promotion decisions.

## Consistency Model

The platform favors durable evidence consistency over optimistic workflow
shortcuts.

A run, eval, comparison, or gate decision should not be treated as complete
unless the corresponding platform record and supporting artifacts have been
written. External trace systems can enrich evidence, but they do not determine
the source-of-truth state.

This means a Langfuse sync failure can leave a run usable, while a failed
platform evidence write should leave the operation incomplete.

## Failure Posture

The default recovery strategy is to preserve inspectable status and continue to
support deterministic workflows.

Examples:

- live provider failures should not break mock mode;
- Langfuse sync failures should not erase normalized platform evidence;
- invalid tool schemas should keep tools out of executable allowlists;
- candidate regressions should remain visible in comparisons;
- gate decisions should link to supporting evidence rather than infer readiness
  from the latest score.

See [`OPERABILITY_AND_FAILURE_MODES.md`](OPERABILITY_AND_FAILURE_MODES.md) for
the detailed failure-mode catalog.

## Tradeoff Summary

The most important design choices are:

- use artifacts and links as the common evidence surface;
- keep eval contracts as product data instead of hardcoded branches;
- run deterministic checks before optional LLM judges;
- keep tool definitions and allowlists platform-owned;
- treat Langfuse as observability, not product state;
- keep one monorepo while preserving package boundaries;
- start synchronous for product clarity, then move long-running work to workers
  when scale requires it.

See [`SYSTEM_TRADEOFFS.md`](SYSTEM_TRADEOFFS.md) for the full tradeoff record.

## Product Signal

The architecture is meant to show that the repo is not a one-off agent demo.

It is a reusable evaluation platform where multiple eval/research workflows use
the same backend, evidence model, runner boundary, and UI patterns.
