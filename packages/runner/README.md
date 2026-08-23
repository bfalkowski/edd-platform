# packages/runner

Execution harness for runnable agent implementations.

The runner does not own tool governance. The platform owns tool
definitions, approval status, and agent allowlists; the runner adapts
approved platform tools into LangChain/LangGraph tool primitives, executes
the graph, and returns tool calls, tool results, traces, and final responses
as evidence.

Current slice:

- `run_mock_agent` executes a deterministic scenario — no model-provider
  keys required, used by CI and tests.
- Live execution calls Anthropic directly (`AnthropicRunnerConfig`) via a
  LangChain/LangGraph-backed agent loop when tools are involved. The default
  live model is Claude Haiku; override with `EDD_ANTHROPIC_MODEL`.
  `ANTHROPIC_API_KEY` is required for live runs.
- Live execution can instead target Azure AI Foundry Agent Service
  (`FoundryRunnerConfig`, `run_foundry_agent`), selected per-run via
  `provider: "foundry"` on the run request. Each run creates a scratch
  Foundry agent, drives one thread through to completion (resolving any
  `requires_action` function-tool calls against the same approved tool set
  used by the Anthropic path), and deletes the agent afterward so runs stay
  stateless. Requires `AZURE_AI_FOUNDRY_PROJECT_ENDPOINT` and
  `EDD_FOUNDRY_MODEL` (a deployed model/agent name in the target Foundry
  project); auth uses `azure-identity`'s `DefaultAzureCredential`.
- `get_weather`, `lookup_event_schedule`, `lookup_event_result`, and
  `browse_webpage` are available as deterministic/live tool fixtures.
- The API stores the result as a `RUN_RESULT` artifact, plus a `TRACE_REF`
  artifact when Langfuse is configured.

Langfuse tracing is opt-in for live mode and defaults to the local Langfuse
Docker stack. Start `./scripts/dev_langfuse.sh` from the repo root, or set
`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL`
manually. The runner wraps live calls in a Langfuse agent observation and
returns the trace id/URL so the platform can link a `TRACE_REF` artifact.
