import sys
import types
from typing import List

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from edd_platform_api import main as api_main
from edd_platform_api.main import app

import edd_runner  # noqa: E402  (importable once main has put the runner on sys.path)

P = "/api/projects/project_default"
_ANTHROPIC_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


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


@pytest.mark.parametrize(
    ("provider_error", "expected_error"),
    [
        (
            anthropic.BadRequestError(
                "Bad tool schema.",
                response=httpx.Response(400, request=_ANTHROPIC_REQUEST),
                body=None,
            ),
            "Anthropic request failed with status 400: Bad tool schema.",
        ),
        (
            anthropic.APIConnectionError(request=_ANTHROPIC_REQUEST),
            "Anthropic request failed: Connection error.",
        ),
    ],
)
def test_suite_run_records_a_provider_error_on_a_tools_agent_as_a_test_error(
    monkeypatch, provider_error, expected_error
) -> None:
    client = TestClient(app)
    setup = _suite_agent(client, "Suite Tools Provider Error Agent", ["alpha", "beta"])
    agent = setup["agent"]
    v0 = _version(client, agent, "v0", "Always say alpha and beta.")
    calls = []

    class FakeMessage:
        type = "ai"
        content = "alpha and beta"
        response_metadata = {}

    class FlakyGraph:
        def invoke(self, _state, config=None):
            calls.append(_state)
            if len(calls) == 1:
                raise provider_error
            return {"messages": [FakeMessage()]}

    fake_agents_module = types.ModuleType("langchain.agents")
    fake_agents_module.create_agent = lambda **_kwargs: FlakyGraph()
    monkeypatch.setitem(sys.modules, "langchain.agents", fake_agents_module)
    monkeypatch.setattr(edd_runner, "build_langchain_tools", lambda _definitions: [object()])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    response = client.post(
        f"{P}/agent-designs/{agent['id']}/versions/{v0['id']}/suite-runs",
        json={"mode": "live", "provider": "anthropic", "judge_mode": "deterministic"},
    )

    assert response.status_code == 201, response.text
    result = response.json()
    assert len(calls) == 2
    assert [test["error"] for test in result["tests"]] == [expected_error, None]
    assert [test["eval_result"] is not None for test in result["tests"]] == [False, True]
    assert result["passed"] == 1


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


def _shared_contract_agent(client: TestClient, name: str, scenario_names: List[str]) -> dict:
    """An agent whose active scenarios name no contract; one contract is each one's default."""
    agent = client.post(
        f"{P}/agent-designs",
        json={"name": name, "intent": "Answer support questions."},
    ).json()["agent"]
    shared = client.post(
        f"{P}/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Shared contract",
            "checks": [{"id": "says_alpha", "type": "output_contains", "value": "alpha"}],
        },
    ).json()
    scenarios = [
        client.post(
            f"{P}/scenarios",
            json={
                "agent_design_id": agent["id"],
                "name": scenario_name,
                "input": "A customer reports a failed deployment.",
                "default_eval_contract_id": shared["id"],
                "status": "active",
            },
        ).json()
        for scenario_name in scenario_names
    ]
    return {"agent": agent, "shared": shared, "scenarios": scenarios}


def test_suite_runs_and_compares_scenarios_that_share_a_default_contract() -> None:
    client = TestClient(app)
    setup = _shared_contract_agent(client, "Shared Contract Agent", ["one", "two", "three"])
    agent, shared = setup["agent"], setup["shared"]
    scenario_ids = [scenario["id"] for scenario in setup["scenarios"]]
    v0 = _version(client, agent, "v0", "Say nothing useful.")
    v1 = _version(client, agent, "v1", "Always say alpha.")

    baseline = _run_suite(client, agent, v0)
    candidate = _run_suite(client, agent, v1)

    assert [test["scenario_id"] for test in candidate["tests"]] == scenario_ids
    assert {test["eval_contract_id"] for test in candidate["tests"]} == {shared["id"]}
    assert all(test["error"] is None for test in candidate["tests"])
    assert (baseline["passed"], baseline["total"]) == (0, 3)
    assert (candidate["passed"], candidate["total"]) == (3, 3)
    # Each scenario reads its own eval of the shared contract, not another scenario's.
    eval_run_ids = [test["eval_result"]["run_id"] for test in candidate["tests"]]
    runs = {run["id"]: run for run in client.get(f"{P}/runs", params={"agent_design_id": agent["id"]}).json()}
    assert [runs[run_id]["scenario_id"] for run_id in eval_run_ids] == scenario_ids

    comparison = _compare_suites(client, v0, v1)

    assert [row["scenario_id"] for row in comparison["tests"]] == scenario_ids
    assert [row["outcome"] for row in comparison["tests"]] == ["fixed", "fixed", "fixed"]


def test_suite_uses_a_scenarios_own_contract_over_its_default_contract() -> None:
    client = TestClient(app)
    setup = _shared_contract_agent(client, "Own Contract Agent", ["own", "shared"])
    agent, shared = setup["agent"], setup["shared"]
    own_scenario = setup["scenarios"][0]
    own = client.post(
        f"{P}/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "Own contract",
            "scenario_id": own_scenario["id"],
            "checks": [{"id": "says_beta", "type": "output_contains", "value": "beta"}],
        },
    ).json()
    v0 = _version(client, agent, "v0", "Always say alpha.")

    result = _run_suite(client, agent, v0)

    assert [(test["scenario_id"], test["eval_contract_id"]) for test in result["tests"]] == [
        (own_scenario["id"], own["id"]),
        (setup["scenarios"][1]["id"], shared["id"]),
    ]
    assert [test["eval_result"]["passed"] for test in result["tests"]] == [False, True]


