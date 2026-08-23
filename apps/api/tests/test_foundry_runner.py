import json

import pytest
from azure.ai.agents.models import (
    Agent,
    AgentThread,
    MessageRole,
    MessageTextContent,
    MessageTextDetails,
    RequiredFunctionToolCall,
    RequiredFunctionToolCallDetails,
    RunStatus,
    SubmitToolOutputsAction,
    SubmitToolOutputsDetails,
    ThreadMessage,
    ThreadRun,
)
from fastapi.testclient import TestClient

import edd_platform_api.main as api_main
from edd_platform_api import service_status
from edd_runner import FoundryRunnerConfig, RunnerAgentDesign, RunnerScenario, RunnerToolDefinition
from edd_runner import foundry_config_from_env, run_foundry_agent_core
from edd_platform_api.main import app  # noqa: E402


def assistant_message(text: str) -> ThreadMessage:
    return ThreadMessage(
        id="msg_fake",
        object="thread.message",
        created_at=0,
        thread_id="thread_fake",
        status="completed",
        role=MessageRole.AGENT,
        content=[MessageTextContent(text=MessageTextDetails(value=text, annotations=[]))],
    )


class FakeThreadsOperations:
    def create(self, **_kwargs):
        return AgentThread(id="thread_fake", object="thread", created_at=0)


class FakeMessagesOperations:
    def __init__(self, response_messages):
        self._response_messages = list(response_messages)
        self.created = []

    def create(self, *, thread_id, role, content, **_kwargs):
        self.created.append({"thread_id": thread_id, "role": role, "content": content})

    def list(self, *, thread_id, **_kwargs):
        return list(self._response_messages)


class FakeRunsOperations:
    def __init__(self, run_sequence):
        self._run_sequence = list(run_sequence)
        self.submitted_outputs = []

    def create(self, *, thread_id, agent_id, **_kwargs):
        return self._run_sequence.pop(0)

    def get(self, *, thread_id, run_id, **_kwargs):
        return self._run_sequence.pop(0)

    def submit_tool_outputs(self, *, thread_id, run_id, tool_outputs, **_kwargs):
        self.submitted_outputs.append(tool_outputs)


class FakeAgentsClient:
    def __init__(self, *, run_sequence, response_messages=()):
        self.threads = FakeThreadsOperations()
        self.messages = FakeMessagesOperations(response_messages)
        self.runs = FakeRunsOperations(run_sequence)
        self.create_agent_calls = []
        self.deleted_agent_ids = []

    def create_agent(self, **kwargs):
        self.create_agent_calls.append(kwargs)
        return Agent(id="agent_fake", object="agent", created_at=0, name=kwargs.get("name"), model=kwargs.get("model"))

    def delete_agent(self, agent_id):
        self.deleted_agent_ids.append(agent_id)


FOUNDRY_AGENT = RunnerAgentDesign(
    id="agent_1",
    name="Foundry Agent",
    intent="Gather evidence and recommend a safe next action.",
    allowed_tool_names=["get_local_time"],
)
FOUNDRY_SCENARIO = RunnerScenario(input="A customer reports a failed deployment.")
FOUNDRY_CONFIG = FoundryRunnerConfig(project_endpoint="https://example.services.ai.azure.com/api/projects/demo", model="gpt-4o-mini")


def test_foundry_config_from_env_requires_project_endpoint(monkeypatch) -> None:
    monkeypatch.delenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("EDD_FOUNDRY_MODEL", raising=False)

    with pytest.raises(RuntimeError, match="AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"):
        foundry_config_from_env()


def test_foundry_config_from_env_requires_model(monkeypatch) -> None:
    monkeypatch.setenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", "https://example.services.ai.azure.com/api/projects/demo")
    monkeypatch.delenv("EDD_FOUNDRY_MODEL", raising=False)

    with pytest.raises(RuntimeError, match="EDD_FOUNDRY_MODEL"):
        foundry_config_from_env()


def test_run_foundry_agent_core_returns_completed_response() -> None:
    completed_run = ThreadRun(
        id="run_fake", object="thread.run", created_at=0,
        thread_id="thread_fake", agent_id="agent_fake", status=RunStatus.COMPLETED,
    )
    client = FakeAgentsClient(
        run_sequence=[completed_run],
        response_messages=[assistant_message("Gathered evidence and recommended a safe rollback.")],
    )

    result = run_foundry_agent_core(
        agent=FOUNDRY_AGENT,
        scenario=FOUNDRY_SCENARIO,
        config=FOUNDRY_CONFIG,
        tool_definitions=[],
        client=client,
    )

    assert result.mode == "live"
    assert result.response == "Gathered evidence and recommended a safe rollback."
    assert client.create_agent_calls[0]["model"] == "gpt-4o-mini"
    assert client.deleted_agent_ids == ["agent_fake"]
    assert any("Foundry Agent Service" in item for item in result.evidence)


