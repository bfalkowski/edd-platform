import time
from datetime import datetime

from fastapi.testclient import TestClient

from edd_platform_api.main import app

import edd_runner  # noqa: E402  (importable once main has put the runner on sys.path)


def create_agent_and_scenario(client: TestClient) -> tuple[dict, dict]:
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Model Record Agent", "intent": "Answer briefly."},
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={"agent_design_id": agent["id"], "name": "Model record", "input": "Say hi."},
    ).json()
    return agent, scenario


def stub_anthropic(monkeypatch, payload_model):
    """Send live runs to a fake Messages API that reports payload_model."""
    sent_bodies = []

    def fake_send(_config, body):
        sent_bodies.append(body)
        time.sleep(0.01)
        payload = {"content": [{"type": "text", "text": "Hi."}], "stop_reason": "end_turn"}
        if payload_model is not None:
            payload["model"] = payload_model
        return payload

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setattr(edd_runner, "build_langchain_tools", lambda _definitions: [])
    monkeypatch.setattr(edd_runner, "send_anthropic_messages_request", fake_send)
    return sent_bodies


def test_live_run_records_provider_reported_model_and_duration(monkeypatch) -> None:
    client = TestClient(app)
    agent, scenario = create_agent_and_scenario(client)
    sent_bodies = stub_anthropic(monkeypatch, payload_model="claude-sonnet-5-5-20261001")

    response = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "mode": "live",
            "model": "claude-sonnet-5-5",
        },
    )

    assert response.status_code == 201
    run = response.json()
    assert sent_bodies[0]["model"] == "claude-sonnet-5-5"
    assert run["model"] == "claude-sonnet-5-5-20261001"
    assert datetime.fromisoformat(run["completed_at"]) > datetime.fromisoformat(run["started_at"])
    stored = client.get(f"/api/projects/project_default/runs/{run['id']}").json()
    assert stored["model"] == "claude-sonnet-5-5-20261001"


def test_live_run_records_requested_model_when_provider_does_not_report_one(monkeypatch) -> None:
    client = TestClient(app)
    agent, scenario = create_agent_and_scenario(client)
    stub_anthropic(monkeypatch, payload_model=None)

    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "mode": "live",
            "model": "claude-opus-5-5",
        },
    ).json()

    assert run["model"] == "claude-opus-5-5"


def test_live_run_without_a_model_uses_the_default(monkeypatch) -> None:
    client = TestClient(app)
    agent, scenario = create_agent_and_scenario(client)
    monkeypatch.delenv("EDD_ANTHROPIC_MODEL", raising=False)
    sent_bodies = stub_anthropic(monkeypatch, payload_model=None)

    run = client.post(
        "/api/projects/project_default/runs",
        json={"agent_design_id": agent["id"], "scenario_id": scenario["id"], "mode": "live"},
    ).json()

    assert sent_bodies[0]["model"] == edd_runner.DEFAULT_ANTHROPIC_MODEL
    assert run["model"] == edd_runner.DEFAULT_ANTHROPIC_MODEL


def test_mock_run_records_no_model() -> None:
    client = TestClient(app)
    agent, scenario = create_agent_and_scenario(client)

    run = client.post(
        "/api/projects/project_default/runs",
        json={"agent_design_id": agent["id"], "scenario_id": scenario["id"], "mode": "mock"},
    ).json()

    assert run["model"] is None


def test_models_route_lists_current_models_with_default(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.delenv("EDD_ANTHROPIC_MODEL", raising=False)

    catalog = client.get("/api/models").json()

    ids = [model["id"] for model in catalog["models"]]
    assert ids == ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]
    assert catalog["default_model"] == "claude-haiku-5-5"
    assert catalog["provider"] == "anthropic"


def test_models_route_default_follows_env_override(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setenv("EDD_ANTHROPIC_MODEL", "claude-opus-5-5")
    assert client.get("/api/models").json()["default_model"] == "claude-opus-5-5"

    monkeypatch.setenv("EDD_ANTHROPIC_MODEL", "claude-custom-model")
    catalog = client.get("/api/models").json()
    assert catalog["default_model"] == "claude-custom-model"
    assert catalog["models"][0] == {"id": "claude-custom-model", "label": "claude-custom-model"}
