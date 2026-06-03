"""Runner package for EDD Platform."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from pydantic import BaseModel


class RunnerAgentDesign(BaseModel):
    id: str
    name: str
    intent: str
    allowed_tool_names: List[str] = []


class RunnerScenario(BaseModel):
    input: str


class RunnerToolCall(BaseModel):
    name: str
    output: str


class RunnerToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_description: str
    implementation_key: str
    status: str


class RunnerResult(BaseModel):
    id: str
    agent_design_id: str
    mode: str
    scenario_input: str
    response: str
    tool_calls: List[RunnerToolCall]
    evidence: List[str]
    created_at: datetime


@dataclass(frozen=True)
class OpenAIRunnerConfig:
    api_key: str
    model: str = "gpt-5-nano"
    base_url: str = "https://api.openai.com/v1"


def run_mock_agent(agent: RunnerAgentDesign, scenario: RunnerScenario) -> RunnerResult:
    """Run a deterministic agent-shaped scenario without provider credentials."""
    tool_calls = [
        RunnerToolCall(
            name="collect_design_intent",
            output=agent.intent,
        ),
        RunnerToolCall(
            name="classify_request",
            output="scenario_requires_grounded_next_action",
        ),
    ]
    response = (
        f"{agent.name} reviewed the scenario and stayed within its design intent. "
        f"It should gather relevant evidence, state assumptions, and recommend a safe next action. "
        f"Scenario: {scenario.input}"
    )
    return RunnerResult(
        id=f"run_{uuid4().hex[:12]}",
        agent_design_id=agent.id,
        mode="mock",
        scenario_input=scenario.input,
        response=response,
        tool_calls=tool_calls,
        evidence=[
            "Used agent design intent as the target behavior.",
            "Used deterministic mock classification instead of a model provider.",
        ],
        created_at=datetime.now(timezone.utc),
    )


def get_weather(zip_code: str) -> str:
    """Return deterministic weather data for local EDD tool-calling runs."""
    normalized = zip_code.strip()
    if normalized == "06511":
        return "Current weather for 06511 New Haven, CT: 41°F and cloudy."
    return f"Current weather for {normalized}: 55°F and clear. Source: deterministic local fixture."


def build_langchain_tools(tool_definitions: List[RunnerToolDefinition]):
    try:
        from langchain_core.tools import tool
    except ImportError as exc:
        raise RuntimeError("LangChain tools require langchain-core to be installed.") from exc

    tools = []
    for definition in tool_definitions:
        if definition.status != "approved":
            continue
        if definition.implementation_key == "local_weather_fixture":

            @tool("get_weather")
            def weather_tool(zip_code: str) -> str:
                """Get current weather for a US ZIP code."""
                return get_weather(zip_code)

            tools.append(weather_tool)
    return tools


def openai_config_from_env() -> OpenAIRunnerConfig:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for live OpenAI runs.")
    return OpenAIRunnerConfig(
        api_key=api_key,
        model=os.environ.get("EDD_OPENAI_MODEL", "gpt-5-nano").strip() or "gpt-5-nano",
        base_url=os.environ.get("EDD_OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
    )


def collect_text_values(value) -> List[str]:
    if isinstance(value, dict):
        values: List[str] = []
        for key, child in value.items():
            if key in {"text", "output_text"} and isinstance(child, str):
                values.append(child)
            else:
                values.extend(collect_text_values(child))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(collect_text_values(item))
        return values
    return []


def extract_response_text(payload: dict) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    return "\n".join(collect_text_values(payload.get("output", []))).strip()


def describe_empty_response(payload: dict) -> str:
    status = payload.get("status")
    incomplete_details = payload.get("incomplete_details")
    if status == "incomplete" and isinstance(incomplete_details, dict):
        reason = incomplete_details.get("reason", "unknown")
        return f"OpenAI response was incomplete: {reason}."
    output_types = [
        item.get("type")
        for item in payload.get("output", [])
        if isinstance(item, dict) and isinstance(item.get("type"), str)
    ]
    if output_types:
        return f"OpenAI response did not include output text. Output types: {', '.join(output_types)}."
    return "OpenAI response did not include output text."


def run_openai_agent(
    agent: RunnerAgentDesign,
    scenario: RunnerScenario,
    config: OpenAIRunnerConfig,
    tool_definitions: List[RunnerToolDefinition] | None = None,
) -> RunnerResult:
    """Run a scenario through a LangGraph-backed LangChain agent."""
    instructions = (
        "You are the candidate agent being designed in an eval-driven workflow. "
        "Stay inside the design intent, gather or cite relevant evidence from the scenario, "
        "state assumptions clearly, and recommend a safe next action."
    )
    active_tools = build_langchain_tools(tool_definitions or [])
    if active_tools:
        return run_langchain_agent(agent, scenario, config, instructions, active_tools)

    body = {
        "model": config.model,
        "reasoning": {"effort": "minimal"},
        "text": {"verbosity": "low"},
        "input": [
            {
                "role": "system",
                "content": f"{instructions}\n\nAgent name: {agent.name}\nDesign intent: {agent.intent}",
            },
            {
                "role": "user",
                "content": scenario.input,
            },
        ],
        "max_output_tokens": 2000,
    }
    request = Request(
        f"{config.base_url}/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI request failed with status {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"OpenAI request failed: {exc.reason}") from exc

    response_text = extract_response_text(payload)
    if not response_text:
        raise RuntimeError(describe_empty_response(payload))

    return RunnerResult(
        id=f"run_{uuid4().hex[:12]}",
        agent_design_id=agent.id,
        mode="live",
        scenario_input=scenario.input,
        response=response_text,
        tool_calls=[
            RunnerToolCall(
                name="openai.responses",
                output=config.model,
            )
        ],
        evidence=[
            f"Used OpenAI Responses API model {config.model}.",
            "Live provider run; output should be evaluated before promotion.",
        ],
        created_at=datetime.now(timezone.utc),
    )


def message_text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(collect_text_values(content))
    return str(content)


def run_langchain_agent(
    agent: RunnerAgentDesign,
    scenario: RunnerScenario,
    config: OpenAIRunnerConfig,
    instructions: str,
    tools,
) -> RunnerResult:
    try:
        from langchain.agents import create_agent
    except ImportError as exc:
        raise RuntimeError("LangChain agent execution requires langchain to be installed.") from exc

    graph = create_agent(
        model=f"openai:{config.model}",
        tools=tools,
        system_prompt=(
            f"{instructions}\n\n"
            f"Agent name: {agent.name}\n"
            f"Design intent: {agent.intent}\n"
            f"Allowed tools: {', '.join(agent.allowed_tool_names) or 'none'}"
        ),
    )
    result = graph.invoke({"messages": [{"role": "user", "content": scenario.input}]})
    messages = result.get("messages", [])
    response_text = ""
    tool_calls: List[RunnerToolCall] = []

    for message in messages:
        message_type = getattr(message, "type", "")
        if message_type == "tool":
            tool_calls.append(
                RunnerToolCall(
                    name=getattr(message, "name", None) or "tool",
                    output=message_text(message),
                )
            )
        elif message_type in {"ai", "assistant"}:
            text = message_text(message).strip()
            if text:
                response_text = text

    if not response_text:
        raise RuntimeError("LangGraph agent did not return a final response.")

    return RunnerResult(
        id=f"run_{uuid4().hex[:12]}",
        agent_design_id=agent.id,
        mode="live",
        scenario_input=scenario.input,
        response=response_text,
        tool_calls=tool_calls or [
            RunnerToolCall(
                name="langchain.agent",
                output=config.model,
            )
        ],
        evidence=[
            f"Used LangChain/LangGraph agent with OpenAI model {config.model}.",
            f"Allowed tools: {', '.join(agent.allowed_tool_names) or 'none'}.",
        ],
        created_at=datetime.now(timezone.utc),
    )


__all__ = [
    "OpenAIRunnerConfig",
    "RunnerAgentDesign",
    "RunnerResult",
    "RunnerScenario",
    "RunnerToolCall",
    "RunnerToolDefinition",
    "build_langchain_tools",
    "openai_config_from_env",
    "run_mock_agent",
    "run_openai_agent",
]
