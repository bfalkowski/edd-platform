"""llm_judge is an alias of rubric_judge everywhere a rubric check is read or written."""

from __future__ import annotations

import types
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from edd_platform_api import main as api_main
from edd_platform_api.eval_checks import contract_rubric, evaluate_contract_check
from edd_platform_api.main import app
from edd_platform_api.schemas import RunRecord

RUBRIC = "Asks for deployment logs before diagnosing."


def _run() -> RunRecord:
    now = datetime.now(timezone.utc)
    return RunRecord(
        id="run_x",
        project_id="project_default",
        agent_design_id="agent_x",
        scenario_id="scenario_x",
        eval_contract_id="contract_x",
        mode="mock",
        input="input",
        output="Please send the deployment logs.",
        status="completed",
        artifact_ids=[],
        started_at=now,
        completed_at=now,
    )


def _agent_with_llm_judge_contract(client: TestClient) -> tuple[dict, dict]:
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "LLM Judge Alias Agent", "intent": "Answer with evidence."},
    ).json()["agent"]
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "LLM judge alias contract",
            "checks": [{"id": "asks_for_logs", "type": "llm_judge", "value": RUBRIC}],
        },
    ).json()
    return agent, contract


def test_deterministic_llm_judge_check_needs_the_live_judge() -> None:
    result = evaluate_contract_check(
        check={"id": "asks_for_logs", "type": "llm_judge", "value": RUBRIC},
        run=_run(),
        evidence_artifact_ids=[],
        run_artifact_body="",
    )

    assert result.passed is False
    assert result.comment == "Live judge required for rubric checks."


def test_patch_rubric_updates_llm_judge_check() -> None:
    client = TestClient(app)
    _agent, contract = _agent_with_llm_judge_contract(client)

    response = client.patch(
        f"/api/projects/project_default/eval-contracts/{contract['id']}/rubric",
        json={"rubric": "  Cites the error code.  "},
    )

    assert response.status_code == 200
    [check] = response.json()["checks"]
    assert check["type"] == "llm_judge"
    assert check["value"] == "Cites the error code."


def test_fix_proposal_prompt_includes_llm_judge_rubric(monkeypatch) -> None:
    client = TestClient(app)
    agent, contract = _agent_with_llm_judge_contract(client)
    version = client.post(
        f"/api/projects/project_default/agent-designs/{agent['id']}/versions", json={}
    ).json()
    prompts: list[str] = []

    class FakeMessages:
        def create(self, **kwargs):
            prompts.append(kwargs["messages"][0]["content"])
            return types.SimpleNamespace(content=[types.SimpleNamespace(text="New instructions.")])

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        api_main, "_anthropic_client", lambda _config: types.SimpleNamespace(messages=FakeMessages())
    )

    response = client.post(
        "/api/projects/project_default/fix-proposals/generate",
        json={
            "agent_design_id": agent["id"],
            "target_version_id": version["id"],
            "validation_contract_id": contract["id"],
        },
    )

    assert response.status_code == 200, response.text
    [prompt] = prompts
    assert f"Success criteria (rubric): {RUBRIC}" in prompt


def test_patch_rubric_rejects_a_contract_with_two_rubric_checks() -> None:
    client = TestClient(app)
    agent = client.post(
        "/api/projects/project_default/agent-designs",
        json={"name": "Two Rubric Checks Agent", "intent": "Answer with evidence."},
    ).json()["agent"]
    checks = [
        {"id": "asks_for_logs", "type": "rubric_judge", "value": "Asks for logs."},
        {"id": "stays_polite", "type": "llm_judge", "value": "Stays polite."},
    ]
    contract = client.post(
        "/api/projects/project_default/eval-contracts",
        json={"agent_design_id": agent["id"], "name": "Two rubric checks", "checks": checks},
    ).json()

    response = client.patch(
        f"/api/projects/project_default/eval-contracts/{contract['id']}/rubric",
        json={"rubric": "Cites the error code."},
    )

    assert response.status_code == 409
    assert "/checks" in response.json()["detail"]
    stored = client.get(f"/api/projects/project_default/eval-contracts/{contract['id']}").json()
    assert stored["checks"] == checks


def test_contract_rubric_skips_a_blank_rubric() -> None:
    checks = [
        {"id": "blank", "type": "rubric_judge", "value": "   "},
        {"id": "asks_for_logs", "type": "llm_judge", "value": RUBRIC},
    ]

    assert contract_rubric(checks) == RUBRIC
