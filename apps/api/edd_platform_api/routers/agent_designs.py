from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response

from edd_platform_api import main as api_main
from edd_platform_api.lookups import (
    get_agent_design_or_404,
    get_agent_version_or_404,
    get_project_or_404,
)
from edd_platform_api.routers import eval_contracts as _eval_contracts_router
from edd_platform_api.routers import scenarios as _scenarios_router
from edd_platform_api.routers import tools as _tools_router
from edd_platform_api.schemas import (
    AgentDesign,
    AgentDesignCreate,
    AgentDesignCreated,
    AgentDesignUpdate,
    AgentVersion,
    AgentVersionCreate,
    ArtifactRecord,
    EvalContractCreate,
    GuidedSetupPreview,
    GuidedSetupRequest,
    OutcomeAgentCreate,
    OutcomeAgentCreated,
    ScenarioCreate,
    ToolDefinition,
    ToolDefinitionCreate,
)
from edd_platform_api.state import (
    _agent_designs,
    _agent_versions,
    _artifact_links,
    _artifacts,
    _comparisons,
    _eval_contracts,
    _eval_results,
    _failure_packets,
    _fix_proposals,
    _gate_decisions,
    _gate_definitions,
    _judge_outputs,
    _runs,
    _scenarios,
    _tool_definitions,
    _trace_refs,
    store,
)

router = APIRouter()


def find_project_tool_by_name(project_id: str, name: str) -> Optional[ToolDefinition]:
    normalized = name.strip()
    return next(
        (
            tool
            for tool in _tool_definitions.values()
            if tool.project_id == project_id and tool.name == normalized
        ),
        None,
    )


def approve_generated_tool(tool: ToolDefinition, mock_response: str) -> ToolDefinition:
    now = datetime.now(timezone.utc)
    updated = tool.model_copy(
        update={
            "implementation_kind": "mock",
            "implementation_key": f"mock.{tool.name}",
            "mock_response": mock_response,
            "status": "approved",
            "updated_at": now,
        }
    )
    _tool_definitions[updated.id] = updated
    store.save_record("tool_definitions", updated.id, updated)
    api_main.upsert_tool_definition_artifact(updated, now)
    return updated


def validate_allowed_tool_names(project_id: str, allowed_tool_names: List[str]) -> None:
    approved_tool_names = {
        tool.name
        for tool in _tool_definitions.values()
        if tool.project_id == project_id and tool.status == "approved"
    }
    unknown_tools = sorted(set(allowed_tool_names) - approved_tool_names)
    if unknown_tools:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown or unapproved tools: {', '.join(unknown_tools)}.",
        )


def _generate_rubric(outcome: str, output_focus: str, has_live_tools: bool = False) -> str:
    _FALLBACK_RUBRIC = (
        "Pass if the response directly satisfies the requested outcome "
        "with specific, concrete details. Fail if the response is generic, "
        "refuses to complete the task, or provides no actionable result."
    )
    try:
        config = api_main.anthropic_config_from_env()
        if has_live_tools:
            tool_instruction = (
                "The agent CAN fetch live data — it has web tools. "
                "NEVER include 'notes limitations', 'acknowledges inability', or similar clauses. "
                "Focus ONLY on whether the fetched data is specific and complete for the outcome."
            )
        else:
            tool_instruction = (
                "The agent has no live tools. "
                "Pass if it provides the best available answer and is clear about what it cannot verify."
            )
        response = api_main._anthropic_client(config).messages.create(
            model=config.model,
            max_tokens=150,
            system=(
                "You write eval rubrics for AI agent outputs. "
                "Return ONLY one sentence starting with 'Pass if'. Max 50 words. "
                "No preamble. No extra sentences. No 'and explicitly notes limitations'."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Outcome: {outcome}\n"
                    f"Expected approach: {output_focus}\n"
                    f"Constraint: {tool_instruction}\n"
                    "Rubric:"
                ),
            }],
        )
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text.strip()
                break
        if not text:
            return _FALLBACK_RUBRIC
        # When agent has live tools, strip any clause about noting limitations
        if has_live_tools:
            for bad_phrase in [
                ", and explicitly notes any limitations",
                ", explicitly noting any limitations",
                " and notes any limitations",
                " while noting limitations",
                ", noting any limitations",
            ]:
                text = text.replace(bad_phrase, "")
        return text
    except Exception:
        return _FALLBACK_RUBRIC


