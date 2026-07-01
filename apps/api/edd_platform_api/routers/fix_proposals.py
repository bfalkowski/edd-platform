from __future__ import annotations

import json as _json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from edd_platform_api import main as api_main
from edd_platform_api.lookups import (
    get_agent_design_or_404,
    get_agent_version_or_404,
    get_artifact_or_404,
    get_eval_contract_or_404,
    get_eval_result_or_404,
    get_failure_packet_or_404,
    get_fix_proposal_or_404,
    get_project_or_404,
)
from edd_platform_api.schemas import (
    FailureDiagnosis,
    FailureDiagnosisRequest,
    FailurePacket,
    FailurePacketCreate,
    FailurePacketUpdate,
    FixProposal,
    FixProposalCreate,
    FixProposalGenerateRequest,
    FixProposalGenerated,
    FixProposalUpdate,
)
from edd_platform_api.state import (
    _agent_versions,
    _artifacts,
    _eval_contracts,
    _failure_packets,
    _fix_proposals,
    _judge_outputs,
    _runs,
    store,
)

router = APIRouter()


def validate_fix_proposal_references(
    *,
    project_id: str,
    agent_design_id: str,
    target_version_id: Optional[str],
    addressed_failure_packet_ids: List[str],
    validation_contract_ids: List[str],
) -> None:
    get_agent_design_or_404(project_id, agent_design_id)
    if target_version_id is not None:
        target_version = get_agent_version_or_404(project_id, target_version_id)
        if target_version.agent_design_id != agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Fix proposal target version must belong to the same agent design.",
            )

    for failure_packet_id in addressed_failure_packet_ids:
        failure_packet = get_failure_packet_or_404(project_id, failure_packet_id)
        if failure_packet.agent_design_id != agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Fix proposal failure packets must belong to the same agent design.",
            )

    for contract_id in validation_contract_ids:
        contract = get_eval_contract_or_404(project_id, contract_id)
        if contract.agent_design_id != agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Fix proposal validation contracts must belong to the same agent design.",
            )


def fix_proposal_artifact_body(fix_proposal: FixProposal) -> str:
    change_lines = "\n".join(
        f"- {change.get('surface', 'change')}: {change.get('change', change)}"
        for change in fix_proposal.proposed_changes
    )
    return (
        f"Rationale\n{fix_proposal.rationale}\n\n"
        f"Target version\n{fix_proposal.target_version_id or 'None'}\n\n"
        f"Addressed failures\n"
        + "\n".join(
            f"- {failure_id}" for failure_id in fix_proposal.addressed_failure_packet_ids
        )
        + "\n\nValidation contracts\n"
        + "\n".join(
            f"- {contract_id}" for contract_id in fix_proposal.validation_contract_ids
        )
        + f"\n\nProposed changes\n{change_lines or 'Needs review'}"
    )


def create_fix_proposal_record(
    *,
    project_id: str,
    agent_design_id: str,
    target_version_id: Optional[str],
    title: str,
    rationale: str,
    proposed_changes: List[Dict[str, object]],
    addressed_failure_packet_ids: List[str],
    validation_contract_ids: List[str],
    status: str,
    now: datetime,
) -> FixProposal:
    fix_proposal = FixProposal(
        id=f"fix_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=agent_design_id,
        target_version_id=target_version_id,
        title=title,
        rationale=rationale,
        proposed_changes=proposed_changes,
        addressed_failure_packet_ids=addressed_failure_packet_ids,
        validation_contract_ids=validation_contract_ids,
        status=status,
        created_at=now,
        updated_at=now,
    )

    artifact = api_main.create_artifact(
        project_id=project_id,
        artifact_type="FIX_PROPOSAL",
        artifact_id=fix_proposal.id,
        title=fix_proposal.title,
        body=fix_proposal_artifact_body(fix_proposal),
        source="fix-proposal",
        agent_design_id=agent_design_id,
        now=now,
    )
    fix_proposal = fix_proposal.model_copy(update={"artifact_ids": [artifact.id]})
    _fix_proposals[fix_proposal.id] = fix_proposal
    store.save_record("fix_proposals", fix_proposal.id, fix_proposal)

    for failure_packet_id in addressed_failure_packet_ids:
        failure_artifact = api_main.find_artifact_by_type_and_artifact_id(
            "FAILURE_PACKET",
            failure_packet_id,
        )
        if failure_artifact is not None:
            api_main.link_artifacts(
                project_id=project_id,
                source_artifact_id=artifact.id,
                target_artifact_id=failure_artifact.id,
                relationship_type="ADDRESSES",
                now=now,
            )
    api_main.link_to_agent_design(
        project_id=project_id,
        agent_design_id=agent_design_id,
        artifact=artifact,
        now=now,
    )
    return fix_proposal


