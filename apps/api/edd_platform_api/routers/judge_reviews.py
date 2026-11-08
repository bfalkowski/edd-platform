from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException

from edd_platform_api import main as api_main
from edd_platform_api.lookups import (
    get_eval_contract_or_404,
    get_eval_result_or_404,
    get_project_or_404,
    get_run_or_404,
)
from edd_platform_api.schemas import (
    FailurePacket,
    JudgeAgreement,
    JudgeReview,
    JudgeReviewCreate,
    JudgeReviewResult,
)
from edd_platform_api.state import (
    _eval_results,
    _failure_packets,
    _judge_outputs,
    store,
)

router = APIRouter()


@router.post(
    "/api/projects/{project_id}/judge-outputs/{judge_output_id}/review",
    status_code=201,
)
def review_judge_output(
    project_id: str,
    judge_output_id: str,
    payload: JudgeReviewCreate,
) -> JudgeReviewResult:
    """Record a reviewer verdict on a judge output: agree, or overrule its pass/fail."""
    get_project_or_404(project_id)
    judge_output = _judge_outputs.get(judge_output_id)
    if judge_output is None or judge_output.project_id != project_id:
        raise HTTPException(status_code=404, detail="Judge output not found.")
    eval_result = get_eval_result_or_404(project_id, judge_output.eval_result_id)
    contract = get_eval_contract_or_404(project_id, eval_result.eval_contract_id)
    run = get_run_or_404(project_id, eval_result.run_id)

    # A second review replaces the first; the judge's own verdict stays fixed.
    judge_passed = (
        judge_output.review.judge_passed if judge_output.review is not None else eval_result.passed
    )
    passed = judge_passed if payload.verdict == "agree" else not judge_passed
    now = datetime.now(timezone.utc)

    review = JudgeReview(
        verdict=payload.verdict,
        reason=payload.reason,
        reviewer=payload.reviewer,
        judge_passed=judge_passed,
        reviewed_at=now,
    )
    judge_output = judge_output.model_copy(update={"review": review})
    _judge_outputs[judge_output.id] = judge_output
    store.save_record("judge_outputs", judge_output.id, judge_output)

    eval_result = eval_result.model_copy(update={"passed": passed})
    _eval_results[eval_result.id] = eval_result
    store.save_record("eval_results", eval_result.id, eval_result)

    judge_verdict = "pass" if judge_passed else "fail"
    review_artifact = api_main.create_artifact(
        project_id=project_id,
        artifact_type="JUDGE_REVIEW",
        artifact_id=judge_output.id,
        title=f"Judge review: {contract.name}",
        body=(
            f"Reviewer\n{payload.reviewer}\n\n"
            f"Verdict\n{'Agreed' if payload.verdict == 'agree' else 'Overruled'}"
            f" (judge said {judge_verdict})\n\n"
            f"Result\n{'Passed' if passed else 'Failed'}\n\n"
            f"Reason\n{payload.reason}"
        ),
        source=f"review:{payload.reviewer}",
        agent_design_id=run.agent_design_id,
        now=now,
    )
    for judge_artifact_id in judge_output.artifact_ids:
        api_main.link_artifacts(
            project_id=project_id,
            source_artifact_id=review_artifact.id,
            target_artifact_id=judge_artifact_id,
            relationship_type="COMMENTS_ON",
            now=now,
        )

    # Packets on a result the judge failed are the judge's; a reviewer overrule
    # closes them as "overruled". Packets on a result the judge passed came from
    # a reviewer overrule; agreeing with the judge closes them as "withdrawn".
    closed_status = "withdrawn" if judge_passed else "overruled"
    diagnosis = f"A reviewer overruled the judge's pass. Reason: {payload.reason}"
    failure_packet: Optional[FailurePacket] = None
    for packet in list(_failure_packets.values()):
        if packet.eval_result_id != eval_result.id:
            continue
        update: dict = {}
        if passed and packet.status == "open":
            update = {"status": closed_status}
        elif not passed and packet.status == closed_status:
            update = {"status": "open"}
            if judge_passed:
                update["diagnosis"] = diagnosis
        if update:
            packet = packet.model_copy(update={**update, "updated_at": now})
            _failure_packets[packet.id] = packet
            store.save_record("failure_packets", packet.id, packet)
        if not passed and packet.status == "open" and failure_packet is None:
            failure_packet = packet
    if not passed and failure_packet is None and judge_passed:
        failure_packet = api_main.create_failure_packet_record(
            project_id=project_id,
            agent_design_id=run.agent_design_id,
            agent_version_id=run.agent_version_id,
            run_id=run.id,
            eval_result_id=eval_result.id,
            eval_contract_id=contract.id,
            failed_check_ids=[check.check_id for check in eval_result.checks],
            title=f"Reviewer overruled judge: {contract.name}",
            diagnosis=diagnosis,
            severity="medium",
            evidence_artifact_ids=[*eval_result.artifact_ids, review_artifact.id],
            recommended_fix="Address the reviewer's reason and propose a bounded agent change.",
            status="open",
            now=now,
        )

    return JudgeReviewResult(
        judge_output=judge_output,
        eval_result=eval_result,
        failure_packet=failure_packet,
    )


@router.get("/api/projects/{project_id}/eval-contracts/{contract_id}/judge-agreement")
def get_judge_agreement(project_id: str, contract_id: str) -> JudgeAgreement:
    """How often reviewers agreed with the judge on this contract's eval results."""
    get_project_or_404(project_id)
    get_eval_contract_or_404(project_id, contract_id)
    eval_result_ids = {
        eval_result.id
        for eval_result in _eval_results.values()
        if eval_result.project_id == project_id and eval_result.eval_contract_id == contract_id
    }
    reviews = [
        judge_output.review
        for judge_output in _judge_outputs.values()
        if judge_output.eval_result_id in eval_result_ids and judge_output.review is not None
    ]
    agreed = sum(1 for review in reviews if review.verdict == "agree")
    return JudgeAgreement(
        eval_contract_id=contract_id,
        reviewed=len(reviews),
        agreed=agreed,
        overruled=len(reviews) - agreed,
        agreement_rate=agreed / len(reviews) if reviews else None,
    )
