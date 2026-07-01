from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from edd_platform_api import main as api_main
from edd_platform_api.lookups import (
    get_agent_design_or_404,
    get_comparison_or_404,
    get_eval_result_or_404,
    get_gate_decision_or_404,
    get_gate_definition_or_404,
    get_project_or_404,
    get_run_or_404,
)
from edd_platform_api.schemas import (
    ArtifactRecord,
    GateDecision,
    GateDecisionCreate,
    GateDefinition,
    GateDefinitionCreate,
)
from edd_platform_api.state import _artifacts, _failure_packets, _gate_decisions, _gate_definitions, store

router = APIRouter()


def artifacts_for_agent_by_type(
    *,
    project_id: str,
    agent_design_id: str,
    artifact_type: str,
) -> List[ArtifactRecord]:
    return [
        artifact
        for artifact in _artifacts.values()
        if artifact.project_id == project_id
        and artifact.agent_design_id == agent_design_id
        and artifact.artifact_type == artifact_type
    ]


def create_gate_decision_record(
    *,
    project_id: str,
    gate: GateDefinition,
    payload: GateDecisionCreate,
    now: datetime,
) -> GateDecision:
    evidence_artifact_ids: List[str] = []
    missing_artifact_types: List[str] = []
    for artifact_type in gate.required_artifact_types:
        matching_artifacts = artifacts_for_agent_by_type(
            project_id=project_id,
            agent_design_id=gate.agent_design_id,
            artifact_type=artifact_type,
        )
        if matching_artifacts:
            evidence_artifact_ids.extend(artifact.id for artifact in matching_artifacts)
        else:
            missing_artifact_types.append(artifact_type)

    if payload.eval_result_id is not None:
        eval_result = get_eval_result_or_404(project_id, payload.eval_result_id)
        if eval_result.run_id:
            run = get_run_or_404(project_id, eval_result.run_id)
            if run.agent_design_id != gate.agent_design_id:
                raise HTTPException(
                    status_code=400,
                    detail="Gate decision eval result must belong to the same agent design.",
                )
        evidence_artifact_ids.extend(eval_result.artifact_ids)

    if payload.comparison_id is not None:
        comparison = get_comparison_or_404(project_id, payload.comparison_id)
        if comparison.agent_design_id != gate.agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Gate decision comparison must belong to the same agent design.",
            )
        evidence_artifact_ids.extend(comparison.artifact_ids)

    blocking_failure_packet_ids = [
        failure.id
        for failure in _failure_packets.values()
        if failure.project_id == project_id
        and failure.agent_design_id == gate.agent_design_id
        and failure.status in gate.blocking_failure_statuses
    ]
    for failure_id in blocking_failure_packet_ids:
        failure_artifact = api_main.find_artifact_by_type_and_artifact_id("FAILURE_PACKET", failure_id)
        if failure_artifact is not None:
            evidence_artifact_ids.append(failure_artifact.id)

    evidence_artifact_ids = sorted(set(evidence_artifact_ids))
    passed = not missing_artifact_types and not blocking_failure_packet_ids
    decision_value: Literal["passed", "blocked"] = "passed" if passed else "blocked"
    rationale_parts = []
    if missing_artifact_types:
        rationale_parts.append(f"Missing required artifacts: {', '.join(missing_artifact_types)}.")
    if blocking_failure_packet_ids:
        rationale_parts.append(
            f"Blocking failure packets remain: {', '.join(blocking_failure_packet_ids)}."
        )
    if not rationale_parts:
        rationale_parts.append("Required evidence is present and no blocking failures remain.")
    decision = GateDecision(
        id=f"gate_decision_{uuid4().hex[:12]}",
        project_id=project_id,
        gate_id=gate.id,
        agent_design_id=gate.agent_design_id,
        eval_result_id=payload.eval_result_id,
        comparison_id=payload.comparison_id,
        decision=decision_value,
        rationale=" ".join(rationale_parts),
        missing_artifact_types=missing_artifact_types,
        blocking_failure_packet_ids=blocking_failure_packet_ids,
        evidence_artifact_ids=evidence_artifact_ids,
        decided_by=payload.decided_by.strip(),
        created_at=now,
    )
    _gate_decisions[decision.id] = decision
    store.save_record("gate_decisions", decision.id, decision)

    gate_artifact = api_main.find_artifact_by_type_and_artifact_id("GATE", gate.id)
    artifact = api_main.create_artifact(
        project_id=project_id,
        artifact_type="GATE_DECISION",
        artifact_id=decision.id,
        title=f"Gate decision: {gate.name}",
        body=(
            f"Decision\n{decision.decision}\n\n"
            f"Rationale\n{decision.rationale}\n\n"
            f"Missing artifacts\n"
            + ("\n".join(f"- {item}" for item in missing_artifact_types) or "None")
            + "\n\nBlocking failures\n"
            + ("\n".join(f"- {item}" for item in blocking_failure_packet_ids) or "None")
        ),
        source="gate-decision",
        agent_design_id=gate.agent_design_id,
        now=now,
    )
    if gate_artifact is not None:
        api_main.link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=gate_artifact.id,
            relationship_type="GENERATED_FROM",
            now=now,
        )
    for evidence_artifact_id in evidence_artifact_ids:
        api_main.link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=evidence_artifact_id,
            relationship_type="SUPPORTED_BY",
            now=now,
        )
    return decision