def test_a_default_contract_of_another_agent_is_not_a_test() -> None:
    client = TestClient(app)
    other = _shared_contract_agent(client, "Contract Owner Agent", [])
    agent = client.post(
        f"{P}/agent-designs",
        json={"name": "Borrowing Agent", "intent": "Answer support questions."},
    ).json()["agent"]
    client.post(
        f"{P}/scenarios",
        json={
            "agent_design_id": agent["id"],
            "input": "A customer reports a failed deployment.",
            "default_eval_contract_id": other["shared"]["id"],
            "status": "active",
        },
    )
    v0 = _version(client, agent, "v0", "Always say alpha.")

    response = client.post(
        f"{P}/agent-designs/{agent['id']}/versions/{v0['id']}/suite-runs",
        json={"mode": "mock", "judge_mode": "deterministic"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Agent has no active tests to run."


def _open_packet_ids(client: TestClient, agent: dict, version: dict) -> List[str]:
    return sorted(
        packet["id"]
        for packet in client.get(
            f"{P}/failure-packets", params={"agent_design_id": agent["id"]}
        ).json()
        if packet["agent_version_id"] == version["id"] and packet["status"] == "open"
    )


def test_gate_ignores_open_packets_from_a_version_outside_the_comparison() -> None:
    client = TestClient(app)
    setup = _suite_agent(client, "Older Packets Agent", ["alpha", "beta"])
    agent = setup["agent"]
    v1 = _version(client, agent, "v1", "Say nothing useful.")
    v2 = _version(client, agent, "v2", "Always say alpha.")
    v3 = _version(client, agent, "v3", "Always say alpha and beta.")
    for version in (v1, v2, v3):
        _run_suite(client, agent, version)
    v1_packet_ids = _open_packet_ids(client, agent, v1)
    assert len(v1_packet_ids) == 2

    comparison = _compare_suites(client, v2, v3)
    decision = _decide(client, setup["gate"], comparison)

    assert _outcomes(comparison, setup) == ["still_passing", "fixed"]
    assert decision["decision"] == "passed"
    assert decision["blocking_failure_packet_ids"] == []
    for packet_id in v1_packet_ids:
        assert packet_id not in decision["rationale"]


def test_gate_blocks_on_an_open_packet_from_the_candidate_version() -> None:
    client = TestClient(app)
    setup = _suite_agent(client, "Candidate Packet Agent", ["alpha", "beta"])
    agent = setup["agent"]
    v2 = _version(client, agent, "v2", "Always say alpha and beta.")
    v3 = _version(client, agent, "v3", "Always say alpha.")
    _run_suite(client, agent, v2)
    _run_suite(client, agent, v3)
    [v3_packet_id] = _open_packet_ids(client, agent, v3)

    decision = _decide(client, setup["gate"], _compare_suites(client, v2, v3))

    assert decision["decision"] == "blocked"
    assert decision["blocking_failure_packet_ids"] == [v3_packet_id]
    assert v3_packet_id in decision["rationale"]


def test_gate_leaves_a_later_version_packet_out_of_an_earlier_comparison() -> None:
    client = TestClient(app)
    setup = _suite_agent(client, "Later Packet Agent", ["alpha", "beta"])
    agent = setup["agent"]
    v1 = _version(client, agent, "v1", "Say nothing useful.")
    v2 = _version(client, agent, "v2", "Always say alpha and beta.")
    v3 = _version(client, agent, "v3", "Always say alpha.")
    for version in (v1, v2, v3):
        _run_suite(client, agent, version)
    [v3_packet_id] = _open_packet_ids(client, agent, v3)

    decision = _decide(client, setup["gate"], _compare_suites(client, v1, v2))

    assert decision["decision"] == "passed"
    assert v3_packet_id not in decision["blocking_failure_packet_ids"]
    assert v3_packet_id not in decision["rationale"]


def test_gate_on_an_eval_result_blocks_on_that_versions_open_packets() -> None:
    client = TestClient(app)
    setup = _suite_agent(client, "Eval Result Packet Agent", ["alpha", "beta"])
    agent = setup["agent"]
    v1 = _version(client, agent, "v1", "Always say alpha.")
    v2 = _version(client, agent, "v2", "Always say beta.")
    v1_result = _run_suite(client, agent, v1)
    _run_suite(client, agent, v2)
    [v1_packet_id] = _open_packet_ids(client, agent, v1)
    [v2_packet_id] = _open_packet_ids(client, agent, v2)
    v1_alpha_eval = v1_result["tests"][0]["eval_result"]
    assert v1_alpha_eval["passed"] is True

    response = client.post(
        f"{P}/gates/{setup['gate']['id']}/decisions",
        json={"eval_result_id": v1_alpha_eval["id"]},
    )
    assert response.status_code == 201, response.text
    decision = response.json()

    assert decision["decision"] == "blocked"
    assert decision["blocking_failure_packet_ids"] == [v1_packet_id]
    assert v2_packet_id not in decision["rationale"]