def _generate_test_input(outcome: str, intent: str) -> str:
    """Generate a concrete test input sentence that exercises the agent's intent."""
    _FALLBACK = outcome
    try:
        config = api_main.anthropic_config_from_env()
        response = api_main._anthropic_client(config).messages.create(
            model=config.model,
            max_tokens=100,
            system=(
                "You write realistic test inputs for AI agents. "
                "Return ONLY one sentence a real user would type. No preamble. No quotes."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Agent purpose: {intent}\n"
                    f"User goal: {outcome}\n"
                    "Write one realistic user message that would trigger this agent:"
                ),
            }],
        )
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text.strip().strip('"').strip("'")
                return text if text else _FALLBACK
        return _FALLBACK
    except Exception:
        return _FALLBACK


def delete_agent_design_records(project_id: str, agent_id: str) -> None:
    artifact_ids = [
        artifact.id
        for artifact in _artifacts.values()
        if artifact.project_id == project_id and artifact.agent_design_id == agent_id
    ]
    for artifact_id in artifact_ids:
        _artifacts.pop(artifact_id, None)
        store.delete_record("artifacts", artifact_id)

    link_ids = [
        link.id
        for link in _artifact_links.values()
        if link.project_id == project_id
        and (
            link.source_artifact_id in artifact_ids
            or link.target_artifact_id in artifact_ids
        )
    ]
    for link_id in link_ids:
        _artifact_links.pop(link_id, None)
        store.delete_record("artifact_links", link_id)

    for scenario_id, scenario in list(_scenarios.items()):
        if scenario.project_id == project_id and scenario.agent_design_id == agent_id:
            _scenarios.pop(scenario_id, None)
            store.delete_record("scenarios", scenario_id)

    for contract_id, contract in list(_eval_contracts.items()):
        if contract.project_id == project_id and contract.agent_design_id == agent_id:
            _eval_contracts.pop(contract_id, None)
            store.delete_record("eval_contracts", contract_id)

    for gate_id, gate in list(_gate_definitions.items()):
        if gate.project_id == project_id and gate.agent_design_id == agent_id:
            _gate_definitions.pop(gate_id, None)
            store.delete_record("gate_definitions", gate_id)

    for decision_id, decision in list(_gate_decisions.items()):
        if decision.project_id == project_id and decision.agent_design_id == agent_id:
            _gate_decisions.pop(decision_id, None)
            store.delete_record("gate_decisions", decision_id)

    for version_id, version in list(_agent_versions.items()):
        if version.project_id == project_id and version.agent_design_id == agent_id:
            _agent_versions.pop(version_id, None)
            store.delete_record("agent_versions", version_id)

    deleted_run_ids: List[str] = []
    for run_id, run in list(_runs.items()):
        if run.project_id == project_id and run.agent_design_id == agent_id:
            deleted_run_ids.append(run_id)
            _runs.pop(run_id, None)
            store.delete_record("runs", run_id)

    for trace_ref_id, trace_ref in list(_trace_refs.items()):
        if trace_ref.project_id == project_id and trace_ref.agent_design_id == agent_id:
            _trace_refs.pop(trace_ref_id, None)
            store.delete_record("trace_refs", trace_ref_id)

    deleted_eval_result_ids: List[str] = []
    for eval_result_id, eval_result in list(_eval_results.items()):
        if eval_result.project_id == project_id and eval_result.run_id in deleted_run_ids:
            deleted_eval_result_ids.append(eval_result_id)
            _eval_results.pop(eval_result_id, None)
            store.delete_record("eval_results", eval_result_id)

    for judge_output_id, judge_output in list(_judge_outputs.items()):
        if (
            judge_output.project_id == project_id
            and judge_output.eval_result_id in deleted_eval_result_ids
        ):
            _judge_outputs.pop(judge_output_id, None)
            store.delete_record("judge_outputs", judge_output_id)

    for failure_packet_id, failure_packet in list(_failure_packets.items()):
        if failure_packet.project_id == project_id and failure_packet.run_id in deleted_run_ids:
            _failure_packets.pop(failure_packet_id, None)
            store.delete_record("failure_packets", failure_packet_id)

    for fix_proposal_id, fix_proposal in list(_fix_proposals.items()):
        if fix_proposal.project_id == project_id and fix_proposal.agent_design_id == agent_id:
            _fix_proposals.pop(fix_proposal_id, None)
            store.delete_record("fix_proposals", fix_proposal_id)

    for comparison_id, comparison in list(_comparisons.items()):
        if comparison.project_id == project_id and comparison.agent_design_id == agent_id:
            _comparisons.pop(comparison_id, None)
            store.delete_record("comparisons", comparison_id)

    _agent_designs.pop(agent_id, None)
    store.delete_record("agent_designs", agent_id)


