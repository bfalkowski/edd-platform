from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter

from edd_platform_api import main as api_main
from edd_platform_api.lookups import get_agent_design_or_404, get_eval_contract_or_404, get_project_or_404, get_scenario_or_404
from edd_platform_api.schemas import ExternalArtifactRef, Scenario, ScenarioCreate
from edd_platform_api.state import _scenarios, store

router = APIRouter()


def planned_langfuse_scenario_refs(
    *,
    project_id: str,
    scenario: Scenario,
    metadata: Optional[Dict[str, object]] = None,
) -> List[ExternalArtifactRef]:
    base_metadata: Dict[str, object] = {"sync_mode": "planned"}
    if metadata is not None:
        base_metadata.update(metadata)
    return [
        ExternalArtifactRef(
            provider="langfuse",
            ref_type="dataset",
            external_id=f"dataset:{project_id}:{scenario.agent_design_id}",
            label="Langfuse dataset",
            metadata=base_metadata,
        ),
        ExternalArtifactRef(
            provider="langfuse",
            ref_type="dataset_item",
            external_id=f"dataset_item:{scenario.id}",
            label="Langfuse dataset item",
            metadata=base_metadata,
        ),
    ]


def langfuse_dataset_sync_enabled() -> bool:
    return os.environ.get("EDD_PLATFORM_LANGFUSE_DATASET_SYNC", "").strip().lower() == "live"


def object_field(value: object, field_name: str, fallback: str) -> str:
    field_value = getattr(value, field_name, None)
    if field_value is None and isinstance(value, dict):
        field_value = value.get(field_name)
    return str(field_value or fallback)


def sync_langfuse_scenario_dataset_refs(
    *,
    project_id: str,
    scenario: Scenario,
) -> List[ExternalArtifactRef]:
    if not langfuse_dataset_sync_enabled():
        return planned_langfuse_scenario_refs(project_id=project_id, scenario=scenario)
    if not api_main.langfuse_credentials_configured():
        return planned_langfuse_scenario_refs(
            project_id=project_id,
            scenario=scenario,
            metadata={"sync_requested": "live", "sync_error": "missing_langfuse_credentials"},
        )

    dataset_name = f"edd:{project_id}:{scenario.agent_design_id}:scenarios"
    dataset_metadata: Dict[str, object] = {
        "project_id": project_id,
        "agent_design_id": scenario.agent_design_id,
        "source": "edd-platform",
    }
    item_metadata: Dict[str, object] = {
        **dataset_metadata,
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "setup_context": scenario.setup_context,
        "fixture_refs": scenario.fixture_refs,
        "default_eval_contract_id": scenario.default_eval_contract_id,
    }
    try:
        langfuse = api_main.get_langfuse_client()
        dataset = langfuse.create_dataset(
            name=dataset_name,
            description=f"EDD scenarios for agent design {scenario.agent_design_id}.",
            metadata=dataset_metadata,
        )
        dataset_item = langfuse.create_dataset_item(
            dataset_name=dataset_name,
            input=scenario.input,
            expected_output=None,
            metadata=item_metadata,
            id=scenario.id,
        )
    except Exception as exc:
        return planned_langfuse_scenario_refs(
            project_id=project_id,
            scenario=scenario,
            metadata={"sync_requested": "live", "sync_error": str(exc)},
        )

    return [
        ExternalArtifactRef(
            provider="langfuse",
            ref_type="dataset",
            external_id=object_field(dataset, "id", dataset_name),
            label="Langfuse dataset",
            metadata={
                **dataset_metadata,
                "sync_mode": "live",
                "dataset_name": dataset_name,
            },
        ),
        ExternalArtifactRef(
            provider="langfuse",
            ref_type="dataset_item",
            external_id=object_field(dataset_item, "id", scenario.id),
            label="Langfuse dataset item",
            metadata={
                **item_metadata,
                "sync_mode": "live",
                "dataset_name": dataset_name,
            },
        ),
    ]


@router.get("/api/projects/{project_id}/scenarios")
def list_scenarios(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[Scenario]:
    get_project_or_404(project_id)
    scenarios = [
        scenario
        for scenario in _scenarios.values()
        if scenario.project_id == project_id
        and (agent_design_id is None or scenario.agent_design_id == agent_design_id)
    ]
    return sorted(scenarios, key=lambda scenario: scenario.updated_at, reverse=True)


@router.post("/api/projects/{project_id}/scenarios", status_code=201)
def create_scenario(project_id: str, payload: ScenarioCreate) -> Scenario:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, payload.agent_design_id)
    if payload.default_eval_contract_id is not None:
        get_eval_contract_or_404(project_id, payload.default_eval_contract_id)

    now = datetime.now(timezone.utc)
    scenario = Scenario(
        id=f"scenario_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        name=payload.name.strip(),
        input=payload.input.strip(),
        setup_context=payload.setup_context.strip(),
        fixture_refs=payload.fixture_refs,
        default_eval_contract_id=payload.default_eval_contract_id,
        status=payload.status.strip(),
        created_at=now,
        updated_at=now,
    )
    _scenarios[scenario.id] = scenario
    store.save_record("scenarios", scenario.id, scenario)

    artifact = api_main.create_artifact(
        project_id=project_id,
        artifact_type="SCENARIO",
        artifact_id=scenario.id,
        title=scenario.name,
        body=(
            f"Input\n{scenario.input}\n\n"
            f"Setup context\n{scenario.setup_context or 'None'}\n\n"
            f"Default eval contract\n{scenario.default_eval_contract_id or 'None'}"
        ),
        source="scenario",
        agent_design_id=scenario.agent_design_id,
        now=now,
        external_refs=sync_langfuse_scenario_dataset_refs(
            project_id=project_id,
            scenario=scenario,
        ),
    )
    api_main.link_to_agent_design(
        project_id=project_id,
        agent_design_id=scenario.agent_design_id,
        artifact=artifact,
        now=now,
    )
    return scenario


@router.get("/api/projects/{project_id}/scenarios/{scenario_id}")
def get_scenario(project_id: str, scenario_id: str) -> Scenario:
    get_project_or_404(project_id)
    return get_scenario_or_404(project_id, scenario_id)
