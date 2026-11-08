from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter

from edd_platform_api.lookups import get_project_or_404
from edd_platform_api.schemas import ModelCatalog, ModelOption, Project
from edd_platform_api.service_status import ServiceStatusResponse, service_status_response
from edd_platform_api.state import _projects
from edd_runner import ANTHROPIC_MODELS, default_anthropic_model

router = APIRouter()


@router.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@router.get("/api/services", response_model=ServiceStatusResponse)
def get_service_status() -> ServiceStatusResponse:
    return service_status_response()


@router.get("/api/models")
def list_models() -> ModelCatalog:
    """Models a live run can use, and the one used when a run names none."""
    default_model = default_anthropic_model()
    models = [ModelOption(id=model_id, label=label) for model_id, label in ANTHROPIC_MODELS]
    if default_model not in {model.id for model in models}:
        models.insert(0, ModelOption(id=default_model, label=default_model))
    return ModelCatalog(provider="anthropic", default_model=default_model, models=models)


@router.get("/api/projects")
def list_projects() -> List[Project]:
    return sorted(_projects.values(), key=lambda project: project.updated_at, reverse=True)


@router.get("/api/projects/{project_id}")
def get_project(project_id: str) -> Project:
    return get_project_or_404(project_id)