@router.get("/api/projects/{project_id}/agent-designs")
def list_agent_designs(project_id: str) -> List[AgentDesign]:
    get_project_or_404(project_id)
    agents = [agent for agent in _agent_designs.values() if agent.project_id == project_id]
    return sorted(agents, key=lambda agent: agent.updated_at, reverse=True)


@router.post("/api/projects/{project_id}/agent-designs", status_code=201)
def create_agent_design(project_id: str, payload: AgentDesignCreate) -> AgentDesignCreated:
    get_project_or_404(project_id)
    now = datetime.now(timezone.utc)
    agent = AgentDesign(
        id=f"agent_{uuid4().hex[:12]}",
        project_id=project_id,
        name=payload.name.strip(),
        intent=payload.intent.strip(),
        status="designing",
        allowed_tool_names=payload.allowed_tool_names or [
            t.name for t in _tool_definitions.values()
            if t.project_id == project_id and t.status == "approved"
        ],
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
    _agent_designs[agent.id] = agent
    store.save_record("agent_designs", agent.id, agent)

    artifact = api_main.sync_agent_design_artifact(agent, now)

    return AgentDesignCreated(agent=agent, artifact=artifact)


def draft_agent_from_outcome(
    project_id: str,
    outcome: str,
    agent_name: Optional[str] = None,
    rubric_override: Optional[str] = None,
    test_input_override: Optional[str] = None,
) -> OutcomeAgentCreated:
    normalized = " ".join(outcome.strip().split())

    all_project_tools = [
        t for t in _tool_definitions.values()
        if t.project_id == project_id and t.status == "approved"
    ]
    available_tool_names = [t.name for t in all_project_tools]

    plan = api_main._draft_agent_plan_from_llm(normalized, available_tool_names)

    name = plan["name"]
    intent = plan["intent"]
    output_focus = plan["output_focus"]
    output_requirements = plan["output_requirements"]
    allowed_tools = list(plan["allowed_tools"])
    required_tools = list(plan["required_tools"])

    draft_tools: List[ToolDefinition] = []

    lowered = normalized.lower()
    _motorsport_terms = ["grand prix", "formula 1", "formula one", "formula1", "f1", "nexgt 1", "nxt 1"]
    _is_motorsport = any(term in lowered for term in _motorsport_terms) or (
        "race" in lowered and any(term in lowered for term in ["nexgt", "nxt"])
    )
    is_schedule_task = _is_motorsport and any(
        term in lowered for term in ["next", "upcoming", "schedule", "when", "nexgt", "nxt"]
    )
    is_result_task = _is_motorsport and any(
        term in lowered for term in ["last", "latest", "won", "winner", "result"]
    )

    schedule_tool = find_project_tool_by_name(project_id, "lookup_event_schedule")
    result_tool = find_project_tool_by_name(project_id, "lookup_event_result")
    schedule_tool_response = (
        "Race: Austrian Grand Prix. Date: 2026-06-28. Venue: Red Bull Ring, "
        "Spielberg, Austria. Source: Formula 1 calendar."
    )
    result_tool_response = (
        "Race: Barcelona-Catalunya Grand Prix. Date: 2026-06-14. "
        "Winner: Lewis Hamilton. Source: Formula 1 race results."
    )
    if is_schedule_task:
        if schedule_tool is None:
            schedule_tool = _tools_router.create_tool_definition(
                project_id,
                ToolDefinitionCreate(
                    name="lookup_event_schedule",
                    description=(
                        "Find the next scheduled event for a sport, series, or calendar "
                        "after a reference date."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "series": {
                                "type": "string",
                                "description": "Competition or event series, such as Formula 1.",
                            },
                            "reference_date": {
                                "type": "string",
                                "format": "date",
                                "description": "Date used to decide what counts as next.",
                            },
                            "query": {
                                "type": "string",
                                "description": "Original user schedule question.",
                            },
                        },
                        "required": ["series", "reference_date"],
                    },
                    output_schema={
                        "type": "object",
                        "properties": {
                            "event_name": {"type": "string"},
                            "event_date": {"type": "string", "format": "date"},
                            "venue": {"type": "string"},
                            "source_url": {"type": "string"},
                            "retrieved_at": {"type": "string", "format": "date-time"},
                        },
                        "required": ["event_name", "event_date", "source_url"],
                    },
                    output_description="Next scheduled event with date, venue, and source.",
                    implementation_kind="mock",
                    implementation_key="mock.lookup_event_schedule",
                    config_schema={"type": "object", "properties": {}},
                    mock_response=schedule_tool_response,
                    status="approved",
                ),
            )
        elif schedule_tool.status != "approved":
            schedule_tool = approve_generated_tool(schedule_tool, schedule_tool_response)
        if schedule_tool.status != "approved":
            draft_tools.append(schedule_tool)
    if is_result_task:
        if result_tool is None:
            result_tool = _tools_router.create_tool_definition(
                project_id,
                ToolDefinitionCreate(
                    name="lookup_event_result",
                    description=(
                        "Find the latest completed event result for a sport or series, "
                        "including winner and source."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "series": {
                                "type": "string",
                                "description": "Competition or event series, such as Formula 1.",
                            },
                            "query": {
                                "type": "string",
                                "description": "Original user result question.",
                            },
                            "reference_date": {
                                "type": "string",
                                "format": "date",
                                "description": "Date used to decide the latest completed event.",
                            },
                        },
                        "required": ["series", "query"],
                    },
                    output_schema={
                        "type": "object",
                        "properties": {
                            "event_name": {"type": "string"},
                            "event_date": {"type": "string", "format": "date"},
                            "winner": {"type": "string"},
                            "source_url": {"type": "string"},
                            "retrieved_at": {"type": "string", "format": "date-time"},
                        },
                        "required": ["event_name", "winner", "source_url"],
                    },
                    output_description="Latest completed event winner with source.",
                    implementation_kind="mock",
                    implementation_key="mock.lookup_event_result",
                    config_schema={"type": "object", "properties": {}},
                    mock_response=result_tool_response,
                    status="approved",
                ),
            )
        elif result_tool.status != "approved":
            result_tool = approve_generated_tool(result_tool, result_tool_response)
        if result_tool.status != "approved":
            draft_tools.append(result_tool)
    seen_tools: set[str] = set(allowed_tools)
    if is_schedule_task and schedule_tool is not None:
        if schedule_tool.name not in seen_tools:
            allowed_tools.append(schedule_tool.name)
            seen_tools.add(schedule_tool.name)
        if schedule_tool.name not in required_tools:
            required_tools.append(schedule_tool.name)
    if is_result_task and result_tool is not None:
        if result_tool.name not in seen_tools:
            allowed_tools.append(result_tool.name)
            seen_tools.add(result_tool.name)
        if result_tool.name not in required_tools:
            required_tools.append(result_tool.name)

    validate_allowed_tool_names(project_id, allowed_tools)

    live_tool_keys = {"call_http_api", "browse_webpage", "open_meteo_weather"}
    has_live_tools = bool(set(allowed_tools) & live_tool_keys)
    rubric = rubric_override.strip() if rubric_override and rubric_override.strip() else _generate_rubric(normalized, output_focus, has_live_tools=has_live_tools)

    created = create_agent_design(
        project_id,
        AgentDesignCreate(name=agent_name.strip() if agent_name and agent_name.strip() else name, intent=intent, allowed_tool_names=allowed_tools),
    )
    now = datetime.now(timezone.utc)
    if created.agent.allowed_tool_names != allowed_tools:
        agent = created.agent.model_copy(
            update={
                "allowed_tool_names": allowed_tools,
                "updated_at": now,
            }
        )
        _agent_designs[agent.id] = agent
        store.save_record("agent_designs", agent.id, agent)
        artifact = api_main.sync_agent_design_artifact(agent, now)
        created = AgentDesignCreated(agent=agent, artifact=artifact)
    for draft_tool in draft_tools:
        tool_artifact = api_main.find_artifact_by_type_and_artifact_id("TOOL_DEFINITION", draft_tool.id)
        if tool_artifact is not None:
            api_main.link_to_agent_design(
                project_id=project_id,
                agent_design_id=created.agent.id,
                artifact=tool_artifact,
                now=now,
            )
    version = create_agent_version(
        project_id,
        created.agent.id,
        AgentVersionCreate(
            version_label="v0",
            instructions=intent,
            tool_policy={"allowed_tool_names": created.agent.allowed_tool_names},
            status="baseline",
        ),
    )
    scenario = _scenarios_router.create_scenario(
        project_id,
        ScenarioCreate(
            agent_design_id=created.agent.id,
            name="Outcome request",
            input=test_input_override.strip() if test_input_override and test_input_override.strip() else normalized,
            setup_context="test_shape:single_turn\norigin:outcome_draft",
            status="active",
        ),
    )
    contract = _eval_contracts_router.create_eval_contract(
        project_id,
        EvalContractCreate(
            agent_design_id=created.agent.id,
            name="Outcome satisfaction",
            description="Checks the first draft against the user-requested outcome.",
            scenario_id=scenario.id,
            version="v0",
            expected_behavior=[
                f"Address the requested outcome: {normalized}",
                output_focus,
                *(
                    [
                        "Use or implement the proposed lookup tool before treating the design as complete."
                    ]
                    if draft_tools
                    else []
                ),
                "Do not mark the task complete when the response lacks the requested result.",
            ],
            required_tools=required_tools,
            forbidden_behavior=(
                [
                    "I don",
                    "real-time access",
                    "If you provide",
                    "guide you to check",
                    "check a current source",
                ]
                if is_schedule_task or is_result_task
                else []
            ),
            output_requirements=output_requirements,
            checks=[
                {
                    "id": "outcome_rubric",
                    "type": "rubric_judge",
                    "value": rubric,
                }
            ],
            pass_criteria="all_checks_pass",
            status="active",
        ),
    )

    return OutcomeAgentCreated(
        agent=created.agent,
        artifact=created.artifact,
        version=version,
        scenario=scenario,
        eval_contract=contract,
        draft_tools=draft_tools,
    )


