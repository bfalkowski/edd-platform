from __future__ import annotations

import json
from hashlib import sha256
from typing import Dict, List, Optional

from edd_platform_api.schemas import ArtifactRecord, ExternalArtifactRef


def context_pack_cache_key(
    *,
    project_id: str,
    agent_design_id: Optional[str],
    purpose: str,
    summary_type: str,
    mode: str,
    artifacts: List[ArtifactRecord],
) -> str:
    payload = {
        "project_id": project_id,
        "agent_design_id": agent_design_id,
        "purpose": purpose,
        "summary_type": summary_type,
        "mode": mode,
        "artifacts": [
            {
                "id": artifact.id,
                "artifact_type": artifact.artifact_type,
                "updated_at": artifact.updated_at.isoformat(),
            }
            for artifact in artifacts
        ],
    }
    return sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def build_evidence_summary_prompt(
    *,
    purpose: str,
    summary_type: str,
    artifacts: List[ArtifactRecord],
) -> str:
    artifact_blocks = "\n\n".join(
        (
            f"Artifact {index}: {artifact.artifact_type} / {artifact.title}\n"
            f"Source: {artifact.source}\n"
            f"External refs: {artifact_external_ref_summary(artifact)}\n"
            f"Body:\n{artifact.body[:1200]}"
        )
        for index, artifact in enumerate(artifacts[:12], start=1)
    )
    return (
        "Summarize the evidence context below for a product user. "
        "Cite only the supplied artifacts. Keep it concise and decision-oriented.\n\n"
        f"Context purpose: {purpose}\n"
        f"Summary type: {summary_type}\n\n"
        f"{artifact_blocks or 'No artifacts are available.'}"
    )


def build_deterministic_evidence_summary(
    *,
    purpose: str,
    artifacts: List[ArtifactRecord],
) -> str:
    if not artifacts:
        return f"No evidence artifacts are available for {purpose}."
    type_counts: Dict[str, int] = {}
    for artifact in artifacts:
        type_counts[artifact.artifact_type] = type_counts.get(artifact.artifact_type, 0) + 1
    counts = ", ".join(
        f"{artifact_type.lower()}={count}"
        for artifact_type, count in sorted(type_counts.items())
    )
    titles = "; ".join(artifact.title for artifact in artifacts[:3])
    langfuse_refs = [
        external_ref_display(ref)
        for artifact in artifacts
        for ref in artifact.external_refs
        if ref.provider == "langfuse"
    ]
    langfuse_summary = ""
    if langfuse_refs:
        langfuse_summary = (
            " Langfuse refs: "
            + "; ".join(dict.fromkeys(langfuse_refs[:6]))
            + "."
        )
    return (
        f"{purpose} context includes {len(artifacts)} evidence artifacts "
        f"({counts}). Key artifacts: {titles}.{langfuse_summary}"
    )


def external_ref_display(ref: ExternalArtifactRef) -> str:
    label = ref.label or f"{ref.provider} {ref.ref_type}"
    metadata_label = (
        ref.metadata.get("score_name")
        or ref.metadata.get("prompt_name")
        or ref.metadata.get("dataset_name")
        or ref.metadata.get("sync_mode")
    )
    detail = f" ({metadata_label})" if isinstance(metadata_label, str) and metadata_label else ""
    return f"{label}{detail}: {ref.external_id}"


def artifact_external_ref_summary(artifact: ArtifactRecord) -> str:
    if not artifact.external_refs:
        return "None"
    return "; ".join(external_ref_display(ref) for ref in artifact.external_refs)
