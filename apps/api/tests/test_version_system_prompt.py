import sys
import types
from typing import List

from fastapi.testclient import TestClient

from edd_platform_api.main import app

edd_runner = sys.modules["edd_runner"]

VERSION_INSTRUCTIONS = "You write clear Jira tickets. Use the template: Title, Context, Acceptance criteria."
SCENARIO_INPUT = "Write a ticket for adding dark mode."


def create_versioned_run(client: TestClient, allowed_tool_names: List[str] | None) -> dict:
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Ticket Writer", "intent": "Write tickets."},
    ).json()["agent"]
    if allowed_tool_names is not None:
        agent = client.patch(
            f"/api/projects/project_default/agent-designs/{agent['id']}",
            json={"allowed_tool_names": allowed_tool_names},
        ).json()
    version = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/versions",
        json={"instructions": VERSION_INSTRUCTIONS},
    ).json()
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={"agent_design_id": agent["id"], "name": "Dark mode ticket", "input": SCENARIO_INPUT},
    ).json()
    response = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "agent_version_id": version["id"],
            "scenario_id": scenario["id"],
            "mode": "live",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def stub_live_env(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)


def capture_anthropic_bodies(monkeypatch) -> List[dict]:
    bodies: List[dict] = []

    def fake_send_anthropic_messages_request(_config, body):
        bodies.append(body)
        return {
            "id": "msg_fake",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Title: Dark mode"}],
            "stop_reason": "end_turn",
        }

    stub_live_env(monkeypatch)
    monkeypatch.setattr(edd_runner, "send_anthropic_messages_request", fake_send_anthropic_messages_request)
    return bodies


def capture_langchain_system_prompts(monkeypatch) -> List[str]:
    prompts: List[str] = []

    class FakeMessage:
        type = "ai"
        content = "Title: Dark mode"

    class FakeGraph:
        def invoke(self, _state, config=None):
            return {"messages": [FakeMessage()]}

    def fake_create_agent(*, model, tools, system_prompt):
        prompts.append(system_prompt)
        return FakeGraph()

    stub_live_env(monkeypatch)
    fake_agents_module = types.ModuleType("langchain.agents")
    fake_agents_module.create_agent = fake_create_agent
    monkeypatch.setitem(sys.modules, "langchain.agents", fake_agents_module)
    return prompts


def run_artifact_body(client: TestClient, run: dict) -> str:
    artifact = client.get(
        f"/api/projects/project_default/artifacts/{run['artifact_ids'][0]}"
    ).json()
    assert artifact["artifact_type"] == "RUN_RESULT"
    return artifact["body"]


def test_live_run_sends_version_instructions_as_whole_system_prompt(monkeypatch) -> None:
    client = TestClient(app)
    bodies = capture_anthropic_bodies(monkeypatch)

    create_versioned_run(client, allowed_tool_names=[])

    assert len(bodies) == 1
    assert bodies[0]["system"] == VERSION_INSTRUCTIONS


def test_run_artifact_shows_system_prompt_sent(monkeypatch) -> None:
    client = TestClient(app)
    bodies = capture_anthropic_bodies(monkeypatch)

    run = create_versioned_run(client, allowed_tool_names=[])

    body = run_artifact_body(client, run)
    assert f"System prompt\n{bodies[0]['system']}\n\n" in body


def test_live_run_with_tools_sends_version_instructions_unchanged(monkeypatch) -> None:
    client = TestClient(app)
    prompts = capture_langchain_system_prompts(monkeypatch)

    run = create_versioned_run(client, allowed_tool_names=None)

    assert len(prompts) == 1
    assert prompts[0] == VERSION_INSTRUCTIONS
    assert f"System prompt\n{VERSION_INSTRUCTIONS}\n\n" in run_artifact_body(client, run)