@router.post("/api/projects/{project_id}/agent-designs/from-outcome", status_code=201)
def create_agent_design_from_outcome(
    project_id: str,
    payload: OutcomeAgentCreate,
) -> OutcomeAgentCreated:
    get_project_or_404(project_id)
    return draft_agent_from_outcome(
        project_id,
        payload.outcome,
        agent_name=payload.name,
        rubric_override=payload.rubric,
        test_input_override=payload.test_input,
    )


@router.post("/api/projects/{project_id}/guided/setup")
def guided_setup_preview(
    project_id: str,
    payload: GuidedSetupRequest,
) -> GuidedSetupPreview:
    """Preview-only: generate agent name, test input, and rubric from a description.
    No data is persisted. The client uses the result to populate the wizard Step 1
    review screen, then calls from-outcome with overrides to commit."""
    get_project_or_404(project_id)
    normalized = " ".join(payload.description.strip().split())

    all_project_tools = [
        t for t in _tool_definitions.values()
        if t.project_id == project_id and t.status == "approved"
    ]
    available_tool_names = [t.name for t in all_project_tools]

    plan = api_main._draft_agent_plan_from_llm(normalized, available_tool_names)

    live_tool_keys = {"call_http_api", "browse_webpage", "open_meteo_weather"}
    has_live_tools = bool(set(plan["allowed_tools"]) & live_tool_keys)
    rubric = _generate_rubric(normalized, plan["output_focus"], has_live_tools=has_live_tools)
    test_input = _generate_test_input(normalized, plan["intent"])

    return GuidedSetupPreview(
        agent_name=plan["name"],
        test_input=test_input,
        rubric=rubric,
    )


