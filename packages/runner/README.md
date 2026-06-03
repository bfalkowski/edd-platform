# packages/runner

Execution harness for runnable agent implementations.

This package is the clean successor to the useful Agent Lab runtime ideas. It
should run LangGraph agents, mock tools, scenarios, and deterministic eval
loops, then return evidence to the platform API.

Current slice:

- `run_mock_agent` executes an agent-shaped deterministic scenario.
- The API stores the result as a `RUN_RESULT` artifact.
- No model-provider keys are required.

The next runner milestone is replacing the deterministic mock body with a
LangGraph graph while keeping the same platform evidence contract.
