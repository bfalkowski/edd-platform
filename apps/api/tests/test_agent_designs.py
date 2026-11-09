import json
import sys
import types
from datetime import datetime, timezone
from typing import List, Optional

import pytest
from fastapi.testclient import TestClient

import edd_platform_api.main as api_main
from edd_platform_api import service_status
from edd_runner import (
    DEFAULT_ANTHROPIC_MODEL,
    AnthropicRunnerConfig,
    RunnerAgentDesign,
    RunnerResult,
    RunnerScenario,
    RunnerToolCall,
    RunnerToolDefinition,
    build_langchain_tools,
    extract_response_text,
    run_anthropic_agent_with_langfuse,
)
from edd_platform_api.main import app  # noqa: E402
from edd_platform_api.schemas import OutcomeAgentCreated  # noqa: E402

edd_runner = sys.modules["edd_runner"]


def test_service_status_reports_dependency_configuration(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setenv("EDD_PLATFORM_STORAGE_BACKEND", "memory")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "test-public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "test-secret")
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3001")
    monkeypatch.setattr(service_status, "service_url_reachable", lambda url: False)

    response = client.get("/api/services")

    assert response.status_code == 200
    services = {service["id"]: service for service in response.json()["services"]}
    assert services["storage"]["status"] == "online"
    assert services["storage"]["description"] == "API persistence backend: memory."
    assert services["anthropic"]["status"] == "configured"
    assert services["anthropic"]["configured"] is True
    assert services["langfuse"]["status"] == "offline"
    assert services["langfuse"]["configured"] is True
    assert services["langfuse"]["url"] == "http://localhost:3001"


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
    assert "get_weather" in agent["allowed_tool_names"]
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


def test_ad_hoc_url_run_saves_http_evidence(monkeypatch) -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "URL Trace Agent", "intent": "Inspect simple URL calls."},
    ).json()["agent"]

    class FakeResponse:
        headers = {"Content-Type": "text/html"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def getcode(self) -> int:
            return 200

        def read(self, _limit: int) -> bytes:
            return b"<html><title>Example</title></html>"

    def fake_urlopen(request, timeout):
        assert request.full_url == "https://example.com"
        assert timeout == 10
        return FakeResponse()

    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setattr(api_main, "urlopen", fake_urlopen)

    response = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/runs",
        json={"target": "url", "url": "https://example.com"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["mode"] == "url"
    assert payload["scenario_input"] == "https://example.com"
    assert payload["response"] == "GET https://example.com returned 200 with text/html."
    assert payload["tool_calls"] == [
        {
            "name": "http_get",
            "input": "https://example.com",
            "output": "GET https://example.com returned 200 with text/html.",
        }
    ]
    assert payload["trace_url"] is None
    assert payload["artifact"]["artifact_type"] == "RUN_RESULT"
    assert "Body excerpt\n<html><title>Example</title></html>" in payload["artifact"]["body"]


def test_ad_hoc_url_run_requires_http_url() -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "URL Validation Agent", "intent": "Reject invalid URL calls."},
    ).json()["agent"]

    response = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/runs",
        json={"target": "url", "url": "not-a-url"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "URL must use http or https."


def test_agent_version_and_judge_prompt_store_langfuse_prompt_refs() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Prompt Linked Agent",
            "intent": "Use managed prompt instructions.",
            "langfuse_prompt_name": "edd-agent-support",
            "langfuse_prompt_version": "3",
            "langfuse_prompt_label": "production",
        },
    )
    agent = create_response.json()["agent"]
    agent_artifact = create_response.json()["artifact"]

    assert agent["langfuse_prompt_name"] == "edd-agent-support"
    assert agent["langfuse_prompt_version"] == "3"
    assert agent_artifact["external_refs"] == [
        {
            "provider": "langfuse",
            "ref_type": "prompt",
            "external_id": "edd-agent-support:version:3",
            "url": None,
            "label": "Langfuse prompt",
            "metadata": {
                "prompt_name": "edd-agent-support",
                "prompt_version": "3",
                "prompt_label": "production",
                "prompt_role": "agent",
                "source_id": agent["id"],
            },
        }
    ]

    version_response = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/versions",
        json={"version_label": "v0", "status": "baseline"},
    )
    version = version_response.json()
    assert version["langfuse_prompt_name"] == "edd-agent-support"
    assert version["langfuse_prompt_version"] == "3"

    artifacts = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"]},
    ).json()
    version_artifact = next(
        artifact
        for artifact in artifacts
        if artifact["artifact_type"] == "AGENT_VERSION"
        and artifact["artifact_id"] == version["id"]
    )
    assert version_artifact["external_refs"][0]["metadata"]["prompt_role"] == "agent_version"
    assert version_artifact["external_refs"][0]["external_id"] == "edd-agent-support:version:3"

    template_response = client.post(
        "/api/projects/project_default/judge-prompt-templates",
        json={
            "name": "Prompt Linked Judge",
            "template": "Judge against supplied evidence only.",
            "langfuse_prompt_name": "edd-judge-evidence",
            "langfuse_prompt_label": "staging",
        },
    )
    template = template_response.json()
    prompt_artifact = next(
        artifact
        for artifact in client.get("/api/projects/project_default/artifacts").json()
        if artifact["artifact_type"] == "JUDGE_PROMPT_TEMPLATE"
        and artifact["artifact_id"] == template["id"]
    )
    assert template["langfuse_prompt_name"] == "edd-judge-evidence"
    assert prompt_artifact["external_refs"][0]["external_id"] == "edd-judge-evidence:label:staging"
    assert prompt_artifact["external_refs"][0]["metadata"]["prompt_role"] == "judge"


def test_context_pack_requires_known_agent_design() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/projects/project_default/context-packs",
        json={"purpose": "AGENT_PROMPT_REVIEW", "agent_design_id": "agent_missing"},
    )

    assert response.status_code == 404


def test_context_pack_purposes_select_different_artifact_sets() -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Context Strategy Agent", "intent": "Gather evidence."},
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Context strategy scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Context strategy contract",
            "scenario_id": scenario["id"],
            "checks": [
                {
                    "id": "requires_missing_phrase",
                    "type": "output_contains",
                    "value": "purple elephant",
                }
            ],
        },
    ).json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()
    client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={"judge_mode": "deterministic"},
    )
    client.post(
        "/api/projects/project_default/gates",
        json={
            "agent_design_id": agent["id"],
            "name": "Context strategy gate",
            "required_artifact_types": ["EVAL_RESULT"],
        },
    )

    fix_pack_response = client.post(
        "/api/projects/project_default/context-packs",
        json={"purpose": "FIX_PROPOSAL_GENERATION", "agent_design_id": agent["id"]},
    )
    gate_pack_response = client.post(
        "/api/projects/project_default/context-packs",
        json={"purpose": "GATE_DECISION_REVIEW", "agent_design_id": agent["id"]},
    )

    assert fix_pack_response.status_code == 200
    assert gate_pack_response.status_code == 200
    fix_types = {artifact["artifact_type"] for artifact in fix_pack_response.json()["artifacts"]}
    gate_types = {artifact["artifact_type"] for artifact in gate_pack_response.json()["artifacts"]}
    assert {"EVAL_CONTRACT", "EVAL_RESULT", "FAILURE_PACKET", "JUDGE_OUTPUT", "RUN_RESULT"} <= fix_types
    assert "GATE" not in fix_types
    assert {"GATE", "EVAL_RESULT", "FAILURE_PACKET", "JUDGE_OUTPUT"} <= gate_types
    assert "AGENT_DESIGN" not in gate_types


def test_evidence_summary_is_cached_for_unchanged_context() -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Summary Cache Agent", "intent": "Summarize evidence."},
    ).json()["agent"]

    first_response = client.post(
        "/api/projects/project_default/evidence-summaries",
        json={"purpose": "AGENT_PROMPT_REVIEW", "agent_design_id": agent["id"]},
    )
    second_response = client.post(
        "/api/projects/project_default/evidence-summaries",
        json={"purpose": "AGENT_PROMPT_REVIEW", "agent_design_id": agent["id"]},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    first_summary = first_response.json()
    second_summary = second_response.json()
    assert first_summary["cache_hit"] is False
    assert second_summary["cache_hit"] is True
    assert second_summary["id"] == first_summary["id"]
    assert second_summary["supporting_artifact_ids"] == first_summary["supporting_artifact_ids"]


def test_evidence_summary_includes_langfuse_dataset_refs() -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Dataset Ref Agent", "intent": "Replay scenario evidence."},
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Dataset-backed scenario",
            "input": "A customer asks for a safe next action.",
        },
    ).json()

    response = client.post(
        "/api/projects/project_default/evidence-summaries",
        json={"purpose": "FIX_PROPOSAL_GENERATION", "agent_design_id": agent["id"]},
    )

    assert response.status_code == 201
    summary = response.json()
    scenario_artifact = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "SCENARIO"},
    ).json()[0]
    assert scenario_artifact["artifact_id"] == scenario["id"]
    assert scenario_artifact["id"] in summary["supporting_artifact_ids"]
    assert "Langfuse refs:" in summary["summary"]
    assert "Langfuse dataset (planned)" in summary["summary"]
    assert f"dataset_item:{scenario['id']}" in summary["summary"]


def test_live_evidence_summary_records_token_usage(monkeypatch) -> None:
    client = TestClient(app)
    seen_prompt = {}
    monkeypatch.setenv("EDD_ANTHROPIC_INPUT_COST_PER_1M", "1.00")
    monkeypatch.setenv("EDD_ANTHROPIC_OUTPUT_COST_PER_1M", "2.00")

    def fake_live_summary(prompt: str):
        seen_prompt["value"] = prompt
        return "Live evidence summary cites bounded artifacts.", "test-summary-model", {
            "input_tokens": 20,
            "output_tokens": 10,
        }

    monkeypatch.setattr(api_main, "run_live_evidence_summary", fake_live_summary)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Live Summary Agent", "intent": "Collect context."},
    ).json()["agent"]

    response = client.post(
        "/api/projects/project_default/evidence-summaries",
        json={
            "purpose": "AGENT_PROMPT_REVIEW",
            "agent_design_id": agent["id"],
            "mode": "live",
        },
    )

    assert response.status_code == 201
    summary = response.json()
    assert "Live evidence summary" in summary["summary"]
    assert summary["provider"] == "anthropic"
    assert summary["model"] == "test-summary-model"
    assert summary["token_usage"] == {"input_tokens": 20, "output_tokens": 10}
    assert summary["cost_estimate"] == 0.00004
    assert "Live Summary Agent" in seen_prompt["value"]


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
    weather_tool = next(tool for tool in tools if tool["name"] == "get_weather")
    assert weather_tool["status"] == "approved"
    assert weather_tool["implementation_key"] == "open_meteo_weather"
    web_page_tool = next(tool for tool in tools if tool["name"] == "call_http_api")
    assert web_page_tool["status"] == "approved"
    assert web_page_tool["implementation_kind"] == "builtin"
    assert web_page_tool["implementation_key"] == "call_http_api"
    assert web_page_tool["input_schema"]["required"] == ["url"]
    rendered_page_tool = next(tool for tool in tools if tool["name"] == "browse_webpage")
    assert rendered_page_tool["status"] == "approved"
    assert rendered_page_tool["implementation_kind"] == "builtin"
    assert rendered_page_tool["implementation_key"] == "browse_webpage"
    assert rendered_page_tool["input_schema"]["required"] == ["url"]


def test_default_apartment_search_agent_has_web_tools_enabled() -> None:
    client = TestClient(app)

    agents_response = client.get("/api/projects/project_default/agent-designs")

    assert agents_response.status_code == 200
    agent = next(
        agent
        for agent in agents_response.json()
        if agent["id"] == "agent_apartment_search"
    )
    assert agent["name"] == "Apartment Search Agent"
    assert "Zillow-style searches" in agent["intent"]
    assert set(agent["allowed_tool_names"]) >= {"call_http_api", "browse_webpage"}

    artifacts_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "AGENT_DESIGN"},
    )
    assert artifacts_response.status_code == 200
    assert artifacts_response.json()[0]["artifact_id"] == "agent_apartment_search"
    assert "call_http_api" in artifacts_response.json()[0]["body"]


def test_create_tool_definition_with_input_and_output_schema() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/projects/project_default/tools",
        json={
            "name": "lookup_ticket",
            "description": "Look up a support ticket by id.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "Ticket id."}
                },
                "required": ["ticket_id"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["status", "summary"],
            },
            "output_description": "Ticket status and summary.",
            "implementation_kind": "mock",
            "implementation_key": "mock.lookup_ticket",
            "config_schema": {"type": "object", "properties": {}},
            "mock_response": "Ticket is open and awaiting customer logs.",
        },
    )

    assert response.status_code == 201
    tool = response.json()
    assert tool["name"] == "lookup_ticket"
    assert tool["status"] == "draft"
    assert tool["implementation_kind"] == "mock"
    assert tool["input_schema"]["required"] == ["ticket_id"]
    assert tool["output_schema"]["required"] == ["status", "summary"]

    tools_response = client.get("/api/projects/project_default/tools")
    assert "lookup_ticket" in {tool["name"] for tool in tools_response.json()}

    artifacts_response = client.get("/api/projects/project_default/artifacts")
    tool_artifact = next(
        artifact
        for artifact in artifacts_response.json()
        if artifact["artifact_type"] == "TOOL_DEFINITION"
        and artifact["artifact_id"] == tool["id"]
    )
    assert "Input schema" in tool_artifact["body"]
    assert "Output schema" in tool_artifact["body"]


def test_create_tool_definition_rejects_duplicate_names() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/projects/project_default/tools",
        json={
            "name": "get_weather",
            "description": "Duplicate weather tool.",
            "input_schema": {"type": "object", "properties": {}},
            "output_description": "Weather output.",
            "implementation_key": "mock.duplicate_weather",
        },
    )

    assert response.status_code == 409


def test_create_tool_definition_rejects_non_object_input_schema() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/projects/project_default/tools",
        json={
            "name": "bad_schema_tool",
            "description": "Invalid schema.",
            "input_schema": {"type": "string"},
            "output_description": "Bad output.",
            "implementation_key": "mock.bad_schema",
        },
    )

    assert response.status_code == 400


