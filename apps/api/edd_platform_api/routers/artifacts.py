from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from edd_platform_api.eval_checks import evaluate_run_text
from edd_platform_api.lookups import get_artifact_or_404, get_project_or_404
from edd_platform_api.schemas import (
    ArtifactLink,
    ArtifactLinkCreate,
    ArtifactRecord,
    EvalRunResult,
)
from edd_platform_api.state import _artifact_links, _artifacts, store

router = APIRouter()


@router.post("/api/projects/{project_id}/artifacts/{artifact_id}/evaluate", status_code=201)
def evaluate_run_artifact(project_id: str, artifact_id: str) -> EvalRunResult:
    get_project_or_404(project_id)
    run_artifact = get_artifact_or_404(project_id, artifact_id)
    if run_artifact.artifact_type != "RUN_RESULT" or run_artifact.agent_design_id is None:
        raise HTTPException(status_code=400, detail="Only run result artifacts can be evaluated.")

    checks = evaluate_run_text(run_artifact.body)
    score = sum(1 for check in checks if check.passed)
    passed = score == len(checks)
    now = datetime.now(timezone.utc)
    eval_id = f"eval_{uuid4().hex[:12]}"
    check_lines = "\n".join(
        f"- {check.id}: {'pass' if check.passed else 'fail'} - {check.comment}"
        for check in checks
    )
    artifact = ArtifactRecord(
        id=f"artifact_{uuid4().hex[:12]}",
        project_id=project_id,
        artifact_type="EVAL_RESULT",
        artifact_id=eval_id,
        title=f"Eval: {run_artifact.title.replace('Run: ', '')}",
        body=f"Score\n{score}/{len(checks)}\n\nResult\n{'Passed' if passed else 'Failed'}\n\nChecks\n{check_lines}",
        source="judge:mock",
        agent_design_id=run_artifact.agent_design_id,
        created_at=now,
        updated_at=now,
    )
    _artifacts[artifact.id] = artifact
    store.save_record("artifacts", artifact.id, artifact)

    link = ArtifactLink(
        id=f"link_{uuid4().hex[:12]}",
        project_id=project_id,
        source_artifact_id=artifact.id,
        target_artifact_id=run_artifact.id,
        relationship_type="GENERATED_FROM",
        created_at=now,
    )
    _artifact_links[link.id] = link
    store.save_record("artifact_links", link.id, link)

    return EvalRunResult(
        id=eval_id,
        project_id=project_id,
        agent_design_id=run_artifact.agent_design_id,
        run_artifact_id=run_artifact.id,
        mode="mock",
        score=score,
        passed=passed,
        checks=checks,
        artifact=artifact,
        created_at=now,
    )


@router.get("/api/projects/{project_id}/artifacts")
def list_project_artifacts(
    project_id: str,
    agent_design_id: Optional[str] = None,
    artifact_type: Optional[str] = None,
) -> List[ArtifactRecord]:
    get_project_or_404(project_id)
    artifacts = [
        artifact
        for artifact in _artifacts.values()
        if artifact.project_id == project_id
        and (agent_design_id is None or artifact.agent_design_id == agent_design_id)
        and (artifact_type is None or artifact.artifact_type == artifact_type)
    ]
    return sorted(artifacts, key=lambda artifact: artifact.updated_at, reverse=True)


@router.get("/api/projects/{project_id}/artifacts/search")
def search_project_artifacts(
    project_id: str,
    q: str = "",
    artifact_type: Optional[str] = None,
) -> List[ArtifactRecord]:
    get_project_or_404(project_id)
    query = q.strip().lower()
    artifacts = list_project_artifacts(project_id=project_id, artifact_type=artifact_type)
    if not query:
        return artifacts
    return [
        artifact
        for artifact in artifacts
        if query in artifact.title.lower() or query in artifact.body.lower()
    ]


@router.get("/api/projects/{project_id}/artifacts/{artifact_id}")
def get_project_artifact(project_id: str, artifact_id: str) -> ArtifactRecord:
    get_project_or_404(project_id)
    return get_artifact_or_404(project_id, artifact_id)


@router.post("/api/projects/{project_id}/artifact-links", status_code=201)
def create_artifact_link(project_id: str, payload: ArtifactLinkCreate) -> ArtifactLink:
    get_project_or_404(project_id)
    get_artifact_or_404(project_id, payload.source_artifact_id)
    get_artifact_or_404(project_id, payload.target_artifact_id)

    link = ArtifactLink(
        id=f"link_{uuid4().hex[:12]}",
        project_id=project_id,
        source_artifact_id=payload.source_artifact_id,
        target_artifact_id=payload.target_artifact_id,
        relationship_type=payload.relationship_type.strip().upper(),
        created_at=datetime.now(timezone.utc),
    )
    _artifact_links[link.id] = link
    store.save_record("artifact_links", link.id, link)
    return link


@router.get("/api/projects/{project_id}/artifacts/{artifact_id}/links")
def list_artifact_links(project_id: str, artifact_id: str) -> List[ArtifactLink]:
    get_project_or_404(project_id)
    get_artifact_or_404(project_id, artifact_id)
    links = [
        link
        for link in _artifact_links.values()
        if link.project_id == project_id
        and (
            link.source_artifact_id == artifact_id
            or link.target_artifact_id == artifact_id
        )
    ]
    return sorted(links, key=lambda link: link.created_at, reverse=True)
