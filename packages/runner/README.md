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
- `run_openai_agent` executes the same scenario through OpenAI's Responses API.
- The API stores the result as a `RUN_RESULT` artifact.
- No model-provider keys are required for mock mode or CI.

Live mode is opt-in. Set `OPENAI_API_KEY` before starting the API. The default
live model is `gpt-5-nano`; override it with `EDD_OPENAI_MODEL`.

The next runner milestone is replacing the deterministic mock body with a
LangGraph graph while keeping the same platform evidence contract and
platform-governed tool allowlist.
