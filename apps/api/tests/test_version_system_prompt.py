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


def test_live_run_sends_version_instructions_as_whole_system_prompt(monkeypatch) -> None:
    client = TestClient(app)
    bodies = capture_anthropic_bodies(monkeypatch)

    create_versioned_run(client, allowed_tool_names=[])

    assert len(bodies) == 1
    assert bodies[0]["system"] == VERSION_INSTRUCTIONS


def test_run_record_shows_system_prompt_sent(monkeypatch) -> None:
    client = TestClient(app)
    bodies = capture_anthropic_bodies(monkeypatch)

    run = create_versioned_run(client, allowed_tool_names=[])

    assert run["system_prompt"] == bodies[0]["system"]
    saved = client.get(f"/api/projects/project_default/runs/{run['id']}").json()
    assert saved["system_prompt"] == bodies[0]["system"]


def test_system_prompt_is_not_read_as_run_output(monkeypatch) -> None:
    # Instructions that name a tool and the mock judge's keywords must not
    # make the run look like it called the tool or met the judge's checks.
    instructions = (
        "- get_weather: look up the weather first.\n"
        "Cite evidence, state assumptions, recommend a safe next action."
    )
    monkeypatch.setattr(sys.modules[__name__], "VERSION_INSTRUCTIONS", instructions)
    client = TestClient(app)
    capture_anthropic_bodies(monkeypatch)
    run = create_versioned_run(client, allowed_tool_names=[])
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": run["agent_design_id"],
            "name": "Weather tool contract",
            "scenario_id": run["scenario_id"],
            "forbidden_tools": ["get_weather"],
        },
    ).json()

    contract_eval = client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={"eval_contract_id": contract["id"], "judge_mode": "deterministic"},
    ).json()
    mock_judge_eval = client.post(
        f"/api/projects/project_default/artifacts/{run['artifact_ids'][0]}/evaluate"
    ).json()

    forbids = [c for c in contract_eval["checks"] if c["check_type"] == "tool_not_called"]
    assert forbids and all(check["passed"] for check in forbids)
    assert mock_judge_eval["passed"] is False


def test_live_run_with_tools_sends_version_instructions_unchanged(monkeypatch) -> None:
    client = TestClient(app)
    prompts = capture_langchain_system_prompts(monkeypatch)

    run = create_versioned_run(client, allowed_tool_names=None)

    assert len(prompts) == 1
    assert prompts[0] == VERSION_INSTRUCTIONS
    assert run["system_prompt"] == VERSION_INSTRUCTIONS
