#!/usr/bin/env python3
"""Full proof-loop E2E: outcome → baseline → diagnose → fix → v1 → compare.

Each LifecycleCase describes one agent outcome and what the harness should
assert at each stage. The default run/judge modes are deterministic so no
provider credentials are required. Pass --run-mode live --judge-mode live
for end-to-end live verification.

Add new cases by appending to CASES — no other changes needed.

Usage:
    uv run scripts/outcome_agent_lifecycle_e2e.py
    uv run scripts/outcome_agent_lifecycle_e2e.py --case weather_lookup
    uv run scripts/outcome_agent_lifecycle_e2e.py --run-mode live --judge-mode live
    uv run scripts/outcome_agent_lifecycle_e2e.py --keep-agents
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


# ---------------------------------------------------------------------------
# Case definitions — add new cases here
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LifecycleCase:
    name: str
    outcome: str

    # Draft assertions
    expected_allowed_tools: List[str] = field(default_factory=list)
    forbidden_allowed_tools: List[str] = field(default_factory=list)
    expected_required_tools: List[str] = field(default_factory=list)

    # Loop control
    run_baseline: bool = True
    expect_baseline_failure: bool = True
    run_full_loop: bool = True   # diagnose → generate fix → v1 → compare


CASES: List[LifecycleCase] = [
    LifecycleCase(
        name="f1_schedule",
        outcome="Deterime where the nexgt 1 race is",
        expected_allowed_tools=["lookup_event_schedule"],
        forbidden_allowed_tools=["get_weather"],   # cross-domain contamination is the real risk
        expected_required_tools=["lookup_event_schedule"],
    ),
    LifecycleCase(
        name="f1_last_result",
        outcome="Who won the last F1 race?",
        expected_allowed_tools=["lookup_event_result"],
        forbidden_allowed_tools=["get_weather"],
        expected_required_tools=["lookup_event_result"],
    ),
    LifecycleCase(
        name="web_search",
        outcome="Find apartments in Greenwich CT from Zillow.",
        expected_allowed_tools=["browse_webpage"],
        forbidden_allowed_tools=["lookup_event_schedule", "lookup_event_result", "get_weather"],
        expected_required_tools=["browse_webpage"],
    ),
    LifecycleCase(
        name="weather_lookup",
        outcome="What is the weather in Boston today?",
        expected_allowed_tools=["get_weather"],
        forbidden_allowed_tools=["lookup_event_schedule", "lookup_event_result"],
        expected_required_tools=["get_weather"],
    ),
    LifecycleCase(
        name="no_tool_draft",
        outcome="Create a support triage agent that classifies refund escalation emails.",
        forbidden_allowed_tools=[
            "get_weather",
            "lookup_event_schedule",
            "lookup_event_result",
        ],
        run_baseline=False,
        run_full_loop=False,
    ),
]


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

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
        timeout: int = 60,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else None
        except HTTPError as exc:
            detail = exc.read().decode("utf-8")
            raise RuntimeError(f"{method} {url} → {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"{method} {url} → {exc.reason}") from exc

    # --- agent lifecycle ---

    def create_from_outcome(self, outcome: str) -> JsonObject:
        return self.request("POST", f"/projects/{self.project_id}/agent-designs/from-outcome", {"outcome": outcome})

    def run_agent(self, agent_id: str, version_id: str, scenario_id: str, contract_id: str, mode: str) -> JsonObject:
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

    def evaluate_run(self, run_id: str, contract_id: str, judge_mode: str) -> JsonObject:
        return self.request(
            "POST",
            f"/projects/{self.project_id}/runs/{run_id}/evaluate",
            {"eval_contract_id": contract_id, "judge_mode": judge_mode},
        )

    def list_failure_packets(self, agent_id: str) -> List[JsonObject]:
        return self.request("GET", f"/projects/{self.project_id}/failure-packets", query={"agent_design_id": agent_id})

    # --- new: diagnose + generate fix ---

    def diagnose_failure(self, eval_result_id: str) -> JsonObject:
        return self.request(
            "POST",
            f"/projects/{self.project_id}/failure-diagnosis",
            {"eval_result_id": eval_result_id},
        )

    def generate_fix(self, agent_id: str, version_id: str, failure_packets: List[JsonObject], contract_id: str) -> JsonObject:
        return self.request(
            "POST",
            f"/projects/{self.project_id}/fix-proposals/generate",
            {
                "agent_design_id": agent_id,
                "target_version_id": version_id,
                "addressed_failure_packet_ids": [p["id"] for p in failure_packets],
                "validation_contract_id": contract_id,
            },
            timeout=60,
        )

    def create_fix_proposal(
        self,
        agent_id: str,
        version_id: str,
        failure_packets: List[JsonObject],
        contract_id: str,
        proposed_instructions: str,
        rationale: str,
    ) -> JsonObject:
        return self.request(
            "POST",
            f"/projects/{self.project_id}/fix-proposals",
            {
                "agent_design_id": agent_id,
                "target_version_id": version_id,
                "title": "E2E generated fix",
                "rationale": rationale,
                "proposed_changes": [{"surface": "instructions", "change": proposed_instructions}],
                "addressed_failure_packet_ids": [p["id"] for p in failure_packets],
                "validation_contract_ids": [contract_id],
                "status": "proposed",
            },
        )

    def create_candidate_version(self, agent_id: str, parent_version_id: str, instructions: str, fix_proposal_id: str) -> JsonObject:
        return self.request(
            "POST",
            f"/projects/{self.project_id}/agent-designs/{agent_id}/versions",
            {
                "parent_version_id": parent_version_id,
                "instructions": instructions,
                "source_fix_proposal_id": fix_proposal_id,
                "status": "candidate",
            },
        )

    def compare_runs(self, baseline_run_id: str, candidate_run_id: str, contract_id: str) -> JsonObject:
        return self.request(
            "POST",
            f"/projects/{self.project_id}/comparisons",
            {
                "baseline_run_id": baseline_run_id,
                "candidate_run_id": candidate_run_id,
                "eval_contract_id": contract_id,
            },
        )

    def delete_agent(self, agent_id: str) -> None:
        self.request("DELETE", f"/projects/{self.project_id}/agent-designs/{agent_id}")


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------

def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_draft(case: LifecycleCase, draft: JsonObject) -> None:
    agent = draft["agent"]
    contract = draft["eval_contract"]
    allowed = agent["allowed_tool_names"]
    draft_tools = [t["name"] for t in draft.get("draft_tools", [])]

    for tool in case.expected_allowed_tools:
        require(tool in allowed, f"missing allowed tool: {tool}")
    for tool in case.forbidden_allowed_tools:
        require(tool not in allowed, f"unexpected allowed tool: {tool}")
    for tool in case.expected_required_tools:
        require(tool in contract["required_tools"], f"missing required tool: {tool}")

    _ = draft_tools  # available for future assertions


# ---------------------------------------------------------------------------
# Full loop runner
# ---------------------------------------------------------------------------

def run_case(
    client: ApiClient,
    case: LifecycleCase,
    cleanup: bool,
    run_mode: str,
    judge_mode: str,
    verbose: bool,
) -> JsonObject:
    result: JsonObject = {"case": case.name, "steps": []}
    agent_id: Optional[str] = None

    def step(name: str, data: JsonObject) -> None:
        result["steps"].append({"step": name, **data})
        if verbose:
            print(f"    [{name}] {json.dumps(data)}")

    try:
        # 1. Draft from outcome
        draft = client.create_from_outcome(case.outcome)
        agent = draft["agent"]
        agent_id = agent["id"]
        assert_draft(case, draft)
        step("draft", {"agent": agent["name"], "allowed_tools": agent["allowed_tool_names"]})

        if not case.run_baseline:
            result["outcome"] = "draft_only"
            return result

        # 2. Run baseline
        baseline_run = client.run_agent(
            agent["id"], draft["version"]["id"],
            draft["scenario"]["id"], draft["eval_contract"]["id"],
            run_mode,
        )
        step("baseline_run", {"run_id": baseline_run["id"], "status": baseline_run["status"]})

        # 3. Evaluate baseline
        baseline_eval = client.evaluate_run(baseline_run["id"], draft["eval_contract"]["id"], judge_mode)
        failed_checks = [c["check_id"] for c in baseline_eval.get("checks", []) if not c["passed"]]
        step("baseline_eval", {"passed": baseline_eval["passed"], "failed_checks": failed_checks})

        if run_mode == "mock" and case.expect_baseline_failure:
            require(not baseline_eval["passed"], "baseline unexpectedly passed in mock mode")

        if baseline_eval["passed"] or not case.run_full_loop:
            result["outcome"] = "baseline_passed" if baseline_eval["passed"] else "stopped_after_baseline"
            return result

        # 4. Collect failure packets
        packets = client.list_failure_packets(agent["id"])
        step("failure_packets", {"count": len(packets)})

        # 5. Auto-diagnose (best-effort — LLM, may fall back gracefully)
        try:
            diagnosis = client.diagnose_failure(baseline_eval["id"])
            step("diagnosis", {
                "failure_mode": diagnosis.get("failure_mode", ""),
                "severity": diagnosis.get("severity", ""),
            })
        except Exception as exc:
            step("diagnosis", {"skipped": str(exc)})
            diagnosis = None

        # 6. Generate fix via LLM
        generated = client.generate_fix(
            agent["id"], draft["version"]["id"], packets, draft["eval_contract"]["id"]
        )
        step("generate_fix", {"rationale": generated.get("rationale", "")[:80]})

        # 7. Save fix proposal
        fix_proposal = client.create_fix_proposal(
            agent["id"],
            draft["version"]["id"],
            packets,
            draft["eval_contract"]["id"],
            generated["proposed_instructions"],
            generated["rationale"],
        )
        step("fix_proposal", {"id": fix_proposal["id"]})

        # 8. Create v1 candidate
        v1 = client.create_candidate_version(
            agent["id"],
            draft["version"]["id"],
            generated["proposed_instructions"],
            fix_proposal["id"],
        )
        step("v1_version", {"id": v1["id"], "label": v1["version_label"]})

        # 9. Run v1
        v1_run = client.run_agent(
            agent["id"], v1["id"],
            draft["scenario"]["id"], draft["eval_contract"]["id"],
            run_mode,
        )
        step("v1_run", {"run_id": v1_run["id"], "status": v1_run["status"]})

        # 10. Evaluate v1
        v1_eval = client.evaluate_run(v1_run["id"], draft["eval_contract"]["id"], judge_mode)
        step("v1_eval", {"passed": v1_eval["passed"]})

        # 11. Compare
        comparison = client.compare_runs(baseline_run["id"], v1_run["id"], draft["eval_contract"]["id"])
        step("comparison", {"id": comparison["id"], "summary": comparison.get("summary", "")[:80]})

        result["outcome"] = "v1_passed" if v1_eval["passed"] else "v1_still_failing"
        return result

    finally:
        if agent_id and cleanup:
            try:
                client.delete_agent(agent_id)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8001/api")
    parser.add_argument("--project-id", default="project_default")
    parser.add_argument("--keep-agents", action="store_true")
    parser.add_argument("--case", choices=[c.name for c in CASES], help="Run a single case.")
    parser.add_argument("--run-mode", choices=["mock", "live"], default="mock")
    parser.add_argument("--judge-mode", choices=["deterministic", "live"], default="deterministic")
    parser.add_argument("--verbose", action="store_true", help="Print each step as it runs.")
    args = parser.parse_args()

    client = ApiClient(args.api_base_url, args.project_id)
    selected = [c for c in CASES if args.case is None or c.name == args.case]

    passed, failed = 0, 0
    for case in selected:
        print(f"  {case.name} ...", end=" ", flush=True)
        try:
            result = run_case(
                client, case,
                cleanup=not args.keep_agents,
                run_mode=args.run_mode,
                judge_mode=args.judge_mode,
                verbose=args.verbose,
            )
            print(f"PASS  outcome={result['outcome']}  steps={len(result['steps'])}")
            passed += 1
        except Exception as exc:
            print(f"FAIL  {exc}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(1)