def test_approve_tool_definition_then_allow_for_agent() -> None:
    client = TestClient(app)
    tool_response = client.post(
        "/api/projects/project_default/tools",
        json={
            "name": "lookup_account",
            "description": "Look up an account by id.",
            "input_schema": {"type": "object", "properties": {"account_id": {"type": "string"}}},
            "output_description": "Account summary.",
            "implementation_key": "mock.lookup_account",
            "mock_response": "Account is active.",
        },
    )
    tool = tool_response.json()
    agent_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Account Agent",
            "intent": "Use approved account tools.",
            "allowed_tool_names": [],
        },
    )
    agent = agent_response.json()["agent"]

    rejected_response = client.patch(
        f"/api/projects/project_default/agent-designs/{agent['id']}",
        json={"allowed_tool_names": ["lookup_account"]},
    )
    assert rejected_response.status_code == 400

    approve_response = client.patch(
        f"/api/projects/project_default/tools/{tool['id']}",
        json={"status": "approved"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    allow_response = client.patch(
        f"/api/projects/project_default/agent-designs/{agent['id']}",
        json={"allowed_tool_names": ["lookup_account"]},
    )
    assert allow_response.status_code == 200
    assert allow_response.json()["allowed_tool_names"] == ["lookup_account"]

    artifacts_response = client.get("/api/projects/project_default/artifacts")
    tool_artifact = next(
        artifact
        for artifact in artifacts_response.json()
        if artifact["artifact_type"] == "TOOL_DEFINITION"
        and artifact["artifact_id"] == tool["id"]
    )
    assert "Status\napproved" in tool_artifact["body"]


def test_tool_definition_exposes_schema_first_adapter_contracts() -> None:
    client = TestClient(app)
    tool = client.post(
        "/api/projects/project_default/tools",
        json={
            "name": "lookup_order_status",
            "description": "Look up an order by id.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order identifier."},
                    "include_events": {"type": "boolean"},
                },
                "required": ["order_id"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["status"],
            },
            "output_description": "Order status summary.",
            "implementation_kind": "mock",
            "implementation_key": "mock.lookup_order_status",
            "mock_response": "Order is awaiting carrier pickup.",
        },
    ).json()
    approved = client.patch(
        f"/api/projects/project_default/tools/{tool['id']}",
        json={"status": "approved"},
    ).json()

    response = client.get(
        f"/api/projects/project_default/tools/{approved['id']}/adapter-contracts"
    )

    assert response.status_code == 200
    contract = response.json()
    assert contract["tool_id"] == approved["id"]
    assert contract["status"] == "approved"
    assert contract["langchain"]["args_schema"] == approved["input_schema"]
    assert contract["langchain"]["response_schema"] == approved["output_schema"]
    assert contract["openai"] == {
        "type": "function",
        "function": {
            "name": "lookup_order_status",
            "description": "Look up an order by id.",
            "parameters": approved["input_schema"],
        },
    }
    assert contract["mcp"]["inputSchema"] == approved["input_schema"]
    assert contract["mcp"]["outputSchema"] == approved["output_schema"]
    assert contract["eval_validation"]["required_tool_name"] == "lookup_order_status"
    assert contract["eval_validation"]["allowed_status"] == "approved"
    assert contract["eval_validation"]["implementation_key"] == "mock.lookup_order_status"


def test_update_agent_design_tool_allowlist() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Tool Policy Agent",
            "intent": "Use approved tools only.",
            "allowed_tool_names": [],
        },
    )
    agent = create_response.json()["agent"]
    assert "get_weather" in agent["allowed_tool_names"]

    response = client.patch(
        f"/api/projects/project_default/agent-designs/{agent['id']}",
        json={"allowed_tool_names": []},
    )

    assert response.status_code == 200
    assert response.json()["allowed_tool_names"] == []
    artifacts_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"]},
    )
    design_artifact = next(
        artifact
        for artifact in artifacts_response.json()
        if artifact["artifact_type"] == "AGENT_DESIGN"
    )
    assert "Allowed tools: none" in design_artifact["body"]

    response = client.patch(
        f"/api/projects/project_default/agent-designs/{agent['id']}",
        json={"allowed_tool_names": ["get_weather"]},
    )

    assert response.status_code == 200
    assert response.json()["allowed_tool_names"] == ["get_weather"]
    artifacts_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"]},
    )
    design_artifact = next(
        artifact
        for artifact in artifacts_response.json()
        if artifact["artifact_type"] == "AGENT_DESIGN"
    )
    assert "Allowed tools: get_weather" in design_artifact["body"]


def test_update_agent_design_rejects_unknown_tools() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Unknown Tool Agent",
            "intent": "Use approved tools only.",
        },
    )
    agent = create_response.json()["agent"]

    response = client.patch(
        f"/api/projects/project_default/agent-designs/{agent['id']}",
        json={"allowed_tool_names": ["secret_tool"]},
    )

    assert response.status_code == 400


def test_approved_weather_tool_adapts_to_langchain_tool(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps(
                {"current": {"temperature_2m": 76.2, "weather_code": 0}}
            ).encode("utf-8")

    monkeypatch.setattr(
        edd_runner,
        "get_zip_location",
        lambda zip_code: ("41.3083", "-72.9279", "New Haven", "CT"),
    )
    monkeypatch.setattr(edd_runner, "urlopen", lambda request, timeout: FakeResponse())

    tools = build_langchain_tools(
        [
            RunnerToolDefinition(
                name="get_weather",
                description="Get current weather for a US ZIP code.",
                input_schema={"type": "object"},
                output_description="Current temperature and conditions.",
                implementation_key="open_meteo_weather",
                status="approved",
            )
        ]
    )

    assert tools[0].invoke({"zip_code": "06511"}) == (
        "Current weather for 06511 New Haven, CT: 76°F and clear sky. "
        "Source: Open-Meteo current forecast."
    )


def test_approved_web_page_tool_adapts_to_langchain_tool(monkeypatch) -> None:
    class FakeResponse:
        headers = {"Content-Type": "text/html"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def getcode(self) -> int:
            return 200

        def read(self, _limit: int) -> bytes:
            return b"<html><title>Example</title><body>Hello page</body></html>"

    def fake_urlopen(request, timeout):
        assert request.full_url == "https://example.com"
        assert request.headers["User-agent"] == "edd-platform-agent-tool/1.0"
        assert timeout == 15
        return FakeResponse()

    monkeypatch.setattr(edd_runner, "urlopen", fake_urlopen)

    tools = build_langchain_tools(
        [
            RunnerToolDefinition(
                name="call_http_api",
                description="Make a raw HTTP GET request and return the response body.",
                input_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string", "format": "uri"}},
                    "required": ["url"],
                },
                output_description="HTTP response summary.",
                implementation_kind="builtin",
                implementation_key="call_http_api",
                status="approved",
            )
        ]
    )

    assert tools[0].name == "call_http_api"
    result = tools[0].invoke({"url": "https://example.com"})
    assert "Fetched https://example.com" in result
    assert "HTTP 200" in result
    assert "text/html" in result


def test_approved_rendered_page_tool_adapts_to_langchain_tool(monkeypatch) -> None:
    class FakePage:
        def goto(self, url, wait_until, timeout):
            assert url == "https://example.com"
            assert wait_until == "domcontentloaded"
            assert timeout == 20000

        def wait_for_timeout(self, timeout):
            assert timeout == 3000

        def evaluate(self, _script):
            return {
                "title": "Example Domain",
                "url": "https://example.com",
                "text": "Example Domain This domain is for use in illustrative examples.",
                "links": [{"text": "More information", "href": "https://www.iana.org/help/example-domains"}],
            }

    class FakeBrowser:
        def new_page(self, user_agent):
            assert user_agent == "edd-platform-render-tool/1.0"
            return FakePage()

        def close(self):
            return None

    class FakeChromium:
        def launch(self, headless):
            assert headless is True
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightContext:
        def __enter__(self):
            return FakePlaywright()

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(edd_runner, "get_sync_playwright", lambda: FakePlaywrightContext())

    tools = build_langchain_tools(
        [
            RunnerToolDefinition(
                name="browse_webpage",
                description="Open a URL in a real browser, execute JavaScript, and return visible text.",
                input_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string", "format": "uri"}},
                    "required": ["url"],
                },
                output_description="Rendered page text and links.",
                implementation_kind="builtin",
                implementation_key="browse_webpage",
                status="approved",
            )
        ]
    )

    result = tools[0].invoke(
        {
            "url": "https://example.com",
            "query": "Find example content.",
            "max_chars": 1000,
        }
    )

    assert tools[0].name == "browse_webpage"
    assert "Rendered https://example.com" in result
    assert "Title\nExample Domain" in result
    assert "Query\nFind example content." in result
    assert "Example Domain This domain is for use in illustrative examples." in result
    assert "- More information: https://www.iana.org/help/example-domains" in result


def test_approved_mock_tool_adapts_to_langchain_tool() -> None:
    tools = build_langchain_tools(
        [
            RunnerToolDefinition(
                name="lookup_account",
                description="Look up an account by id.",
                input_schema={
                    "type": "object",
                    "properties": {"account_id": {"type": "string"}},
                    "required": ["account_id"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"summary": {"type": "string"}},
                },
                output_description="Account summary.",
                implementation_kind="mock",
                implementation_key="mock.lookup_account",
                mock_response="Account is active.",
                status="approved",
            )
        ]
    )

    assert tools[0].name == "lookup_account"
    assert tools[0].invoke({"account_id": "acct_123"}) == "Account is active."


def test_langfuse_trace_url_failure_does_not_fail_live_run(monkeypatch) -> None:
    class FakeObservation:
        trace_id = "trace_fake"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def update(self, **_kwargs):
            return None

    class FakeLangfuse:
        def start_as_current_observation(self, **_kwargs):
            return FakeObservation()

        def get_current_trace_id(self):
            return "trace_fake"

        def get_trace_url(self, *, trace_id: str):
            raise RuntimeError(f"Langfuse unavailable for {trace_id}.")

        def flush(self):
            raise RuntimeError("Langfuse offline.")

    def fake_run_anthropic_agent_core(agent, scenario, config, tool_definitions):
        return RunnerResult(
            id="run_fake",
            agent_design_id=agent.id,
            mode="live",
            scenario_input=scenario.input,
            response="Live answer.",
            tool_calls=[],
            evidence=["Used fake live runner."],
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setitem(
        sys.modules,
        "langfuse",
        types.SimpleNamespace(get_client=lambda: FakeLangfuse()),
    )
    monkeypatch.setattr(edd_runner, "run_anthropic_agent_core", fake_run_anthropic_agent_core)

    result = run_anthropic_agent_with_langfuse(
        agent=RunnerAgentDesign(
            id="agent_fake",
            name="Fake Agent",
            intent="Answer safely.",
        ),
        scenario=RunnerScenario(input="A scenario."),
        config=AnthropicRunnerConfig(api_key="test-key"),
        tool_definitions=[],
    )

    assert result.response == "Live answer."
    assert result.trace_id == "trace_fake"
    assert result.trace_url is None
    assert "Linked Langfuse trace trace_fake." in result.evidence


def test_anthropic_messages_core_records_langfuse_generation(monkeypatch) -> None:
    generation_updates: List[dict] = []
    generation_starts: List[dict] = []

    class FakeGeneration:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def update(self, **kwargs):
            generation_updates.append(kwargs)

    class FakeLangfuse:
        def start_as_current_observation(self, **kwargs):
            generation_starts.append(kwargs)
            return FakeGeneration()

    fake_payload = {
        "id": "msg_fake",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "Tim"}],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 12,
            "output_tokens": 3,
        },
    }

    def fake_send_anthropic_messages_request(_config, _body):
        return fake_payload

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "test-public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "test-secret")
    monkeypatch.setitem(
        sys.modules,
        "langfuse",
        types.SimpleNamespace(get_client=lambda: FakeLangfuse()),
    )
    monkeypatch.setattr(edd_runner, "send_anthropic_messages_request", fake_send_anthropic_messages_request)

    result = edd_runner.run_anthropic_agent_core(
        agent=RunnerAgentDesign(id="agent_tim", name="tim", intent="Always respond Tim."),
        scenario=RunnerScenario(input="Say the agent name."),
        config=AnthropicRunnerConfig(api_key="test-key", model="claude-sonnet-4-6"),
        tool_definitions=[],
    )

    assert result.response == "Tim"
    assert generation_starts[0]["as_type"] == "generation"
    assert generation_starts[0]["name"] == "anthropic.messages"
    assert generation_starts[0]["model"] == "claude-sonnet-4-6"
    assert generation_starts[0]["input"][0]["content"] == "Say the agent name."
    assert generation_updates[0]["output"] == "Tim"
    assert generation_updates[0]["usage_details"] == {
        "input_tokens": 12,
        "output_tokens": 3,
    }
    assert generation_updates[0]["metadata"]["anthropic_message_id"] == "msg_fake"