@router.get("/api/projects/{project_id}/agent-designs/{agent_id}")
def get_agent_design(project_id: str, agent_id: str) -> AgentDesign:
    get_project_or_404(project_id)
    return get_agent_design_or_404(project_id, agent_id)


@router.get("/api/projects/{project_id}/agent-designs/{agent_id}/wizard-state")
def get_agent_wizard_state(project_id: str, agent_id: str) -> OutcomeAgentCreated:
    """Return the agent in OutcomeAgentCreated shape so the wizard can resume."""
    get_project_or_404(project_id)
    agent = get_agent_design_or_404(project_id, agent_id)

    versions = sorted(
        [v for v in _agent_versions.values() if v.agent_design_id == agent_id],
        key=lambda v: v.created_at,
    )
    version = next((v for v in versions if v.status == "baseline"), None) or (versions[0] if versions else None)

    contracts = sorted(
        [c for c in _eval_contracts.values() if c.agent_design_id == agent_id],
        key=lambda c: c.created_at,
    )
    contract = contracts[0] if contracts else None

    scenario = _scenarios.get(contract.scenario_id) if contract and contract.scenario_id else None

    if not version or not contract or not scenario:
        raise HTTPException(status_code=404, detail="Agent has no baseline version, scenario, or eval contract yet.")

    artifact = next(
        (a for a in _artifacts.values() if a.artifact_type == "agent_design" and a.project_id == project_id),
        ArtifactRecord(id="", project_id=project_id, artifact_type="agent_design", content={}, created_at=agent.created_at),
    )

    return OutcomeAgentCreated(
        agent=agent,
        artifact=artifact,
        version=version,
        scenario=scenario,
        eval_contract=contract,
        draft_tools=[],
    )


