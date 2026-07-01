#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from typing import Optional, Union
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_BASE_URL = os.environ.get("EDD_PLATFORM_API_URL", "http://127.0.0.1:8001").rstrip("/")
PROJECT_ID = os.environ.get("EDD_PLATFORM_PROJECT_ID", "project_default")
AGENT_ID = "agent_sentiment_observer"
SCENARIO_INPUT = """Customer: My deployment failed after the release.
Agent: What error are you seeing?
Customer: The rollout says image pull backoff."""
RUBRIC = (
    "A good observer output should review the latest customer turn in context, "
    "identify that sentiment or escalation risk is worsening, mention the image "
    "pull backoff blocker, avoid claiming the issue is fixed, and produce concise "
    "downstream-safe observer notes."
)


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
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"{method} {path} failed with {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SystemExit(
            f"Could not reach {API_BASE_URL}. Start the app with ./scripts/dev.sh first."
        ) from exc


def get(path: str) -> Union[dict, list]:
    return request_json("GET", path)


def post(path: str, payload: dict) -> dict:
    response = request_json("POST", path, payload)
    if not isinstance(response, dict):
        raise SystemExit(f"Expected object response from {path}.")
    return response


def find_default_agent() -> dict:
    agents = get(f"/api/projects/{PROJECT_ID}/agent-designs")
    if not isinstance(agents, list):
        raise SystemExit("Expected agent list.")
    for agent in agents:
        if agent["id"] == AGENT_ID:
            return agent
    raise SystemExit(
        "Sentiment Observer is not present. Restart the app so default seed data runs."
    )


def should_run_live() -> bool:
    requested = os.environ.get("EDD_SENTIMENT_OBSERVER_DEMO_RUN", "").strip().lower()
    if requested in {"0", "false", "no", "seed"}:
        return False
    if requested in {"1", "true", "yes", "live"}:
        return True
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def main() -> None:
    agent = find_default_agent()
    version = post(
        f"/api/projects/{PROJECT_ID}/agent-designs/{agent['id']}/versions",
        {
            "version_label": "demo",
            "instructions": agent["intent"],
            "status": "baseline",
        },
    )
    scenario = post(
        f"/api/projects/{PROJECT_ID}/scenarios",
        {
            "agent_design_id": agent["id"],
            "name": "Image pull backoff emotional arc",
            "input": SCENARIO_INPUT,
            "setup_context": "test_shape:conversation",
        },
    )
    contract = post(
        f"/api/projects/{PROJECT_ID}/eval-contracts",
        {
            "agent_design_id": agent["id"],
            "name": "Sentiment observer rubric",
            "description": "Judges whether the observer captured the latest emotional movement.",
            "scenario_id": scenario["id"],
            "expected_behavior": [RUBRIC],
            "checks": [
                {
                    "id": "observes_negative_arc",
                    "type": "rubric_judge",
                    "value": RUBRIC,
                }
            ],
        },
    )

    summary = {
        "agent": agent["name"],
        "agent_id": agent["id"],
        "version_id": version["id"],
        "scenario_id": scenario["id"],
        "eval_contract_id": contract["id"],
        "run_id": None,
        "eval_result_id": None,
        "score": None,
    }

    if should_run_live():
        run = post(
            f"/api/projects/{PROJECT_ID}/runs",
            {
                "agent_design_id": agent["id"],
                "agent_version_id": version["id"],
                "scenario_id": scenario["id"],
                "eval_contract_id": contract["id"],
                "mode": "live",
            },
        )
        eval_result = post(
            f"/api/projects/{PROJECT_ID}/runs/{run['id']}/evaluate",
            {"judge_mode": "live"},
        )
        summary.update(
            {
                "run_id": run["id"],
                "eval_result_id": eval_result["id"],
                "score": f"{eval_result['score']}/{len(eval_result['checks'])}",
            }
        )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