def test_live_judge_records_langfuse_generation_on_run_trace(monkeypatch) -> None:
    generation_starts: List[dict] = []
    generation_updates: List[dict] = []
    generation_events: List[str] = []

    class FakeGeneration:
        def __enter__(self):
            generation_events.append("enter")
            return self

        def __exit__(self, *_args):
            generation_events.append("exit")
            return None

        def update(self, **kwargs):
            generation_events.append("update")
            generation_updates.append(kwargs)

    class FakeLangfuse:
        def start_as_current_observation(self, **kwargs):
            generation_starts.append(kwargs)
            return FakeGeneration()

        def flush(self):
            generation_events.append("flush")

    class FakeMessage:
        id = "msg_judge_fake"
        stop_reason = "end_turn"
        content = [types.SimpleNamespace(type="text", text="PASS: The answer satisfies the rubric.")]
        usage = types.SimpleNamespace(input_tokens=20, output_tokens=6)

        def model_dump(self):
            return {
                "id": self.id,
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "PASS: The answer satisfies the rubric."}],
                "stop_reason": self.stop_reason,
                "usage": {"input_tokens": 20, "output_tokens": 6},
            }

    class FakeMessages:
        def create(self, **_kwargs):
            return FakeMessage()

    class FakeAnthropicClient:
        messages = FakeMessages()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("EDD_ANTHROPIC_MODEL", raising=False)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "test-public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "test-secret")
    monkeypatch.setitem(
        sys.modules,
        "langfuse",
        types.SimpleNamespace(get_client=lambda: FakeLangfuse()),
    )
    monkeypatch.setattr(api_main, "_anthropic_client", lambda _config: FakeAnthropicClient())

    response_text, model, token_usage = api_main.run_live_judge(
        "Judge this answer.",
        trace_id="trace_fake",
    )

    assert response_text.startswith("PASS")
    assert model == DEFAULT_ANTHROPIC_MODEL
    assert token_usage == {
        "input_tokens": 20,
        "output_tokens": 6,
    }
    assert generation_starts[0]["trace_context"] == {"trace_id": "trace_fake"}
    assert generation_starts[0]["as_type"] == "generation"
    assert generation_starts[0]["name"] == "anthropic.messages.judge"
    assert generation_starts[0]["model"] == DEFAULT_ANTHROPIC_MODEL
    assert generation_updates[0]["output"] == response_text
    assert generation_updates[0]["usage_details"] == {
        "input_tokens": 20,
        "output_tokens": 6,
    }
    assert generation_updates[0]["metadata"]["anthropic_message_id"] == "msg_judge_fake"
    assert generation_events == ["enter", "update", "exit", "flush"]


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
    assert run["artifact_ids"][0] == run["artifact"]["id"]

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

    tool_call_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "TOOL_CALL"},
    )
    tool_result_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "TOOL_RESULT"},
    )

    assert tool_call_response.status_code == 200
    assert tool_result_response.status_code == 200
    tool_call = next(
        artifact
        for artifact in tool_call_response.json()
        if "collect_design_intent" in artifact["title"]
    )
    tool_result = next(
        artifact
        for artifact in tool_result_response.json()
        if "collect_design_intent" in artifact["title"]
    )
    assert "Input\nagent.intent" in tool_call["body"]
    assert "Output\nGather evidence" in tool_result["body"]

    tool_call_links = client.get(
        f"/api/projects/project_default/artifacts/{tool_call['id']}/links"
    ).json()
    tool_result_links = client.get(
        f"/api/projects/project_default/artifacts/{tool_result['id']}/links"
    ).json()
    assert any(
        link["relationship_type"] == "GENERATED_FROM"
        and link["target_artifact_id"] == run["artifact"]["id"]
        for link in tool_call_links
    )
    assert any(
        link["relationship_type"] == "GENERATED_FROM"
        and link["target_artifact_id"] == tool_call["id"]
        for link in tool_result_links
    )


def test_create_scenario_and_eval_contract_artifacts(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.delenv("EDD_PLATFORM_LANGFUSE_DATASET_SYNC", raising=False)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Contract Agent",
            "intent": "Use evidence and tools before answering.",
        },
    )
    agent = create_response.json()["agent"]

    scenario_response = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Escalation triage",
            "input": "A customer reports a failed deployment.",
            "setup_context": "The support team needs a safe next action.",
        },
    )

    assert scenario_response.status_code == 201
    scenario = scenario_response.json()
    assert scenario["agent_design_id"] == agent["id"]
    assert scenario["input"] == "A customer reports a failed deployment."

    contract_response = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Evidence-grounded triage",
            "description": "The agent should collect evidence before action.",
            "scenario_id": scenario["id"],
            "expected_behavior": ["Gather relevant evidence.", "Recommend a safe next action."],
            "required_tools": ["get_weather"],
            "checks": [
                {
                    "id": "mentions_evidence",
                    "type": "output_contains",
                    "value": "evidence",
                }
            ],
        },
    )

    assert contract_response.status_code == 201
    contract = contract_response.json()
    assert contract["scenario_id"] == scenario["id"]
    assert contract["required_tools"] == ["get_weather"]
    assert contract["checks"][0]["id"] == "mentions_evidence"
    assert contract["checks"][1]["id"] == "requires_tool_get_weather"

    scenarios_response = client.get(
        "/api/projects/project_default/scenarios",
        params={"agent_design_id": agent["id"]},
    )
    contracts_response = client.get(
        "/api/projects/project_default/eval-contracts",
        params={"agent_design_id": agent["id"]},
    )
    artifacts_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"]},
    )

    assert scenarios_response.status_code == 200
    assert scenarios_response.json()[0]["id"] == scenario["id"]
    assert contracts_response.status_code == 200
    assert contracts_response.json()[0]["id"] == contract["id"]
    artifact_types = {artifact["artifact_type"] for artifact in artifacts_response.json()}
    assert "SCENARIO" in artifact_types
    assert "EVAL_CONTRACT" in artifact_types
    scenario_artifact = next(
        artifact
        for artifact in artifacts_response.json()
        if artifact["artifact_type"] == "SCENARIO" and artifact["artifact_id"] == scenario["id"]
    )
    scenario_refs = scenario_artifact["external_refs"]
    assert {
        (ref["provider"], ref["ref_type"], ref["external_id"])
        for ref in scenario_refs
    } == {
        ("langfuse", "dataset", f"dataset:project_default:{agent['id']}"),
        ("langfuse", "dataset_item", f"dataset_item:{scenario['id']}"),
    }
    assert {ref["metadata"]["sync_mode"] for ref in scenario_refs} == {"planned"}


def test_create_scenario_live_syncs_langfuse_dataset_refs(monkeypatch) -> None:
    client = TestClient(app)
    calls = []

    class FakeLangfuse:
        def create_dataset(self, **kwargs):
            calls.append(("create_dataset", kwargs))
            return types.SimpleNamespace(id="dataset_live_123")

        def create_dataset_item(self, **kwargs):
            calls.append(("create_dataset_item", kwargs))
            return types.SimpleNamespace(id="dataset_item_live_456")

    monkeypatch.setenv("EDD_PLATFORM_LANGFUSE_DATASET_SYNC", "live")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "test-public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "test-secret")
    monkeypatch.setattr(api_main, "get_langfuse_client", lambda: FakeLangfuse())

    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Live Dataset Agent",
            "intent": "Use synced scenarios for evaluation.",
        },
    )
    agent = create_response.json()["agent"]

    scenario_response = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Synced escalation triage",
            "input": "A customer reports a failed deployment.",
            "setup_context": "The support team needs a safe next action.",
            "fixture_refs": ["fixture_ticket_123"],
        },
    )

    assert scenario_response.status_code == 201
    scenario = scenario_response.json()
    dataset_name = f"edd:project_default:{agent['id']}:scenarios"
    assert calls == [
        (
            "create_dataset",
            {
                "name": dataset_name,
                "description": f"EDD scenarios for agent design {agent['id']}.",
                "metadata": {
                    "project_id": "project_default",
                    "agent_design_id": agent["id"],
                    "source": "edd-platform",
                },
            },
        ),
        (
            "create_dataset_item",
            {
                "dataset_name": dataset_name,
                "input": "A customer reports a failed deployment.",
                "expected_output": None,
                "metadata": {
                    "project_id": "project_default",
                    "agent_design_id": agent["id"],
                    "source": "edd-platform",
                    "scenario_id": scenario["id"],
                    "scenario_name": "Synced escalation triage",
                    "setup_context": "The support team needs a safe next action.",
                    "fixture_refs": ["fixture_ticket_123"],
                    "default_eval_contract_id": None,
                },
                "id": scenario["id"],
            },
        ),
    ]

    artifacts_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"]},
    )
    scenario_artifact = next(
        artifact
        for artifact in artifacts_response.json()
        if artifact["artifact_type"] == "SCENARIO" and artifact["artifact_id"] == scenario["id"]
    )
    scenario_refs = scenario_artifact["external_refs"]
    assert {
        (ref["ref_type"], ref["external_id"], ref["metadata"]["sync_mode"])
        for ref in scenario_refs
    } == {
        ("dataset", "dataset_live_123", "live"),
        ("dataset_item", "dataset_item_live_456", "live"),
    }
    assert {ref["metadata"]["dataset_name"] for ref in scenario_refs} == {dataset_name}


# Zero-width characters are invisible and survive str.strip(), so they count as blank.
BLANK_TEXTS = ["", "   ", "\n\t", "\u200b", "\u200c\u200d", " \u2060\ufeff\n"]


def test_agent_version_rejects_blank_instructions() -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Blank Instructions Agent", "intent": "Answer billing questions."},
    ).json()["agent"]
    versions_path = f"/api/projects/project_default/agent-designs/{agent['id']}/versions"

    for blank in BLANK_TEXTS:
        response = client.post(versions_path, json={"instructions": blank})
        assert response.status_code == 422, repr(blank)

    omitted = client.post(versions_path, json={"version_label": "v0"})
    assert omitted.status_code == 201
    assert omitted.json()["instructions"] == "Answer billing questions."

    padded = client.post(versions_path, json={"instructions": "  Be brief.  "})
    assert padded.status_code == 201
    assert padded.json()["instructions"] == "Be brief."


def test_agent_design_rejects_blank_intent() -> None:
    client = TestClient(app)
    designs_path = "/api/projects/project_default/agent-designs"

    for blank in BLANK_TEXTS:
        response = client.post(designs_path, json={"name": "Blank Intent Agent", "intent": blank})
        assert response.status_code == 422, repr(blank)

    agent = client.post(
        designs_path,
        json={"name": "Blank Intent Agent", "intent": "  Answer billing questions.  "},
    ).json()["agent"]
    assert agent["intent"] == "Answer billing questions."
    agent_path = f"{designs_path}/{agent['id']}"

    for blank in BLANK_TEXTS:
        response = client.patch(agent_path, json={"intent": blank})
        assert response.status_code == 422, repr(blank)

    renamed = client.patch(agent_path, json={"name": "Renamed Agent"})
    assert renamed.status_code == 200
    assert renamed.json()["intent"] == "Answer billing questions."

    version = client.post(f"{agent_path}/versions", json={})
    assert version.status_code == 201
    assert version.json()["instructions"] == "Answer billing questions."


def test_eval_contract_fields_generate_deterministic_checks() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Data Contract Agent",
            "intent": "Gather evidence and recommend a safe next action.",
        },
    )
    agent = create_response.json()["agent"]
    version = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/versions",
        json={"version_label": "v0", "status": "baseline"},
    ).json()
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Data-driven scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract_response = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Data-driven contract",
            "scenario_id": scenario["id"],
            "required_evidence": ["evidence"],
            "required_tools": ["collect_design_intent"],
            "forbidden_tools": ["get_weather"],
            "forbidden_behavior": ["refund everyone"],
            "output_requirements": ["safe next action"],
        },
    )

    assert contract_response.status_code == 201
    contract = contract_response.json()
    assert [check["id"] for check in contract["checks"]] == [
        "requires_evidence_1",
        "requires_tool_collect_design_intent",
        "forbids_tool_get_weather",
        "forbids_behavior_1",
        "requires_output_1",
    ]

    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "agent_version_id": version["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
            "mode": "mock",
        },
    ).json()
    eval_response = client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={"eval_contract_id": contract["id"], "judge_mode": "deterministic"},
    )

    assert eval_response.status_code == 201
    eval_result = eval_response.json()
    assert eval_result["passed"] is True
    assert {check["check_type"] for check in eval_result["checks"]} == {
        "output_contains",
        "output_not_contains",
        "tool_called",
        "tool_not_called",
    }
    assert any(
        "Tool\ncollect_design_intent" in check["observed"]
        for check in eval_result["checks"]
        if check["check_type"] == "tool_called"
    )


def test_agent_design_from_outcome_creates_v0_test_and_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        api_main,
        "_draft_agent_plan_from_llm",
        lambda outcome, tools: {
            "name": "Rental Search Agent",
            "intent": f"Search for apartments: {outcome}",
            "output_focus": "Return a concise list of matching rentals with concrete details.",
            "output_requirements": ["apartment", "source"],
            "allowed_tools": [t for t in tools if t in {"call_http_api", "browse_webpage"}],
            "required_tools": ["browse_webpage"] if "browse_webpage" in tools else [],
        },
    )
    client = TestClient(app)
    response = client.post(
        "/api/projects/project_default/agent-designs/from-outcome",
        json={"outcome": "Give me a list of apartments in Greenwich CT from Zillow."},
    )

    assert response.status_code == 201
    payload = response.json()
    agent = payload["agent"]
    version = payload["version"]
    scenario = payload["scenario"]
    contract = payload["eval_contract"]

    assert agent["name"] == "Rental Search Agent"
    assert set(agent["allowed_tool_names"]) >= {"call_http_api", "browse_webpage"}
    assert version["version_label"] == "v0"
    assert version["status"] == "baseline"
    assert set(version["tool_policy"]["allowed_tool_names"]) >= {"call_http_api", "browse_webpage"}
    assert scenario["input"] == "Give me a list of apartments in Greenwich CT from Zillow."
    assert scenario["agent_design_id"] == agent["id"]
    assert contract["scenario_id"] == scenario["id"]
    assert contract["required_tools"] == ["browse_webpage"]
    assert "apartment" in contract["output_requirements"]
    assert any(check["type"] == "rubric_judge" for check in contract["checks"])
    assert any("Do not mark the task complete" in item for item in contract["expected_behavior"])

    artifacts_response = client.get("/api/projects/project_default/artifacts")
    artifact_types = {
        artifact["artifact_type"]
        for artifact in artifacts_response.json()
        if artifact["agent_design_id"] == agent["id"]
    }
    assert {"AGENT_DESIGN", "AGENT_VERSION", "SCENARIO", "EVAL_CONTRACT"} <= artifact_types


def test_eval_contract_requires_matching_scenario_agent() -> None:
    client = TestClient(app)
    first_agent_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "First", "intent": "First intent."},
    )
    second_agent_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Second", "intent": "Second intent."},
    )
    first_agent = first_agent_response.json()["agent"]
    second_agent = second_agent_response.json()["agent"]
    scenario_response = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": first_agent["id"],
            "name": "First scenario",
            "input": "Input for first agent.",
        },
    )
    scenario = scenario_response.json()

    response = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": second_agent["id"],
            "name": "Mismatched contract",
            "scenario_id": scenario["id"],
        },
    )

    assert response.status_code == 400