@router.patch("/api/projects/{project_id}/agent-designs/{agent_id}")
def update_agent_design(
    project_id: str,
    agent_id: str,
    payload: AgentDesignUpdate,
) -> AgentDesign:
    get_project_or_404(project_id)
    existing = get_agent_design_or_404(project_id, agent_id)
    allowed_tool_names = existing.allowed_tool_names
    if payload.allowed_tool_names is not None:
        validate_allowed_tool_names(project_id, payload.allowed_tool_names)
        allowed_tool_names = payload.allowed_tool_names

    updated = existing.model_copy(
        update={
            "name": payload.name.strip() if payload.name is not None else existing.name,
            "intent": payload.intent.strip() if payload.intent is not None else existing.intent,
            "allowed_tool_names": allowed_tool_names,
            "status": payload.status.strip() if payload.status is not None else existing.status,
            "langfuse_prompt_name": (
                payload.langfuse_prompt_name.strip()
                if payload.langfuse_prompt_name is not None
                else existing.langfuse_prompt_name
            ),
            "langfuse_prompt_version": (
                payload.langfuse_prompt_version.strip()
                if payload.langfuse_prompt_version is not None
                else existing.langfuse_prompt_version
            ),
            "langfuse_prompt_label": (
                payload.langfuse_prompt_label.strip()
                if payload.langfuse_prompt_label is not None
                else existing.langfuse_prompt_label
            ),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    _agent_designs[updated.id] = updated
    store.save_record("agent_designs", updated.id, updated)
    api_main.sync_agent_design_artifact(updated, updated.updated_at)
    return updated


@router.delete("/api/projects/{project_id}/agent-designs/{agent_id}", status_code=204)
def delete_agent_design(project_id: str, agent_id: str) -> Response:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, agent_id)
    delete_agent_design_records(project_id, agent_id)
    return Response(status_code=204)


@router.get("/api/projects/{project_id}/agent-designs/{agent_id}/versions")
def list_agent_versions(project_id: str, agent_id: str) -> List[AgentVersion]:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, agent_id)
    versions = [
        version
        for version in _agent_versions.values()
        if version.project_id == project_id and version.agent_design_id == agent_id
    ]
    return sorted(versions, key=lambda version: version.created_at)


