from __future__ import annotations

from edd_platform_api.schemas import ToolAdapterContract, ToolDefinition


def tool_adapter_contract(tool: ToolDefinition) -> ToolAdapterContract:
    input_schema = tool.input_schema or {"type": "object", "properties": {}}
    output_schema = tool.output_schema or {"type": "object", "properties": {}}
    return ToolAdapterContract(
        tool_id=tool.id,
        name=tool.name,
        status=tool.status,
        langchain={
            "name": tool.name,
            "description": tool.description,
            "args_schema": input_schema,
            "response_schema": output_schema,
            "implementation_kind": tool.implementation_kind,
            "implementation_key": tool.implementation_key,
        },
        openai={
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": input_schema,
            },
        },
        mcp={
            "name": tool.name,
            "description": tool.description,
            "inputSchema": input_schema,
            "outputSchema": output_schema,
        },
        eval_validation={
            "required_tool_name": tool.name,
            "allowed_status": "approved",
            "status": tool.status,
            "input_schema": input_schema,
            "output_schema": output_schema,
            "output_description": tool.output_description,
            "implementation_kind": tool.implementation_kind,
            "implementation_key": tool.implementation_key,
        },
    )