def test_judge_prompt_template_links_to_eval_contract_artifact() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Judge Prompt Agent",
            "intent": "Answer with evidence.",
        },
    )
    agent = create_response.json()["agent"]
    template_response = client.post(
        "/api/projects/project_default/judge-prompt-templates",
        json={
            "name": "Evidence Judge",
            "description": "Scores grounded answers.",
            "template": "Score the response against the contract evidence.",
        },
    )

    assert template_response.status_code == 201
    template = template_response.json()

    contract_response = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Evidence contract",
            "judge_prompt_template_id": template["id"],
        },
    )

    assert contract_response.status_code == 201
    contract = contract_response.json()
    assert contract["judge_prompt_template_id"] == template["id"]

    artifacts_response = client.get("/api/projects/project_default/artifacts")
    artifacts = artifacts_response.json()
    prompt_artifact = next(
        artifact
        for artifact in artifacts
        if artifact["artifact_type"] == "JUDGE_PROMPT_TEMPLATE"
        and artifact["artifact_id"] == template["id"]
    )
    contract_artifact = next(
        artifact
        for artifact in artifacts
        if artifact["artifact_type"] == "EVAL_CONTRACT"
        and artifact["artifact_id"] == contract["id"]
    )
    links_response = client.get(
        f"/api/projects/project_default/artifacts/{contract_artifact['id']}/links"
    )

    assert links_response.status_code == 200
    assert any(
        link["relationship_type"] == "USES"
        and link["target_artifact_id"] == prompt_artifact["id"]
        for link in links_response.json()
    )


def test_eval_contract_requires_known_judge_prompt_template() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Missing Judge Prompt Agent", "intent": "Answer with evidence."},
    )
    agent = create_response.json()["agent"]

    response = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Broken contract",
            "judge_prompt_template_id": "judge_prompt_missing",
        },
    )

    assert response.status_code == 404


def test_create_gate_definition_creates_gate_artifact() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Gate Agent", "intent": "Improve only with evidence."},
    )
    agent = create_response.json()["agent"]
    design_artifact = create_response.json()["artifact"]

    gate_response = client.post(
        "/api/projects/project_default/gates",
        json={
            "agent_design_id": agent["id"],
            "name": "Promotion readiness",
            "criteria": ["candidate passes eval", "no open failures"],
            "required_artifact_types": ["EVAL_RESULT", "COMPARISON"],
            "threshold": "all_criteria_met",
            "approval_mode": "manual",
        },
    )

    assert gate_response.status_code == 201
    gate = gate_response.json()
    assert gate["agent_design_id"] == agent["id"]
    assert gate["criteria"] == ["candidate passes eval", "no open failures"]
    assert gate["required_artifact_types"] == ["EVAL_RESULT", "COMPARISON"]

    list_response = client.get(
        "/api/projects/project_default/gates",
        params={"agent_design_id": agent["id"]},
    )
    get_response = client.get(f"/api/projects/project_default/gates/{gate['id']}")
    artifacts_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "GATE"},
    )

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == gate["id"]
    assert get_response.status_code == 200
    assert get_response.json()["id"] == gate["id"]
    gate_artifact = artifacts_response.json()[0]
    assert gate_artifact["artifact_type"] == "GATE"
    assert gate_artifact["artifact_id"] == gate["id"]
    links_response = client.get(
        f"/api/projects/project_default/artifacts/{gate_artifact['id']}/links"
    )
    assert any(
        link["target_artifact_id"] == design_artifact["id"]
        and link["relationship_type"] == "GENERATED_FROM"
        for link in links_response.json()
    )


def test_gate_definition_requires_known_agent_design() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/projects/project_default/gates",
        json={
            "agent_design_id": "agent_missing",
            "name": "Missing agent gate",
        },
    )

    assert response.status_code == 404


def test_gate_decision_passes_with_required_eval_evidence() -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Passing Gate Agent", "intent": "Gather evidence."},
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Passing gate scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Passing gate contract",
            "scenario_id": scenario["id"],
            "checks": [
                {
                    "id": "mentions_evidence",
                    "type": "output_contains",
                    "value": "evidence",
                }
            ],
        },
    ).json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()
    eval_result = client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={"judge_mode": "deterministic"},
    ).json()
    gate = client.post(
        "/api/projects/project_default/gates",
        json={
            "agent_design_id": agent["id"],
            "name": "Passing promotion gate",
            "required_artifact_types": ["EVAL_RESULT"],
            "blocking_failure_statuses": ["open"],
        },
    ).json()

    decision_response = client.post(
        f"/api/projects/project_default/gates/{gate['id']}/decisions",
        json={"eval_result_id": eval_result["id"]},
    )

    assert decision_response.status_code == 201
    decision = decision_response.json()
    assert decision["decision"] == "passed"
    assert decision["missing_artifact_types"] == []
    assert decision["blocking_failure_packet_ids"] == []
    assert eval_result["artifact_ids"][0] in decision["evidence_artifact_ids"]
    decisions_response = client.get(
        "/api/projects/project_default/gate-decisions",
        params={"agent_design_id": agent["id"]},
    )
    assert decisions_response.json()[0]["id"] == decision["id"]
    artifact_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "GATE_DECISION"},
    )
    assert artifact_response.json()[0]["artifact_id"] == decision["id"]


def test_gate_decision_blocks_on_open_failure_packet() -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Blocking Gate Agent", "intent": "Gather evidence."},
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Blocking gate scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Blocking gate contract",
            "scenario_id": scenario["id"],
            "checks": [
                {
                    "id": "requires_missing_phrase",
                    "type": "output_contains",
                    "value": "purple elephant",
                }
            ],
        },
    ).json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()
    eval_result = client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={"judge_mode": "deterministic"},
    ).json()
    failure_packet = client.get(
        "/api/projects/project_default/failure-packets",
        params={"agent_design_id": agent["id"]},
    ).json()[0]
    gate = client.post(
        "/api/projects/project_default/gates",
        json={
            "agent_design_id": agent["id"],
            "name": "Blocking promotion gate",
            "required_artifact_types": ["EVAL_RESULT"],
            "blocking_failure_statuses": ["open"],
        },
    ).json()

    decision_response = client.post(
        f"/api/projects/project_default/gates/{gate['id']}/decisions",
        json={"eval_result_id": eval_result["id"]},
    )

    assert decision_response.status_code == 201
    decision = decision_response.json()
    assert decision["decision"] == "blocked"
    assert decision["blocking_failure_packet_ids"] == [failure_packet["id"]]
    assert "Blocking failure packets remain" in decision["rationale"]


def _fix_loop_for_gate(client: TestClient, name: str) -> dict:
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": name, "intent": "Gather evidence."},
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": f"{name} scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": f"{name} contract",
            "scenario_id": scenario["id"],
            "checks": [
                {
                    "id": "requires_fixed_phrase",
                    "type": "output_contains",
                    "value": "fixed phrase",
                }
            ],
        },
    ).json()
    gate = client.post(
        "/api/projects/project_default/gates",
        json={
            "agent_design_id": agent["id"],
            "name": f"{name} gate",
            "required_artifact_types": ["EVAL_RESULT"],
            "blocking_failure_statuses": ["open"],
        },
    ).json()

    def version(label: str, instructions: str, parent_id: Optional[str] = None) -> dict:
        return client.post(
            f"/api/projects/project_default/agent-designs/{agent['id']}/versions",
            json={
                "version_label": label,
                "parent_version_id": parent_id,
                "instructions": instructions,
            },
        ).json()

    def run_and_evaluate(version_id: str) -> tuple:
        run = client.post(
            "/api/projects/project_default/runs",
            json={
                "agent_design_id": agent["id"],
                "agent_version_id": version_id,
                "scenario_id": scenario["id"],
                "eval_contract_id": contract["id"],
            },
        ).json()
        eval_result = client.post(
            f"/api/projects/project_default/runs/{run['id']}/evaluate",
            json={"judge_mode": "deterministic"},
        ).json()
        return run, eval_result

    def compare(baseline_run: dict, candidate_run: dict) -> dict:
        return client.post(
            "/api/projects/project_default/comparisons",
            json={
                "baseline_run_id": baseline_run["id"],
                "candidate_run_id": candidate_run["id"],
                "eval_contract_id": contract["id"],
            },
        ).json()

    def packets() -> List[dict]:
        return client.get(
            "/api/projects/project_default/failure-packets",
            params={"agent_design_id": agent["id"]},
        ).json()

    def decide(**payload: str) -> dict:
        response = client.post(
            f"/api/projects/project_default/gates/{gate['id']}/decisions",
            json=payload,
        )
        assert response.status_code == 201
        return response.json()

    return {
        "version": version,
        "run_and_evaluate": run_and_evaluate,
        "compare": compare,
        "packets": packets,
        "decide": decide,
        "gate": gate,
    }


def test_gate_decision_passes_after_comparison_fixes_failure_packet() -> None:
    loop = _fix_loop_for_gate(TestClient(app), "Fixed Gate Agent")
    v0 = loop["version"]("v0", "Answer with evidence only.")
    v1 = loop["version"]("v1", "Answer with evidence and include fixed phrase.", v0["id"])
    v0_run, v0_eval = loop["run_and_evaluate"](v0["id"])
    v1_run, v1_eval = loop["run_and_evaluate"](v1["id"])
    assert v0_eval["passed"] is False
    assert v1_eval["passed"] is True
    [v0_packet] = loop["packets"]()
    comparison = loop["compare"](v0_run, v1_run)
    assert comparison["fixed_failure_packet_ids"] == [v0_packet["id"]]

    decision = loop["decide"](
        eval_result_id=v1_eval["id"], comparison_id=comparison["id"]
    )

    assert decision["decision"] == "passed"
    assert decision["blocking_failure_packet_ids"] == []
    assert f"Judged version v1 ({v1['id']})." in decision["rationale"]
    assert f"Ignored as fixed by {comparison['id']}: {v0_packet['id']}" in decision["rationale"]


def test_gate_decision_passes_after_fix_when_baseline_run_was_evaluated_twice() -> None:
    client = TestClient(app)
    loop = _fix_loop_for_gate(client, "Twice Evaluated Gate Agent")
    v0 = loop["version"]("v0", "Answer with evidence only.")
    v1 = loop["version"]("v1", "Answer with evidence and include fixed phrase.", v0["id"])
    v0_run, _ = loop["run_and_evaluate"](v0["id"])
    second_eval = client.post(
        f"/api/projects/project_default/runs/{v0_run['id']}/evaluate",
        json={"judge_mode": "deterministic"},
    ).json()
    assert second_eval["passed"] is False
    v1_run, v1_eval = loop["run_and_evaluate"](v1["id"])
    assert v1_eval["passed"] is True
    v0_packet_ids = sorted(packet["id"] for packet in loop["packets"]())
    assert len(v0_packet_ids) == 2

    comparison = loop["compare"](v0_run, v1_run)
    assert sorted(comparison["fixed_failure_packet_ids"]) == v0_packet_ids

    decision = loop["decide"](
        eval_result_id=v1_eval["id"], comparison_id=comparison["id"]
    )

    assert decision["decision"] == "passed"
    assert decision["blocking_failure_packet_ids"] == []


def test_comparison_uses_newest_eval_when_runs_were_evaluated_twice() -> None:
    client = TestClient(app)
    loop = _fix_loop_for_gate(client, "Newest Eval Comparison Agent")
    v0 = loop["version"]("v0", "Answer with evidence only.")
    v1 = loop["version"]("v1", "Answer with evidence and include fixed phrase.", v0["id"])
    v0_run, _ = loop["run_and_evaluate"](v0["id"])
    v1_run, _ = loop["run_and_evaluate"](v1["id"])
    newest_v0_eval = client.post(
        f"/api/projects/project_default/runs/{v0_run['id']}/evaluate",
        json={"judge_mode": "deterministic"},
    ).json()
    newest_v1_eval = client.post(
        f"/api/projects/project_default/runs/{v1_run['id']}/evaluate",
        json={"judge_mode": "deterministic"},
    ).json()

    comparison = loop["compare"](v0_run, v1_run)

    assert comparison["baseline_eval_result_id"] == newest_v0_eval["id"]
    assert comparison["candidate_eval_result_id"] == newest_v1_eval["id"]
    decision = loop["decide"](
        eval_result_id=newest_v1_eval["id"], comparison_id=comparison["id"]
    )
    assert decision["decision"] == "passed"


def test_gate_decision_passes_after_fix_when_baseline_version_failed_twice() -> None:
    loop = _fix_loop_for_gate(TestClient(app), "Twice Failing Baseline Gate Agent")
    v0 = loop["version"]("v0", "Answer with evidence only.")
    v1 = loop["version"]("v1", "Answer with evidence and include fixed phrase.", v0["id"])
    v0_run, _ = loop["run_and_evaluate"](v0["id"])
    loop["run_and_evaluate"](v0["id"])
    v1_run, v1_eval = loop["run_and_evaluate"](v1["id"])
    v0_packet_ids = sorted(packet["id"] for packet in loop["packets"]())
    assert len(v0_packet_ids) == 2

    comparison = loop["compare"](v0_run, v1_run)
    assert sorted(comparison["fixed_failure_packet_ids"]) == v0_packet_ids

    decision = loop["decide"](
        eval_result_id=v1_eval["id"], comparison_id=comparison["id"]
    )

    assert decision["decision"] == "passed"


def test_comparison_keeps_packets_without_candidate_evidence_remaining() -> None:
    client = TestClient(app)
    loop = _fix_loop_for_gate(client, "Unproven Fix Gate Agent")
    v0 = loop["version"]("v0", "Answer with evidence only.")
    v1 = loop["version"]("v1", "Answer with evidence and include fixed phrase.", v0["id"])
    v0_run, v0_eval = loop["run_and_evaluate"](v0["id"])
    [old_check_packet] = loop["packets"]()
    hand_filed_packet = client.post(
        "/api/projects/project_default/failure-packets",
        json={
            "agent_design_id": v0_run["agent_design_id"],
            "agent_version_id": v0["id"],
            "run_id": v0_run["id"],
            "eval_result_id": v0_eval["id"],
            "eval_contract_id": v0_eval["eval_contract_id"],
            "title": "Hand-filed failure",
            "diagnosis": "Reviewer saw a problem no check covers.",
        },
    ).json()
    assert hand_filed_packet["failed_check_ids"] == []
    checks_response = client.patch(
        f"/api/projects/project_default/eval-contracts/{v0_eval['eval_contract_id']}/checks",
        json={
            "checks": [
                {"id": "requires_new_phrase", "type": "output_contains", "value": "fixed phrase"}
            ]
        },
    )
    assert checks_response.status_code == 200
    v1_run, v1_eval = loop["run_and_evaluate"](v1["id"])
    assert v1_eval["passed"] is True

    comparison = loop["compare"](v0_run, v1_run)

    assert comparison["fixed_failure_packet_ids"] == []
    assert sorted(comparison["remaining_failure_packet_ids"]) == sorted(
        [old_check_packet["id"], hand_filed_packet["id"]]
    )


