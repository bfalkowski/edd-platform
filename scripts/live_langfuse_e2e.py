#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from typing import Optional, Union
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_BASE_URL = os.environ.get("EDD_PLATFORM_API_URL", "http://127.0.0.1:8001").rstrip("/")
PROJECT_ID = os.environ.get("EDD_PLATFORM_PROJECT_ID", "project_default")


def require_env(name: str) -> None:
    if not os.environ.get(name, "").strip():
        raise SystemExit(f"{name} is required for the live Langfuse E2E.")


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
        with urlopen(request, timeout=120) as response:
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


def get(path: str) -> Union[dict, list]:
    return request_json("GET", path)


def main() -> None:
    require_env("OPENAI_API_KEY")
    os.environ.setdefault("LANGFUSE_BASE_URL", "http://localhost:3001")
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "pk-lf-local-demo")
    os.environ.setdefault("LANGFUSE_SECRET_KEY", "sk-lf-local-demo")

    agent_response = post(
        f"/api/projects/{PROJECT_ID}/agent-designs",
        {
            "name": "Live Langfuse E2E Agent",
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
            "name": "Live Langfuse failed deployment",
            "input": (
                "A customer says a deployment failed after release. They need a "
                "safe next action and are not sure which logs matter."
            ),
        },
    )
    prompt_template = post(
        f"/api/projects/{PROJECT_ID}/judge-prompt-templates",
        {
            "name": "Live Langfuse E2E judge",
            "template": (
                "Judge whether the run satisfies the eval contract using only "
                "the supplied run output and deterministic checks."
            ),
        },
    )
    contract = post(
        f"/api/projects/{PROJECT_ID}/eval-contracts",
        {
            "agent_design_id": agent["id"],
            "name": "Live Langfuse E2E contract",
            "scenario_id": scenario["id"],
            "judge_prompt_template_id": prompt_template["id"],
            "expected_behavior": [
                "Recommend a safe next action.",
                "Ask for deployment logs or equivalent evidence.",
                "State assumptions before diagnosis.",
            ],
            "checks": [
                {
                    "id": "mentions_safe_next_action",
                    "type": "output_contains",
                    "value": "safe next action",
                },
                {
                    "id": "mentions_logs",
                    "type": "output_contains",
                    "value": "logs",
                },
            ],
        },
    )
    run = post(
        f"/api/projects/{PROJECT_ID}/runs",
        {
            "agent_design_id": agent["id"],
            "scenario_id": scenario["id"],
            "eval_contract_id": contract["id"],
            "mode": "live",
        },
    )
    eval_result = post(
        f"/api/projects/{PROJECT_ID}/runs/{run['id']}/evaluate",
        {
            "eval_contract_id": contract["id"],
            "judge_mode": "live",
        },
    )
    trace_refs = get(f"/api/projects/{PROJECT_ID}/trace-refs?run_id={run['id']}")
    if not isinstance(trace_refs, list) or not trace_refs:
        raise SystemExit("Live run completed, but no Langfuse trace ref was created.")

    trace_ref = trace_refs[0]
    print(
        json.dumps(
            {
                "agent": agent["name"],
                "run_id": run["id"],
                "eval_result_id": eval_result["id"],
                "eval_score": f"{eval_result['score']}/{len(eval_result['checks'])}",
                "eval_passed": eval_result["passed"],
                "langfuse_trace_id": trace_ref["external_trace_id"],
                "langfuse_trace_url": trace_ref["url"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
