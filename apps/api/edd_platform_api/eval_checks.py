from __future__ import annotations

from typing import Dict, List

from edd_platform_api.schemas import (
    EvalCheck,
    EvalCheckResult,
    EvalContractCreate,
    RunRecord,
)


def contract_generated_checks(payload: EvalContractCreate) -> List[Dict[str, object]]:
    checks: List[Dict[str, object]] = []
    checks.extend(payload.checks)
    checks.extend(
        {
            "id": f"requires_evidence_{index}",
            "type": "output_contains",
            "value": evidence,
        }
        for index, evidence in enumerate(payload.required_evidence, start=1)
    )
    checks.extend(
        {
            "id": f"requires_tool_{tool}",
            "type": "tool_called",
            "tool": tool,
        }
        for tool in payload.required_tools
    )
    checks.extend(
        {
            "id": f"forbids_tool_{tool}",
            "type": "tool_not_called",
            "tool": tool,
        }
        for tool in payload.forbidden_tools
    )
    checks.extend(
        {
            "id": f"forbids_behavior_{index}",
            "type": "output_not_contains",
            "value": behavior,
        }
        for index, behavior in enumerate(payload.forbidden_behavior, start=1)
    )
    checks.extend(
        {
            "id": f"requires_output_{index}",
            "type": "output_contains",
            "value": requirement,
        }
        for index, requirement in enumerate(payload.output_requirements, start=1)
    )
    return checks


def evaluate_run_text(body: str) -> List[EvalCheck]:
    normalized = body.lower()
    return [
        EvalCheck(
            id="mentions_evidence",
            passed="evidence" in normalized,
            comment="Response should gather or cite evidence before recommending action.",
        ),
        EvalCheck(
            id="states_assumptions",
            passed="assumption" in normalized,
            comment="Response should make assumptions visible.",
        ),
        EvalCheck(
            id="recommends_safe_action",
            passed="safe next action" in normalized,
            comment="Response should recommend a safe next action.",
        ),
    ]


def evaluate_contract_check(
    *,
    check: Dict[str, object],
    run: RunRecord,
    evidence_artifact_ids: List[str],
    run_artifact_body: str,
) -> EvalCheckResult:
    check_id = str(check.get("id") or "unnamed_check")
    check_type = str(check.get("type") or "manual_review_required")
    expected = str(check.get("value") or check.get("tool") or "")
    normalized_output = run.output.lower()
    normalized_body = run_artifact_body.lower()
    normalized_expected = expected.lower()
    expected_tool_marker = f"tool\n{normalized_expected}"

    if check_type == "output_contains":
        passed = bool(normalized_expected and normalized_expected in normalized_output)
        observed = run.output
        comment = f"Output should contain {expected!r}."
    elif check_type == "output_not_contains":
        passed = bool(normalized_expected and normalized_expected not in normalized_output)
        observed = run.output
        comment = f"Output should not contain {expected!r}."
    elif check_type == "tool_called":
        passed = bool(
            normalized_expected
            and (
                f"- {normalized_expected}:" in normalized_body
                or expected_tool_marker in normalized_body
            )
        )
        observed = run_artifact_body
        comment = f"Run should call tool {expected!r}."
    elif check_type == "tool_not_called":
        passed = bool(
            normalized_expected
            and f"- {normalized_expected}:" not in normalized_body
            and expected_tool_marker not in normalized_body
        )
        observed = run_artifact_body
        comment = f"Run should not call tool {expected!r}."
    elif check_type == "rubric_judge":
        passed = False
        observed = run.output
        comment = "Live judge required for rubric checks."
    else:
        passed = False
        observed = "manual review required"
        comment = f"Unsupported deterministic check type {check_type!r}."

    return EvalCheckResult(
        check_id=check_id,
        check_type=check_type,
        passed=passed,
        observed=observed,
        expected=expected,
        evidence_artifact_ids=evidence_artifact_ids,
        comment=comment,
    )