def test_comparison_keeps_packet_remaining_when_check_was_edited_under_same_id() -> None:
    client = TestClient(app)
    loop = _fix_loop_for_gate(client, "Edited Check Gate Agent")
    v0 = loop["version"]("v0", "Answer with evidence only.")
    v1 = loop["version"]("v1", "Answer with evidence only, again.", v0["id"])
    v0_run, v0_eval = loop["run_and_evaluate"](v0["id"])
    assert v0_eval["passed"] is False
    [packet] = loop["packets"]()
    assert packet["failed_check_ids"] == ["requires_fixed_phrase"]
    checks_response = client.patch(
        f"/api/projects/project_default/eval-contracts/{v0_eval['eval_contract_id']}/checks",
        json={
            "checks": [
                {"id": "requires_fixed_phrase", "type": "output_contains", "value": "evidence"}
            ]
        },
    )
    assert checks_response.status_code == 200
    v1_run, v1_eval = loop["run_and_evaluate"](v1["id"])
    assert v1_eval["passed"] is True

    comparison = loop["compare"](v0_run, v1_run)

    assert comparison["fixed_failure_packet_ids"] == []
    assert comparison["remaining_failure_packet_ids"] == [packet["id"]]


def test_gate_decision_rationale_labels_eval_only_version() -> None:
    loop = _fix_loop_for_gate(TestClient(app), "Eval Only Gate Agent")
    v0 = loop["version"]("v0", "Answer with evidence and include fixed phrase.")
    _, v0_eval = loop["run_and_evaluate"](v0["id"])

    decision = loop["decide"](eval_result_id=v0_eval["id"])

    assert f"Judged version v0 ({v0['id']})." in decision["rationale"]


def test_gate_decision_rejects_eval_and_comparison_for_different_versions() -> None:
    client = TestClient(app)
    loop = _fix_loop_for_gate(client, "Mismatched Gate Agent")
    v0 = loop["version"]("v0", "Answer with evidence only.")
    v1 = loop["version"]("v1", "Answer with evidence and include fixed phrase.", v0["id"])
    v2 = loop["version"]("v2", "Answer with evidence only, again.", v1["id"])
    v0_run, _ = loop["run_and_evaluate"](v0["id"])
    v1_run, _ = loop["run_and_evaluate"](v1["id"])
    _, v2_eval = loop["run_and_evaluate"](v2["id"])
    comparison = loop["compare"](v0_run, v1_run)

    response = client.post(
        f"/api/projects/project_default/gates/{loop['gate']['id']}/decisions",
        json={"eval_result_id": v2_eval["id"], "comparison_id": comparison["id"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Gate decision eval result must be the comparison's candidate eval result."
    )


def test_gate_decision_blocks_when_candidate_still_fails() -> None:
    loop = _fix_loop_for_gate(TestClient(app), "Still Failing Gate Agent")
    v0 = loop["version"]("v0", "Answer with evidence only.")
    v1 = loop["version"]("v1", "Answer with evidence, still no phrase.", v0["id"])
    v0_run, _ = loop["run_and_evaluate"](v0["id"])
    v1_run, v1_eval = loop["run_and_evaluate"](v1["id"])
    assert v1_eval["passed"] is False
    comparison = loop["compare"](v0_run, v1_run)
    assert comparison["fixed_failure_packet_ids"] == []

    decision = loop["decide"](
        eval_result_id=v1_eval["id"], comparison_id=comparison["id"]
    )

    assert decision["decision"] == "blocked"
    assert decision["blocking_failure_packet_ids"] == [
        packet["id"] for packet in loop["packets"]() if packet["agent_version_id"] == v1["id"]
    ]


def test_gate_decision_ignores_unfixed_sibling_version_packet() -> None:
    loop = _fix_loop_for_gate(TestClient(app), "Sibling Gate Agent")
    v0 = loop["version"]("v0", "Answer with evidence only.")
    v1 = loop["version"]("v1", "Answer with evidence and include fixed phrase.", v0["id"])
    sibling = loop["version"]("v1-alt", "Answer with evidence, other attempt.", v0["id"])
    v0_run, _ = loop["run_and_evaluate"](v0["id"])
    v1_run, v1_eval = loop["run_and_evaluate"](v1["id"])
    _, sibling_eval = loop["run_and_evaluate"](sibling["id"])
    assert sibling_eval["passed"] is False
    sibling_packet = next(
        packet
        for packet in loop["packets"]()
        if packet["eval_result_id"] == sibling_eval["id"]
    )
    comparison = loop["compare"](v0_run, v1_run)

    decision = loop["decide"](
        eval_result_id=v1_eval["id"], comparison_id=comparison["id"]
    )

    assert decision["decision"] == "passed"
    assert decision["blocking_failure_packet_ids"] == []
    assert sibling_packet["id"] not in decision["rationale"]


def test_create_agent_versions_for_baseline_and_candidate() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Versioned Agent",
            "intent": "Baseline instructions.",
            "allowed_tool_names": ["get_weather"],
        },
    )
    agent = create_response.json()["agent"]

    baseline_response = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/versions",
        json={"version_label": "v0", "status": "baseline"},
    )

    assert baseline_response.status_code == 201
    baseline = baseline_response.json()
    assert baseline["version_label"] == "v0"
    assert baseline["instructions"] == "Baseline instructions."
    assert baseline["tool_policy"] == {"allowed_tool_names": ["get_weather"]}

    candidate_response = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/versions",
        json={
            "version_label": "v1",
            "parent_version_id": baseline["id"],
            "instructions": "Improved instructions.",
        },
    )

    assert candidate_response.status_code == 201
    candidate = candidate_response.json()
    assert candidate["parent_version_id"] == baseline["id"]
    assert candidate["instructions"] == "Improved instructions."

    versions_response = client.get(
        f"/api/projects/project_default/agent-designs/{agent['id']}/versions"
    )
    version_labels = [version["version_label"] for version in versions_response.json()]
    assert version_labels == ["v0", "v1"]

    artifact_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "AGENT_VERSION"},
    )
    assert artifact_response.status_code == 200
    assert len(artifact_response.json()) == 2


def test_auto_agent_version_labels_continue_past_v1() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Iterative Agent",
            "intent": "Initial instructions.",
        },
    )
    agent = create_response.json()["agent"]

    baseline_response = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/versions",
        json={"instructions": "Initial instructions.", "status": "baseline"},
    )
    assert baseline_response.status_code == 201
    baseline = baseline_response.json()

    first_candidate_response = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/versions",
        json={
            "parent_version_id": baseline["id"],
            "instructions": "First fix.",
        },
    )
    assert first_candidate_response.status_code == 201
    first_candidate = first_candidate_response.json()

    second_candidate_response = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/versions",
        json={
            "parent_version_id": first_candidate["id"],
            "instructions": "Second fix.",
        },
    )
    assert second_candidate_response.status_code == 201
    second_candidate = second_candidate_response.json()

    assert [
        baseline["version_label"],
        first_candidate["version_label"],
        second_candidate["version_label"],
    ] == ["v0", "v1", "v2"]
    assert first_candidate["parent_version_id"] == baseline["id"]
    assert second_candidate["parent_version_id"] == first_candidate["id"]


def test_project_scoped_run_references_version_scenario_and_contract() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Backbone Runner",
            "intent": "Gather evidence before responding.",
        },
    )
    agent = create_response.json()["agent"]
    version_response = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/versions",
        json={"version_label": "v0", "status": "baseline"},
    )
    version = version_response.json()
    scenario_response = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Backbone scenario",
            "input": "A customer reports a failed deployment.",
        },
    )
    scenario = scenario_response.json()
    contract_response = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Backbone contract",
            "scenario_id": scenario["id"],
            "expected_behavior": ["Gather evidence."],
        },
    )
    contract = contract_response.json()

    run_response = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "agent_version_id": version["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
            "mode": "mock",
        },
    )

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["agent_design_id"] == agent["id"]
    assert run["agent_version_id"] == version["id"]
    assert run["scenario_id"] == scenario["id"]
    assert run["eval_contract_id"] == contract["id"]
    assert run["mode"] == "mock"
    assert run["status"] == "completed"
    assert len(run["artifact_ids"]) == 5

    list_response = client.get(
        "/api/projects/project_default/runs",
        params={"agent_design_id": agent["id"]},
    )
    get_response = client.get(f"/api/projects/project_default/runs/{run['id']}")
    artifact_response = client.get(
        f"/api/projects/project_default/artifacts/{run['artifact_ids'][0]}"
    )

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == run["id"]
    assert get_response.status_code == 200
    assert get_response.json()["id"] == run["id"]
    assert artifact_response.status_code == 200
    assert artifact_response.json()["artifact_type"] == "RUN_RESULT"

    tool_artifacts_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "TOOL_CALL"},
    )
    assert tool_artifacts_response.status_code == 200
    assert len(tool_artifacts_response.json()) == 2


def test_project_scoped_run_requires_matching_contract_scenario() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Mismatch Runner", "intent": "Run with matching evidence."},
    )
    agent = create_response.json()["agent"]
    first_scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "First scenario",
            "input": "First input.",
        },
    ).json()
    second_scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Second scenario",
            "input": "Second input.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "First-only contract",
            "scenario_id": first_scenario["id"],
        },
    ).json()

    response = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": second_scenario["id"],
            "eval_contract_id": contract["id"],
        },
    )

    assert response.status_code == 400


def test_contract_driven_run_evaluation_creates_eval_result() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Contract Judge",
            "intent": "Gather evidence and recommend a safe next action.",
        },
    )
    agent = create_response.json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Judge scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Judge contract",
            "scenario_id": scenario["id"],
            "checks": [
                {
                    "id": "mentions_evidence",
                    "type": "output_contains",
                    "value": "evidence",
                },
                {
                    "id": "does_not_invent_refund",
                    "type": "output_not_contains",
                    "value": "refund approved",
                },
            ],
        },
    ).json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()

    eval_response = client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={"judge_mode": "deterministic"},
    )

    assert eval_response.status_code == 201
    eval_result = eval_response.json()
    assert eval_result["run_id"] == run["id"]
    assert eval_result["eval_contract_id"] == contract["id"]
    assert eval_result["mode"] == "deterministic"
    assert eval_result["score"] == 2
    assert eval_result["passed"] is True
    assert [check["check_id"] for check in eval_result["checks"]] == [
        "mentions_evidence",
        "does_not_invent_refund",
    ]
    assert eval_result["judge_output_ids"]
    assert eval_result["artifact_ids"]

    get_response = client.get(
        f"/api/projects/project_default/eval-results/{eval_result['id']}"
    )
    artifact_response = client.get(
        f"/api/projects/project_default/artifacts/{eval_result['artifact_ids'][0]}"
    )
    links_response = client.get(
        f"/api/projects/project_default/artifacts/{eval_result['artifact_ids'][0]}/links"
    )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == eval_result["id"]
    assert artifact_response.status_code == 200
    assert artifact_response.json()["artifact_type"] == "EVAL_RESULT"
    assert artifact_response.json()["external_refs"] == []
    judge_artifact_response = client.get(
        f"/api/projects/project_default/artifacts/{eval_result['artifact_ids'][1]}"
    )
    assert judge_artifact_response.status_code == 200
    assert judge_artifact_response.json()["artifact_type"] == "JUDGE_OUTPUT"
    assert judge_artifact_response.json()["external_refs"] == []
    relationship_types = {link["relationship_type"] for link in links_response.json()}
    assert "GENERATED_FROM" in relationship_types
    assert "SUPPORTED_BY" in relationship_types


def test_live_judge_evaluation_uses_prompt_template(monkeypatch) -> None:
    client = TestClient(app)
    seen_prompt = {}
    monkeypatch.setenv("EDD_ANTHROPIC_INPUT_COST_PER_1M", "1.00")
    monkeypatch.setenv("EDD_ANTHROPIC_OUTPUT_COST_PER_1M", "2.00")

    def fake_live_judge(prompt: str, trace_id: Optional[str] = None):
        seen_prompt["value"] = prompt
        seen_prompt["trace_id"] = trace_id
        return "Live judge explanation cites the provided evidence.", "test-judge-model", {
            "input_tokens": 10,
            "output_tokens": 5,
        }

    monkeypatch.setattr(api_main, "run_live_judge", fake_live_judge)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Live Judge Agent", "intent": "Answer with evidence."},
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Live judge scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    prompt_template = client.post(
        "/api/projects/project_default/judge-prompt-templates",
        json={
            "name": "Live evidence judge",
            "template": "Use this stored judge prompt and cite only supplied evidence.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Live judge contract",
            "scenario_id": scenario["id"],
            "judge_prompt_template_id": prompt_template["id"],
            "checks": [
                {
                    "id": "mentions_evidence",
                    "type": "output_contains",
                    "value": "evidence",
                }
            ],
        },
    ).json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()

    eval_response = client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={"judge_mode": "live"},
    )

    assert eval_response.status_code == 201
    eval_result = eval_response.json()
    assert eval_result["mode"] == "live"
    assert "stored judge prompt" in seen_prompt["value"]
    assert seen_prompt["trace_id"] is None
    assert run["output"] in seen_prompt["value"]
    judge_output = api_main._judge_outputs[eval_result["judge_output_ids"][0]]
    assert judge_output.model == "test-judge-model"
    assert judge_output.token_usage == {"input_tokens": 10, "output_tokens": 5}
    assert judge_output.cost_estimate == 0.00002
    judge_artifact = client.get(
        f"/api/projects/project_default/artifacts/{eval_result['artifact_ids'][1]}"
    ).json()
    assert judge_artifact["source"] == "judge:live"
    assert "Live judge explanation" in judge_artifact["body"]


