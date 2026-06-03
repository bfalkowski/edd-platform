"""Runner package for EDD Platform."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from pydantic import BaseModel


class RunnerAgentDesign(BaseModel):
    id: str
    name: str
    intent: str


class RunnerScenario(BaseModel):
    input: str


class RunnerToolCall(BaseModel):
    name: str
    output: str


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
) -> RunnerResult:
    """Run a scenario through OpenAI's Responses API."""
    instructions = (
        "You are the candidate agent being designed in an eval-driven workflow. "
        "Stay inside the design intent, gather or cite relevant evidence from the scenario, "
        "state assumptions clearly, and recommend a safe next action."
    )
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


__all__ = [
    "OpenAIRunnerConfig",
    "RunnerAgentDesign",
    "RunnerResult",
    "RunnerScenario",
    "RunnerToolCall",
    "openai_config_from_env",
    "run_mock_agent",
    "run_openai_agent",
]
