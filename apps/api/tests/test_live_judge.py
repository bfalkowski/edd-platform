from datetime import datetime, timezone

import pytest

from edd_platform_api import main as _api_main  # noqa: F401  (load main before the router)
from edd_platform_api.routers.runs import build_live_judge_prompt, live_judge_passed
from edd_platform_api.schemas import EvalCheckResult, EvalContract, RunRecord

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_check(check_id: str, check_type: str, passed: bool, comment: str) -> EvalCheckResult:
    return EvalCheckResult(
        check_id=check_id,
        check_type=check_type,
        passed=passed,
        observed="observed",
        expected="expected",
        evidence_artifact_ids=[],
        comment=comment,
    )


def test_live_judge_prompt_leaves_out_rubric_placeholder_result() -> None:
    contract = EvalContract(
        id="contract_1",
        project_id="project_default",
        agent_design_id="agent_1",
        name="Triage",
        description="",
        version="v1",
        expected_behavior=["Ask for logs before diagnosing."],
        required_evidence=[],
        required_tools=[],
        forbidden_tools=[],
        forbidden_behavior=[],
        output_requirements=[],
        checks=[{"id": "asks_for_logs_before_diagnosing", "type": "rubric_judge", "value": "Asks for logs."}],
        pass_criteria="all",
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )
    run = RunRecord(
        id="run_1",
        project_id="project_default",
        agent_design_id="agent_1",
        scenario_id="scenario_1",
        mode="live",
        input="My deploy failed.",
        output="Please share the deployment logs.",
        status="completed",
        artifact_ids=[],
        started_at=NOW,
        completed_at=NOW,
    )
    checks = [
        make_check(
            "asks_for_logs_before_diagnosing",
            "rubric_judge",
            False,
            "Live judge required for rubric checks.",
        ),
        make_check("mentions_logs", "contains", True, "Found logs."),
    ]

    prompt = build_live_judge_prompt(
        contract=contract, run=run, checks=checks, template=None, rubric="Asks for logs."
    )

    assert "Live judge required" not in prompt
    assert "asks_for_logs_before_diagnosing: fail" not in prompt
    assert "- mentions_logs: pass" in prompt
    assert "Rubric:\nAsks for logs." in prompt


@pytest.mark.parametrize(
    "reply",
    [
        "PASS: asks for logs.",
        "pass - asks for logs.",
        "**PASS** The agent asks for logs.",
        "__PASS__ asks for logs.",
        "Verdict: PASS. Asks for logs.",
        "**Verdict:** PASS",
        "Verdict: **PASS**",
        "  \n*pass*\nAsks for logs.",
    ],
)
def test_live_judge_reads_pass_verdict_forms(reply: str) -> None:
    assert live_judge_passed(reply) is True


@pytest.mark.parametrize(
    "reply",
    [
        "FAIL: diagnoses without logs.",
        "**FAIL** passes over the logs.",
        "Verdict: FAIL",
        "The response does not pass.",
        "PASSIVE wording only.",
        "",
    ],
)
def test_live_judge_reads_fail_and_unclear_verdicts_as_fail(reply: str) -> None:
    assert live_judge_passed(reply) is False