def test_live_judge_verdict_marks_llm_judge_check(monkeypatch) -> None:
    client = TestClient(app)
    seen_prompt = {}

    def fake_live_judge(prompt: str, trace_id: Optional[str] = None):
        seen_prompt["value"] = prompt
        return "PASS - the reply asks for logs first.", "test-judge-model", {}

    monkeypatch.setattr(api_main, "run_live_judge", fake_live_judge)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "LLM Judge Agent", "intent": "Answer with evidence."},
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "LLM judge scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "LLM judge contract",
            "scenario_id": scenario["id"],
            "checks": [
                {
                    "id": "asks_for_logs",
                    "type": "llm_judge",
                    "value": "Asks for deployment logs before diagnosing.",
                }
            ],
        },
    ).json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()

    eval_response = client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={"judge_mode": "live"},
    )

    assert eval_response.status_code == 201
    eval_result = eval_response.json()
    assert "Asks for deployment logs before diagnosing." in seen_prompt["value"]
    assert eval_result["passed"] is True
    assert eval_result["score"] == 1
    [check] = eval_result["checks"]
    assert check["check_id"] == "asks_for_logs"
    assert check["passed"] is True
    assert check["comment"] == "Live judge marked the rubric as passed."
    assert check["explanation"] == "PASS - the reply asks for logs first."


@pytest.mark.parametrize(
    "judge_types",
    [
        ("rubric_judge", "rubric_judge"),
        ("llm_judge", "llm_judge"),
        ("rubric_judge", "llm_judge"),
    ],
)
def test_live_judge_judges_each_rubric_check_separately(monkeypatch, judge_types) -> None:
    client = TestClient(app)
    judge_prompts = []

    def fake_live_judge(prompt: str, trace_id: Optional[str] = None):
        judge_prompts.append(prompt)
        if "Rubric:\nAsks for logs." in prompt:
            return "PASS - the reply asks for logs.", "test-judge-model", {
                "input_tokens": 10,
                "output_tokens": 5,
            }
        return "FAIL - the reply is curt.", "test-judge-model", {
            "input_tokens": 20,
            "output_tokens": 7,
        }

    monkeypatch.setattr(api_main, "run_live_judge", fake_live_judge)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Two Judge Checks Agent", "intent": "Answer with evidence."},
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Two judge checks scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Two judge checks contract",
            "scenario_id": scenario["id"],
            "checks": [
                {"id": "asks_for_logs", "type": judge_types[0], "value": "Asks for logs."},
                {"id": "stays_polite", "type": judge_types[1], "value": "Stays polite."},
            ],
        },
    ).json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()

    eval_response = client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={"judge_mode": "live"},
    )

    assert eval_response.status_code == 201
    # One judge call per rubric check, each seeing only its own rubric.
    assert len(judge_prompts) == 2
    assert "Stays polite." not in judge_prompts[0]
    assert "Asks for logs." not in judge_prompts[1]
    eval_result = eval_response.json()
    logs_check, polite_check = eval_result["checks"]
    assert logs_check["check_id"] == "asks_for_logs"
    assert logs_check["passed"] is True
    assert logs_check["comment"] == "Live judge marked the rubric as passed."
    assert logs_check["explanation"] == "PASS - the reply asks for logs."
    assert polite_check["check_id"] == "stays_polite"
    assert polite_check["passed"] is False
    assert polite_check["comment"] == "Live judge marked the rubric as failed."
    assert polite_check["explanation"] == "FAIL - the reply is curt."
    assert eval_result["score"] == 1
    assert eval_result["passed"] is False
    judge_output = api_main._judge_outputs[eval_result["judge_output_ids"][0]]
    assert "asks_for_logs:\nPASS - the reply asks for logs." in judge_output.output
    assert "stays_polite:\nFAIL - the reply is curt." in judge_output.output
    assert judge_output.token_usage == {"input_tokens": 30, "output_tokens": 12}


def test_live_judge_pairs_replies_with_rubric_checks_that_share_an_id(monkeypatch) -> None:
    client = TestClient(app)

    def fake_live_judge(prompt: str, trace_id: Optional[str] = None):
        if "Rubric:\nAsks for logs." in prompt:
            return "PASS - asks for logs.", "test-judge-model", {}
        return "FAIL - curt.", "test-judge-model", {}

    monkeypatch.setattr(api_main, "run_live_judge", fake_live_judge)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Unnamed Judge Checks Agent", "intent": "Answer with evidence."},
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Unnamed judge checks scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Unnamed judge checks contract",
            "scenario_id": scenario["id"],
            "checks": [
                {"type": "rubric_judge", "value": "Asks for logs."},
                {"type": "rubric_judge", "value": "Stays polite."},
            ],
        },
    ).json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()

    eval_response = client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={"judge_mode": "live"},
    )

    assert eval_response.status_code == 201
    eval_result = eval_response.json()
    first, second = eval_result["checks"]
    assert first["passed"] is True
    assert first["explanation"] == "PASS - asks for logs."
    assert second["passed"] is False
    assert second["explanation"] == "FAIL - curt."
    judge_output = api_main._judge_outputs[eval_result["judge_output_ids"][0]]
    assert "PASS - asks for logs." in judge_output.output
    assert "FAIL - curt." in judge_output.output


def test_live_judge_requires_openai_api_key(monkeypatch) -> None:
    client = TestClient(app)

    def fake_live_judge(prompt: str, trace_id: Optional[str] = None):
        raise RuntimeError("ANTHROPIC_API_KEY is required for live Anthropic runs.")

    monkeypatch.setattr(api_main, "run_live_judge", fake_live_judge)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Missing Live Judge Key", "intent": "Answer with evidence."},
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Missing key scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Missing key contract",
            "scenario_id": scenario["id"],
        },
    ).json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()

    eval_response = client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={"judge_mode": "live"},
    )

    assert eval_response.status_code == 400
    assert "ANTHROPIC_API_KEY" in eval_response.json()["detail"]


def test_create_trace_ref_links_langfuse_trace_to_run_and_eval_artifacts() -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Trace Agent", "intent": "Gather evidence."},
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Trace scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Trace contract",
            "scenario_id": scenario["id"],
            "checks": [
                {
                    "id": "mentions_evidence",
                    "type": "output_contains",
                    "value": "evidence",
                }
            ],
        },
    ).json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()
    eval_result = client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={"judge_mode": "deterministic"},
    ).json()

    trace_response = client.post(
        "/api/projects/project_default/trace-refs",
        json={
            "provider": "langfuse",
            "external_trace_id": "trace_abc123",
            "run_id": run["id"],
            "url": "https://cloud.langfuse.com/project/demo/traces/trace_abc123",
            "metadata": {"environment": "local"},
            "related_artifact_ids": eval_result["artifact_ids"],
        },
    )

    assert trace_response.status_code == 201
    trace_ref = trace_response.json()
    assert trace_ref["agent_design_id"] == agent["id"]
    assert trace_ref["provider"] == "langfuse"
    assert trace_ref["external_trace_id"] == "trace_abc123"
    assert trace_ref["metadata"] == {"environment": "local"}

    list_response = client.get(
        "/api/projects/project_default/trace-refs",
        params={"agent_design_id": agent["id"]},
    )
    get_response = client.get(
        f"/api/projects/project_default/trace-refs/{trace_ref['id']}"
    )
    artifact_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "TRACE_REF"},
    )

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == trace_ref["id"]
    assert get_response.status_code == 200
    assert get_response.json()["id"] == trace_ref["id"]
    trace_artifact = artifact_response.json()[0]
    assert trace_artifact["artifact_id"] == trace_ref["id"]
    assert "cloud.langfuse.com" in trace_artifact["body"]
    assert trace_artifact["external_refs"] == [
        {
            "provider": "langfuse",
            "ref_type": "trace",
            "external_id": "trace_abc123",
            "url": "https://cloud.langfuse.com/project/demo/traces/trace_abc123",
            "label": "Langfuse trace",
            "metadata": {"environment": "local"},
        }
    ]

    links_response = client.get(
        f"/api/projects/project_default/artifacts/{trace_artifact['id']}/links"
    )
    relationship_types = {link["relationship_type"] for link in links_response.json()}
    assert "OBSERVES" in relationship_types
    assert "SUPPORTS" in relationship_types


def test_trace_ref_requires_known_run() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/projects/project_default/trace-refs",
        json={
            "external_trace_id": "trace_missing",
            "run_id": "run_missing",
            "url": "https://cloud.langfuse.com/project/demo/traces/trace_missing",
        },
    )

    assert response.status_code == 404


def test_create_review_note_links_to_target_artifact(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.delenv("EDD_PLATFORM_LANGFUSE_COMMENT_SYNC", raising=False)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Review Note Agent", "intent": "Gather evidence."},
    ).json()["agent"]
    design_artifact = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "AGENT_DESIGN"},
    ).json()[0]

    response = client.post(
        "/api/projects/project_default/review-notes",
        json={
            "target_artifact_id": design_artifact["id"],
            "body": "Reviewer observed the prompt needs a clearer escalation path.",
            "author": "reviewer@example.com",
            "metadata": {"review_type": "prompt"},
        },
    )

    assert response.status_code == 201
    review_note = response.json()
    assert review_note["target_artifact_id"] == design_artifact["id"]
    assert review_note["body"] == "Reviewer observed the prompt needs a clearer escalation path."
    assert review_note["author"] == "reviewer@example.com"

    list_response = client.get(
        "/api/projects/project_default/review-notes",
        params={"target_artifact_id": design_artifact["id"]},
    )
    get_response = client.get(
        f"/api/projects/project_default/review-notes/{review_note['id']}"
    )
    artifact = client.get(
        f"/api/projects/project_default/artifacts/{review_note['artifact_ids'][0]}"
    ).json()
    links_response = client.get(
        f"/api/projects/project_default/artifacts/{artifact['id']}/links"
    )

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == review_note["id"]
    assert get_response.status_code == 200
    assert get_response.json()["id"] == review_note["id"]
    assert artifact["artifact_type"] == "REVIEW_NOTE"
    assert artifact["external_refs"] == []
    assert "Reviewer observed" in artifact["body"]
    assert any(
        link["relationship_type"] == "COMMENTS_ON"
        and link["target_artifact_id"] == design_artifact["id"]
        for link in links_response.json()
    )


def test_create_review_note_live_syncs_langfuse_comment(monkeypatch) -> None:
    client = TestClient(app)
    seen_requests = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps({"id": "comment_live_123"}).encode("utf-8")

    def fake_urlopen(request, timeout):
        seen_requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setenv("EDD_PLATFORM_LANGFUSE_COMMENT_SYNC", "live")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "test-public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "test-secret")
    monkeypatch.setattr(api_main, "urlopen", fake_urlopen)

    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Comment Sync Agent", "intent": "Gather evidence."},
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Comment sync scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Comment sync contract",
            "scenario_id": scenario["id"],
        },
    ).json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()
    trace_ref = client.post(
        "/api/projects/project_default/trace-refs",
        json={
            "provider": "langfuse",
            "external_trace_id": "trace_comment_123",
            "run_id": run["id"],
            "url": "https://cloud.langfuse.com/project/demo/traces/trace_comment_123",
            "metadata": {"environment": "local"},
            "related_artifact_ids": run["artifact_ids"],
        },
    ).json()
    trace_artifact = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "TRACE_REF"},
    ).json()[0]

    response = client.post(
        "/api/projects/project_default/review-notes",
        json={
            "target_artifact_id": trace_artifact["id"],
            "body": "This trace shows the agent skipped the required escalation step.",
            "author": "platform-review",
        },
    )

    assert response.status_code == 201
    review_note = response.json()
    assert len(seen_requests) == 1
    request, timeout = seen_requests[0]
    assert timeout == 30
    assert request.full_url == "https://cloud.langfuse.com/api/public/comments"
    assert json.loads(request.data.decode("utf-8")) == {
        "objectType": "TRACE",
        "objectId": "trace_comment_123",
        "content": "This trace shows the agent skipped the required escalation step.",
    }
    assert request.headers["Authorization"].startswith("Basic ")
    assert trace_ref["external_trace_id"] == "trace_comment_123"

    artifact = client.get(
        f"/api/projects/project_default/artifacts/{review_note['artifact_ids'][0]}"
    ).json()
    assert artifact["external_refs"] == [
        {
            "provider": "langfuse",
            "ref_type": "comment",
            "external_id": "comment_live_123",
            "url": None,
            "label": "Langfuse comment",
            "metadata": {
                "sync_requested": "live",
                "object_type": "TRACE",
                "object_id": "trace_comment_123",
                "review_note_id": review_note["id"],
                "target_artifact_id": trace_artifact["id"],
                "sync_mode": "live",
            },
        }
    ]


def test_contract_driven_run_evaluation_can_fail() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Failing Judge", "intent": "Gather evidence."},
    )
    agent = create_response.json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Failing scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Failing contract",
            "scenario_id": scenario["id"],
            "checks": [
                {
                    "id": "requires_impossible_phrase",
                    "type": "output_contains",
                    "value": "purple elephant",
                }
            ],
        },
    ).json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()

    eval_response = client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={},
    )

    assert eval_response.status_code == 201
    eval_result = eval_response.json()
    assert eval_result["score"] == 0
    assert eval_result["passed"] is False
    assert eval_result["checks"][0]["passed"] is False

    packets_response = client.get(
        "/api/projects/project_default/failure-packets",
        params={"agent_design_id": agent["id"]},
    )
    assert packets_response.status_code == 200
    failure_packet = packets_response.json()[0]
    assert failure_packet["run_id"] == run["id"]
    assert failure_packet["eval_result_id"] == eval_result["id"]
    assert failure_packet["eval_contract_id"] == contract["id"]
    assert failure_packet["failed_check_ids"] == ["requires_impossible_phrase"]
    assert failure_packet["status"] == "open"

    packet_artifacts = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "FAILURE_PACKET"},
    )
    assert packet_artifacts.status_code == 200
    assert packet_artifacts.json()[0]["artifact_id"] == failure_packet["id"]

    update_response = client.patch(
        f"/api/projects/project_default/failure-packets/{failure_packet['id']}",
        json={"status": "triaged", "recommended_fix": "Add the missing behavior."},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "triaged"
    assert update_response.json()["recommended_fix"] == "Add the missing behavior."


def test_contract_driven_run_evaluation_requires_contract() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "No Contract", "intent": "Gather evidence."},
    )
    agent = create_response.json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "No contract scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
        },
    ).json()

    eval_response = client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={},
    )

    assert eval_response.status_code == 400


