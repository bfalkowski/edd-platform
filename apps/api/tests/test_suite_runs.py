from typing import List

from fastapi.testclient import TestClient

from edd_platform_api import main as api_main
from edd_platform_api.main import app

import edd_runner  # noqa: E402  (importable once main has put the runner on sys.path)

P = "/api/projects/project_default"


def _suite_agent(client: TestClient, name: str, phrases: List[str]) -> dict:
    """An agent with one active test per phrase; each test passes when the output has its phrase.

    The mock runner echoes a version's instructions, so a version passes the
    tests whose phrases its instructions contain.
    """
    agent = client.post(
        f"{P}/agent-designs",
        json={"name": name, "intent": "Answer support questions."},
    ).json()["agent"]
    tests = []
    for phrase in phrases:
        scenario = client.post(
            f"{P}/scenarios",
            json={
                "agent_design_id": agent["id"],
                "name": f"{phrase} test",
                "input": "A customer reports a failed deployment.",
                "status": "active",
            },
        ).json()
        contract = client.post(
            f"{P}/eval-contracts",
            json={
                "agent_design_id": agent["id"],
                "name": f"{phrase} contract",
                "scenario_id": scenario["id"],
                "checks": [{"id": f"says_{phrase}", "type": "output_contains", "value": phrase}],
            },
        ).json()
        tests.append({"scenario": scenario, "contract": contract})
    gate = client.post(
        f"{P}/gates",
        json={
            "agent_design_id": agent["id"],
            "name": f"{name} gate",
            "required_artifact_types": ["EVAL_RESULT"],
            "blocking_failure_statuses": ["open"],
        },
    ).json()
    return {"agent": agent, "tests": tests, "gate": gate}


def _version(client: TestClient, agent: dict, label: str, instructions: str) -> dict:
    return client.post(
        f"{P}/agent-designs/{agent['id']}/versions",
        json={"version_label": label, "instructions": instructions},
    ).json()


