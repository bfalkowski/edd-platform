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
    assert agent["allowed_tool_names"] == ["get_weather"]

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


def test_create_scenario_and_eval_contract_artifacts() -> None:
    client = TestClient(app)
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
    assert run["artifact_ids"]

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
    judge_artifact_response = client.get(
        f"/api/projects/project_default/artifacts/{eval_result['artifact_ids'][1]}"
    )
    assert judge_artifact_response.status_code == 200
    assert judge_artifact_response.json()["artifact_type"] == "JUDGE_OUTPUT"
    relationship_types = {link["relationship_type"] for link in links_response.json()}
    assert "GENERATED_FROM" in relationship_types
    assert "SUPPORTED_BY" in relationship_types


def test_live_judge_evaluation_uses_prompt_template(monkeypatch) -> None:
    client = TestClient(app)
    seen_prompt = {}
    monkeypatch.setenv("EDD_OPENAI_INPUT_COST_PER_1M", "1.00")
    monkeypatch.setenv("EDD_OPENAI_OUTPUT_COST_PER_1M", "2.00")

    def fake_live_judge(prompt: str):
        seen_prompt["value"] = prompt
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


def test_live_judge_requires_openai_api_key(monkeypatch) -> None:
    client = TestClient(app)

    def fake_live_judge(prompt: str):
        raise RuntimeError("OPENAI_API_KEY is required for live OpenAI runs.")

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
    assert "OPENAI_API_KEY" in eval_response.json()["detail"]


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