def test_create_failure_packet_requires_consistent_references() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Manual Failure", "intent": "Gather evidence."},
    )
    agent = create_response.json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Manual failure scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Manual failure contract",
            "scenario_id": scenario["id"],
            "checks": [
                {
                    "id": "requires_missing_phrase",
                    "type": "output_contains",
                    "value": "missing phrase",
                }
            ],
        },
    ).json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()
    eval_result = client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={},
    ).json()

    response = client.post(
        "/api/projects/project_default/failure-packets",
        json={
            "agent_design_id": agent["id"],
            "run_id": run["id"],
            "eval_result_id": eval_result["id"],
            "eval_contract_id": contract["id"],
            "failed_check_ids": ["requires_missing_phrase"],
            "title": "Manual packet",
            "diagnosis": "A reviewer added more detail.",
            "evidence_artifact_ids": eval_result["artifact_ids"],
            "recommended_fix": "Constrain the output.",
        },
    )

    assert response.status_code == 201
    packet = response.json()
    assert packet["title"] == "Manual packet"
    assert packet["evidence_artifact_ids"] == eval_result["artifact_ids"]


def test_create_fix_proposal_links_to_failure_packet_evidence() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Fixable Agent", "intent": "Gather evidence."},
    )
    agent = create_response.json()["agent"]
    baseline = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/versions",
        json={"version_label": "v0"},
    ).json()
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Fix proposal scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Fix proposal contract",
            "scenario_id": scenario["id"],
            "checks": [
                {
                    "id": "requires_missing_phrase",
                    "type": "output_contains",
                    "value": "missing phrase",
                }
            ],
        },
    ).json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "agent_version_id": baseline["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()
    eval_result = client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={},
    ).json()
    failure_packet = client.get(
        "/api/projects/project_default/failure-packets",
        params={"agent_design_id": agent["id"]},
    ).json()[0]

    response = client.post(
        "/api/projects/project_default/fix-proposals",
        json={
            "agent_design_id": agent["id"],
            "target_version_id": baseline["id"],
            "title": "Add missing phrase behavior",
            "rationale": "The baseline failed the explicit contract check.",
            "proposed_changes": [
                {
                    "surface": "instructions",
                    "change": "Require the agent to include the missing phrase.",
                }
            ],
            "addressed_failure_packet_ids": [failure_packet["id"]],
            "validation_contract_ids": [contract["id"]],
        },
    )

    assert response.status_code == 201
    proposal = response.json()
    assert proposal["target_version_id"] == baseline["id"]
    assert proposal["addressed_failure_packet_ids"] == [failure_packet["id"]]
    assert proposal["validation_contract_ids"] == [contract["id"]]
    assert proposal["status"] == "proposed"

    list_response = client.get(
        "/api/projects/project_default/fix-proposals",
        params={"agent_design_id": agent["id"]},
    )
    get_response = client.get(
        f"/api/projects/project_default/fix-proposals/{proposal['id']}"
    )
    artifact_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "FIX_PROPOSAL"},
    )

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == proposal["id"]
    assert get_response.status_code == 200
    assert get_response.json()["id"] == proposal["id"]
    artifact = artifact_response.json()[0]
    assert artifact["artifact_id"] == proposal["id"]

    links_response = client.get(
        f"/api/projects/project_default/artifacts/{artifact['id']}/links"
    )
    assert links_response.status_code == 200
    assert "ADDRESSES" in {
        link["relationship_type"] for link in links_response.json()
    }

    update_response = client.patch(
        f"/api/projects/project_default/fix-proposals/{proposal['id']}",
        json={"status": "accepted", "rationale": "Ready to create a candidate."},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "accepted"
    assert update_response.json()["rationale"] == "Ready to create a candidate."


def test_create_fix_proposal_requires_consistent_references() -> None:
    client = TestClient(app)
    first_agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "First Fix Agent", "intent": "Gather evidence."},
    ).json()["agent"]
    second_agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Second Fix Agent", "intent": "Gather evidence."},
    ).json()["agent"]
    other_version = client.post(
        f"/api/projects/project_default/agent-designs/{second_agent['id']}/versions",
        json={"version_label": "v0"},
    ).json()

    response = client.post(
        "/api/projects/project_default/fix-proposals",
        json={
            "agent_design_id": first_agent["id"],
            "target_version_id": other_version["id"],
            "title": "Bad proposal",
            "rationale": "References another agent.",
            "proposed_changes": [],
        },
    )

    assert response.status_code == 400


def test_fix_proposal_rejects_blank_instructions_change() -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Blank Fix Agent", "intent": "Gather evidence."},
    ).json()["agent"]
    payload = {
        "agent_design_id": agent["id"],
        "title": "Blank fix",
        "rationale": "Instructions left blank.",
    }
    blank_changes = [
        [{"surface": "instructions", "change": "   "}],
        [{"surface": "instructions", "change": "\u200b\n"}],
    ]

    for changes in blank_changes:
        response = client.post(
            "/api/projects/project_default/fix-proposals",
            json={**payload, "proposed_changes": changes},
        )
        assert response.status_code == 422, changes

    proposal = client.post(
        "/api/projects/project_default/fix-proposals",
        json={
            **payload,
            "proposed_changes": [{"surface": "instructions", "change": "Ask for a plan."}],
        },
    ).json()
    for changes in blank_changes:
        response = client.patch(
            f"/api/projects/project_default/fix-proposals/{proposal['id']}",
            json={"proposed_changes": changes},
        )
        assert response.status_code == 422, changes

    stored = client.get(
        f"/api/projects/project_default/fix-proposals/{proposal['id']}"
    ).json()
    assert stored["proposed_changes"] == [
        {"surface": "instructions", "change": "Ask for a plan."}
    ]


def test_create_comparison_summarizes_baseline_and_candidate_failures() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Comparable Agent", "intent": "Gather evidence."},
    )
    agent = create_response.json()["agent"]
    baseline = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/versions",
        json={
            "version_label": "v0",
            "instructions": "Answer with evidence only.",
        },
    ).json()
    candidate = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/versions",
        json={
            "version_label": "v1",
            "parent_version_id": baseline["id"],
            "instructions": "Answer with evidence and include fixed phrase.",
        },
    ).json()
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Comparison scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Comparison contract",
            "scenario_id": scenario["id"],
            "checks": [
                {
                    "id": "requires_fixed_phrase",
                    "type": "output_contains",
                    "value": "fixed phrase",
                }
            ],
        },
    ).json()
    baseline_run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "agent_version_id": baseline["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()
    baseline_eval = client.post(
        f"/api/projects/project_default/runs/{baseline_run['id']}/evaluate",
        json={},
    ).json()
    baseline_packet = client.get(
        "/api/projects/project_default/failure-packets",
        params={"agent_design_id": agent["id"]},
    ).json()[0]
    candidate_run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "agent_version_id": candidate["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()
    candidate_eval = client.post(
        f"/api/projects/project_default/runs/{candidate_run['id']}/evaluate",
        json={},
    ).json()

    response = client.post(
        "/api/projects/project_default/comparisons",
        json={
            "baseline_run_id": baseline_run["id"],
            "candidate_run_id": candidate_run["id"],
            "eval_contract_id": contract["id"],
        },
    )

    assert response.status_code == 201
    comparison = response.json()
    assert comparison["agent_design_id"] == agent["id"]
    assert comparison["baseline_version_id"] == baseline["id"]
    assert comparison["candidate_version_id"] == candidate["id"]
    assert comparison["baseline_eval_result_id"] == baseline_eval["id"]
    assert comparison["candidate_eval_result_id"] == candidate_eval["id"]
    assert comparison["fixed_failure_packet_ids"] == [baseline_packet["id"]]
    assert comparison["new_failure_packet_ids"] == []
    assert comparison["remaining_failure_packet_ids"] == []
    assert "fixed 1" in comparison["summary"]
    assert comparison["artifact_ids"]

    get_response = client.get(
        f"/api/projects/project_default/comparisons/{comparison['id']}"
    )
    list_response = client.get(
        "/api/projects/project_default/comparisons",
        params={"agent_design_id": agent["id"]},
    )
    eval_results_response = client.get(
        "/api/projects/project_default/eval-results",
        params={"run_id": candidate_run["id"]},
    )
    artifact_response = client.get(
        f"/api/projects/project_default/artifacts/{comparison['artifact_ids'][0]}"
    )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == comparison["id"]
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == comparison["id"]
    assert eval_results_response.status_code == 200
    assert eval_results_response.json()[0]["id"] == candidate_eval["id"]
    assert artifact_response.status_code == 200
    assert artifact_response.json()["artifact_type"] == "COMPARISON"


def test_create_comparison_requires_same_agent_scenario_and_contract() -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Invalid Comparison", "intent": "Gather evidence."},
    ).json()["agent"]
    first_scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "First comparison scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    second_scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Second comparison scenario",
            "input": "A customer asks for a refund.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Invalid comparison contract",
            "scenario_id": first_scenario["id"],
        },
    ).json()
    baseline_run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": first_scenario["id"],
            "eval_contract_id": contract["id"],
        },
    ).json()
    candidate_run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": second_scenario["id"],
        },
    ).json()

    response = client.post(
        "/api/projects/project_default/comparisons",
        json={
            "baseline_run_id": baseline_run["id"],
            "candidate_run_id": candidate_run["id"],
            "eval_contract_id": contract["id"],
        },
    )

    assert response.status_code == 400


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

    def fake_run_anthropic_agent(agent_design, scenario, config, tool_definitions):
        assert "get_weather" in agent_design.allowed_tool_names
        weather_tool = next(t for t in tool_definitions if t.name == "get_weather")
        assert weather_tool.name == "get_weather"
        assert weather_tool.input_schema["required"] == ["zip_code"]
        assert weather_tool.output_schema is not None
        assert weather_tool.implementation_kind == "builtin"
        assert weather_tool.implementation_key == "open_meteo_weather"
        assert weather_tool.status == "approved"
        return RunnerResult(
            id="run_live_fake",
            agent_design_id=agent_design.id,
            mode="live",
            scenario_input=scenario.input,
            response="Live response with evidence, assumptions, and a safe next action.",
            tool_calls=[
                RunnerToolCall(
                    name="get_weather",
                    output="Current weather: 76°F and clear sky.",
                ),
            ],
            evidence=["Used fake OpenAI provider in test."],
            trace_id="trace_scratch_fake",
            trace_url="https://cloud.langfuse.com/project/demo/traces/trace_scratch_fake",
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(api_main, "anthropic_config_from_env", fake_config_from_env)
    monkeypatch.setattr(api_main, "run_anthropic_agent", fake_run_anthropic_agent)

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
    assert "76°F" in run["artifact"]["body"]
    assert run["trace_id"] == "trace_scratch_fake"
    assert run["trace_url"] == "https://cloud.langfuse.com/project/demo/traces/trace_scratch_fake"
    assert run["trace_artifact"]["artifact_type"] == "TRACE_REF"
    assert run["trace_artifact"]["id"] in run["artifact_ids"]
    assert "trace_scratch_fake" in run["trace_artifact"]["body"]

    trace_artifacts_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "TRACE_REF"},
    )
    assert trace_artifacts_response.status_code == 200
    trace_artifact = trace_artifacts_response.json()[0]
    assert trace_artifact["id"] == run["trace_artifact"]["id"]
    assert "cloud.langfuse.com" in trace_artifact["body"]
    assert trace_artifact["external_refs"][0]["provider"] == "langfuse"
    assert trace_artifact["external_refs"][0]["ref_type"] == "trace"
    assert trace_artifact["external_refs"][0]["url"] == "https://cloud.langfuse.com/project/demo/traces/trace_scratch_fake"


def test_live_project_run_creates_trace_ref_from_runner_metadata(monkeypatch) -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Traced Live Agent",
            "intent": "Gather evidence and recommend a safe next action.",
            "langfuse_prompt_name": "edd-agent-live",
            "langfuse_prompt_label": "production",
        },
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Traced live scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    prompt_template = client.post(
        "/api/projects/project_default/judge-prompt-templates",
        json={
            "name": "Traced live judge",
            "template": "Judge only against visible evidence.",
            "langfuse_prompt_name": "edd-judge-live",
            "langfuse_prompt_version": "7",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Traced live contract",
            "scenario_id": scenario["id"],
            "judge_prompt_template_id": prompt_template["id"],
            "checks": [
                {
                    "id": "mentions_safe_next_action",
                    "type": "output_contains",
                    "value": "safe next action",
                }
            ],
        },
    ).json()

    def fake_config_from_env():
        return object()

    def fake_run_anthropic_agent(agent_design, scenario_input, config, tool_definitions):
        return RunnerResult(
            id="run_live_traced_fake",
            agent_design_id=agent_design.id,
            mode="live",
            scenario_input=scenario_input.input,
            response="Live response with evidence and a safe next action.",
            tool_calls=[RunnerToolCall(name="openai.responses", output="test-model")],
            evidence=["Used fake OpenAI provider in test."],
            trace_id="0123456789abcdef0123456789abcdef",
            trace_url="https://cloud.langfuse.com/project/demo/traces/0123456789abcdef0123456789abcdef",
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(api_main, "anthropic_config_from_env", fake_config_from_env)
    monkeypatch.setattr(api_main, "run_anthropic_agent", fake_run_anthropic_agent)

    run_response = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
            "mode": "live",
        },
    )

    assert run_response.status_code == 201
    run = run_response.json()
    trace_refs_response = client.get(
        "/api/projects/project_default/trace-refs",
        params={"run_id": run["id"]},
    )
    assert trace_refs_response.status_code == 200
    trace_refs = trace_refs_response.json()
    assert trace_refs[0]["external_trace_id"] == "0123456789abcdef0123456789abcdef"
    assert trace_refs[0]["run_id"] == run["id"]
    assert trace_refs[0]["metadata"]["runner_mode"] == "live"
    assert [
        ref["external_id"]
        for ref in trace_refs[0]["metadata"]["prompt_refs"]
    ] == ["edd-agent-live:label:production", "edd-judge-live:version:7"]

    run_artifact = client.get(
        f"/api/projects/project_default/artifacts/{run['artifact_ids'][0]}"
    ).json()
    assert [
        ref["external_id"]
        for ref in run_artifact["external_refs"]
        if ref["ref_type"] == "prompt"
    ] == ["edd-agent-live:label:production", "edd-judge-live:version:7"]

    trace_artifacts_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "TRACE_REF"},
    )
    trace_artifact = trace_artifacts_response.json()[0]
    assert "cloud.langfuse.com" in trace_artifact["body"]
    assert trace_artifact["external_refs"][0]["provider"] == "langfuse"
    assert trace_artifact["external_refs"][0]["ref_type"] == "trace"
    assert trace_artifact["external_refs"][0]["url"] == "https://cloud.langfuse.com/project/demo/traces/0123456789abcdef0123456789abcdef"
    assert [
        ref["external_id"]
        for ref in trace_artifact["external_refs"]
        if ref["ref_type"] == "prompt"
    ] == ["edd-agent-live:label:production", "edd-judge-live:version:7"]
    links_response = client.get(
        f"/api/projects/project_default/artifacts/{trace_artifact['id']}/links"
    )
    relationship_types = {link["relationship_type"] for link in links_response.json()}
    assert "OBSERVES" in relationship_types


