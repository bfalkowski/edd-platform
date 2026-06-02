from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from edd_platform_api.storage import create_store_from_env


class AgentDesignCreate(BaseModel):
    name: str = Field(min_length=1)
    intent: str = Field(min_length=1)


class Project(BaseModel):
    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


class AgentDesign(BaseModel):
    id: str
    project_id: str
    name: str
    intent: str
    status: str
    created_at: datetime
    updated_at: datetime


class ArtifactRecord(BaseModel):
    id: str
    project_id: str
    artifact_type: str
    artifact_id: str
    title: str
    body: str
    source: str
    agent_design_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ArtifactLinkCreate(BaseModel):
    source_artifact_id: str = Field(min_length=1)
    target_artifact_id: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)


class ArtifactLink(BaseModel):
    id: str
    project_id: str
    source_artifact_id: str
    target_artifact_id: str
    relationship_type: str
    created_at: datetime


class AgentDesignCreated(BaseModel):
    agent: AgentDesign
    artifact: ArtifactRecord


class ContextPackCreate(BaseModel):
    purpose: str = Field(min_length=1)
    agent_design_id: Optional[str] = None


class ContextPack(BaseModel):
    id: str
    project_id: str
    purpose: str
    agent_design_id: Optional[str] = None
    artifacts: List[ArtifactRecord]
    created_at: datetime


app = FastAPI(title="EDD Platform API")
store = create_store_from_env()
seeded_at = datetime.now(timezone.utc)
default_project = Project(
    id="project_default",
    name="EDD Platform",
    description="Local EDD product workspace.",
    created_at=seeded_at,
    updated_at=seeded_at,
)
_projects: Dict[str, Project] = store.load_collection("projects", Project)
_agent_designs: Dict[str, AgentDesign] = store.load_collection("agent_designs", AgentDesign)
_artifacts: Dict[str, ArtifactRecord] = store.load_collection("artifacts", ArtifactRecord)
_artifact_links: Dict[str, ArtifactLink] = store.load_collection("artifact_links", ArtifactLink)
if default_project.id not in _projects:
    _projects[default_project.id] = default_project
    store.save_record("projects", default_project.id, default_project)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


def get_project_or_404(project_id: str) -> Project:
    project = _projects.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def get_artifact_or_404(project_id: str, artifact_id: str) -> ArtifactRecord:
    artifact = _artifacts.get(artifact_id)
    if artifact is None or artifact.project_id != project_id:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return artifact


@app.get("/api/projects")
def list_projects() -> List[Project]:
    return sorted(_projects.values(), key=lambda project: project.updated_at, reverse=True)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> Project:
    return get_project_or_404(project_id)


@app.get("/api/projects/{project_id}/agent-designs")
def list_agent_designs(project_id: str) -> List[AgentDesign]:
    get_project_or_404(project_id)
    agents = [agent for agent in _agent_designs.values() if agent.project_id == project_id]
    return sorted(agents, key=lambda agent: agent.updated_at, reverse=True)


@app.post("/api/projects/{project_id}/agent-designs", status_code=201)
def create_agent_design(project_id: str, payload: AgentDesignCreate) -> AgentDesignCreated:
    get_project_or_404(project_id)
    now = datetime.now(timezone.utc)
    agent = AgentDesign(
        id=f"agent_{uuid4().hex[:12]}",
        project_id=project_id,
        name=payload.name.strip(),
        intent=payload.intent.strip(),
        status="designing",
        created_at=now,
        updated_at=now,
    )
    _agent_designs[agent.id] = agent
    store.save_record("agent_designs", agent.id, agent)

    artifact = ArtifactRecord(
        id=f"artifact_{uuid4().hex[:12]}",
        project_id=project_id,
        artifact_type="AGENT_DESIGN",
        artifact_id=agent.id,
        title=agent.name,
        body=agent.intent,
        source="intent",
        agent_design_id=agent.id,
        created_at=now,
        updated_at=now,
    )
    _artifacts[artifact.id] = artifact
    store.save_record("artifacts", artifact.id, artifact)

    return AgentDesignCreated(agent=agent, artifact=artifact)


@app.get("/api/projects/{project_id}/agent-designs/{agent_id}")
def get_agent_design(project_id: str, agent_id: str) -> AgentDesign:
    get_project_or_404(project_id)
    agent = _agent_designs.get(agent_id)
    if agent is None or agent.project_id != project_id:
        raise HTTPException(status_code=404, detail="Agent design not found.")
    return agent


@app.get("/api/projects/{project_id}/artifacts")
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


@app.get("/api/projects/{project_id}/artifacts/search")
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


@app.get("/api/projects/{project_id}/artifacts/{artifact_id}")
def get_project_artifact(project_id: str, artifact_id: str) -> ArtifactRecord:
    get_project_or_404(project_id)
    return get_artifact_or_404(project_id, artifact_id)


@app.post("/api/projects/{project_id}/artifact-links", status_code=201)
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


@app.get("/api/projects/{project_id}/artifacts/{artifact_id}/links")
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


@app.post("/api/projects/{project_id}/context-packs")
def build_context_pack(project_id: str, payload: ContextPackCreate) -> ContextPack:
    get_project_or_404(project_id)
    agent = _agent_designs.get(payload.agent_design_id) if payload.agent_design_id else None
    if payload.agent_design_id is not None and (
        agent is None or agent.project_id != project_id
    ):
        raise HTTPException(status_code=404, detail="Agent design not found.")

    artifacts = list_project_artifacts(
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
    )
    return ContextPack(
        id=f"context_{uuid4().hex[:12]}",
        project_id=project_id,
        purpose=payload.purpose,
        agent_design_id=payload.agent_design_id,
        artifacts=artifacts,
        created_at=datetime.now(timezone.utc),
    )
