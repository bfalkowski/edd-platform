from datetime import datetime, timezone

from fastapi.testclient import TestClient

import edd_platform_api.main as api_main
from edd_runner import (
    RunnerResult,
    RunnerToolCall,
    RunnerToolDefinition,
    build_langchain_tools,
    extract_response_text,
)
from edd_platform_api.main import app  # noqa: E402


def test_create_and_list_agent_designs() -> None:
    client = TestClient(app)

    projects_response = client.get("/api/projects")

    assert projects_response.status_code == 200
    assert projects_response.json()[0]["id"] == "project_default"

    response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Customer Service Triage Agent",
            "intent": "Determine why an issue escalated and recommend a safe next action.",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    agent = payload["agent"]
    artifact = payload["artifact"]
    assert agent["name"] == "Customer Service Triage Agent"
    assert agent["project_id"] == "project_default"
    assert agent["status"] == "designing"
    assert agent["allowed_tool_names"] == ["get_weather"]
    assert artifact["artifact_type"] == "AGENT_DESIGN"
    assert artifact["artifact_id"] == agent["id"]

    list_response = client.get("/api/projects/project_default/agent-designs")

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == agent["id"]

    artifacts_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"]},
    )

    assert artifacts_response.status_code == 200
    listed_artifact = artifacts_response.json()[0]
    assert listed_artifact["title"] == "Customer Service Triage Agent"

    artifact_detail_response = client.get(
        f"/api/projects/project_default/artifacts/{listed_artifact['id']}"
    )

    assert artifact_detail_response.status_code == 200
    assert artifact_detail_response.json()["artifact_id"] == agent["id"]

    search_response = client.get(
        "/api/projects/project_default/artifacts/search",
        params={"q": "safe next action"},
    )

    assert search_response.status_code == 200
    assert search_response.json()[0]["artifact_id"] == agent["id"]

    context_response = client.post(
        "/api/projects/project_default/context-packs",
        json={"purpose": "AGENT_PROMPT_REVIEW", "agent_design_id": agent["id"]},
    )

    assert context_response.status_code == 200
    context_pack = context_response.json()
    assert context_pack["purpose"] == "AGENT_PROMPT_REVIEW"
    assert context_pack["artifacts"][0]["artifact_id"] == agent["id"]


def test_context_pack_requires_known_agent_design() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/projects/project_default/context-packs",
        json={"purpose": "AGENT_PROMPT_REVIEW", "agent_design_id": "agent_missing"},
    )

    assert response.status_code == 404


def test_project_scoped_routes_require_known_project() -> None:
    client = TestClient(app)

    response = client.get("/api/projects/project_missing/agent-designs")

    assert response.status_code == 404


def test_artifact_detail_requires_known_artifact() -> None:
    client = TestClient(app)

    response = client.get("/api/projects/project_default/artifacts/artifact_missing")

    assert response.status_code == 404


def test_list_tool_definitions_includes_approved_weather_tool() -> None:
    client = TestClient(app)

    response = client.get("/api/projects/project_default/tools")

    assert response.status_code == 200
    tools = response.json()
    assert tools[0]["name"] == "get_weather"
    assert tools[0]["status"] == "approved"
    assert tools[0]["implementation_key"] == "local_weather_fixture"


def test_approved_weather_tool_adapts_to_langchain_tool() -> None:
    tools = build_langchain_tools(
        [
            RunnerToolDefinition(
                name="get_weather",
                description="Get current weather for a US ZIP code.",
                input_schema={"type": "object"},
                output_description="Current temperature and conditions.",
                implementation_key="local_weather_fixture",
                status="approved",
            )
        ]
    )

    assert tools[0].invoke({"zip_code": "06511"}) == (
        "Current weather for 06511 New Haven, CT: 41°F and cloudy."
    )


def test_artifact_links_create_and_list_related_artifacts() -> None:
    client = TestClient(app)

    source_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Source Agent",
            "intent": "Creates the first evidence artifact.",
        },
    )
    target_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Target Agent",
            "intent": "Creates the second evidence artifact.",
        },
    )
    source_artifact = source_response.json()["artifact"]
    target_artifact = target_response.json()["artifact"]

    link_response = client.post(
        "/api/projects/project_default/artifact-links",
        json={
            "source_artifact_id": source_artifact["id"],
            "target_artifact_id": target_artifact["id"],
            "relationship_type": "related_to",
        },
    )

    assert link_response.status_code == 201
    link = link_response.json()
    assert link["source_artifact_id"] == source_artifact["id"]
    assert link["target_artifact_id"] == target_artifact["id"]
    assert link["relationship_type"] == "RELATED_TO"

    source_links_response = client.get(
        f"/api/projects/project_default/artifacts/{source_artifact['id']}/links"
    )
    target_links_response = client.get(
        f"/api/projects/project_default/artifacts/{target_artifact['id']}/links"
    )

    assert source_links_response.status_code == 200
    assert source_links_response.json()[0]["id"] == link["id"]
    assert target_links_response.status_code == 200
    assert target_links_response.json()[0]["id"] == link["id"]


def test_artifact_links_require_known_artifacts() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/projects/project_default/artifact-links",
        json={
            "source_artifact_id": "artifact_missing",
            "target_artifact_id": "artifact_also_missing",
            "relationship_type": "RELATED_TO",
        },
    )

    assert response.status_code == 404