@router.post("/api/projects/{project_id}/failure-diagnosis")
def diagnose_failure(
    project_id: str,
    payload: FailureDiagnosisRequest,
) -> FailureDiagnosis:
    get_project_or_404(project_id)
    eval_result = get_eval_result_or_404(project_id, payload.eval_result_id)
    contract = _eval_contracts.get(eval_result.eval_contract_id)
    run = _runs.get(eval_result.run_id)

    judge_output = next(
        (j for j in _judge_outputs.values() if j.eval_result_id == eval_result.id),
        None,
    )
    judge_text = judge_output.output if judge_output else ""

    failed_check_summaries = []
    for check_result in eval_result.checks:
        if not check_result.passed:
            summary = f"- {check_result.check_id} ({check_result.check_type})"
            if check_result.comment:
                summary += f": {check_result.comment}"
            elif check_result.observed:
                summary += f": observed={check_result.observed}"
            failed_check_summaries.append(summary)

    rubric = ""
    if contract:
        for check in contract.checks:
            if check.get("type") == "rubric_judge" and check.get("value"):
                rubric = check["value"]
                break

    run_output = run.output if run else ""

    prompt = (
        "You are helping a developer debug why an AI agent failed an evaluation.\n\n"
        f"Agent run output:\n{run_output[:1500]}\n\n"
        f"Success criteria (rubric): {rubric or 'Not specified.'}\n\n"
        f"Failed checks:\n" + ("\n".join(failed_check_summaries) or "None listed.") + "\n\n"
        f"Judge verdict:\n{judge_text[:1500]}\n\n"
        "Based on this evidence, provide:\n"
        "1. failure_mode: a short phrase naming what went wrong (e.g. 'missed rollback step', 'hallucinated tool call')\n"
        "2. severity: one of low / medium / high\n"
        "3. review_note: one or two sentences explaining why the response failed and what specifically needs to change\n\n"
        "Respond as JSON only: {\"failure_mode\": \"...\", \"severity\": \"...\", \"review_note\": \"...\"}"
    )

    try:
        config = api_main.anthropic_config_from_env()
        response = api_main._anthropic_client(config).messages.create(
            model=config.model,
            max_tokens=400,
            system="You diagnose AI agent evaluation failures. Respond with JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw = block.text.strip()
                break
        data = _json.loads(raw)
        return {
            "failure_mode": str(data.get("failure_mode", "")),
            "severity": str(data.get("severity", "medium")),
            "review_note": str(data.get("review_note", "")),
            "judge_output": judge_text,
        }
    except Exception:
        return {
            "failure_mode": "",
            "severity": "medium",
            "review_note": "",
            "judge_output": judge_text,
        }


@router.get("/api/projects/{project_id}/failure-packets")
def list_failure_packets(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[FailurePacket]:
    get_project_or_404(project_id)
    failure_packets = [
        failure_packet
        for failure_packet in _failure_packets.values()
        if failure_packet.project_id == project_id
        and (
            agent_design_id is None
            or failure_packet.agent_design_id == agent_design_id
        )
    ]
    return sorted(
        failure_packets,
        key=lambda failure_packet: failure_packet.updated_at,
        reverse=True,
    )


@router.post("/api/projects/{project_id}/failure-packets", status_code=201)
def create_failure_packet(
    project_id: str,
    payload: FailurePacketCreate,
) -> FailurePacket:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, payload.agent_design_id)
    run = _runs.get(payload.run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found.")
    eval_result = get_eval_result_or_404(project_id, payload.eval_result_id)
    contract = get_eval_contract_or_404(project_id, payload.eval_contract_id)
    if (
        run.agent_design_id != payload.agent_design_id
        or eval_result.run_id != run.id
        or contract.agent_design_id != payload.agent_design_id
    ):
        raise HTTPException(
            status_code=400,
            detail="Failure packet references must belong to the same evaluated run.",
        )
    for evidence_artifact_id in payload.evidence_artifact_ids:
        get_artifact_or_404(project_id, evidence_artifact_id)

    return api_main.create_failure_packet_record(
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        agent_version_id=payload.agent_version_id,
        run_id=payload.run_id,
        eval_result_id=payload.eval_result_id,
        eval_contract_id=payload.eval_contract_id,
        failed_check_ids=payload.failed_check_ids,
        title=payload.title.strip(),
        diagnosis=payload.diagnosis.strip(),
        severity=payload.severity.strip(),
        evidence_artifact_ids=payload.evidence_artifact_ids,
        recommended_fix=payload.recommended_fix.strip(),
        status=payload.status.strip(),
        now=datetime.now(timezone.utc),
    )


@router.get("/api/projects/{project_id}/failure-packets/{failure_packet_id}")
def get_failure_packet(project_id: str, failure_packet_id: str) -> FailurePacket:
    get_project_or_404(project_id)
    return get_failure_packet_or_404(project_id, failure_packet_id)


@router.patch("/api/projects/{project_id}/failure-packets/{failure_packet_id}")
def update_failure_packet(
    project_id: str,
    failure_packet_id: str,
    payload: FailurePacketUpdate,
) -> FailurePacket:
    get_project_or_404(project_id)
    existing = get_failure_packet_or_404(project_id, failure_packet_id)
    updated = existing.model_copy(
        update={
            "title": payload.title.strip() if payload.title is not None else existing.title,
            "diagnosis": (
                payload.diagnosis.strip()
                if payload.diagnosis is not None
                else existing.diagnosis
            ),
            "severity": (
                payload.severity.strip()
                if payload.severity is not None
                else existing.severity
            ),
            "recommended_fix": (
                payload.recommended_fix.strip()
                if payload.recommended_fix is not None
                else existing.recommended_fix
            ),
            "status": payload.status.strip() if payload.status is not None else existing.status,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    _failure_packets[updated.id] = updated
    store.save_record("failure_packets", updated.id, updated)
    return updated


@router.get("/api/projects/{project_id}/fix-proposals")
def list_fix_proposals(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[FixProposal]:
    get_project_or_404(project_id)
    fix_proposals = [
        fix_proposal
        for fix_proposal in _fix_proposals.values()
        if fix_proposal.project_id == project_id
        and (
            agent_design_id is None
            or fix_proposal.agent_design_id == agent_design_id
        )
    ]
    return sorted(
        fix_proposals,
        key=lambda fix_proposal: fix_proposal.updated_at,
        reverse=True,
    )


@router.post("/api/projects/{project_id}/fix-proposals/generate")
def generate_fix_proposal(
    project_id: str,
    payload: FixProposalGenerateRequest,
) -> FixProposalGenerated:
    get_project_or_404(project_id)
    agent = get_agent_design_or_404(project_id, payload.agent_design_id)
    version = _agent_versions.get(payload.target_version_id)
    if version is None or version.project_id != project_id:
        raise HTTPException(status_code=404, detail="Agent version not found.")
    packets = [
        _failure_packets[pid]
        for pid in payload.addressed_failure_packet_ids
        if pid in _failure_packets and _failure_packets[pid].project_id == project_id
    ]
    contract = _eval_contracts.get(payload.validation_contract_id) if payload.validation_contract_id else None

    rubric_text = ""
    if contract:
        for check in contract.checks:
            if check.get("type") == "rubric_judge" and check.get("value"):
                rubric_text = check["value"]
                break

    failure_lines = []
    for p in packets:
        failure_lines.append(f"- Failure: {p.title}")
        failure_lines.append(f"  Diagnosis: {p.diagnosis}")
        failure_lines.append(f"  Severity: {p.severity}")
        if p.recommended_fix:
            failure_lines.append(f"  Suggested fix direction: {p.recommended_fix}")
    failure_summary = "\n".join(failure_lines) or "No failure packets provided."

    human_note = (payload.failure_description or "").strip()
    prompt = (
        f"You are improving an AI agent's instructions after a failed evaluation.\n\n"
        f"Agent name: {agent.name}\n"
        f"Agent intent: {agent.intent}\n"
        f"Allowed tools: {', '.join(agent.allowed_tool_names) or 'none'}\n\n"
        f"Current instructions ({version.version_label}):\n{version.instructions}\n\n"
        f"What failed:\n{failure_summary}\n\n"
        + (f"Human diagnosis: {human_note}\n\n" if human_note else "")
        + f"Success criteria (rubric): {rubric_text or 'Not specified.'}\n\n"
        f"Write improved instructions for the next version that directly address the failure. "
        f"Prioritise the human diagnosis above all else if provided. "
        f"Keep everything that worked. Fix only what caused the failure. "
        f"If tools are available, be explicit about when and how to use them. "
        f"Return only the instructions text — no preamble, no explanation, no headers."
    )

    try:
        config = api_main.anthropic_config_from_env()
        response = api_main._anthropic_client(config).messages.create(
            model=config.model,
            max_tokens=1200,
            system="You write precise AI agent instructions. Return only the instruction text.",
            messages=[{"role": "user", "content": prompt}],
        )
        proposed_instructions = ""
        for block in response.content:
            if hasattr(block, "text"):
                proposed_instructions = block.text.strip()
                break
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM fix generation failed: {exc}") from exc

    rationale = (
        f"Generated fix addressing: {'; '.join(p.title for p in packets)}."
        if packets else "Generated fix from failure context."
    )
    return {"proposed_instructions": proposed_instructions, "rationale": rationale}


@router.post("/api/projects/{project_id}/fix-proposals", status_code=201)
def create_fix_proposal(
    project_id: str,
    payload: FixProposalCreate,
) -> FixProposal:
    get_project_or_404(project_id)
    validate_fix_proposal_references(
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        target_version_id=payload.target_version_id,
        addressed_failure_packet_ids=payload.addressed_failure_packet_ids,
        validation_contract_ids=payload.validation_contract_ids,
    )
    return create_fix_proposal_record(
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        target_version_id=payload.target_version_id,
        title=payload.title.strip(),
        rationale=payload.rationale.strip(),
        proposed_changes=payload.proposed_changes,
        addressed_failure_packet_ids=payload.addressed_failure_packet_ids,
        validation_contract_ids=payload.validation_contract_ids,
        status=payload.status.strip(),
        now=datetime.now(timezone.utc),
    )


@router.get("/api/projects/{project_id}/fix-proposals/{fix_proposal_id}")
def get_fix_proposal(project_id: str, fix_proposal_id: str) -> FixProposal:
    get_project_or_404(project_id)
    return get_fix_proposal_or_404(project_id, fix_proposal_id)


@router.patch("/api/projects/{project_id}/fix-proposals/{fix_proposal_id}")
def update_fix_proposal(
    project_id: str,
    fix_proposal_id: str,
    payload: FixProposalUpdate,
) -> FixProposal:
    get_project_or_404(project_id)
    existing = get_fix_proposal_or_404(project_id, fix_proposal_id)
    target_version_id = existing.target_version_id
    addressed_failure_packet_ids = existing.addressed_failure_packet_ids
    validation_contract_ids = existing.validation_contract_ids
    if payload.addressed_failure_packet_ids is not None:
        addressed_failure_packet_ids = payload.addressed_failure_packet_ids
    if payload.validation_contract_ids is not None:
        validation_contract_ids = payload.validation_contract_ids
    validate_fix_proposal_references(
        project_id=project_id,
        agent_design_id=existing.agent_design_id,
        target_version_id=target_version_id,
        addressed_failure_packet_ids=addressed_failure_packet_ids,
        validation_contract_ids=validation_contract_ids,
    )
    updated = existing.model_copy(
        update={
            "title": payload.title.strip() if payload.title is not None else existing.title,
            "rationale": (
                payload.rationale.strip()
                if payload.rationale is not None
                else existing.rationale
            ),
            "proposed_changes": (
                payload.proposed_changes
                if payload.proposed_changes is not None
                else existing.proposed_changes
            ),
            "addressed_failure_packet_ids": addressed_failure_packet_ids,
            "validation_contract_ids": validation_contract_ids,
            "status": payload.status.strip() if payload.status is not None else existing.status,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    _fix_proposals[updated.id] = updated
    store.save_record("fix_proposals", updated.id, updated)
    for artifact_id in updated.artifact_ids:
        artifact = _artifacts.get(artifact_id)
        if artifact is not None:
            updated_artifact = artifact.model_copy(
                update={
                    "title": updated.title,
                    "body": fix_proposal_artifact_body(updated),
                    "updated_at": updated.updated_at,
                }
            )
            _artifacts[updated_artifact.id] = updated_artifact
            store.save_record("artifacts", updated_artifact.id, updated_artifact)
    return updated
