from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter

from edd_platform_api import main as api_main
from edd_platform_api.lookups import get_artifact_or_404, get_project_or_404, get_run_or_404, get_trace_ref_or_404
from edd_platform_api.schemas import ExternalArtifactRef, TraceRef, TraceRefCreate
from edd_platform_api.state import _trace_refs, store

router = APIRouter()


def create_trace_ref_record(
    *,
    project_id: str,
    payload: TraceRefCreate,
    now: datetime,
) -> TraceRef:
    run = get_run_or_404(project_id, payload.run_id)
    related_artifacts = [
        get_artifact_or_404(project_id, artifact_id)
        for artifact_id in payload.related_artifact_ids
    ]
    trace_ref = TraceRef(
        id=f"trace_ref_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=run.agent_design_id,
        provider=payload.provider.strip(),
        external_trace_id=payload.external_trace_id.strip(),
        run_id=run.id,
        url=payload.url.strip(),
        metadata=payload.metadata,
        artifact_ids=[],
        created_at=now,
    )
    artifact = api_main.create_artifact(
        project_id=project_id,
        artifact_type="TRACE_REF",
        artifact_id=trace_ref.id,
        title=f"{trace_ref.provider} trace: {trace_ref.external_trace_id}",
        body=(
            f"Provider\n{trace_ref.provider}\n\n"
            f"External trace id\n{trace_ref.external_trace_id}\n\n"
            f"Run\n{trace_ref.run_id}\n\n"
            f"URL\n{trace_ref.url}\n\n"
            f"Metadata\n{json.dumps(trace_ref.metadata, sort_keys=True)}"
        ),
        source=f"trace-ref:{trace_ref.provider}",
        agent_design_id=run.agent_design_id,
        now=now,
        external_refs=[
            ExternalArtifactRef(
                provider=trace_ref.provider,
                ref_type="trace",
                external_id=trace_ref.external_trace_id,
                url=trace_ref.url,
                label="Langfuse trace" if trace_ref.provider == "langfuse" else "Trace",
                metadata=trace_ref.metadata,
            )
        ]
        + api_main.prompt_refs_from_metadata(trace_ref.metadata),
    )
    trace_ref = trace_ref.model_copy(update={"artifact_ids": [artifact.id]})
    _trace_refs[trace_ref.id] = trace_ref
    store.save_record("trace_refs", trace_ref.id, trace_ref)

    for run_artifact_id in run.artifact_ids:
        api_main.link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=run_artifact_id,
            relationship_type="OBSERVES",
            now=now,
        )
    for related_artifact in related_artifacts:
        api_main.link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=related_artifact.id,
            relationship_type="SUPPORTS",
            now=now,
        )
    api_main.link_to_agent_design(
        project_id=project_id,
        agent_design_id=run.agent_design_id,
        artifact=artifact,
        now=now,
    )
    return trace_ref


@router.get("/api/projects/{project_id}/trace-refs")
def list_trace_refs(
    project_id: str,
    agent_design_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> List[TraceRef]:
    get_project_or_404(project_id)
    trace_refs = [
        trace_ref
        for trace_ref in _trace_refs.values()
        if trace_ref.project_id == project_id
        and (agent_design_id is None or trace_ref.agent_design_id == agent_design_id)
        and (run_id is None or trace_ref.run_id == run_id)
    ]
    return sorted(trace_refs, key=lambda trace_ref: trace_ref.created_at, reverse=True)


@router.post("/api/projects/{project_id}/trace-refs", status_code=201)
def create_trace_ref(project_id: str, payload: TraceRefCreate) -> TraceRef:
    get_project_or_404(project_id)
    return create_trace_ref_record(
        project_id=project_id,
        payload=payload,
        now=datetime.now(timezone.utc),
    )


@router.get("/api/projects/{project_id}/trace-refs/{trace_ref_id}")
def get_trace_ref(project_id: str, trace_ref_id: str) -> TraceRef:
    get_project_or_404(project_id)
    return get_trace_ref_or_404(project_id, trace_ref_id)
