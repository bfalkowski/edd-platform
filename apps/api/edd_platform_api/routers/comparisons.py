from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from edd_platform_api import main as api_main
from edd_platform_api.lookups import (
    get_comparison_or_404,
    get_eval_contract_or_404,
    get_project_or_404,
    get_run_or_404,
)
from edd_platform_api.schemas import Comparison, ComparisonCreate, EvalResult, FailurePacket
from edd_platform_api.state import _comparisons, _eval_results, _failure_packets, store

router = APIRouter()


def find_eval_result_for_run(
    *,
    project_id: str,
    run_id: str,
    eval_contract_id: str,
) -> Optional[EvalResult]:
    for eval_result in _eval_results.values():
        if (
            eval_result.project_id == project_id
            and eval_result.run_id == run_id
            and eval_result.eval_contract_id == eval_contract_id
        ):
            return eval_result
    return None


def failure_packets_for_eval(
    *,
    project_id: str,
    eval_result_id: str,
) -> List[FailurePacket]:
    return [
        failure_packet
        for failure_packet in _failure_packets.values()
        if failure_packet.project_id == project_id
        and failure_packet.eval_result_id == eval_result_id
    ]


def create_comparison_record(
    *,
    project_id: str,
    baseline_run,
    candidate_run,
    eval_contract_id: str,
    baseline_eval_result: EvalResult,
    candidate_eval_result: EvalResult,
    now: datetime,
) -> Comparison:
    baseline_packets = failure_packets_for_eval(
        project_id=project_id,
        eval_result_id=baseline_eval_result.id,
    )
    candidate_packets = failure_packets_for_eval(
        project_id=project_id,
        eval_result_id=candidate_eval_result.id,
    )
    candidate_failed_check_ids = {
        check.check_id for check in candidate_eval_result.checks if not check.passed
    }
    baseline_failed_check_ids = {
        check.check_id for check in baseline_eval_result.checks if not check.passed
    }
    fixed_failure_packet_ids = [
        packet.id
        for packet in baseline_packets
        if not set(packet.failed_check_ids) & candidate_failed_check_ids
    ]
    remaining_failure_packet_ids = [
        packet.id
        for packet in baseline_packets
        if set(packet.failed_check_ids) & candidate_failed_check_ids
    ]
    new_failure_packet_ids = [
        packet.id
        for packet in candidate_packets
        if bool(set(packet.failed_check_ids) - baseline_failed_check_ids)
    ]
    summary = (
        f"Comparison fixed {len(fixed_failure_packet_ids)} failure packet(s), "
        f"left {len(remaining_failure_packet_ids)} remaining, "
        f"and introduced {len(new_failure_packet_ids)} new failure packet(s)."
    )
    comparison_id = f"comparison_{uuid4().hex[:12]}"
    artifact = api_main.create_artifact(
        project_id=project_id,
        artifact_type="COMPARISON",
        artifact_id=comparison_id,
        title="Version comparison",
        body=(
            f"Baseline run\n{baseline_run.id}\n\n"
            f"Candidate run\n{candidate_run.id}\n\n"
            f"Eval contract\n{eval_contract_id}\n\n"
            f"Summary\n{summary}\n\n"
            f"Fixed failures\n"
            + "\n".join(f"- {failure_id}" for failure_id in fixed_failure_packet_ids)
            + "\n\nRemaining failures\n"
            + "\n".join(f"- {failure_id}" for failure_id in remaining_failure_packet_ids)
            + "\n\nNew failures\n"
            + "\n".join(f"- {failure_id}" for failure_id in new_failure_packet_ids)
        ),
        source="comparison",
        agent_design_id=baseline_run.agent_design_id,
        now=now,
    )
    for artifact_id in baseline_run.artifact_ids + candidate_run.artifact_ids:
        api_main.link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=artifact_id,
            relationship_type="SUPPORTED_BY",
            now=now,
        )

    comparison = Comparison(
        id=comparison_id,
        project_id=project_id,
        agent_design_id=baseline_run.agent_design_id,
        baseline_version_id=baseline_run.agent_version_id,
        candidate_version_id=candidate_run.agent_version_id,
        baseline_run_id=baseline_run.id,
        candidate_run_id=candidate_run.id,
        baseline_eval_result_id=baseline_eval_result.id,
        candidate_eval_result_id=candidate_eval_result.id,
        fixed_failure_packet_ids=fixed_failure_packet_ids,
        new_failure_packet_ids=new_failure_packet_ids,
        remaining_failure_packet_ids=remaining_failure_packet_ids,
        summary=summary,
        artifact_ids=[artifact.id],
        created_at=now,
    )
    _comparisons[comparison.id] = comparison
    store.save_record("comparisons", comparison.id, comparison)
    return comparison


@router.post("/api/projects/{project_id}/comparisons", status_code=201)
def create_comparison(
    project_id: str,
    payload: ComparisonCreate,
) -> Comparison:
    get_project_or_404(project_id)
    baseline_run = get_run_or_404(project_id, payload.baseline_run_id)
    candidate_run = get_run_or_404(project_id, payload.candidate_run_id)
    contract = get_eval_contract_or_404(project_id, payload.eval_contract_id)
    if baseline_run.agent_design_id != candidate_run.agent_design_id:
        raise HTTPException(
            status_code=400,
            detail="Comparison runs must belong to the same agent design.",
        )
    if contract.agent_design_id != baseline_run.agent_design_id:
        raise HTTPException(
            status_code=400,
            detail="Comparison eval contract must belong to the same agent design.",
        )
    if baseline_run.scenario_id != candidate_run.scenario_id:
        raise HTTPException(
            status_code=400,
            detail="Comparison runs must use the same scenario.",
        )
    if contract.scenario_id is not None and contract.scenario_id != baseline_run.scenario_id:
        raise HTTPException(
            status_code=400,
            detail="Comparison eval contract must match the compared scenario.",
        )

    baseline_eval_result = find_eval_result_for_run(
        project_id=project_id,
        run_id=baseline_run.id,
        eval_contract_id=contract.id,
    )
    candidate_eval_result = find_eval_result_for_run(
        project_id=project_id,
        run_id=candidate_run.id,
        eval_contract_id=contract.id,
    )
    if baseline_eval_result is None or candidate_eval_result is None:
        raise HTTPException(
            status_code=400,
            detail="Comparison requires both runs to be evaluated against the contract.",
        )

    return create_comparison_record(
        project_id=project_id,
        baseline_run=baseline_run,
        candidate_run=candidate_run,
        eval_contract_id=contract.id,
        baseline_eval_result=baseline_eval_result,
        candidate_eval_result=candidate_eval_result,
        now=datetime.now(timezone.utc),
    )


@router.get("/api/projects/{project_id}/comparisons")
def list_comparisons(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[Comparison]:
    get_project_or_404(project_id)
    comparisons = [
        comparison
        for comparison in _comparisons.values()
        if comparison.project_id == project_id
        and (
            agent_design_id is None
            or comparison.agent_design_id == agent_design_id
        )
    ]
    return sorted(comparisons, key=lambda comparison: comparison.created_at, reverse=True)


@router.get("/api/projects/{project_id}/comparisons/{comparison_id}")
def get_comparison(project_id: str, comparison_id: str) -> Comparison:
    get_project_or_404(project_id)
    return get_comparison_or_404(project_id, comparison_id)
