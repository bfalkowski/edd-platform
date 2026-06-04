"""Langfuse trace reference helpers for EDD Platform."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LangfuseTraceRef(BaseModel):
    """Reference to a Langfuse trace without copying trace internals."""

    external_trace_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    related_artifact_ids: list[str] = Field(default_factory=list)
    provider: str = "langfuse"

    def to_platform_payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "external_trace_id": self.external_trace_id,
            "run_id": self.run_id,
            "url": self.url,
            "metadata": self.metadata,
            "related_artifact_ids": self.related_artifact_ids,
        }


def build_langfuse_trace_url(*, base_url: str, project_id: str, trace_id: str) -> str:
    normalized_base = base_url.rstrip("/")
    return f"{normalized_base}/project/{project_id}/traces/{trace_id}"


def build_trace_ref_payload(
    *,
    trace_id: str,
    run_id: str,
    base_url: str,
    langfuse_project_id: str,
    metadata: dict[str, Any] | None = None,
    related_artifact_ids: list[str] | None = None,
) -> dict[str, Any]:
    trace_ref = LangfuseTraceRef(
        external_trace_id=trace_id,
        run_id=run_id,
        url=build_langfuse_trace_url(
            base_url=base_url,
            project_id=langfuse_project_id,
            trace_id=trace_id,
        ),
        metadata=metadata or {},
        related_artifact_ids=related_artifact_ids or [],
    )
    return trace_ref.to_platform_payload()


__all__ = [
    "LangfuseTraceRef",
    "build_langfuse_trace_url",
    "build_trace_ref_payload",
]
