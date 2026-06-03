# Architecture

EDD Platform is a single product repo for evaluation-driven agent development.

The product has one React console, one platform API, shared domain objects, a
LangGraph-capable runner layer, and optional Langfuse trace evidence.

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

  U->>W: Run scenario
  W->>A: Request run
  A->>R: Execute graph with scenario
  R-->>A: Return response, tool events, trace metadata
  A->>S: Store RUN_RESULT artifact
  A->>L: Link trace when enabled

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
| Examples | seeded portfolio/demo projects using the shared backend |

## Portfolio Signal

The architecture is meant to show that the repo is not a one-off agent demo.

It is a reusable evaluation platform where multiple eval/research workflows use
the same backend, evidence model, runner boundary, and UI patterns.