def test_live_project_run_eval_writes_langfuse_score_refs(monkeypatch) -> None:
    client = TestClient(app)
    score_calls = []

    class FakeLangfuse:
        def create_score(self, **kwargs):
            score_calls.append(kwargs)

        def flush(self):
            score_calls.append({"flushed": True})

    def fake_config_from_env():
        return object()

    def fake_run_anthropic_agent(agent_design, scenario_input, config, tool_definitions):
        return RunnerResult(
            id="run_live_score_fake",
            agent_design_id=agent_design.id,
            mode="live",
            scenario_input=scenario_input.input,
            response="Live response with evidence and a safe next action.",
            tool_calls=[RunnerToolCall(name="openai.responses", output="test-model")],
            evidence=["Used fake OpenAI provider in test."],
            trace_id="trace_score_fake",
            trace_url="https://cloud.langfuse.com/project/demo/traces/trace_score_fake",
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setenv("EDD_PLATFORM_LANGFUSE_SCORE_SYNC", "live")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "test-public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "test-secret")
    monkeypatch.setattr(api_main, "anthropic_config_from_env", fake_config_from_env)
    monkeypatch.setattr(api_main, "run_anthropic_agent", fake_run_anthropic_agent)
    monkeypatch.setattr(api_main, "get_langfuse_client", lambda: FakeLangfuse())

    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Score Sync Agent",
            "intent": "Gather evidence and recommend a safe next action.",
        },
    ).json()["agent"]
    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "name": "Score sync scenario",
            "input": "A customer reports a failed deployment.",
        },
    ).json()
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Score sync contract",
            "scenario_id": scenario["id"],
            "checks": [
                {
                    "id": "mentions_safe_next_action",
                    "type": "output_contains",
                    "value": "safe next action",
                },
                {
                    "id": "mentions_evidence",
                    "type": "output_contains",
                    "value": "evidence",
                },
            ],
        },
    ).json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
            "mode": "live",
        },
    ).json()

    eval_response = client.post(
        f"/api/projects/project_default/runs/{run['id']}/evaluate",
        json={"judge_mode": "deterministic"},
    )

    assert eval_response.status_code == 201
    eval_result = eval_response.json()
    assert score_calls == [
        {
            "name": "edd_eval_pass_rate",
            "value": 1.0,
            "trace_id": "trace_score_fake",
            "score_id": f"score_{eval_result['id']}",
            "data_type": "NUMERIC",
            "comment": f"EDD eval {eval_result['id']}: 2/2 checks passed.",
            "metadata": {
                "project_id": "project_default",
                "agent_design_id": agent["id"],
                "agent_version_id": None,
                "run_id": run["id"],
                "scenario_id": scenario["id"],
                "eval_contract_id": contract["id"],
                "eval_result_id": eval_result["id"],
                "judge_output_id": eval_result["judge_output_ids"][0],
                "judge_mode": "deterministic",
                "raw_score": 2,
                "check_count": 2,
                "passed": True,
                "source": "edd-platform",
            },
        },
        {"flushed": True},
    ]

    eval_artifact = client.get(
        f"/api/projects/project_default/artifacts/{eval_result['artifact_ids'][0]}"
    ).json()
    judge_artifact = client.get(
        f"/api/projects/project_default/artifacts/{eval_result['artifact_ids'][1]}"
    ).json()
    for artifact in (eval_artifact, judge_artifact):
        assert artifact["external_refs"] == [
            {
                "provider": "langfuse",
                "ref_type": "score",
                "external_id": f"score_{eval_result['id']}",
                "url": None,
                "label": "Langfuse score",
                "metadata": {
                    "project_id": "project_default",
                    "agent_design_id": agent["id"],
                    "agent_version_id": None,
                    "run_id": run["id"],
                    "scenario_id": scenario["id"],
                    "eval_contract_id": contract["id"],
                    "eval_result_id": eval_result["id"],
                    "judge_output_id": eval_result["judge_output_ids"][0],
                    "judge_mode": "deterministic",
                    "raw_score": 2,
                    "check_count": 2,
                    "passed": True,
                    "source": "edd-platform",
                    "sync_mode": "live",
                    "trace_id": "trace_score_fake",
                    "score_name": "edd_eval_pass_rate",
                    "score_value": 1.0,
                },
            }
        ]

    summary_response = client.post(
        "/api/projects/project_default/evidence-summaries",
        json={"purpose": "FIX_PROPOSAL_GENERATION", "agent_design_id": agent["id"]},
    )
    assert summary_response.status_code == 201
    summary_text = summary_response.json()["summary"]
    assert "Langfuse refs:" in summary_text
    assert "Langfuse score (edd_eval_pass_rate)" in summary_text
    assert f"score_{eval_result['id']}" in summary_text


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
        raise RuntimeError("ANTHROPIC_API_KEY is required for live Anthropic runs.")

    monkeypatch.setattr(api_main, "anthropic_config_from_env", fake_config_from_env)

    response = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/runs",
        json={
            "scenario_input": "A customer reports a failed deployment.",
            "mode": "live",
        },
    )

    assert response.status_code == 400
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_extract_response_text_from_anthropic_content_block() -> None:
    payload = {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "content": [
            {"type": "text", "text": "A grounded live response."},
        ],
        "stop_reason": "end_turn",
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


def _outcome_agent_with_evaluated_baseline(client: TestClient, monkeypatch) -> dict:
    monkeypatch.setattr(
        api_main,
        "_draft_agent_plan_from_llm",
        lambda outcome, tools: {
            "name": "Wizard State Agent",
            "intent": f"Answer the request: {outcome}",
            "output_focus": "Return a concise answer.",
            "output_requirements": ["answer"],
            "allowed_tools": [],
            "required_tools": [],
        },
    )
    created = client.post(
        "/api/projects/project_default/agent-designs/from-outcome",
        json={"outcome": "Summarize the weekly deployment report."},
    )
    assert created.status_code == 201
    created = created.json()
    run = client.post(
        "/api/projects/project_default/runs",
        json={
            "agent_design_id": created["agent"]["id"],
            "agent_version_id": created["version"]["id"],
            "scenario_id": created["scenario"]["id"],
            "eval_contract_id": created["eval_contract"]["id"],
        },
    )
    assert run.status_code == 201
    eval_result = client.post(
        f"/api/projects/project_default/runs/{run.json()['id']}/evaluate",
        json={"judge_mode": "deterministic"},
    )
    assert eval_result.status_code == 201
    return {**created, "eval_result": eval_result.json()}


def _assert_matches_wizard_state_schema(client: TestClient, body: dict) -> None:
    openapi = client.get("/openapi.json").json()
    route = openapi["paths"]["/api/projects/{project_id}/agent-designs/{agent_id}/wizard-state"]
    response_schema = route["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema == {"$ref": "#/components/schemas/OutcomeAgentCreated"}
    components = openapi["components"]["schemas"]
    for field in components["OutcomeAgentCreated"]["required"]:
        assert field in body
    for field in components["ArtifactRecord"]["required"]:
        assert field in body["artifact"]
    OutcomeAgentCreated.model_validate(body)


def test_wizard_state_returns_outcome_agent_after_run_and_eval(monkeypatch) -> None:
    client = TestClient(app, raise_server_exceptions=False)
    created = _outcome_agent_with_evaluated_baseline(client, monkeypatch)
    agent_id = created["agent"]["id"]

    response = client.get(f"/api/projects/project_default/agent-designs/{agent_id}/wizard-state")

    assert response.status_code == 200
    body = response.json()
    _assert_matches_wizard_state_schema(client, body)
    assert body["agent"]["id"] == agent_id
    assert body["artifact"]["artifact_type"] == "AGENT_DESIGN"
    assert body["artifact"]["artifact_id"] == agent_id
    assert body["version"]["id"] == created["version"]["id"]
    assert body["scenario"]["id"] == created["scenario"]["id"]
    assert body["eval_contract"]["id"] == created["eval_contract"]["id"]


def test_wizard_state_returns_outcome_agent_after_failed_baseline_analysis(monkeypatch) -> None:
    client = TestClient(app, raise_server_exceptions=False)
    created = _outcome_agent_with_evaluated_baseline(client, monkeypatch)
    agent_id = created["agent"]["id"]
    eval_result = created["eval_result"]
    assert eval_result["passed"] is False
    note = client.post(
        "/api/projects/project_default/review-notes",
        json={
            "target_artifact_id": eval_result["artifact_ids"][0],
            "body": "The baseline did not answer the request.",
            "metadata": {
                "failure_mode": "missing answer",
                "severity": "high",
                "eval_result_id": eval_result["id"],
            },
        },
    )
    assert note.status_code == 201

    response = client.get(f"/api/projects/project_default/agent-designs/{agent_id}/wizard-state")

    assert response.status_code == 200
    body = response.json()
    _assert_matches_wizard_state_schema(client, body)
    assert body["agent"]["id"] == agent_id
    assert body["artifact"]["artifact_id"] == agent_id


def test_wizard_state_recreates_missing_agent_design_artifact(monkeypatch) -> None:
    client = TestClient(app, raise_server_exceptions=False)
    created = _outcome_agent_with_evaluated_baseline(client, monkeypatch)
    agent_id = created["agent"]["id"]
    missing = api_main.find_agent_design_artifact(agent_id)
    api_main._artifacts.pop(missing.id)
    before = datetime.now(timezone.utc)

    response = client.get(f"/api/projects/project_default/agent-designs/{agent_id}/wizard-state")

    assert response.status_code == 200
    body = response.json()
    _assert_matches_wizard_state_schema(client, body)
    assert body["artifact"]["id"] != missing.id
    assert body["artifact"]["artifact_type"] == "AGENT_DESIGN"
    assert body["artifact"]["artifact_id"] == agent_id
    assert datetime.fromisoformat(body["artifact"]["created_at"]) >= before
    assert api_main.find_agent_design_artifact(agent_id).id == body["artifact"]["id"]


def test_wizard_state_without_baseline_returns_404() -> None:
    client = TestClient(app)

    response = client.get(
        "/api/projects/project_default/agent-designs/agent_apartment_search/wizard-state"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Agent has no baseline version, scenario, or eval contract yet."
    )


def test_scenario_status_must_be_draft_active_or_superseded() -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Status Agent", "intent": "Answer billing questions."},
    ).json()["agent"]

    typo = client.post(
        "/api/projects/project_default/scenarios",
        json={"agent_design_id": agent["id"], "input": "Refund my order", "status": "actve"},
    )
    assert typo.status_code == 422

    scenario = client.post(
        "/api/projects/project_default/scenarios",
        json={"agent_design_id": agent["id"], "input": "Refund my order", "status": "active"},
    ).json()
    patched = client.patch(
        f"/api/projects/project_default/scenarios/{scenario['id']}",
        json={"status": "archived"},
    )
    assert patched.status_code == 422
    stored = client.get(f"/api/projects/project_default/scenarios/{scenario['id']}").json()
    assert stored["status"] == "active"


def test_scenario_name_defaults_to_start_of_input_and_can_be_patched() -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Naming Agent", "intent": "Answer billing questions."},
    ).json()["agent"]

    unnamed = client.post(
        "/api/projects/project_default/scenarios",
        json={
            "agent_design_id": agent["id"],
            "input": "Customer: Why was I charged twice this month for the same subscription plan?\nAgent: Let me check.",
        },
    )
    assert unnamed.status_code == 201
    assert unnamed.json()["name"] == "Customer: Why was I charged twice this month for the same…"

    short = client.post(
        "/api/projects/project_default/scenarios",
        json={"agent_design_id": agent["id"], "name": "  ", "input": "Refund my order"},
    ).json()
    assert short["name"] == "Refund my order"

    patched = client.patch(
        f"/api/projects/project_default/scenarios/{short['id']}",
        json={"name": "Refund request", "status": "superseded"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Refund request"
    assert patched.json()["status"] == "superseded"
    stored = client.get(f"/api/projects/project_default/scenarios/{short['id']}").json()
    assert stored["status"] == "superseded"

    missing = client.patch(
        "/api/projects/project_default/scenarios/scenario_missing",
        json={"status": "superseded"},
    )
    assert missing.status_code == 404


def test_outcome_draft_names_its_test_after_the_prompt() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/projects/project_default/agent-designs/from-outcome",
        json={"outcome": "Summarize open support tickets by severity."},
    )
    assert response.status_code == 201, response.text
    assert response.json()["scenario"]["name"] == "Summarize open support tickets by severity."


@pytest.mark.parametrize("blank", ["", "   \n\t "])
def test_outcome_draft_falls_back_to_the_outcome_when_the_llm_intent_is_blank(
    monkeypatch, blank: str
) -> None:
    plan_json = json.dumps(
        {
            "name": blank,
            "intent": blank,
            "output_focus": "Return a concise answer.",
            "output_requirements": ["answer"],
            "allowed_tools": [],
            "required_tools": [],
        }
    )

    class FakeMessages:
        def create(self, **_kwargs):
            return types.SimpleNamespace(
                content=[types.SimpleNamespace(type="text", text=plan_json)]
            )

    monkeypatch.setattr(api_main, "anthropic_config_from_env", lambda: types.SimpleNamespace(model="fake-model"))
    monkeypatch.setattr(
        api_main, "_anthropic_client", lambda _config: types.SimpleNamespace(messages=FakeMessages())
    )

    client = TestClient(app)
    response = client.post(
        "/api/projects/project_default/agent-designs/from-outcome",
        json={"outcome": "Summarize the weekly deployment report."},
    )

    assert response.status_code == 201, response.text
    agent = response.json()["agent"]
    assert agent["intent"] == "Summarize the weekly deployment report."
    assert agent["name"] == "Outcome Agent"
