#!/usr/bin/env python3
"""E2E: Anthropic job search agent for eval and safeguards roles.

The agent must browse the Anthropic careers page and return relevant job
listings in a single tool call. Using more than one browse call is a fail.

Requires a running local API (default http://127.0.0.1:8001/api) with
ANTHROPIC_API_KEY set in the environment or .env.local.

Usage:
    uv run scripts/anthropic_jobs_e2e.py
    uv run scripts/anthropic_jobs_e2e.py --keep-agent
    uv run scripts/anthropic_jobs_e2e.py --api-base-url http://127.0.0.1:8001/api
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


JsonObject = Dict[str, Any]

AGENT_INSTRUCTIONS = """\
You help users find relevant job openings at Anthropic.

When given a search topic:
1. Call browse_webpage EXACTLY ONCE on https://www.anthropic.com/careers/jobs.
2. From what that single call returns, identify roles related to the user's topic.
3. Return a concise list of matching job titles with their departments or locations.

Rules:
- You have ONE tool call budget. Use it on https://www.anthropic.com/jobs.
- Do NOT call browse_webpage a second time under any circumstances.
- Do NOT follow links or load additional pages.
- If the first call returns enough to answer, stop and respond immediately.
"""

SCENARIO_INPUT = (
    "Find Anthropic job listings related to evaluations and AI safeguards."
)

RUBRIC = """\
The agent must return a list of Anthropic job openings related to evaluations, \
safeguards, trust and safety, policy, or alignment research.