def test_run_foundry_agent_core_executes_tool_calls() -> None:
    tool_call = RequiredFunctionToolCall(
        id="call_1",
        function=RequiredFunctionToolCallDetails(name="get_local_time", arguments=json.dumps({"zip_code": "10001"})),
    )
    requires_action_run = ThreadRun(
        id="run_fake", object="thread.run", created_at=0,
        thread_id="thread_fake", agent_id="agent_fake", status=RunStatus.REQUIRES_ACTION,
        required_action=SubmitToolOutputsAction(submit_tool_outputs=SubmitToolOutputsDetails(tool_calls=[tool_call])),
    )
    completed_run = ThreadRun(
        id="run_fake", object="thread.run", created_at=0,
        thread_id="thread_fake", agent_id="agent_fake", status=RunStatus.COMPLETED,
    )
    client = FakeAgentsClient(
        run_sequence=[requires_action_run, completed_run],
        response_messages=[assistant_message("It is currently 12:00 PM.")],
    )
    tool_definitions = [
        RunnerToolDefinition(
            name="get_local_time",
            description="Look up the local time for a ZIP code.",
            input_schema={"type": "object", "properties": {"zip_code": {"type": "string"}}, "required": ["zip_code"]},
            output_description="The local time.",
            implementation_kind="mock",
            implementation_key="mock.local_time",
            mock_response="12:00 PM",
            status="approved",
        )
    ]

    result = run_foundry_agent_core(
        agent=FOUNDRY_AGENT,
        scenario=FOUNDRY_SCENARIO,
        config=FOUNDRY_CONFIG,
        tool_definitions=tool_definitions,
        client=client,
    )

    assert result.response == "It is currently 12:00 PM."
    assert result.tool_calls[0].name == "get_local_time"
    assert result.tool_calls[0].output == "12:00 PM"
    assert client.runs.submitted_outputs[0][0].tool_call_id == "call_1"
    assert client.runs.submitted_outputs[0][0].output == "12:00 PM"
    assert client.deleted_agent_ids == ["agent_fake"]


def test_run_foundry_agent_core_raises_and_still_cleans_up_on_failed_run() -> None:
    failed_run = ThreadRun(
        id="run_fake", object="thread.run", created_at=0,
        thread_id="thread_fake", agent_id="agent_fake", status=RunStatus.FAILED,
    )
    client = FakeAgentsClient(run_sequence=[failed_run])

    with pytest.raises(RuntimeError, match="status=failed"):
        run_foundry_agent_core(
            agent=FOUNDRY_AGENT,
            scenario=FOUNDRY_SCENARIO,
            config=FOUNDRY_CONFIG,
            tool_definitions=[],
            client=client,
        )

    assert client.deleted_agent_ids == ["agent_fake"]


def test_service_status_reports_foundry_configuration(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setenv("EDD_PLATFORM_STORAGE_BACKEND", "memory")
    monkeypatch.setenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", "https://example.services.ai.azure.com/api/projects/demo")
    monkeypatch.setenv("EDD_FOUNDRY_MODEL", "gpt-4o-mini")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(service_status, "service_url_reachable", lambda url: False)

    response = client.get("/api/services")

    assert response.status_code == 200
    services = {service["id"]: service for service in response.json()["services"]}
    assert services["foundry"]["status"] == "configured"
    assert services["foundry"]["configured"] is True


def test_service_status_reports_foundry_not_configured(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setenv("EDD_PLATFORM_STORAGE_BACKEND", "memory")
    monkeypatch.delenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("EDD_FOUNDRY_MODEL", raising=False)
    monkeypatch.setattr(service_status, "service_url_reachable", lambda url: False)

    response = client.get("/api/services")

    services = {service["id"]: service for service in response.json()["services"]}
    assert services["foundry"]["status"] == "not_configured"
    assert services["foundry"]["configured"] is False


def test_live_run_uses_foundry_provider_when_selected(monkeypatch) -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Foundry Provider Agent", "intent": "Gather evidence."},
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Foundry provider scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()

    from edd_runner import RunnerResult, RunnerToolCall
    from datetime import datetime, timezone

    def fake_foundry_config_from_env():
        return object()

    def fake_run_foundry_agent(agent_design, scenario_input, config, tool_definitions):
        return RunnerResult(
            id="run_foundry_fake",
            agent_design_id=agent_design.id,
            mode="live",
            scenario_input=scenario_input.input,
            response="Foundry response with evidence and a safe next action.",
            tool_calls=[RunnerToolCall(name="foundry.agent", output="gpt-4o-mini")],
            evidence=["Used fake Foundry provider in test."],
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(api_main, "foundry_config_from_env", fake_foundry_config_from_env)
    monkeypatch.setattr(api_main, "run_foundry_agent", fake_run_foundry_agent)

    response = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "mode": "live",
            "provider": "foundry",
        },
    )

    assert response.status_code == 201
    run = response.json()
    assert run["mode"] == "live"
    assert run["provider"] == "foundry"
    assert run["output"] == "Foundry response with evidence and a safe next action."


def test_live_run_requires_foundry_project_endpoint(monkeypatch) -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Foundry Needs Config Agent", "intent": "Gather evidence."},
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Foundry missing config scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()

    def fake_foundry_config_from_env():
        raise RuntimeError("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT is required for live Foundry runs.")

    monkeypatch.setattr(api_main, "foundry_config_from_env", fake_foundry_config_from_env)

    response = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "mode": "live",
            "provider": "foundry",
        },
    )

    assert response.status_code == 400
    assert "AZURE_AI_FOUNDRY_PROJECT_ENDPOINT" in response.json()["detail"]