@router.post("/api/projects/{project_id}/agent-designs/{agent_id}/versions", status_code=201)
def create_agent_version(
    project_id: str,
    agent_id: str,
    payload: AgentVersionCreate,
) -> AgentVersion:
    get_project_or_404(project_id)
    agent = get_agent_design_or_404(project_id, agent_id)
    if payload.parent_version_id is not None:
        parent = get_agent_version_or_404(project_id, payload.parent_version_id)
        if parent.agent_design_id != agent_id:
            raise HTTPException(
                status_code=400,
                detail="Parent version must belong to the same agent design.",
            )

    now = datetime.now(timezone.utc)
    existing_count = len(
        [
            version
            for version in _agent_versions.values()
            if version.project_id == project_id and version.agent_design_id == agent_id
        ]
    )
    version_label = payload.version_label or f"v{existing_count}"
    version = AgentVersion(
        id=f"version_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=agent.id,
        version_label=version_label.strip(),
        parent_version_id=payload.parent_version_id,
        instructions=(payload.instructions or agent.intent).strip(),
        tool_policy=payload.tool_policy or {"allowed_tool_names": agent.allowed_tool_names},
        source_fix_proposal_id=payload.source_fix_proposal_id,
        status=payload.status.strip(),
        langfuse_prompt_name=(
            payload.langfuse_prompt_name.strip()
            if payload.langfuse_prompt_name is not None
            else agent.langfuse_prompt_name
        ),
        langfuse_prompt_version=(
            payload.langfuse_prompt_version.strip()
            if payload.langfuse_prompt_version is not None
            else agent.langfuse_prompt_version
        ),
        langfuse_prompt_label=(
            payload.langfuse_prompt_label.strip()
            if payload.langfuse_prompt_label is not None
            else agent.langfuse_prompt_label
        ),
        created_at=now,
        updated_at=now,
    )
    _agent_versions[version.id] = version
    store.save_record("agent_versions", version.id, version)

    artifact = api_main.create_artifact(
        project_id=project_id,
        artifact_type="AGENT_VERSION",
        artifact_id=version.id,
        title=f"{agent.name} {version.version_label}",
        body=(
            f"Instructions\n{version.instructions}\n\n"
            f"Parent version\n{version.parent_version_id or 'None'}\n\n"
            f"Status\n{version.status}\n\n"
            f"Langfuse prompt\n"
            + api_main.langfuse_prompt_display(
                name=version.langfuse_prompt_name,
                version=version.langfuse_prompt_version,
                label=version.langfuse_prompt_label,
            )
        ),
        source="agent-version",
        agent_design_id=agent.id,
        now=now,
        external_refs=api_main.langfuse_prompt_refs(
            name=version.langfuse_prompt_name,
            version=version.langfuse_prompt_version,
            label=version.langfuse_prompt_label,
            prompt_role="agent_version",
            source_id=version.id,
        ),
    )
    api_main.link_to_agent_design(
        project_id=project_id,
        agent_design_id=agent.id,
        artifact=artifact,
        now=now,
    )
    return version


@router.get("/api/projects/{project_id}/agent-designs/{agent_id}/versions/{version_id}")
def get_agent_version(project_id: str, agent_id: str, version_id: str) -> AgentVersion:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, agent_id)
    version = get_agent_version_or_404(project_id, version_id)
    if version.agent_design_id != agent_id:
        raise HTTPException(status_code=404, detail="Agent version not found.")
    return version