Pass requires ALL of the following:
1. At least one specific job title is mentioned (not just "various roles").
2. The response is grounded in what was actually on the careers page — no hallucinated titles.
"""


class ApiClient:
    def __init__(self, base_url: str, project_id: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.project_id = project_id

    def request(
        self,
        method: str,
        path: str,
        payload: Optional[JsonObject] = None,
        query: Optional[JsonObject] = None,
        timeout: int = 120,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else None
        except HTTPError as exc:
            detail = exc.read().decode("utf-8")
            raise RuntimeError(f"{method} {url} failed: {exc.code} {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc

    def create_agent(self, name: str, intent: str, allowed_tools: List[str]) -> JsonObject:
        result = self.request(
            "POST",
            f"/projects/{self.project_id}/agent-designs",
            {
                "name": name,
                "intent": intent,
                "allowed_tool_names": allowed_tools,
            },
        )
        return result["agent"]

    def create_version(self, agent_id: str, instructions: str) -> JsonObject:
        return self.request(
            "POST",
            f"/projects/{self.project_id}/agent-designs/{agent_id}/versions",
            {
                "instructions": instructions,
                "version_label": "v0",
                "status": "baseline",
            },
        )

    def create_scenario(self, agent_id: str, name: str, input_text: str) -> JsonObject:
        return self.request(
            "POST",
            f"/projects/{self.project_id}/scenarios",
            {
                "agent_design_id": agent_id,
                "name": name,
                "input": input_text,
                "setup_context": "single_turn",
            },
        )

    def create_contract(
        self,
        agent_id: str,
        scenario_id: str,
        name: str,
        rubric: str,
    ) -> JsonObject:
        return self.request(
            "POST",
            f"/projects/{self.project_id}/eval-contracts",
            {
                "agent_design_id": agent_id,
                "scenario_id": scenario_id,
                "name": name,
                "checks": [
                    {
                        "id": "rubric_jobs_single_call",
                        "type": "rubric_judge",
                        "value": rubric,
                    }
                ],
                "required_tools": ["browse_webpage"],
                "status": "active",
            },
        )

    def run_agent(
        self,
        agent_id: str,
        version_id: str,
        scenario_id: str,
        contract_id: str,
        mode: str = "live",
    ) -> JsonObject:
        return self.request(
            "POST",
            f"/projects/{self.project_id}/runs",
            {
                "agent_design_id": agent_id,
                "agent_version_id": version_id,
                "scenario_id": scenario_id,
                "eval_contract_id": contract_id,
                "mode": mode,
            },
            timeout=180,
        )

    def evaluate_run(self, run_id: str, contract_id: str) -> JsonObject:
        return self.request(
            "POST",
            f"/projects/{self.project_id}/runs/{run_id}/evaluate",
            {"eval_contract_id": contract_id, "judge_mode": "live"},
            timeout=60,
        )

    def get_judge_output(self, eval_result_id: str) -> Optional[JsonObject]:
        results = self.request(
            "GET",
            f"/projects/{self.project_id}/judge-outputs",
            query={"eval_result_id": eval_result_id},
        )
        return results[0] if results else None

    def delete_agent(self, agent_id: str) -> None:
        self.request("DELETE", f"/projects/{self.project_id}/agent-designs/{agent_id}")


def count_tool_calls(run: JsonObject) -> int:
    """Infer tool call count from artifact_ids.

    Each tool call produces exactly two artifacts (TOOL_CALL + TOOL_RESULT).
    The run itself produces one artifact. So: tool_calls = (len(artifact_ids) - 1) / 2.
    """
    return max(0, (len(run.get("artifact_ids", [])) - 1) // 2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8001/api")
    parser.add_argument("--project-id", default="project_default")
    parser.add_argument(
        "--keep-agent",
        action="store_true",
        help="Leave the agent in the API for manual inspection.",
    )
    args = parser.parse_args()

    client = ApiClient(args.api_base_url, args.project_id)
    agent_id: Optional[str] = None

    try:
        print("Creating agent...")
        agent = client.create_agent(
            name="Anthropic Jobs Agent",
            intent="Find Anthropic job listings relevant to a given search topic by browsing the careers page.",
            allowed_tools=["browse_webpage"],
        )
        agent_id = agent["id"]
        print(f"  agent={agent_id}  allowed_tools={agent['allowed_tool_names']}")

        print("Creating version...")
        version = client.create_version(agent_id, AGENT_INSTRUCTIONS)
        print(f"  version={version['id']}  label={version['version_label']}")

        print("Creating scenario...")
        scenario = client.create_scenario(agent_id, "Eval and safeguards job search", SCENARIO_INPUT)
        print(f"  scenario={scenario['id']}")

        print("Creating eval contract...")
        contract = client.create_contract(
            agent_id,
            scenario["id"],
            "Anthropic jobs: eval and safeguards (single call)",
            RUBRIC,
        )
        print(f"  contract={contract['id']}")

        print("Running agent (live)... this may take up to 2 minutes")
        run = client.run_agent(agent_id, version["id"], scenario["id"], contract["id"])
        print(f"  run={run['id']}  status={run['status']}")
        print(f"\n--- Agent output ---\n{run['output']}\n---\n")

        tool_calls = count_tool_calls(run)
        print(f"  tool_calls={tool_calls}")
        if tool_calls > 1:
            print(
                f"FAIL: agent made {tool_calls} tool calls (max 1 allowed).",
                file=sys.stderr,
            )
            return 1

        print("Evaluating run (live judge)...")
        eval_result = client.evaluate_run(run["id"], contract["id"])
        print(f"  eval_result={eval_result['id']}  passed={eval_result['passed']}")

        judge_output = client.get_judge_output(eval_result["id"])
        if judge_output:
            print(f"\n--- Judge reasoning ---\n{judge_output.get('output', '')}\n---\n")

        failed_checks = [c["check_id"] for c in eval_result.get("checks", []) if not c["passed"]]
        if failed_checks:
            print(f"FAIL: failed checks: {failed_checks}", file=sys.stderr)
            return 1

        if not eval_result["passed"]:
            print("FAIL: eval did not pass.", file=sys.stderr)
            return 1

        print(f"PASS: agent found relevant jobs in {tool_calls} tool call(s).")
        return 0

    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    finally:
        if agent_id and not args.keep_agent:
            try:
                client.delete_agent(agent_id)
                print(f"Cleaned up agent {agent_id}.")
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
