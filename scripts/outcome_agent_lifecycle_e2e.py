#!/usr/bin/env python3
"""Exercise outcome-first agent drafting across multiple domains.

The default mode is deterministic and does not call model providers. It uses the
live local API so route wiring, persistence, artifacts, runs, evals, and failure
packets are exercised together.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


JsonObject = Dict[str, Any]


@dataclass(frozen=True)
class LifecycleCase:
    name: str
    outcome: str
    expected_agent_name: str
    expected_allowed_tools: List[str] = field(default_factory=list)
    expected_draft_tools: List[str] = field(default_factory=list)
    expected_capabilities: List[str] = field(default_factory=list)
    forbidden_allowed_tools: List[str] = field(default_factory=list)
    expected_required_tools: List[str] = field(default_factory=list)
    expected_output_requirements: List[str] = field(default_factory=list)
    run_baseline: bool = True
    expect_baseline_failure: bool = True


CASES: List[LifecycleCase] = [
    LifecycleCase(
        name="f1_schedule_typo",
        outcome="Deterime where the nexgt 1 race is",
        expected_agent_name="Schedule Lookup Agent",
        expected_allowed_tools=["lookup_event_schedule"],
        forbidden_allowed_tools=["fetch_web_page", "render_web_page", "get_weather"],
        expected_required_tools=["lookup_event_schedule"],
        expected_output_requirements=["race", "date", "source"],
    ),
    LifecycleCase(
        name="f1_last_result",
        outcome="Who won the last F1 race?",
        expected_agent_name="Race Result Agent",
        expected_allowed_tools=["lookup_event_result"],
        forbidden_allowed_tools=["fetch_web_page", "render_web_page", "get_weather"],
        expected_required_tools=["lookup_event_result"],
        expected_output_requirements=["winner", "race", "source"],
    ),
    LifecycleCase(
        name="apartment_search",
        outcome="Find apartments in Greenwich CT from Zillow.",
        expected_agent_name="Rental Search Agent",
        expected_allowed_tools=["fetch_web_page", "render_web_page"],
        forbidden_allowed_tools=["lookup_event_schedule", "lookup_event_result", "get_weather"],
        expected_required_tools=["render_web_page"],
        expected_output_requirements=["apartment", "source"],
    ),
    LifecycleCase(
        name="weather_lookup",
        outcome="What is the weather in Boston today?",
        expected_agent_name="Weather Agent",
        expected_allowed_tools=["get_weather"],
        forbidden_allowed_tools=["fetch_web_page", "render_web_page"],
        expected_required_tools=["get_weather"],
        expected_output_requirements=["weather"],
    ),
    LifecycleCase(
        name="support_triage_draft_only",
        outcome="Create a support triage agent that classifies refund escalation emails.",
        expected_agent_name="Outcome Agent",
        forbidden_allowed_tools=[
            "fetch_web_page",
            "render_web_page",
            "get_weather",
            "lookup_event_schedule",
            "lookup_event_result",
        ],
        expected_output_requirements=["outcome"],
        run_baseline=False,
    ),
]


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
    ) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=15) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else None
        except HTTPError as exc:
            detail = exc.read().decode("utf-8")
            raise RuntimeError(f"{method} {url} failed: {exc.code} {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc

    def create_from_outcome(self, outcome: str) -> JsonObject:
        return self.request(
            "POST",
            f"/projects/{self.project_id}/agent-designs/from-outcome",
            {"outcome": outcome},
        )

    def run_agent(
        self,
        agent_id: str,
        version_id: str,
        scenario_id: str,
        contract_id: str,
        mode: str,
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
        )

    def evaluate_run(self, run_id: str, contract_id: str, judge_mode: str) -> JsonObject:
        return self.request(
            "POST",
            f"/projects/{self.project_id}/runs/{run_id}/evaluate",
            {"eval_contract_id": contract_id, "judge_mode": judge_mode},
        )

    def list_failure_packets(self, agent_id: str) -> List[JsonObject]:
        return self.request(
            "GET",
            f"/projects/{self.project_id}/failure-packets",
            query={"agent_design_id": agent_id},
        )

    def create_fix_proposal(
        self,
        agent_id: str,
        version_id: str,
        failure_packets: List[JsonObject],
        contract_id: str,
    ) -> JsonObject:
        return self.request(
            "POST",
            f"/projects/{self.project_id}/fix-proposals",
            {
                "agent_design_id": agent_id,
                "target_version_id": version_id,
                "title": "E2E bounded fix",
                "rationale": "Generated by deterministic outcome lifecycle harness.",
                "proposed_changes": [
                    {
                        "surface": "tool_policy",
                        "change": "Approve or implement the required draft tools, then rerun.",
                    }
                ],
                "addressed_failure_packet_ids": [packet["id"] for packet in failure_packets],
                "validation_contract_ids": [contract_id],
                "status": "proposed",
            },
        )

    def delete_agent(self, agent_id: str) -> None:
        self.request("DELETE", f"/projects/{self.project_id}/agent-designs/{agent_id}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_case_draft(case: LifecycleCase, draft: JsonObject) -> None:
    agent = draft["agent"]
    contract = draft["eval_contract"]
    allowed_tools = agent["allowed_tool_names"]
    draft_tools = [tool["name"] for tool in draft.get("draft_tools", [])]

    require(agent["name"] == case.expected_agent_name, f"{case.name}: wrong agent name {agent['name']!r}")
    for tool in case.expected_allowed_tools:
        require(tool in allowed_tools, f"{case.name}: missing allowed tool {tool}")
    for tool in case.expected_draft_tools:
        require(tool in draft_tools, f"{case.name}: missing draft tool {tool}")
    for tool in case.expected_capabilities:
        require(
            tool in allowed_tools or tool in draft_tools,
            f"{case.name}: missing selected or drafted capability {tool}",
        )
    for tool in case.forbidden_allowed_tools:
        require(tool not in allowed_tools, f"{case.name}: unexpectedly allowed tool {tool}")
    for tool in case.expected_required_tools:
        require(tool in contract["required_tools"], f"{case.name}: missing required tool {tool}")
    for item in case.expected_output_requirements:
        require(
            item in contract["output_requirements"],
            f"{case.name}: missing output requirement {item}",
        )


def run_case(
    client: ApiClient,
    case: LifecycleCase,
    cleanup: bool,
    run_mode: str,
    judge_mode: str,
) -> JsonObject:
    draft = client.create_from_outcome(case.outcome)
    agent = draft["agent"]
    try:
        assert_case_draft(case, draft)
        fix_proposal = None
        if case.run_baseline:
            run = client.run_agent(
                agent["id"],
                draft["version"]["id"],
                draft["scenario"]["id"],
                draft["eval_contract"]["id"],
                run_mode,
            )
            eval_result = client.evaluate_run(run["id"], draft["eval_contract"]["id"], judge_mode)
            failure_packets = client.list_failure_packets(agent["id"])
            if run_mode == "mock" and case.expect_baseline_failure:
                require(not eval_result["passed"], f"{case.name}: baseline unexpectedly passed")
                require(failure_packets, f"{case.name}: expected failure packet")
                fix_proposal = client.create_fix_proposal(
                    agent["id"],
                    draft["version"]["id"],
                    failure_packets,
                    draft["eval_contract"]["id"],
                )
            elif run_mode == "mock":
                require(eval_result["passed"], f"{case.name}: baseline unexpectedly failed")
            elif failure_packets:
                fix_proposal = client.create_fix_proposal(
                    agent["id"],
                    draft["version"]["id"],
                    failure_packets,
                    draft["eval_contract"]["id"],
                )
            eval_passed = eval_result["passed"]
            failed_checks = [
                check["check_id"] for check in eval_result["checks"] if not check["passed"]
            ]
        else:
            failure_packets = []
            fix_proposal = None
            eval_passed = None
            failed_checks = []
        return {
            "case": case.name,
            "run_mode": run_mode if case.run_baseline else None,
            "judge_mode": judge_mode if case.run_baseline else None,
            "agent": agent["name"],
            "allowed_tools": agent["allowed_tool_names"],
            "draft_tools": [tool["name"] for tool in draft.get("draft_tools", [])],
            "eval_passed": eval_passed,
            "failed_checks": failed_checks,
            "failure_packets": len(failure_packets),
            "fix_proposal": None if fix_proposal is None else fix_proposal["id"],
        }
    finally:
        if cleanup:
            client.delete_agent(agent["id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8001/api")
    parser.add_argument("--project-id", default="project_default")
    parser.add_argument(
        "--keep-agents",
        action="store_true",
        help="Leave temporary agents in the API for manual inspection.",
    )
    parser.add_argument(
        "--case",
        choices=[case.name for case in CASES],
        help="Run one lifecycle case instead of the full suite.",
    )
    parser.add_argument(
        "--run-mode",
        choices=["mock", "live"],
        default="mock",
        help="Run mode for baseline execution.",
    )
    parser.add_argument(
        "--judge-mode",
        choices=["deterministic", "live"],
        default="deterministic",
        help="Judge mode for run evaluation.",
    )
    args = parser.parse_args()

    client = ApiClient(args.api_base_url, args.project_id)
    results = []
    selected_cases = [case for case in CASES if args.case is None or case.name == args.case]
    for case in selected_cases:
        result = run_case(
            client,
            case,
            cleanup=not args.keep_agents,
            run_mode=args.run_mode,
            judge_mode=args.judge_mode,
        )
        results.append(result)
        print(
            f"PASS {case.name}: agent={result['agent']} "
            f"allowed={result['allowed_tools']} draft={result['draft_tools']} "
            f"eval_passed={result['eval_passed']} "
            f"run_mode={result['run_mode']} judge_mode={result['judge_mode']}"
        )
    print(json.dumps({"results": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
