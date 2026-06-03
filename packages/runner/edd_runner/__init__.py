"""Deterministic runner package for EDD Platform."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List
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


__all__ = [
    "RunnerAgentDesign",
    "RunnerResult",
    "RunnerScenario",
    "RunnerToolCall",
    "run_mock_agent",
]