def _run_suite(client: TestClient, agent: dict, version: dict) -> dict:
    response = client.post(
        f"{P}/agent-designs/{agent['id']}/versions/{version['id']}/suite-runs",
        json={"mode": "mock", "judge_mode": "deterministic"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _compare_suites(client: TestClient, baseline: dict, candidate: dict) -> dict:
    response = client.post(
        f"{P}/comparisons/suite",
        json={"baseline_version_id": baseline["id"], "candidate_version_id": candidate["id"]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _decide(client: TestClient, gate: dict, comparison: dict) -> dict:
    response = client.post(
        f"{P}/gates/{gate['id']}/decisions",
        json={"comparison_id": comparison["id"]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _outcomes(comparison: dict, setup: dict) -> List[str]:
    by_scenario = {row["scenario_id"]: row["outcome"] for row in comparison["tests"]}
    return [by_scenario[test["scenario"]["id"]] for test in setup["tests"]]


def test_suite_run_stores_one_run_and_eval_per_active_test() -> None:
    client = TestClient(app)
    setup = _suite_agent(client, "Suite Run Agent", ["alpha", "beta", "gamma"])
    agent = setup["agent"]
    superseded = client.post(
        f"{P}/scenarios",
        json={"agent_design_id": agent["id"], "input": "Old test.", "status": "active"},
    ).json()
    client.post(
        f"{P}/eval-contracts",
        json={"agent_design_id": agent["id"], "name": "old", "scenario_id": superseded["id"]},
    )
    client.patch(f"{P}/scenarios/{superseded['id']}", json={"status": "superseded"})
    v0 = _version(client, agent, "v0", "Always say alpha.")

    result = _run_suite(client, agent, v0)

    runs = [
        run
        for run in client.get(f"{P}/runs", params={"agent_design_id": agent["id"]}).json()
        if run["agent_version_id"] == v0["id"]
    ]
    assert len(runs) == 3
    run_ids = {run["id"] for run in runs}
    evals = [
        client.get(f"{P}/eval-results", params={"eval_contract_id": test["contract"]["id"]}).json()
        for test in setup["tests"]
    ]
    assert [len(items) for items in evals] == [1, 1, 1]
    assert {items[0]["run_id"] for items in evals} == run_ids
    assert result["agent_version_id"] == v0["id"]
    assert result["total"] == 3
    assert result["passed"] == 1
    assert [test["scenario_id"] for test in result["tests"]] == [
        test["scenario"]["id"] for test in setup["tests"]
    ]


def test_suite_result_reads_latest_eval_per_test_without_a_stored_record() -> None:
    client = TestClient(app)
    setup = _suite_agent(client, "Suite Result Agent", ["alpha", "beta"])
    agent = setup["agent"]
    v0 = _version(client, agent, "v0", "Always say alpha.")
    url = f"{P}/agent-designs/{agent['id']}/versions/{v0['id']}/suite-result"

    before = client.get(url).json()
    assert before["passed"] == 0
    assert before["total"] == 2
    assert [test["eval_result"] for test in before["tests"]] == [None, None]

    _run_suite(client, agent, v0)
    second = _run_suite(client, agent, v0)
    result = client.get(url).json()

    assert result == second
    assert result["passed"] == 1
    assert result["total"] == 2
    alpha_evals = client.get(
        f"{P}/eval-results", params={"eval_contract_id": setup["tests"][0]["contract"]["id"]}
    ).json()
    assert len(alpha_evals) == 2
    newest = max(alpha_evals, key=lambda item: item["created_at"])
    assert result["tests"][0]["eval_result"]["id"] == newest["id"]
    assert result["tests"][0]["eval_result"]["passed"] is True
    assert result["tests"][1]["eval_result"]["passed"] is False


def test_suite_result_rejects_a_version_of_another_agent() -> None:
    client = TestClient(app)
    first = _suite_agent(client, "Suite Owner Agent", ["alpha"])
    second = _suite_agent(client, "Suite Other Agent", ["alpha"])
    v0 = _version(client, first["agent"], "v0", "Always say alpha.")

    response = client.get(
        f"{P}/agent-designs/{second['agent']['id']}/versions/{v0['id']}/suite-result"
    )

    assert response.status_code == 404


def test_suite_comparison_marks_fixed_and_regressed_tests_and_gate_blocks() -> None:
    client = TestClient(app)
    setup = _suite_agent(client, "Suite Regression Agent", ["alpha", "beta", "gamma", "delta"])
    agent = setup["agent"]
    v0 = _version(client, agent, "v0", "Always say alpha and gamma.")
    v1 = _version(client, agent, "v1", "Always say beta and gamma.")
    _run_suite(client, agent, v0)
    _run_suite(client, agent, v1)

    comparison = _compare_suites(client, v0, v1)

    assert _outcomes(comparison, setup) == ["regressed", "fixed", "still_passing", "still_failing"]
    assert comparison["totals"] == {
        "total": 4,
        "fixed": 1,
        "regressed": 1,
        "still_passing": 1,
        "still_failing": 1,
    }
    assert comparison["baseline_version_id"] == v0["id"]
    assert comparison["candidate_version_id"] == v1["id"]
    assert comparison["baseline_run_id"] is None
    beta_packets = [
        packet
        for packet in client.get(
            f"{P}/failure-packets", params={"agent_design_id": agent["id"]}
        ).json()
        if packet["eval_contract_id"] == setup["tests"][1]["contract"]["id"]
        and packet["agent_version_id"] == v0["id"]
    ]
    assert comparison["fixed_failure_packet_ids"] == [packet["id"] for packet in beta_packets]
    assert client.get(f"{P}/comparisons/{comparison['id']}").json() == comparison

    decision = _decide(client, setup["gate"], comparison)

    assert decision["decision"] == "blocked"
    assert f"{setup['tests'][0]['scenario']['id']} (regressed)" in decision["rationale"]
    assert f"{setup['tests'][3]['scenario']['id']} (still_failing)" in decision["rationale"]


def test_gate_passes_when_every_suite_test_is_fixed_or_still_passing() -> None:
    client = TestClient(app)
    setup = _suite_agent(client, "Suite Pass Agent", ["alpha", "beta"])
    agent = setup["agent"]
    v0 = _version(client, agent, "v0", "Always say alpha.")
    v1 = _version(client, agent, "v1", "Always say alpha and beta.")
    _run_suite(client, agent, v0)
    _run_suite(client, agent, v1)

    comparison = _compare_suites(client, v0, v1)
    assert _outcomes(comparison, setup) == ["still_passing", "fixed"]

    decision = _decide(client, setup["gate"], comparison)

    assert decision["decision"] == "passed", decision["rationale"]
    assert decision["blocking_failure_packet_ids"] == []
    assert f"Judged version v1 ({v1['id']})." in decision["rationale"]


def test_gate_blocks_on_a_suite_regression_alone() -> None:
    client = TestClient(app)
    setup = _suite_agent(client, "Suite Lone Regression Agent", ["alpha"])
    agent = setup["agent"]
    v0 = _version(client, agent, "v0", "Always say alpha.")
    v1 = _version(client, agent, "v1", "Say nothing useful.")
    _run_suite(client, agent, v0)
    _run_suite(client, agent, v1)
    comparison = _compare_suites(client, v0, v1)
    assert _outcomes(comparison, setup) == ["regressed"]
    # Close the candidate's packet so only the suite rule can block.
    for packet in client.get(
        f"{P}/failure-packets", params={"agent_design_id": agent["id"]}
    ).json():
        client.patch(f"{P}/failure-packets/{packet['id']}", json={"status": "resolved"})

    decision = _decide(client, setup["gate"], comparison)

    assert decision["decision"] == "blocked"
    assert decision["blocking_failure_packet_ids"] == []


def test_suite_comparison_requires_both_versions_evaluated_on_every_test() -> None:
    client = TestClient(app)
    setup = _suite_agent(client, "Suite Missing Agent", ["alpha"])
    agent = setup["agent"]
    v0 = _version(client, agent, "v0", "Always say alpha.")
    v1 = _version(client, agent, "v1", "Always say alpha.")
    _run_suite(client, agent, v0)

    response = client.post(
        f"{P}/comparisons/suite",
        json={"baseline_version_id": v0["id"], "candidate_version_id": v1["id"]},
    )

    assert response.status_code == 400
    assert f"alpha test ({setup['tests'][0]['scenario']['id']})" in response.json()["detail"]


def test_gate_accepts_a_suite_rows_candidate_eval_result() -> None:
    client = TestClient(app)
    setup = _suite_agent(client, "Suite Eval Ref Agent", ["alpha"])
    agent = setup["agent"]
    v0 = _version(client, agent, "v0", "Say nothing useful.")
    v1 = _version(client, agent, "v1", "Always say alpha.")
    _run_suite(client, agent, v0)
    _run_suite(client, agent, v1)
    comparison = _compare_suites(client, v0, v1)
    [row] = comparison["tests"]

    accepted = client.post(
        f"{P}/gates/{setup['gate']['id']}/decisions",
        json={"comparison_id": comparison["id"], "eval_result_id": row["candidate_eval_result_id"]},
    )
    rejected = client.post(
        f"{P}/gates/{setup['gate']['id']}/decisions",
        json={"comparison_id": comparison["id"], "eval_result_id": row["baseline_eval_result_id"]},
    )

    assert accepted.status_code == 201
    assert accepted.json()["decision"] == "passed"
    assert rejected.status_code == 400


def test_suite_run_records_a_test_error_and_runs_the_remaining_tests(monkeypatch) -> None:
    client = TestClient(app)
    setup = _suite_agent(client, "Suite Error Agent", ["alpha", "beta", "gamma"])
    agent = setup["agent"]
    v0 = _version(client, agent, "v0", "Always say alpha and gamma.")
    calls = []

    def flaky_runner(runner_agent, runner_scenario, _config, _tools):
        calls.append(runner_scenario)
        if len(calls) == 2:
            raise RuntimeError("Provider timed out.")
        return edd_runner.run_mock_agent(runner_agent, runner_scenario)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(api_main, "run_anthropic_agent", flaky_runner)

    response = client.post(
        f"{P}/agent-designs/{agent['id']}/versions/{v0['id']}/suite-runs",
        json={"mode": "live", "provider": "anthropic", "judge_mode": "deterministic"},
    )

    assert response.status_code == 201, response.text
    result = response.json()
    assert len(calls) == 3
    assert [test["error"] for test in result["tests"]] == [None, "Provider timed out.", None]
    assert [test["eval_result"] is not None for test in result["tests"]] == [True, False, True]
    assert result["passed"] == 2
    assert result["total"] == 3
    runs = [
        run
        for run in client.get(f"{P}/runs", params={"agent_design_id": agent["id"]}).json()
        if run["agent_version_id"] == v0["id"]
    ]
    assert len(runs) == 2
    evals = [
        client.get(f"{P}/eval-results", params={"eval_contract_id": test["contract"]["id"]}).json()
        for test in setup["tests"]
    ]
    assert [len(items) for items in evals] == [1, 0, 1]
    assert {evals[0][0]["run_id"], evals[2][0]["run_id"]} == {run["id"] for run in runs}


def test_suite_run_records_a_judge_error_after_the_run_is_stored(monkeypatch) -> None:
    client = TestClient(app)
    setup = _suite_agent(client, "Suite Judge Error Agent", ["alpha", "beta"])
    agent = setup["agent"]
    v0 = _version(client, agent, "v0", "Always say alpha and beta.")
    calls = []

    def flaky_judge(prompt, trace_id=None):
        calls.append(prompt)
        if len(calls) == 1:
            raise RuntimeError("Judge timed out.")
        return "Judge agrees.", "test-judge-model", {"input_tokens": 1, "output_tokens": 1}

    monkeypatch.setattr(api_main, "run_live_judge", flaky_judge)

    response = client.post(
        f"{P}/agent-designs/{agent['id']}/versions/{v0['id']}/suite-runs",
        json={"mode": "mock", "judge_mode": "live"},
    )

    assert response.status_code == 201, response.text
    result = response.json()
    assert len(calls) == 2
    assert [test["error"] for test in result["tests"]] == ["Judge timed out.", None]
    assert [test["eval_result"] is not None for test in result["tests"]] == [False, True]
    assert result["passed"] == 1
    runs = [
        run
        for run in client.get(f"{P}/runs", params={"agent_design_id": agent["id"]}).json()
        if run["agent_version_id"] == v0["id"]
    ]
    assert len(runs) == 2
    evals = [
        client.get(f"{P}/eval-results", params={"eval_contract_id": test["contract"]["id"]}).json()
        for test in setup["tests"]
    ]
    assert [len(items) for items in evals] == [0, 1]