@router.get("/api/projects/{project_id}/gates")
def list_gate_definitions(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[GateDefinition]:
    get_project_or_404(project_id)
    gates = [
        gate
        for gate in _gate_definitions.values()
        if gate.project_id == project_id
        and (agent_design_id is None or gate.agent_design_id == agent_design_id)
    ]
    return sorted(gates, key=lambda gate: gate.updated_at, reverse=True)


@router.post("/api/projects/{project_id}/gates", status_code=201)
def create_gate_definition(project_id: str, payload: GateDefinitionCreate) -> GateDefinition:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, payload.agent_design_id)
    now = datetime.now(timezone.utc)
    gate = GateDefinition(
        id=f"gate_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        name=payload.name.strip(),
        criteria=payload.criteria,
        required_artifact_types=payload.required_artifact_types,
        threshold=payload.threshold.strip(),
        blocking_failure_statuses=payload.blocking_failure_statuses,
        approval_mode=payload.approval_mode,
        status=payload.status.strip(),
        created_at=now,
        updated_at=now,
    )
    _gate_definitions[gate.id] = gate
    store.save_record("gate_definitions", gate.id, gate)
    artifact = api_main.create_artifact(
        project_id=project_id,
        artifact_type="GATE",
        artifact_id=gate.id,
        title=gate.name,
        body=(
            "Criteria\n"
            + ("\n".join(f"- {criterion}" for criterion in gate.criteria) or "None")
            + "\n\nRequired artifacts\n"
            + (
                "\n".join(f"- {artifact_type}" for artifact_type in gate.required_artifact_types)
                or "None"
            )
            + f"\n\nThreshold\n{gate.threshold}\n\nApproval mode\n{gate.approval_mode}"
        ),
        source="gate-definition",
        agent_design_id=gate.agent_design_id,
        now=now,
    )
    api_main.link_to_agent_design(
        project_id=project_id,
        agent_design_id=gate.agent_design_id,
        artifact=artifact,
        now=now,
    )
    return gate


@router.get("/api/projects/{project_id}/gates/{gate_id}")
def get_gate_definition(project_id: str, gate_id: str) -> GateDefinition:
    get_project_or_404(project_id)
    return get_gate_definition_or_404(project_id, gate_id)


@router.get("/api/projects/{project_id}/gate-decisions")
def list_gate_decisions(
    project_id: str,
    agent_design_id: Optional[str] = None,
    gate_id: Optional[str] = None,
) -> List[GateDecision]:
    get_project_or_404(project_id)
    decisions = [
        decision
        for decision in _gate_decisions.values()
        if decision.project_id == project_id
        and (agent_design_id is None or decision.agent_design_id == agent_design_id)
        and (gate_id is None or decision.gate_id == gate_id)
    ]
    return sorted(decisions, key=lambda decision: decision.created_at, reverse=True)


@router.post("/api/projects/{project_id}/gates/{gate_id}/decisions", status_code=201)
def create_gate_decision(
    project_id: str,
    gate_id: str,
    payload: GateDecisionCreate,
) -> GateDecision:
    get_project_or_404(project_id)
    gate = get_gate_definition_or_404(project_id, gate_id)
    return create_gate_decision_record(
        project_id=project_id,
        gate=gate,
        payload=payload,
        now=datetime.now(timezone.utc),
    )


@router.get("/api/projects/{project_id}/gate-decisions/{decision_id}")
def get_gate_decision(project_id: str, decision_id: str) -> GateDecision:
    get_project_or_404(project_id)
    return get_gate_decision_or_404(project_id, decision_id)
