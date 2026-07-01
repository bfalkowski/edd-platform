from __future__ import annotations

from datetime import datetime, timezone
from typing import List
from uuid import uuid4

from fastapi import APIRouter

from edd_platform_api import main as api_main
from edd_platform_api.lookups import get_judge_prompt_template_or_404, get_project_or_404
from edd_platform_api.schemas import JudgePromptTemplate, JudgePromptTemplateCreate
from edd_platform_api.state import _judge_prompt_templates, store

router = APIRouter()


@router.get("/api/projects/{project_id}/judge-prompt-templates")
def list_judge_prompt_templates(project_id: str) -> List[JudgePromptTemplate]:
    get_project_or_404(project_id)
    templates = [
        template
        for template in _judge_prompt_templates.values()
        if template.project_id == project_id
    ]
    return sorted(templates, key=lambda template: template.updated_at, reverse=True)


@router.post("/api/projects/{project_id}/judge-prompt-templates", status_code=201)
def create_judge_prompt_template(
    project_id: str,
    payload: JudgePromptTemplateCreate,
) -> JudgePromptTemplate:
    get_project_or_404(project_id)
    now = datetime.now(timezone.utc)
    template = JudgePromptTemplate(
        id=f"judge_prompt_{uuid4().hex[:12]}",
        project_id=project_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        template=payload.template.strip(),
        version=payload.version.strip(),
        status=payload.status.strip(),
        langfuse_prompt_name=(
            payload.langfuse_prompt_name.strip()
            if payload.langfuse_prompt_name is not None
            else None
        ),
        langfuse_prompt_version=(
            payload.langfuse_prompt_version.strip()
            if payload.langfuse_prompt_version is not None
            else None
        ),
        langfuse_prompt_label=(
            payload.langfuse_prompt_label.strip()
            if payload.langfuse_prompt_label is not None
            else None
        ),
        created_at=now,
        updated_at=now,
    )
    _judge_prompt_templates[template.id] = template
    store.save_record("judge_prompt_templates", template.id, template)
    api_main.create_artifact(
        project_id=project_id,
        artifact_type="JUDGE_PROMPT_TEMPLATE",
        artifact_id=template.id,
        title=template.name,
        body=(
            f"Description\n{template.description or 'None'}\n\n"
            f"Version\n{template.version}\n\n"
            f"Langfuse prompt\n"
            + api_main.langfuse_prompt_display(
                name=template.langfuse_prompt_name,
                version=template.langfuse_prompt_version,
                label=template.langfuse_prompt_label,
            )
            + "\n\n"
            f"Template\n{template.template}"
        ),
        source="judge-prompt-template",
        agent_design_id=None,
        now=now,
        external_refs=api_main.langfuse_prompt_refs(
            name=template.langfuse_prompt_name,
            version=template.langfuse_prompt_version,
            label=template.langfuse_prompt_label,
            prompt_role="judge",
            source_id=template.id,
        ),
    )
    return template


@router.get("/api/projects/{project_id}/judge-prompt-templates/{judge_prompt_template_id}")
def get_judge_prompt_template(
    project_id: str,
    judge_prompt_template_id: str,
) -> JudgePromptTemplate:
    get_project_or_404(project_id)
    return get_judge_prompt_template_or_404(project_id, judge_prompt_template_id)
