from typing import Tuple

from fastapi.testclient import TestClient

from edd_platform_api.main import app

PROJECT = "/api/projects/project_default"


def create_contract(client: TestClient, judge_passes: bool) -> Tuple[str, str, str]:
    """Return (agent id, scenario id, contract id) for a contract the mock run passes or fails."""
    agent = client.post(
        f"{PROJECT}/agent-designs",
        json={"name": "Reviewed Agent", "intent": "Write tickets."},
    ).json()["agent"]
    scenario = client.post(
        f"{PROJECT}/scenarios",
        json={"agent_design_id": agent["id"], "name": "Ticket", "input": "Write a ticket."},
    ).json()
    check_type = "output_not_contains" if judge_passes else "output_contains"
    contract = client.post(
        f"{PROJECT}/eval-contracts",
        json={
            "agent_design_id": agent["id"],
            "name": "One fix per ticket",
            "scenario_id": scenario["id"],
            "checks": [{"id": "phrase", "type": check_type, "value": "purple elephant"}],
        },
    ).json()
    return agent["id"], scenario["id"], contract["id"]


def evaluate(client: TestClient, agent_id: str, scenario_id: str, contract_id: str) -> dict:
    run = client.post(
        f"{PROJECT}/runs",
        json={
            "agent_design_id": agent_id,
            "scenario_id": scenario_id,
            "eval_contract_id": contract_id,
        },
    ).json()
    response = client.post(f"{PROJECT}/runs/{run['id']}/evaluate", json={})
    assert response.status_code == 201, response.text
    return response.json()


def review(client: TestClient, eval_result: dict, verdict: str, reason: str = "Checked by hand."):
    return client.post(
        f"{PROJECT}/judge-outputs/{eval_result['judge_output_ids'][0]}/review",
        json={"verdict": verdict, "reason": reason},
    )


def open_packets(client: TestClient, agent_id: str, eval_result_id: str) -> list:
    packets = client.get(
        f"{PROJECT}/failure-packets", params={"agent_design_id": agent_id}
    ).json()
    return [
        packet
        for packet in packets
        if packet["eval_result_id"] == eval_result_id and packet["status"] == "open"
    ]


def test_agree_records_review_and_keeps_result() -> None:
    client = TestClient(app)
    agent_id, scenario_id, contract_id = create_contract(client, judge_passes=True)
    eval_result = evaluate(client, agent_id, scenario_id, contract_id)

    response = review(client, eval_result, "agree", "Ticket is one fix.")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["eval_result"]["passed"] is True
    assert body["failure_packet"] is None
    assert body["judge_output"]["review"]["verdict"] == "agree"
    assert body["judge_output"]["review"]["reason"] == "Ticket is one fix."
    assert body["judge_output"]["review"]["judge_passed"] is True
    review_artifacts = client.get(
        f"{PROJECT}/artifacts",
        params={"agent_design_id": agent_id, "artifact_type": "JUDGE_REVIEW"},
    ).json()
    assert len(review_artifacts) == 1


def test_overrule_passed_verdict_fails_eval_and_opens_failure_packet() -> None:
    client = TestClient(app)
    agent_id, scenario_id, contract_id = create_contract(client, judge_passes=True)
    eval_result = evaluate(client, agent_id, scenario_id, contract_id)
    assert eval_result["passed"] is True
    assert open_packets(client, agent_id, eval_result["id"]) == []
    [judge_before] = client.get(
        f"{PROJECT}/judge-outputs", params={"eval_result_id": eval_result["id"]}
    ).json()

    response = review(client, eval_result, "overrule", "Bundles three fixes into one ticket.")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["eval_result"]["passed"] is False
    assert body["judge_output"]["review"]["judge_passed"] is True
    assert body["judge_output"]["output"] == judge_before["output"]
    stored = client.get(f"{PROJECT}/eval-results/{eval_result['id']}").json()
    assert stored["passed"] is False
    packets = open_packets(client, agent_id, eval_result["id"])
    assert len(packets) == 1
    assert packets[0]["id"] == body["failure_packet"]["id"]
    assert "Bundles three fixes into one ticket." in packets[0]["diagnosis"]


def test_overrule_failed_verdict_passes_eval_and_closes_failure_packet() -> None:
    client = TestClient(app)
    agent_id, scenario_id, contract_id = create_contract(client, judge_passes=False)
    eval_result = evaluate(client, agent_id, scenario_id, contract_id)
    assert eval_result["passed"] is False
    assert len(open_packets(client, agent_id, eval_result["id"])) == 1

    response = review(client, eval_result, "overrule", "The phrase is not needed here.")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["eval_result"]["passed"] is True
    assert body["judge_output"]["review"]["verdict"] == "overrule"
    assert body["judge_output"]["review"]["judge_passed"] is False
    judge_outputs = client.get(
        f"{PROJECT}/judge-outputs", params={"eval_result_id": eval_result["id"]}
    ).json()
    assert judge_outputs[0]["review"]["judge_passed"] is False
    assert open_packets(client, agent_id, eval_result["id"]) == []
    assert client.get(f"{PROJECT}/eval-results/{eval_result['id']}").json()["passed"] is True


def packets_for(client: TestClient, agent_id: str, eval_result_id: str) -> list:
    packets = client.get(
        f"{PROJECT}/failure-packets", params={"agent_design_id": agent_id}
    ).json()
    return [packet for packet in packets if packet["eval_result_id"] == eval_result_id]


