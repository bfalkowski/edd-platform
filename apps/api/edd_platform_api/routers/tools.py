from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from edd_platform_api import main as api_main
from edd_platform_api.lookups import get_project_or_404
from edd_platform_api.schemas import ToolAdapterContract, ToolDefinition, ToolDefinitionCreate, ToolDefinitionUpdate
from edd_platform_api.state import _agent_designs, _tool_definitions, store
from edd_platform_api.tool_adapters import tool_adapter_contract

router = APIRouter()


def validate_json_schema_object(schema: Dict[str, object], field_name: str) -> None:
    schema_type = schema.get("type")
    if schema_type is not None and schema_type != "object":
        raise HTTPException(status_code=400, detail=f"{field_name} must be an object schema.")
    properties = schema.get("properties")
    if properties is not None and not isinstance(properties, dict):
        raise HTTPException(status_code=400, detail=f"{field_name}.properties must be an object.")
    required = schema.get("required")
    if required is not None:
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            raise HTTPException(status_code=400, detail=f"{field_name}.required must be a list of strings.")


@router.get("/api/projects/{project_id}/tools")
def list_tool_definitions(project_id: str) -> List[ToolDefinition]:
    get_project_or_404(project_id)
    tools = [tool for tool in _tool_definitions.values() if tool.project_id == project_id]
    return sorted(tools, key=lambda tool: tool.name)


@router.post("/api/projects/{project_id}/tools", status_code=201)
def create_tool_definition(project_id: str, payload: ToolDefinitionCreate) -> ToolDefinition:
    get_project_or_404(project_id)
    name = payload.name.strip()
    existing_names = {
        tool.name
        for tool in _tool_definitions.values()
        if tool.project_id == project_id
    }
    if name in existing_names:
        raise HTTPException(status_code=409, detail="Tool name already exists.")
    validate_json_schema_object(payload.input_schema, "input_schema")
    if payload.output_schema is not None:
        validate_json_schema_object(payload.output_schema, "output_schema")
    validate_json_schema_object(payload.config_schema, "config_schema")

    now = datetime.now(timezone.utc)
    tool = ToolDefinition(
        id=f"tool_{uuid4().hex[:12]}",
        project_id=project_id,
        name=name,
        description=payload.description.strip(),
        input_schema=payload.input_schema or {"type": "object", "properties": {}},
        output_schema=payload.output_schema,
        output_description=payload.output_description.strip(),
        implementation_kind=payload.implementation_kind,
        implementation_key=payload.implementation_key.strip(),
        config_schema=payload.config_schema,
        mock_response=payload.mock_response,
        status=payload.status,
        created_at=now,
        updated_at=now,
    )
    _tool_definitions[tool.id] = tool
    store.save_record("tool_definitions", tool.id, tool)
    api_main.upsert_tool_definition_artifact(tool, now)
    return tool


@router.patch("/api/projects/{project_id}/tools/{tool_id}")
def update_tool_definition(
    project_id: str,
    tool_id: str,
    payload: ToolDefinitionUpdate,
) -> ToolDefinition:
    get_project_or_404(project_id)
    existing = _tool_definitions.get(tool_id)
    if existing is None or existing.project_id != project_id:
        raise HTTPException(status_code=404, detail="Tool not found.")
    if payload.status is None:
        return existing

    now = datetime.now(timezone.utc)
    updated = existing.model_copy(update={"status": payload.status, "updated_at": now})
    _tool_definitions[updated.id] = updated
    store.save_record("tool_definitions", updated.id, updated)
    api_main.upsert_tool_definition_artifact(updated, now)
    return updated


@router.delete("/api/projects/{project_id}/tools/{tool_id}", status_code=204, response_model=None)
def delete_tool_definition(project_id: str, tool_id: str) -> None:
    get_project_or_404(project_id)
    existing = _tool_definitions.get(tool_id)
    if existing is None or existing.project_id != project_id:
        raise HTTPException(status_code=404, detail="Tool not found.")
    del _tool_definitions[tool_id]
    store.delete_record("tool_definitions", tool_id)
    # Remove this tool from any agent's allowlist
    for agent in list(_agent_designs.values()):
        if agent.project_id == project_id and existing.name in agent.allowed_tool_names:
            updated_names = [n for n in agent.allowed_tool_names if n != existing.name]
            now = datetime.now(timezone.utc)
            updated_agent = agent.model_copy(update={"allowed_tool_names": updated_names, "updated_at": now})
            _agent_designs[agent.id] = updated_agent
            store.save_record("agent_designs", agent.id, updated_agent)


@router.get("/api/projects/{project_id}/tools/{tool_id}/adapter-contracts")
def get_tool_adapter_contracts(
    project_id: str,
    tool_id: str,
) -> ToolAdapterContract:
    get_project_or_404(project_id)
    tool = _tool_definitions.get(tool_id)
    if tool is None or tool.project_id != project_id:
        raise HTTPException(status_code=404, detail="Tool not found.")
    return tool_adapter_contract(tool)
