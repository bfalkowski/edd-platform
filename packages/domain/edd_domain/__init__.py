"""Shared EDD domain package."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel

AgentDesignStatus = Literal["designing", "running", "evaluating", "ready_for_review"]


class ProjectRecord(BaseModel):
    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


class AgentDesignRecord(BaseModel):
    id: str
    project_id: str
    name: str
    intent: str
    status: AgentDesignStatus
    created_at: datetime
    updated_at: datetime


class EvidenceReference(BaseModel):
    id: str
    kind: str
    title: str
    source: str


ArtifactType = Literal["AGENT_DESIGN"]


class ArtifactRecord(BaseModel):
    id: str
    project_id: str
    artifact_type: ArtifactType
    artifact_id: str
    title: str
    body: str
    source: str
    agent_design_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


ContextPackPurpose = Literal[
    "AGENT_PROMPT_REVIEW",
    "SIDE_BY_SIDE_VERSION_COMPARISON",
    "FIX_PROPOSAL_GENERATION",
    "GATE_DECISION_REVIEW",
    "FAILURE_TRIAGE",
    "VERSION_RELEASE_SUMMARY",
]


class ContextPack(BaseModel):
    id: str
    project_id: str
    purpose: ContextPackPurpose
    agent_design_id: Optional[str] = None
    artifacts: List[ArtifactRecord]
    created_at: datetime


__all__ = [
    "AgentDesignRecord",
    "AgentDesignStatus",
    "ArtifactRecord",
    "ArtifactType",
    "ContextPack",
    "ContextPackPurpose",
    "EvidenceReference",
    "ProjectRecord",
]
