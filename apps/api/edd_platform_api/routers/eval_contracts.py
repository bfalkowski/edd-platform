from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from edd_platform_api import main as api_main
from edd_platform_api.eval_checks import contract_generated_checks
from edd_platform_api.lookups import (
    get_agent_design_or_404,
    get_eval_contract_or_404,
    get_judge_prompt_template_or_404,
    get_project_or_404,
    get_scenario_or_404,
)
from edd_platform_api.schemas import (
    EvalContract,
    EvalContractChecksUpdate,
    EvalContractCreate,
    EvalContractRubricUpdate,
)
from edd_platform_api.state import _eval_contracts, store

router = APIRouter()


@router.get("/api/projects/{project_id}/eval-contracts")
def list_eval_contracts(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[EvalContract]:
    get_project_or_404(project_id)
    contracts = [
        contract
        for contract in _eval_contracts.values()
        if contract.project_id == project_id
        and (agent_design_id is None or contract.agent_design_id == agent_design_id)
    ]
    return sorted(contracts, key=lambda contract: contract.updated_at, reverse=True)


@router.post("/api/projects/{project_id}/eval-contracts", status_code=201)
def create_eval_contract(project_id: str, payload: EvalContractCreate) -> EvalContract:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, payload.agent_design_id)
    if payload.scenario_id is not None:
        scenario = get_scenario_or_404(project_id, payload.scenario_id)
        if scenario.agent_design_id != payload.agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Eval contract scenario must belong to the same agent design.",
            )
    if payload.judge_prompt_template_id is not None:
        get_judge_prompt_template_or_404(project_id, payload.judge_prompt_template_id)

    now = datetime.now(timezone.utc)
    checks = contract_generated_checks(payload)
    contract = EvalContract(
        id=f"contract_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        scenario_id=payload.scenario_id,
        version=payload.version.strip(),
        expected_behavior=payload.expected_behavior,
        required_evidence=payload.required_evidence,
        required_tools=payload.required_tools,
        forbidden_tools=payload.forbidden_tools,
        forbidden_behavior=payload.forbidden_behavior,
        output_requirements=payload.output_requirements,
        checks=checks,
        judge_prompt_template_id=payload.judge_prompt_template_id,
        pass_criteria=payload.pass_criteria.strip(),
        status=payload.status.strip(),
        created_at=now,
        updated_at=now,
    )
    _eval_contracts[contract.id] = contract
    store.save_record("eval_contracts", contract.id, contract)

    check_lines = "\n".join(
        f"- {check.get('id', 'unnamed_check')}: {check.get('type', 'unspecified')}"
        for check in contract.checks
    )
    artifact = api_main.create_artifact(
        project_id=project_id,
        artifact_type="EVAL_CONTRACT",
        artifact_id=contract.id,
        title=contract.name,
        body=(
            f"Description\n{contract.description or 'None'}\n\n"
            f"Expected behavior\n"
            + "\n".join(f"- {item}" for item in contract.expected_behavior)
            + "\n\nRequired tools\n"
            + "\n".join(f"- {tool}" for tool in contract.required_tools)
            + "\n\nChecks\n"
            + (check_lines or "None")
            + f"\n\nPass criteria\n{contract.pass_criteria}"
        ),
        source="eval-contract",
        agent_design_id=contract.agent_design_id,
        now=now,
    )
    api_main.link_to_agent_design(
        project_id=project_id,
        agent_design_id=contract.agent_design_id,
        artifact=artifact,
        now=now,
    )
    if contract.judge_prompt_template_id is not None:
        prompt_artifact = api_main.find_artifact_by_type_and_artifact_id(
            "JUDGE_PROMPT_TEMPLATE",
            contract.judge_prompt_template_id,
        )
        if prompt_artifact is not None:
            api_main.link_artifacts(
                project_id=project_id,
                source_artifact_id=artifact.id,
                target_artifact_id=prompt_artifact.id,
                relationship_type="USES",
                now=now,
            )
    return contract


@router.get("/api/projects/{project_id}/eval-contracts/{contract_id}")
def get_eval_contract(project_id: str, contract_id: str) -> EvalContract:
    get_project_or_404(project_id)
    return get_eval_contract_or_404(project_id, contract_id)


@router.patch("/api/projects/{project_id}/eval-contracts/{contract_id}/rubric")
def update_eval_contract_rubric(
    project_id: str,
    contract_id: str,
    payload: EvalContractRubricUpdate,
) -> EvalContract:
    get_project_or_404(project_id)
    contract = get_eval_contract_or_404(project_id, contract_id)
    updated_checks = []
    for check in contract.checks:
        if check.get("type") == "rubric_judge":
            updated_checks.append({**check, "value": payload.rubric.strip()})
        else:
            updated_checks.append(check)
    updated = contract.model_copy(
        update={"checks": updated_checks, "updated_at": datetime.now(timezone.utc)}
    )
    _eval_contracts[contract_id] = updated
    store.save_record("eval_contracts", contract_id, updated)
    return updated


@router.patch("/api/projects/{project_id}/eval-contracts/{contract_id}/checks")
def update_eval_contract_checks(
    project_id: str,
    contract_id: str,
    payload: EvalContractChecksUpdate,
) -> EvalContract:
    get_project_or_404(project_id)
    contract = get_eval_contract_or_404(project_id, contract_id)
    updated = contract.model_copy(
        update={"checks": payload.checks, "updated_at": datetime.now(timezone.utc)}
    )
    _eval_contracts[contract_id] = updated
    store.save_record("eval_contracts", contract_id, updated)
    return updated