def test_run_agent_design_creates_run_result_artifact() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Runnable Agent",
            "intent": "Gather evidence and recommend a safe next action.",
        },
    )
    agent = create_response.json()["agent"]
    design_artifact = create_response.json()["artifact"]

    run_response = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/runs",
        json={"scenario_input": "A customer reports a failed deployment."},
    )

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["mode"] == "mock"
    assert run["agent_design_id"] == agent["id"]
    assert "failed deployment" in run["response"]
    assert run["tool_calls"][0]["name"] == "collect_design_intent"
    assert run["artifact"]["artifact_type"] == "RUN_RESULT"
    assert run["artifact"]["source"] == "runner:mock"

    artifacts_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "RUN_RESULT"},
    )
    assert artifacts_response.status_code == 200
    assert artifacts_response.json()[0]["artifact_id"] == run["id"]

    links_response = client.get(
        f"/api/projects/project_default/artifacts/{run['artifact']['id']}/links"
    )
    assert links_response.status_code == 200
    link = links_response.json()[0]
    assert link["relationship_type"] == "GENERATED_FROM"
    assert link["target_artifact_id"] == design_artifact["id"]


def test_run_agent_design_requires_known_agent() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/projects/project_default/agent-designs/agent_missing/runs",
        json={"scenario_input": "A customer reports a failed deployment."},
    )

    assert response.status_code == 404


def test_live_run_agent_design_uses_provider_runner(monkeypatch) -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Live Agent",
            "intent": "Gather evidence and recommend a safe next action.",
        },
    )
    agent = create_response.json()["agent"]

    def fake_config_from_env():
        return object()

    def fake_run_openai_agent(agent_design, scenario, config, tool_definitions):
        assert agent_design.allowed_tool_names == ["get_weather"]
        assert tool_definitions == [
            RunnerToolDefinition(
                name="get_weather",
                description="Get current weather for a US ZIP code.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "zip_code": {"type": "string", "description": "US ZIP code."}
                    },
                    "required": ["zip_code"],
                },
                output_description="Current temperature and conditions.",
                implementation_key="local_weather_fixture",
                status="approved",
            )
        ]
        return RunnerResult(
            id="run_live_fake",
            agent_design_id=agent_design.id,
            mode="live",
            scenario_input=scenario.input,
            response="Live response with evidence, assumptions, and a safe next action.",
            tool_calls=[
                RunnerToolCall(name="get_weather", output="Current weather: 41°F and cloudy."),
            ],
            evidence=["Used fake OpenAI provider in test."],
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(api_main, "openai_config_from_env", fake_config_from_env)
    monkeypatch.setattr(api_main, "run_openai_agent", fake_run_openai_agent)

    response = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/runs",
        json={
            "scenario_input": "A customer reports a failed deployment.",
            "mode": "live",
        },
    )

    assert response.status_code == 201
    run = response.json()
    assert run["mode"] == "live"
    assert run["artifact"]["source"] == "runner:live"
    assert run["tool_calls"][0]["name"] == "get_weather"
    assert "41°F" in run["artifact"]["body"]


def test_live_run_requires_openai_api_key(monkeypatch) -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Needs Key",
            "intent": "Gather evidence and recommend a safe next action.",
        },
    )
    agent = create_response.json()["agent"]

    def fake_config_from_env():
        raise RuntimeError("OPENAI_API_KEY is required for live OpenAI runs.")

    monkeypatch.setattr(api_main, "openai_config_from_env", fake_config_from_env)

    response = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/runs",
        json={
            "scenario_input": "A customer reports a failed deployment.",
            "mode": "live",
        },
    )

    assert response.status_code == 400
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_extract_response_text_from_nested_response_output() -> None:
    payload = {
        "output": [
            {"type": "reasoning", "summary": []},
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "A grounded live response.",
                    }
                ],
            },
        ]
    }

    assert extract_response_text(payload) == "A grounded live response."


def test_evaluate_run_artifact_creates_eval_result_artifact() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Evaluate Me",
            "intent": "Gather evidence and recommend a safe next action.",
        },
    )
    agent = create_response.json()["agent"]
    run_response = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/runs",
        json={"scenario_input": "A customer reports a failed deployment."},
    )
    run_artifact = run_response.json()["artifact"]

    eval_response = client.post(
        f"/api/projects/project_default/artifacts/{run_artifact['id']}/evaluate"
    )

    assert eval_response.status_code == 201
    eval_result = eval_response.json()
    assert eval_result["mode"] == "mock"
    assert eval_result["score"] == 3
    assert eval_result["passed"] is True
    assert eval_result["artifact"]["artifact_type"] == "EVAL_RESULT"
    assert eval_result["artifact"]["source"] == "judge:mock"

    links_response = client.get(
        f"/api/projects/project_default/artifacts/{eval_result['artifact']['id']}/links"
    )
    assert links_response.status_code == 200
    link = links_response.json()[0]
    assert link["relationship_type"] == "GENERATED_FROM"
    assert link["target_artifact_id"] == run_artifact["id"]


def test_evaluate_requires_run_result_artifact() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Not A Run",
            "intent": "Temporary agent design.",
        },
    )
    design_artifact = create_response.json()["artifact"]

    response = client.post(
        f"/api/projects/project_default/artifacts/{design_artifact['id']}/evaluate"
    )

    assert response.status_code == 400


def test_delete_agent_design_removes_owned_artifacts() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Delete Me",
            "intent": "Temporary agent design.",
        },
    )
    agent = create_response.json()["agent"]
    design_artifact = create_response.json()["artifact"]
    run_response = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/runs",
        json={"scenario_input": "A temporary scenario."},
    )
    run_artifact = run_response.json()["artifact"]

    delete_response = client.delete(
        f"/api/projects/project_default/agent-designs/{agent['id']}"
    )

    assert delete_response.status_code == 204
    assert (
        client.get(f"/api/projects/project_default/agent-designs/{agent['id']}").status_code
        == 404
    )
    assert (
        client.get(
            f"/api/projects/project_default/artifacts/{design_artifact['id']}"
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/projects/project_default/artifacts/{run_artifact['id']}"
        ).status_code
        == 404
    )
