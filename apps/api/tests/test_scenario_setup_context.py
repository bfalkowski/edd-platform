import sys
from typing import List, Tuple

from fastapi.testclient import TestClient

from edd_platform_api.main import app

edd_runner = sys.modules["edd_runner"]

SETUP_CONTEXT = "Ticket board: T-1 is blocked on T-2. T-2 is in review."
SCENARIO_INPUT = "Which ticket should the team pick up next?"


def create_agent_and_scenario(client: TestClient, setup_context: str) -> Tuple[dict, dict]:
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Setup Context Agent", "intent": "Plan the next ticket."},
    ).json()["agent"]
    # No tools, so a live run takes the plain Anthropic Messages path.
    agent = client.patch(
        f"/api/projects/project_default/agent-designs/{agent['id']}",
        json={"allowed_tool_names": []},
    ).json()
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Setup context scenario",
            "input": SCENARIO_INPUT,
            "setup_context": setup_context,
        },
    ).json()
    return agent, scenario


def create_run(client: TestClient, agent: dict, scenario: dict, mode: str) -> dict:
    response = client.post(
        "/api/projects/project_default/runs",
        json={"agent_design_id": agent["id"], "scenario_id": scenario["id"], "mode": mode},
    )
    assert response.status_code == 201, response.text
    return response.json()


def capture_anthropic_bodies(monkeypatch) -> List[dict]:
    bodies: List[dict] = []

    def fake_send_anthropic_messages_request(_config, body):
        bodies.append(body)
        return {
            "id": "msg_fake",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Pick up T-2."}],
            "stop_reason": "end_turn",
        }

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setattr(edd_runner, "send_anthropic_messages_request", fake_send_anthropic_messages_request)
    return bodies


def test_mock_run_sends_setup_context_to_runner(monkeypatch) -> None:
    client = TestClient(app)
    sent: List[str] = []
    real_run_mock_agent = edd_runner.run_mock_agent

    def spy_run_mock_agent(agent, scenario):
        sent.append(scenario.input)
        return real_run_mock_agent(agent, scenario)

    monkeypatch.setattr("edd_platform_api.routers.runs.run_mock_agent", spy_run_mock_agent)
    agent, scenario = create_agent_and_scenario(client, SETUP_CONTEXT)

    create_run(client, agent, scenario, "mock")

    assert len(sent) == 1
    assert SETUP_CONTEXT in sent[0]
    assert SCENARIO_INPUT in sent[0]


def test_live_anthropic_run_sends_setup_context_in_request_body(monkeypatch) -> None:
    client = TestClient(app)
    bodies = capture_anthropic_bodies(monkeypatch)
    agent, scenario = create_agent_and_scenario(client, SETUP_CONTEXT)

    create_run(client, agent, scenario, "live")

    assert len(bodies) == 1
    user_content = bodies[0]["messages"][0]["content"]
    assert SETUP_CONTEXT in user_content
    assert SCENARIO_INPUT in user_content


def test_live_anthropic_run_with_empty_setup_context_sends_input_only(monkeypatch) -> None:
    client = TestClient(app)
    bodies = capture_anthropic_bodies(monkeypatch)
    agent, scenario = create_agent_and_scenario(client, "")

    create_run(client, agent, scenario, "live")

    assert len(bodies) == 1
    assert bodies[0]["messages"] == [{"role": "user", "content": SCENARIO_INPUT}]


def test_run_record_and_artifact_show_full_text_sent_to_agent(monkeypatch) -> None:
    client = TestClient(app)
    bodies = capture_anthropic_bodies(monkeypatch)
    agent, scenario = create_agent_and_scenario(client, SETUP_CONTEXT)

    run = create_run(client, agent, scenario, "live")

    sent_text = bodies[0]["messages"][0]["content"]
    assert run["input"] == sent_text
    artifact = client.get(
        f"/api/projects/project_default/artifacts/{run['artifact_ids'][0]}"
    ).json()
    assert artifact["artifact_type"] == "RUN_RESULT"
    assert sent_text in artifact["body"]


def test_platform_tags_in_setup_context_are_not_sent_to_agent(monkeypatch) -> None:
    client = TestClient(app)
    bodies = capture_anthropic_bodies(monkeypatch)
    agent, tag_only = create_agent_and_scenario(client, "test_shape:single_turn")
    _, tagged = create_agent_and_scenario(client, f"test_shape:conversation\n{SETUP_CONTEXT}")
    tagged_agent = client.get(
        f"/api/projects/project_default/agent-designs/{tagged['agent_design_id']}"
    ).json()

    create_run(client, agent, tag_only, "live")
    create_run(client, tagged_agent, tagged, "live")

    assert bodies[0]["messages"] == [{"role": "user", "content": SCENARIO_INPUT}]
    tagged_content = bodies[1]["messages"][0]["content"]
    assert SETUP_CONTEXT in tagged_content
    assert "test_shape" not in tagged_content
