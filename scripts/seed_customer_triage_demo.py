#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from typing import Optional, Union
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_BASE_URL = os.environ.get("EDD_PLATFORM_API_URL", "http://127.0.0.1:8001").rstrip("/")
PROJECT_ID = os.environ.get("EDD_PLATFORM_PROJECT_ID", "project_default")


def request_json(
    method: str,
    path: str,
    payload: Optional[dict] = None,
) -> Union[dict, list]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{API_BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"{method} {path} failed with {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SystemExit(
            f"Could not reach {API_BASE_URL}. Start the app with ./scripts/dev.sh first."
        ) from exc


def post(path: str, payload: dict) -> dict:
    response = request_json("POST", path, payload)
    if not isinstance(response, dict):
        raise SystemExit(f"Expected object response from {path}.")
    return response


def require_live_anthropic() -> None:
    status = request_json("GET", "/api/services")
    anthropic = next(
        (service for service in status["services"] if service["id"] == "anthropic"),
        None,
    )
    if anthropic is None or not anthropic["configured"]:
        raise SystemExit(
            f"The API at {API_BASE_URL} has no ANTHROPIC_API_KEY; set it and restart "
            "the API to seed the live Customer Triage demo."
        )


def main() -> None:
    require_live_anthropic()
    agent_response = post(
        f"/api/projects/{PROJECT_ID}/agent-designs",
        {
            "name": "Customer Service Triage Demo",
            "intent": (
                "Triage customer escalations, gather evidence, state assumptions, "
                "and recommend a safe next action."
            ),
        },
    )
    agent = agent_response["agent"]

    scenario = post(
        f"/api/projects/{PROJECT_ID}/scenarios",
        {
            "agent_design_id": agent["id"],
            "name": "Failed deployment escalation",
            "input": (
                "A customer says a deployment failed after release and asks what "
                "to do next. Account impact is unclear."
            ),
        },
    )
    contract = post(
        f"/api/projects/{PROJECT_ID}/eval-contracts",
        {
            "agent_design_id": agent["id"],
            "name": "Escalation triage contract",
            "scenario_id": scenario["id"],
            "expected_behavior": [
                "Ask for deployment logs before diagnosing the failure.",
                "Do not guess at a root cause before seeing the logs.",
                "Do not invent commercial remedies.",
            ],
            "checks": [
                {
                    "id": "asks_for_logs_before_diagnosing",
                    "type": "rubric_judge",
                    "value": (
                        "PASS only if the response asks the customer for deployment "
                        "logs or error output and does not name or list likely root "
                        "causes before seeing them. Judge the meaning, not the wording."
                    ),
                },
                {
                    "id": "does_not_invent_refund",
                    "type": "output_not_contains",
                    "value": "refund approved",
                },
            ],
        },
    )
    v0 = post(
        f"/api/projects/{PROJECT_ID}/agent-designs/{agent['id']}/versions",
        {
            "version_label": "v0",
            "instructions": agent["intent"],
            "status": "baseline",
        },
    )
    v0_run = post(
        f"/api/projects/{PROJECT_ID}/runs",
        {
            "agent_design_id": agent["id"],
            "agent_version_id": v0["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
            "mode": "live",
            "provider": "anthropic",
        },
    )
    v0_eval = post(
        f"/api/projects/{PROJECT_ID}/runs/{v0_run['id']}/evaluate",
        {"judge_mode": "live"},
    )
    failure_packets = request_json(
        "GET",
        f"/api/projects/{PROJECT_ID}/failure-packets?agent_design_id={agent['id']}",
    )
    if not isinstance(failure_packets, list):
        raise SystemExit("Expected failure packet list.")
    v0_failures = [
        packet
        for packet in failure_packets
        if packet["eval_result_id"] == v0_eval["id"]
    ]
    fix = post(
        f"/api/projects/{PROJECT_ID}/fix-proposals",
        {
            "agent_design_id": agent["id"],
            "target_version_id": v0["id"],
            "title": "Ask for deployment logs before diagnosis",
            "rationale": (
                "The contract requires asking for deployment logs before any "
                "diagnosis, and the baseline instructions do not say so."
            ),
            "proposed_changes": [
                {
                    "type": "instruction",
                    "description": (
                        "Ask for deployment logs and recent release changes, and do "
                        "not guess at a cause until you have seen them."
                    ),
                }
            ],
            "addressed_failure_packet_ids": [packet["id"] for packet in v0_failures],
            "validation_contract_ids": [contract["id"]],
        },
    )
    v1 = post(
        f"/api/projects/{PROJECT_ID}/agent-designs/{agent['id']}/versions",
        {
            "version_label": "v1",
            "parent_version_id": v0["id"],
            "source_fix_proposal_id": fix["id"],
            "instructions": (
                f"{agent['intent']} Ask for deployment logs and recent release "
                "changes, and do not guess at a cause until you have seen them."
            ),
            "status": "candidate",
        },
    )
    v1_run = post(
        f"/api/projects/{PROJECT_ID}/runs",
        {
            "agent_design_id": agent["id"],
            "agent_version_id": v1["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
            "mode": "live",
            "provider": "anthropic",
        },
    )
    v1_eval = post(
        f"/api/projects/{PROJECT_ID}/runs/{v1_run['id']}/evaluate",
        {"judge_mode": "live"},
    )
    comparison = post(
        f"/api/projects/{PROJECT_ID}/comparisons",
        {
            "baseline_run_id": v0_run["id"],
            "candidate_run_id": v1_run["id"],
            "eval_contract_id": contract["id"],
        },
    )

    print(
        json.dumps(
            {
                "agent": agent["name"],
                "agent_id": agent["id"],
                "runs": {
                    "v0": f"{v0_run['mode']} / {v0_run['provider']}",
                    "v1": f"{v1_run['mode']} / {v1_run['provider']}",
                },
                "v0_score": f"{v0_eval['score']}/{len(v0_eval['checks'])}",
                "v1_score": f"{v1_eval['score']}/{len(v1_eval['checks'])}",
                "comparison": comparison["summary"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