def test_agree_after_overruling_a_pass_withdraws_the_reviewer_packet() -> None:
    client = TestClient(app)
    agent_id, scenario_id, contract_id = create_contract(client, judge_passes=True)
    eval_result = evaluate(client, agent_id, scenario_id, contract_id)

    review(client, eval_result, "overrule", "Bundles fixes.")
    response = review(client, eval_result, "agree", "On a second read it is one fix.")

    body = response.json()
    assert body["judge_output"]["review"]["judge_passed"] is True
    assert body["eval_result"]["passed"] is True
    assert body["failure_packet"] is None
    [packet] = packets_for(client, agent_id, eval_result["id"])
    assert packet["status"] == "withdrawn"
    assert packet["title"] == "Reviewer overruled judge: One fix per ticket"

    # Overruling again reopens the same packet with the new reason.
    response = review(client, eval_result, "overrule", "It does bundle fixes after all.")
    assert response.json()["failure_packet"]["id"] == packet["id"]
    [packet] = packets_for(client, agent_id, eval_result["id"])
    assert packet["status"] == "open"
    assert packet["diagnosis"].endswith("It does bundle fixes after all.")


def test_second_overrule_updates_the_packet_reason() -> None:
    client = TestClient(app)
    agent_id, scenario_id, contract_id = create_contract(client, judge_passes=True)
    eval_result = evaluate(client, agent_id, scenario_id, contract_id)

    review(client, eval_result, "overrule", "Reason A.")
    review(client, eval_result, "overrule", "Reason B.")

    [packet] = packets_for(client, agent_id, eval_result["id"])
    assert packet["status"] == "open"
    assert packet["diagnosis"].endswith("Reason B.")


def test_gate_follows_reviews_in_both_directions() -> None:
    client = TestClient(app)
    for judge_passes, expected in (
        (True, ["passed", "blocked", "passed"]),
        (False, ["blocked", "passed", "blocked"]),
    ):
        agent_id, scenario_id, contract_id = create_contract(client, judge_passes=judge_passes)
        gate = client.post(
            f"{PROJECT}/gates",
            json={"agent_design_id": agent_id, "name": "Ship", "approval_mode": "automatic"},
        ).json()
        eval_result = evaluate(client, agent_id, scenario_id, contract_id)

        def decide() -> str:
            response = client.post(
                f"{PROJECT}/gates/{gate['id']}/decisions",
                json={"eval_result_id": eval_result["id"]},
            )
            assert response.status_code == 201, response.text
            return response.json()["decision"]

        decisions = [decide()]
        review(client, eval_result, "overrule")
        decisions.append(decide())
        review(client, eval_result, "agree")
        decisions.append(decide())
        assert decisions == expected, f"judge_passes={judge_passes}"


def test_agree_after_overruling_a_fail_reopens_the_judge_packet() -> None:
    client = TestClient(app)
    agent_id, scenario_id, contract_id = create_contract(client, judge_passes=False)
    eval_result = evaluate(client, agent_id, scenario_id, contract_id)
    [judge_packet] = packets_for(client, agent_id, eval_result["id"])

    review(client, eval_result, "overrule", "The phrase is not needed here.")
    [packet] = packets_for(client, agent_id, eval_result["id"])
    assert packet["status"] == "overruled"

    response = review(client, eval_result, "agree", "Judge was right.")

    body = response.json()
    assert body["judge_output"]["review"]["judge_passed"] is False
    assert body["eval_result"]["passed"] is False
    assert body["failure_packet"]["id"] == judge_packet["id"]
    [packet] = packets_for(client, agent_id, eval_result["id"])
    assert packet["status"] == "open"
    assert packet["title"] == judge_packet["title"]
    assert packet["diagnosis"] == judge_packet["diagnosis"]


def test_review_requires_reason_and_known_judge_output() -> None:
    client = TestClient(app)
    agent_id, scenario_id, contract_id = create_contract(client, judge_passes=True)
    eval_result = evaluate(client, agent_id, scenario_id, contract_id)

    assert review(client, eval_result, "agree", "").status_code == 422
    assert review(client, eval_result, "maybe").status_code == 422
    missing = client.post(
        f"{PROJECT}/judge-outputs/judge_missing/review",
        json={"verdict": "agree", "reason": "x"},
    )
    assert missing.status_code == 404


def test_judge_agreement_rate_for_contract() -> None:
    client = TestClient(app)
    agent_id, scenario_id, contract_id = create_contract(client, judge_passes=True)
    empty = client.get(f"{PROJECT}/eval-contracts/{contract_id}/judge-agreement").json()
    assert empty == {
        "eval_contract_id": contract_id,
        "reviewed": 0,
        "agreed": 0,
        "overruled": 0,
        "agreement_rate": None,
    }

    results = [evaluate(client, agent_id, scenario_id, contract_id) for _ in range(4)]
    review(client, results[0], "agree")
    review(client, results[1], "agree")
    review(client, results[2], "overrule")
    # results[3] is not reviewed and does not count.

    response = client.get(f"{PROJECT}/eval-contracts/{contract_id}/judge-agreement")

    assert response.status_code == 200
    assert response.json() == {
        "eval_contract_id": contract_id,
        "reviewed": 3,
        "agreed": 2,
        "overruled": 1,
        "agreement_rate": 2 / 3,
    }
    missing = client.get(f"{PROJECT}/eval-contracts/contract_missing/judge-agreement")
    assert missing.status_code == 404
