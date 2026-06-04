# packages/runner

Execution harness for runnable agent implementations.

This package is the clean successor to the useful Agent Lab runtime ideas. It
should run LangGraph agents, mock tools, scenarios, and deterministic eval
loops, then return evidence to the platform API.

The runner should not own tool governance. The platform owns tool definitions,
approval status, and agent allowlists. The runner adapts approved platform tools
into LangChain/LangGraph tool primitives, executes the graph, and returns tool
calls, tool results, traces, and final responses as evidence.

Current slice:

- `run_mock_agent` executes an agent-shaped deterministic scenario.
- `run_openai_agent` executes the same scenario through a LangChain/LangGraph
  agent when approved tools are available, falling back to a direct OpenAI
  Responses API call when no tools are allowed.
- `get_weather` is available as a deterministic local LangChain tool fixture.
- The API stores the result as a `RUN_RESULT` artifact.
- No model-provider keys are required for mock mode or CI.

Live mode is opt-in. Set `OPENAI_API_KEY` before starting the API. The default
live model is `gpt-5-nano`; override it with `EDD_OPENAI_MODEL`.

Langfuse tracing is opt-in for live mode and is expected to use the local
Langfuse Docker stack by default. Start `./scripts/dev_langfuse.sh` from the
repo root, or set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and
`LANGFUSE_BASE_URL` manually before starting the API. The runner wraps live
calls in a Langfuse agent observation and returns the trace id and URL so the
platform can create a linked `TRACE_REF` artifact.

The next runner milestone is making tool assignment editable in the platform UI
and splitting tool-call records into first-class evidence artifacts.
