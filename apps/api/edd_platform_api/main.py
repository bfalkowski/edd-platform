from __future__ import annotations

import json
import os
import sys
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from edd_platform_api.storage import create_store_from_env

ROOT = Path(__file__).resolve().parents[3]
RUNNER_ROOT = ROOT / "packages" / "runner"
if str(RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNNER_ROOT))

from edd_runner import (  # noqa: E402
    RunnerAgentDesign,
    RunnerScenario,
    RunnerToolDefinition,
    describe_empty_response,
    extract_response_text,
    openai_config_from_env,
    run_mock_agent,
    run_openai_agent,
)


class AgentDesignCreate(BaseModel):
    name: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    allowed_tool_names: List[str] = Field(default_factory=list)


class AgentDesignUpdate(BaseModel):
    name: Optional[str] = None
    intent: Optional[str] = None
    allowed_tool_names: Optional[List[str]] = None
    status: Optional[str] = None


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
    allowed_tool_names: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ScenarioCreate(BaseModel):
    agent_design_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    input: str = Field(min_length=1)
    setup_context: str = ""
    fixture_refs: List[str] = Field(default_factory=list)
    default_eval_contract_id: Optional[str] = None
    status: str = "draft"


class Scenario(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    name: str
    input: str
    setup_context: str
    fixture_refs: List[str]
    default_eval_contract_id: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class EvalContractCreate(BaseModel):
    agent_design_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    scenario_id: Optional[str] = None
    version: str = "v1"
    expected_behavior: List[str] = Field(default_factory=list)
    required_evidence: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    forbidden_tools: List[str] = Field(default_factory=list)
    forbidden_behavior: List[str] = Field(default_factory=list)
    output_requirements: List[str] = Field(default_factory=list)
    checks: List[Dict[str, object]] = Field(default_factory=list)
    judge_prompt_template_id: Optional[str] = None
    pass_criteria: str = "all_checks_pass"
    status: str = "draft"


class EvalContract(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    name: str
    description: str
    scenario_id: Optional[str] = None
    version: str
    expected_behavior: List[str]
    required_evidence: List[str]
    required_tools: List[str]
    forbidden_tools: List[str]
    forbidden_behavior: List[str]
    output_requirements: List[str]
    checks: List[Dict[str, object]]
    judge_prompt_template_id: Optional[str] = None
    pass_criteria: str
    status: str
    created_at: datetime
    updated_at: datetime


class JudgePromptTemplateCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    template: str = Field(min_length=1)
    version: str = "v1"
    status: str = "draft"


class JudgePromptTemplate(BaseModel):
    id: str
    project_id: str
    name: str
    description: str
    template: str
    version: str
    status: str
    created_at: datetime
    updated_at: datetime


class GateDefinitionCreate(BaseModel):
    agent_design_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    criteria: List[str] = Field(default_factory=list)
    required_artifact_types: List[str] = Field(default_factory=list)
    threshold: str = "all_required_artifacts_present"
    blocking_failure_statuses: List[str] = Field(default_factory=lambda: ["open"])
    approval_mode: Literal["automatic", "manual"] = "manual"
    status: str = "draft"


class GateDefinition(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    name: str
    criteria: List[str]
    required_artifact_types: List[str]
    threshold: str
    blocking_failure_statuses: List[str]
    approval_mode: str
    status: str
    created_at: datetime
    updated_at: datetime


class GateDecisionCreate(BaseModel):
    eval_result_id: Optional[str] = None
    comparison_id: Optional[str] = None
    decided_by: str = "platform"


class GateDecision(BaseModel):
    id: str
    project_id: str
    gate_id: str
    agent_design_id: str
    eval_result_id: Optional[str] = None
    comparison_id: Optional[str] = None
    decision: Literal["passed", "blocked"]
    rationale: str
    missing_artifact_types: List[str]
    blocking_failure_packet_ids: List[str]
    evidence_artifact_ids: List[str]
    decided_by: str
    created_at: datetime


class AgentVersionCreate(BaseModel):
    version_label: Optional[str] = None
    parent_version_id: Optional[str] = None
    instructions: Optional[str] = None
    tool_policy: Dict[str, object] = Field(default_factory=dict)
    source_fix_proposal_id: Optional[str] = None
    status: str = "candidate"


class AgentVersion(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    version_label: str
    parent_version_id: Optional[str] = None
    instructions: str
    tool_policy: Dict[str, object]
    source_fix_proposal_id: Optional[str] = None
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


class ToolDefinition(BaseModel):
    id: str
    project_id: str
    name: str
    description: str
    input_schema: Dict[str, object]
    output_schema: Optional[Dict[str, object]] = None
    output_description: str
    implementation_kind: Literal["http", "python", "mcp", "builtin", "mock"] = "builtin"
    implementation_key: str
    config_schema: Dict[str, object] = Field(default_factory=dict)
    mock_response: Optional[str] = None
    status: Literal["draft", "approved"]
    created_at: datetime
    updated_at: datetime


class ToolDefinitionCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    input_schema: Dict[str, object] = Field(default_factory=dict)
    output_schema: Optional[Dict[str, object]] = None
    output_description: str = Field(min_length=1)
    implementation_kind: Literal["http", "python", "mcp", "builtin", "mock"] = "mock"
    implementation_key: str = Field(min_length=1)
    config_schema: Dict[str, object] = Field(default_factory=dict)
    mock_response: Optional[str] = None
    status: Literal["draft", "approved"] = "draft"


class ToolDefinitionUpdate(BaseModel):
    status: Optional[Literal["draft", "approved"]] = None


class AgentRunCreate(BaseModel):
    scenario_input: str = Field(
        default="A customer asks what the agent should do next.",
        min_length=1,
    )
    mode: Literal["mock", "live"] = "mock"


class RunCreate(BaseModel):
    agent_design_id: str = Field(min_length=1)
    agent_version_id: Optional[str] = None
    scenario_id: str = Field(min_length=1)
    eval_contract_id: Optional[str] = None
    mode: Literal["mock", "live"] = "mock"


class RunRecord(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    agent_version_id: Optional[str] = None
    scenario_id: str
    eval_contract_id: Optional[str] = None
    mode: str
    provider: Optional[str] = None
    model: Optional[str] = None
    input: str
    output: str
    status: str
    artifact_ids: List[str]
    started_at: datetime
    completed_at: datetime


class TraceRefCreate(BaseModel):
    provider: str = "langfuse"
    external_trace_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    metadata: Dict[str, object] = Field(default_factory=dict)
    related_artifact_ids: List[str] = Field(default_factory=list)


class TraceRef(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    provider: str
    external_trace_id: str
    run_id: str
    url: str
    metadata: Dict[str, object]
    artifact_ids: List[str]
    created_at: datetime


class AgentRunResult(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    mode: str
    scenario_input: str
    response: str
    tool_calls: List[Dict[str, str]]
    evidence: List[str]
    trace_id: Optional[str] = None
    trace_url: Optional[str] = None
    artifact: ArtifactRecord
    created_at: datetime


class EvalCheck(BaseModel):
    id: str
    passed: bool
    comment: str


class EvalCheckResult(BaseModel):
    check_id: str
    check_type: str
    passed: bool
    observed: str
    expected: str
    evidence_artifact_ids: List[str]
    comment: str


class RunEvaluateCreate(BaseModel):
    eval_contract_id: Optional[str] = None
    judge_mode: Literal["deterministic", "live"] = "deterministic"


class EvalResult(BaseModel):
    id: str
    project_id: str
    run_id: str
    eval_contract_id: str
    judge_prompt_template_id: Optional[str] = None
    mode: str
    score: int
    passed: bool
    checks: List[EvalCheckResult]
    judge_output_ids: List[str]
    artifact_ids: List[str]
    created_at: datetime


class JudgeOutput(BaseModel):
    id: str
    project_id: str
    eval_result_id: str
    judge_prompt_template_id: Optional[str] = None
    mode: str
    model: Optional[str] = None
    input_summary: str
    output: str
    token_usage: Dict[str, object]
    cost_estimate: Optional[float] = None
    artifact_ids: List[str]
    created_at: datetime


class FailurePacketCreate(BaseModel):
    agent_design_id: str = Field(min_length=1)
    agent_version_id: Optional[str] = None
    run_id: str = Field(min_length=1)
    eval_result_id: str = Field(min_length=1)
    eval_contract_id: str = Field(min_length=1)
    failed_check_ids: List[str] = Field(default_factory=list)
    title: str = Field(min_length=1)
    diagnosis: str = Field(min_length=1)
    severity: str = "medium"
    evidence_artifact_ids: List[str] = Field(default_factory=list)
    recommended_fix: str = ""
    status: str = "open"


class FailurePacketUpdate(BaseModel):
    title: Optional[str] = None
    diagnosis: Optional[str] = None
    severity: Optional[str] = None
    recommended_fix: Optional[str] = None
    status: Optional[str] = None


class FailurePacket(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    agent_version_id: Optional[str] = None
    run_id: str
    eval_result_id: str
    eval_contract_id: str
    failed_check_ids: List[str]
    title: str
    diagnosis: str
    severity: str
    evidence_artifact_ids: List[str]
    recommended_fix: str
    status: str
    created_at: datetime
    updated_at: datetime


class FixProposalCreate(BaseModel):
    agent_design_id: str = Field(min_length=1)
    target_version_id: Optional[str] = None
    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    proposed_changes: List[Dict[str, object]] = Field(default_factory=list)
    addressed_failure_packet_ids: List[str] = Field(default_factory=list)
    validation_contract_ids: List[str] = Field(default_factory=list)
    status: str = "proposed"


class FixProposalUpdate(BaseModel):
    title: Optional[str] = None
    rationale: Optional[str] = None
    proposed_changes: Optional[List[Dict[str, object]]] = None
    addressed_failure_packet_ids: Optional[List[str]] = None
    validation_contract_ids: Optional[List[str]] = None
    status: Optional[str] = None


class FixProposal(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    target_version_id: Optional[str] = None
    title: str
    rationale: str
    proposed_changes: List[Dict[str, object]]
    addressed_failure_packet_ids: List[str]
    validation_contract_ids: List[str]
    status: str
    created_at: datetime
    updated_at: datetime


class ComparisonCreate(BaseModel):
    baseline_run_id: str = Field(min_length=1)
    candidate_run_id: str = Field(min_length=1)
    eval_contract_id: str = Field(min_length=1)


class Comparison(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    baseline_version_id: Optional[str] = None
    candidate_version_id: Optional[str] = None
    baseline_run_id: str
    candidate_run_id: str
    baseline_eval_result_id: str
    candidate_eval_result_id: str
    fixed_failure_packet_ids: List[str]
    new_failure_packet_ids: List[str]
    remaining_failure_packet_ids: List[str]
    summary: str
    artifact_ids: List[str]
    created_at: datetime


class EvalRunResult(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    run_artifact_id: str
    mode: str
    score: int
    passed: bool
    checks: List[EvalCheck]
    artifact: ArtifactRecord
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


class EvidenceSummaryCreate(BaseModel):
    purpose: str = Field(min_length=1)
    agent_design_id: Optional[str] = None
    summary_type: str = "CONTEXT_OVERVIEW"
    mode: Literal["deterministic", "live"] = "deterministic"


class EvidenceSummary(BaseModel):
    id: str
    project_id: str
    purpose: str
    agent_design_id: Optional[str] = None
    summary_type: str
    mode: str
    provider: str
    model: str
    summary: str
    supporting_artifact_ids: List[str]
    token_usage: Dict[str, object]
    cost_estimate: Optional[float] = None
    cache_key: str
    cache_hit: bool = False
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
_scenarios: Dict[str, Scenario] = store.load_collection("scenarios", Scenario)
_eval_contracts: Dict[str, EvalContract] = store.load_collection("eval_contracts", EvalContract)
_judge_prompt_templates: Dict[str, JudgePromptTemplate] = store.load_collection(
    "judge_prompt_templates",
    JudgePromptTemplate,
)
_gate_definitions: Dict[str, GateDefinition] = store.load_collection(
    "gate_definitions",
    GateDefinition,
)
_gate_decisions: Dict[str, GateDecision] = store.load_collection(
    "gate_decisions",
    GateDecision,
)
_agent_versions: Dict[str, AgentVersion] = store.load_collection("agent_versions", AgentVersion)
_runs: Dict[str, RunRecord] = store.load_collection("runs", RunRecord)
_trace_refs: Dict[str, TraceRef] = store.load_collection("trace_refs", TraceRef)
_eval_results: Dict[str, EvalResult] = store.load_collection("eval_results", EvalResult)
_judge_outputs: Dict[str, JudgeOutput] = store.load_collection("judge_outputs", JudgeOutput)
_failure_packets: Dict[str, FailurePacket] = store.load_collection("failure_packets", FailurePacket)
_fix_proposals: Dict[str, FixProposal] = store.load_collection("fix_proposals", FixProposal)
_comparisons: Dict[str, Comparison] = store.load_collection("comparisons", Comparison)
_artifacts: Dict[str, ArtifactRecord] = store.load_collection("artifacts", ArtifactRecord)
_artifact_links: Dict[str, ArtifactLink] = store.load_collection("artifact_links", ArtifactLink)
_tool_definitions: Dict[str, ToolDefinition] = store.load_collection("tool_definitions", ToolDefinition)
_evidence_summaries: Dict[str, EvidenceSummary] = store.load_collection(
    "evidence_summaries",
    EvidenceSummary,
)
if default_project.id not in _projects:
    _projects[default_project.id] = default_project
    store.save_record("projects", default_project.id, default_project)

default_tool = ToolDefinition(
    id="tool_get_weather",
    project_id=default_project.id,
    name="get_weather",
    description="Get current weather for a US ZIP code.",
    input_schema={
        "type": "object",
        "properties": {
            "zip_code": {"type": "string", "description": "US ZIP code."}
        },
        "required": ["zip_code"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "source": {"type": "string"},
        },
        "required": ["summary"],
    },
    output_description="Current temperature and conditions.",
    implementation_kind="builtin",
    implementation_key="open_meteo_weather",
    config_schema={},
    mock_response="Current weather for 06511 New Haven, CT: 76°F and clear sky.",
    status="approved",
    created_at=seeded_at,
    updated_at=seeded_at,
)
if default_tool.id not in _tool_definitions:
    _tool_definitions[default_tool.id] = default_tool
    store.save_record("tool_definitions", default_tool.id, default_tool)
elif _tool_definitions[default_tool.id].implementation_key == "local_weather_fixture":
    _tool_definitions[default_tool.id] = default_tool
    store.save_record("tool_definitions", default_tool.id, default_tool)


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


def get_agent_design_or_404(project_id: str, agent_id: str) -> AgentDesign:
    agent = _agent_designs.get(agent_id)
    if agent is None or agent.project_id != project_id:
        raise HTTPException(status_code=404, detail="Agent design not found.")
    return agent


def get_scenario_or_404(project_id: str, scenario_id: str) -> Scenario:
    scenario = _scenarios.get(scenario_id)
    if scenario is None or scenario.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    return scenario


def get_eval_contract_or_404(project_id: str, contract_id: str) -> EvalContract:
    contract = _eval_contracts.get(contract_id)
    if contract is None or contract.project_id != project_id:
        raise HTTPException(status_code=404, detail="Eval contract not found.")
    return contract


def get_judge_prompt_template_or_404(
    project_id: str,
    judge_prompt_template_id: str,
) -> JudgePromptTemplate:
    template = _judge_prompt_templates.get(judge_prompt_template_id)
    if template is None or template.project_id != project_id:
        raise HTTPException(status_code=404, detail="Judge prompt template not found.")
    return template


def get_gate_definition_or_404(project_id: str, gate_id: str) -> GateDefinition:
    gate = _gate_definitions.get(gate_id)
    if gate is None or gate.project_id != project_id:
        raise HTTPException(status_code=404, detail="Gate definition not found.")
    return gate


def get_gate_decision_or_404(project_id: str, decision_id: str) -> GateDecision:
    decision = _gate_decisions.get(decision_id)
    if decision is None or decision.project_id != project_id:
        raise HTTPException(status_code=404, detail="Gate decision not found.")
    return decision


def get_agent_version_or_404(project_id: str, version_id: str) -> AgentVersion:
    version = _agent_versions.get(version_id)
    if version is None or version.project_id != project_id:
        raise HTTPException(status_code=404, detail="Agent version not found.")
    return version


def get_eval_result_or_404(project_id: str, eval_result_id: str) -> EvalResult:
    eval_result = _eval_results.get(eval_result_id)
    if eval_result is None or eval_result.project_id != project_id:
        raise HTTPException(status_code=404, detail="Eval result not found.")
    return eval_result


def get_trace_ref_or_404(project_id: str, trace_ref_id: str) -> TraceRef:
    trace_ref = _trace_refs.get(trace_ref_id)
    if trace_ref is None or trace_ref.project_id != project_id:
        raise HTTPException(status_code=404, detail="Trace reference not found.")
    return trace_ref


def get_failure_packet_or_404(project_id: str, failure_packet_id: str) -> FailurePacket:
    failure_packet = _failure_packets.get(failure_packet_id)
    if failure_packet is None or failure_packet.project_id != project_id:
        raise HTTPException(status_code=404, detail="Failure packet not found.")
    return failure_packet


def get_fix_proposal_or_404(project_id: str, fix_proposal_id: str) -> FixProposal:
    fix_proposal = _fix_proposals.get(fix_proposal_id)
    if fix_proposal is None or fix_proposal.project_id != project_id:
        raise HTTPException(status_code=404, detail="Fix proposal not found.")
    return fix_proposal


def get_comparison_or_404(project_id: str, comparison_id: str) -> Comparison:
    comparison = _comparisons.get(comparison_id)
    if comparison is None or comparison.project_id != project_id:
        raise HTTPException(status_code=404, detail="Comparison not found.")
    return comparison


def find_agent_design_artifact(agent_id: str) -> Optional[ArtifactRecord]:
    for artifact in _artifacts.values():
        if artifact.artifact_type == "AGENT_DESIGN" and artifact.artifact_id == agent_id:
            return artifact
    return None


def agent_design_artifact_body(agent: AgentDesign) -> str:
    tools = ", ".join(agent.allowed_tool_names) if agent.allowed_tool_names else "none"
    return f"{agent.intent}\n\nAllowed tools: {tools}"


def sync_agent_design_artifact(agent: AgentDesign, now: datetime) -> ArtifactRecord:
    artifact = find_agent_design_artifact(agent.id)
    if artifact is None:
        artifact = ArtifactRecord(
            id=f"artifact_{uuid4().hex[:12]}",
            project_id=agent.project_id,
            artifact_type="AGENT_DESIGN",
            artifact_id=agent.id,
            title=agent.name,
            body=agent_design_artifact_body(agent),
            source="intent",
            agent_design_id=agent.id,
            created_at=now,
            updated_at=now,
        )
    else:
        artifact = artifact.model_copy(
            update={
                "title": agent.name,
                "body": agent_design_artifact_body(agent),
                "updated_at": now,
            }
        )
    _artifacts[artifact.id] = artifact
    store.save_record("artifacts", artifact.id, artifact)
    return artifact


def find_artifact_by_type_and_artifact_id(
    artifact_type: str,
    artifact_id: str,
) -> Optional[ArtifactRecord]:
    for artifact in _artifacts.values():
        if artifact.artifact_type == artifact_type and artifact.artifact_id == artifact_id:
            return artifact
    return None


def create_artifact(
    *,
    project_id: str,
    artifact_type: str,
    artifact_id: str,
    title: str,
    body: str,
    source: str,
    agent_design_id: Optional[str],
    now: datetime,
) -> ArtifactRecord:
    artifact = ArtifactRecord(
        id=f"artifact_{uuid4().hex[:12]}",
        project_id=project_id,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        title=title,
        body=body,
        source=source,
        agent_design_id=agent_design_id,
        created_at=now,
        updated_at=now,
    )
    _artifacts[artifact.id] = artifact
    store.save_record("artifacts", artifact.id, artifact)
    return artifact


def tool_definition_artifact_body(tool: ToolDefinition) -> str:
    return (
        f"Description\n{tool.description}\n\n"
        f"Status\n{tool.status}\n\n"
        f"Implementation kind\n{tool.implementation_kind}\n\n"
        f"Implementation key\n{tool.implementation_key}\n\n"
        f"Input schema\n{json.dumps(tool.input_schema, indent=2, sort_keys=True)}\n\n"
        f"Output schema\n{json.dumps(tool.output_schema or {}, indent=2, sort_keys=True)}\n\n"
        f"Output description\n{tool.output_description}\n\n"
        f"Config schema\n{json.dumps(tool.config_schema, indent=2, sort_keys=True)}\n\n"
        f"Mock response\n{tool.mock_response or ''}"
    )


def upsert_tool_definition_artifact(tool: ToolDefinition, now: datetime) -> ArtifactRecord:
    existing = find_artifact_by_type_and_artifact_id("TOOL_DEFINITION", tool.id)
    if existing is not None:
        updated = existing.model_copy(
            update={
                "title": tool.name,
                "body": tool_definition_artifact_body(tool),
                "updated_at": now,
            }
        )
        _artifacts[updated.id] = updated
        store.save_record("artifacts", updated.id, updated)
        return updated
    return create_artifact(
        project_id=tool.project_id,
        artifact_type="TOOL_DEFINITION",
        artifact_id=tool.id,
        title=tool.name,
        body=tool_definition_artifact_body(tool),
        source="tool-registry",
        agent_design_id=None,
        now=now,
    )


def link_artifacts(
    *,
    project_id: str,
    source_artifact_id: str,
    target_artifact_id: str,
    relationship_type: str,
    now: datetime,
) -> ArtifactLink:
    link = ArtifactLink(
        id=f"link_{uuid4().hex[:12]}",
        project_id=project_id,
        source_artifact_id=source_artifact_id,
        target_artifact_id=target_artifact_id,
        relationship_type=relationship_type,
        created_at=now,
    )
    _artifact_links[link.id] = link
    store.save_record("artifact_links", link.id, link)
    return link


def link_to_agent_design(
    *,
    project_id: str,
    agent_design_id: str,
    artifact: ArtifactRecord,
    now: datetime,
) -> None:
    design_artifact = find_agent_design_artifact(agent_design_id)
    if design_artifact is not None:
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=design_artifact.id,
            relationship_type="GENERATED_FROM",
            now=now,
        )


def artifacts_for_agent_by_type(
    *,
    project_id: str,
    agent_design_id: str,
    artifact_type: str,
) -> List[ArtifactRecord]:
    return [
        artifact
        for artifact in _artifacts.values()
        if artifact.project_id == project_id
        and artifact.agent_design_id == agent_design_id
        and artifact.artifact_type == artifact_type
    ]


def create_gate_decision_record(
    *,
    project_id: str,
    gate: GateDefinition,
    payload: GateDecisionCreate,
    now: datetime,
) -> GateDecision:
    evidence_artifact_ids: List[str] = []
    missing_artifact_types: List[str] = []
    for artifact_type in gate.required_artifact_types:
        matching_artifacts = artifacts_for_agent_by_type(
            project_id=project_id,
            agent_design_id=gate.agent_design_id,
            artifact_type=artifact_type,
        )
        if matching_artifacts:
            evidence_artifact_ids.extend(artifact.id for artifact in matching_artifacts)
        else:
            missing_artifact_types.append(artifact_type)

    if payload.eval_result_id is not None:
        eval_result = get_eval_result_or_404(project_id, payload.eval_result_id)
        if eval_result.run_id:
            run = get_run_or_404(project_id, eval_result.run_id)
            if run.agent_design_id != gate.agent_design_id:
                raise HTTPException(
                    status_code=400,
                    detail="Gate decision eval result must belong to the same agent design.",
                )
        evidence_artifact_ids.extend(eval_result.artifact_ids)

    if payload.comparison_id is not None:
        comparison = get_comparison_or_404(project_id, payload.comparison_id)
        if comparison.agent_design_id != gate.agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Gate decision comparison must belong to the same agent design.",
            )
        evidence_artifact_ids.extend(comparison.artifact_ids)

    blocking_failure_packet_ids = [
        failure.id
        for failure in _failure_packets.values()
        if failure.project_id == project_id
        and failure.agent_design_id == gate.agent_design_id
        and failure.status in gate.blocking_failure_statuses
    ]
    for failure_id in blocking_failure_packet_ids:
        failure_artifact = find_artifact_by_type_and_artifact_id("FAILURE_PACKET", failure_id)
        if failure_artifact is not None:
            evidence_artifact_ids.append(failure_artifact.id)

    evidence_artifact_ids = sorted(set(evidence_artifact_ids))
    passed = not missing_artifact_types and not blocking_failure_packet_ids
    decision_value: Literal["passed", "blocked"] = "passed" if passed else "blocked"
    rationale_parts = []
    if missing_artifact_types:
        rationale_parts.append(f"Missing required artifacts: {', '.join(missing_artifact_types)}.")
    if blocking_failure_packet_ids:
        rationale_parts.append(
            f"Blocking failure packets remain: {', '.join(blocking_failure_packet_ids)}."
        )
    if not rationale_parts:
        rationale_parts.append("Required evidence is present and no blocking failures remain.")
    decision = GateDecision(
        id=f"gate_decision_{uuid4().hex[:12]}",
        project_id=project_id,
        gate_id=gate.id,
        agent_design_id=gate.agent_design_id,
        eval_result_id=payload.eval_result_id,
        comparison_id=payload.comparison_id,
        decision=decision_value,
        rationale=" ".join(rationale_parts),
        missing_artifact_types=missing_artifact_types,
        blocking_failure_packet_ids=blocking_failure_packet_ids,
        evidence_artifact_ids=evidence_artifact_ids,
        decided_by=payload.decided_by.strip(),
        created_at=now,
    )
    _gate_decisions[decision.id] = decision
    store.save_record("gate_decisions", decision.id, decision)

    gate_artifact = find_artifact_by_type_and_artifact_id("GATE", gate.id)
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="GATE_DECISION",
        artifact_id=decision.id,
        title=f"Gate decision: {gate.name}",
        body=(
            f"Decision\n{decision.decision}\n\n"
            f"Rationale\n{decision.rationale}\n\n"
            f"Missing artifacts\n"
            + ("\n".join(f"- {item}" for item in missing_artifact_types) or "None")
            + "\n\nBlocking failures\n"
            + ("\n".join(f"- {item}" for item in blocking_failure_packet_ids) or "None")
        ),
        source="gate-decision",
        agent_design_id=gate.agent_design_id,
        now=now,
    )
    if gate_artifact is not None:
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=gate_artifact.id,
            relationship_type="GENERATED_FROM",
            now=now,
        )
    for evidence_artifact_id in evidence_artifact_ids:
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=evidence_artifact_id,
            relationship_type="SUPPORTED_BY",
            now=now,
        )
    return decision


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
    artifact = create_artifact(
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
    )
    trace_ref = trace_ref.model_copy(update={"artifact_ids": [artifact.id]})
    _trace_refs[trace_ref.id] = trace_ref
    store.save_record("trace_refs", trace_ref.id, trace_ref)

    for run_artifact_id in run.artifact_ids:
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=run_artifact_id,
            relationship_type="OBSERVES",
            now=now,
        )
    for related_artifact in related_artifacts:
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=related_artifact.id,
            relationship_type="SUPPORTS",
            now=now,
        )
    link_to_agent_design(
        project_id=project_id,
        agent_design_id=run.agent_design_id,
        artifact=artifact,
        now=now,
    )
    return trace_ref


def approved_tools_for_agent(project_id: str, agent: AgentDesign) -> List[RunnerToolDefinition]:
    allowed = set(agent.allowed_tool_names)
    return [
        RunnerToolDefinition(
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_schema,
            output_schema=tool.output_schema,
            output_description=tool.output_description,
            implementation_kind=tool.implementation_kind,
            implementation_key=tool.implementation_key,
            config_schema=tool.config_schema,
            mock_response=tool.mock_response,
            status=tool.status,
        )
        for tool in _tool_definitions.values()
        if tool.project_id == project_id and tool.status == "approved" and tool.name in allowed
    ]


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


def build_live_judge_prompt(
    *,
    contract: EvalContract,
    run: RunRecord,
    checks: List[EvalCheckResult],
    template: Optional[JudgePromptTemplate],
) -> str:
    check_lines = "\n".join(
        f"- {check.check_id}: {'pass' if check.passed else 'fail'}; "
        f"expected={check.expected}; observed={check.observed}; comment={check.comment}"
        for check in checks
    )
    template_text = (
        template.template
        if template is not None
        else "Explain whether the response satisfies the eval contract. Cite the provided evidence only."
    )
    return (
        f"{template_text}\n\n"
        f"Eval contract: {contract.name}\n"
        f"Expected behavior:\n" + "\n".join(f"- {item}" for item in contract.expected_behavior)
        + "\n\n"
        f"Run input:\n{run.input}\n\n"
        f"Run output:\n{run.output}\n\n"
        f"Deterministic check results:\n{check_lines or 'No deterministic checks defined.'}\n\n"
        "Return a concise judge explanation. Do not invent evidence not shown above."
    )


def run_live_judge(prompt: str) -> tuple[str, str, Dict[str, object]]:
    config = openai_config_from_env()
    body = {
        "model": config.model,
        "reasoning": {"effort": "minimal"},
        "text": {"verbosity": "low"},
        "input": [
            {
                "role": "system",
                "content": "You are an eval judge for an eval-driven design platform.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "max_output_tokens": 1200,
    }
    request = Request(
        f"{config.base_url}/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI judge request failed with status {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"OpenAI judge request failed: {exc.reason}") from exc

    response_text = extract_response_text(payload)
    if not response_text:
        raise RuntimeError(describe_empty_response(payload))
    token_usage = payload.get("usage", {})
    if not isinstance(token_usage, dict):
        token_usage = {}
    return response_text, config.model, token_usage


def run_live_evidence_summary(prompt: str) -> tuple[str, str, Dict[str, object]]:
    config = openai_config_from_env()
    body = {
        "model": config.model,
        "reasoning": {"effort": "minimal"},
        "text": {"verbosity": "low"},
        "input": [
            {
                "role": "system",
                "content": "You summarize bounded evidence for an eval-driven design platform.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "max_output_tokens": 900,
    }
    request = Request(
        f"{config.base_url}/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OpenAI evidence summary request failed with status {exc.code}: {detail}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"OpenAI evidence summary request failed: {exc.reason}") from exc

    response_text = extract_response_text(payload)
    if not response_text:
        raise RuntimeError(describe_empty_response(payload))
    token_usage = payload.get("usage", {})
    if not isinstance(token_usage, dict):
        token_usage = {}
    return response_text, config.model, token_usage


def token_count(token_usage: Dict[str, object], key: str) -> int:
    value = token_usage.get(key, 0)
    return value if isinstance(value, int) else 0


def estimate_live_judge_cost(token_usage: Dict[str, object]) -> Optional[float]:
    input_rate = os.environ.get("EDD_OPENAI_INPUT_COST_PER_1M", "").strip()
    output_rate = os.environ.get("EDD_OPENAI_OUTPUT_COST_PER_1M", "").strip()
    if not input_rate or not output_rate:
        return None
    try:
        input_cost_per_1m = float(input_rate)
        output_cost_per_1m = float(output_rate)
    except ValueError:
        return None

    input_tokens = token_count(token_usage, "input_tokens")
    output_tokens = token_count(token_usage, "output_tokens")
    return round(
        (input_tokens / 1_000_000 * input_cost_per_1m)
        + (output_tokens / 1_000_000 * output_cost_per_1m),
        8,
    )


def run_agent_with_runner(
    *,
    project_id: str,
    agent: AgentDesign,
    instructions: str,
    scenario_input: str,
    mode: Literal["mock", "live"],
) -> tuple[object, ArtifactRecord]:
    runner_agent = RunnerAgentDesign(
        id=agent.id,
        name=agent.name,
        intent=instructions,
        allowed_tool_names=agent.allowed_tool_names,
    )
    runner_scenario = RunnerScenario(input=scenario_input.strip())
    if mode == "live":
        try:
            runner_result = run_openai_agent(
                runner_agent,
                runner_scenario,
                openai_config_from_env(),
                approved_tools_for_agent(project_id, agent),
            )
        except RuntimeError as exc:
            detail = str(exc)
            status_code = 400 if "OPENAI_API_KEY" in detail else 502
            raise HTTPException(status_code=status_code, detail=detail) from exc
    else:
        runner_result = run_mock_agent(runner_agent, runner_scenario)

    now = datetime.now(timezone.utc)
    tool_summary = "\n".join(
        f"- {tool.name}: {tool.output}" for tool in runner_result.tool_calls
    )
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="RUN_RESULT",
        artifact_id=runner_result.id,
        title=f"Run: {agent.name}",
        body=(
            f"Response\n{runner_result.response}\n\n"
            f"Scenario\n{runner_result.scenario_input}\n\n"
            f"Tools\n{tool_summary}"
        ),
        source=f"runner:{runner_result.mode}",
        agent_design_id=agent.id,
        now=now,
    )
    link_to_agent_design(
        project_id=project_id,
        agent_design_id=agent.id,
        artifact=artifact,
        now=now,
    )
    return runner_result, artifact


def evaluate_run_text(body: str) -> List[EvalCheck]:
    normalized = body.lower()
    return [
        EvalCheck(
            id="mentions_evidence",
            passed="evidence" in normalized,
            comment="Response should gather or cite evidence before recommending action.",
        ),
        EvalCheck(
            id="states_assumptions",
            passed="assumption" in normalized,
            comment="Response should make assumptions visible.",
        ),
        EvalCheck(
            id="recommends_safe_action",
            passed="safe next action" in normalized,
            comment="Response should recommend a safe next action.",
        ),
    ]


def evaluate_contract_check(
    *,
    check: Dict[str, object],
    run: RunRecord,
    evidence_artifact_ids: List[str],
    run_artifact_body: str,
) -> EvalCheckResult:
    check_id = str(check.get("id") or "unnamed_check")
    check_type = str(check.get("type") or "manual_review_required")
    expected = str(check.get("value") or check.get("tool") or "")
    normalized_output = run.output.lower()
    normalized_body = run_artifact_body.lower()
    normalized_expected = expected.lower()

    if check_type == "output_contains":
        passed = bool(normalized_expected and normalized_expected in normalized_output)
        observed = run.output
        comment = f"Output should contain {expected!r}."
    elif check_type == "output_not_contains":
        passed = bool(normalized_expected and normalized_expected not in normalized_output)
        observed = run.output
        comment = f"Output should not contain {expected!r}."
    elif check_type == "tool_called":
        passed = bool(normalized_expected and f"- {normalized_expected}:" in normalized_body)
        observed = run_artifact_body
        comment = f"Run should call tool {expected!r}."
    elif check_type == "tool_not_called":
        passed = bool(normalized_expected and f"- {normalized_expected}:" not in normalized_body)
        observed = run_artifact_body
        comment = f"Run should not call tool {expected!r}."
    else:
        passed = False
        observed = "manual review required"
        comment = f"Unsupported deterministic check type {check_type!r}."

    return EvalCheckResult(
        check_id=check_id,
        check_type=check_type,
        passed=passed,
        observed=observed,
        expected=expected,
        evidence_artifact_ids=evidence_artifact_ids,
        comment=comment,
    )


def create_failure_packet_record(
    *,
    project_id: str,
    agent_design_id: str,
    agent_version_id: Optional[str],
    run_id: str,
    eval_result_id: str,
    eval_contract_id: str,
    failed_check_ids: List[str],
    title: str,
    diagnosis: str,
    severity: str,
    evidence_artifact_ids: List[str],
    recommended_fix: str,
    status: str,
    now: datetime,
) -> FailurePacket:
    failure_packet = FailurePacket(
        id=f"failure_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=agent_design_id,
        agent_version_id=agent_version_id,
        run_id=run_id,
        eval_result_id=eval_result_id,
        eval_contract_id=eval_contract_id,
        failed_check_ids=failed_check_ids,
        title=title,
        diagnosis=diagnosis,
        severity=severity,
        evidence_artifact_ids=evidence_artifact_ids,
        recommended_fix=recommended_fix,
        status=status,
        created_at=now,
        updated_at=now,
    )
    _failure_packets[failure_packet.id] = failure_packet
    store.save_record("failure_packets", failure_packet.id, failure_packet)

    body = (
        f"Diagnosis\n{failure_packet.diagnosis}\n\n"
        f"Failed checks\n"
        + "\n".join(f"- {check_id}" for check_id in failure_packet.failed_check_ids)
        + f"\n\nRecommended fix\n{failure_packet.recommended_fix or 'Needs review'}"
    )
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="FAILURE_PACKET",
        artifact_id=failure_packet.id,
        title=failure_packet.title,
        body=body,
        source="failure-packet",
        agent_design_id=agent_design_id,
        now=now,
    )
    for evidence_artifact_id in evidence_artifact_ids:
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=evidence_artifact_id,
            relationship_type="SUPPORTED_BY",
            now=now,
        )
    return failure_packet


def validate_fix_proposal_references(
    *,
    project_id: str,
    agent_design_id: str,
    target_version_id: Optional[str],
    addressed_failure_packet_ids: List[str],
    validation_contract_ids: List[str],
) -> None:
    get_agent_design_or_404(project_id, agent_design_id)
    if target_version_id is not None:
        target_version = get_agent_version_or_404(project_id, target_version_id)
        if target_version.agent_design_id != agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Fix proposal target version must belong to the same agent design.",
            )

    for failure_packet_id in addressed_failure_packet_ids:
        failure_packet = get_failure_packet_or_404(project_id, failure_packet_id)
        if failure_packet.agent_design_id != agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Fix proposal failure packets must belong to the same agent design.",
            )

    for contract_id in validation_contract_ids:
        contract = get_eval_contract_or_404(project_id, contract_id)
        if contract.agent_design_id != agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Fix proposal validation contracts must belong to the same agent design.",
            )


def create_fix_proposal_record(
    *,
    project_id: str,
    agent_design_id: str,
    target_version_id: Optional[str],
    title: str,
    rationale: str,
    proposed_changes: List[Dict[str, object]],
    addressed_failure_packet_ids: List[str],
    validation_contract_ids: List[str],
    status: str,
    now: datetime,
) -> FixProposal:
    fix_proposal = FixProposal(
        id=f"fix_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=agent_design_id,
        target_version_id=target_version_id,
        title=title,
        rationale=rationale,
        proposed_changes=proposed_changes,
        addressed_failure_packet_ids=addressed_failure_packet_ids,
        validation_contract_ids=validation_contract_ids,
        status=status,
        created_at=now,
        updated_at=now,
    )
    _fix_proposals[fix_proposal.id] = fix_proposal
    store.save_record("fix_proposals", fix_proposal.id, fix_proposal)

    change_lines = "\n".join(
        f"- {change.get('surface', 'change')}: {change.get('change', change)}"
        for change in proposed_changes
    )
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="FIX_PROPOSAL",
        artifact_id=fix_proposal.id,
        title=fix_proposal.title,
        body=(
            f"Rationale\n{fix_proposal.rationale}\n\n"
            f"Target version\n{fix_proposal.target_version_id or 'None'}\n\n"
            f"Addressed failures\n"
            + "\n".join(
                f"- {failure_id}" for failure_id in fix_proposal.addressed_failure_packet_ids
            )
            + "\n\nValidation contracts\n"
            + "\n".join(
                f"- {contract_id}" for contract_id in fix_proposal.validation_contract_ids
            )
            + f"\n\nProposed changes\n{change_lines or 'Needs review'}"
        ),
        source="fix-proposal",
        agent_design_id=agent_design_id,
        now=now,
    )
    for failure_packet_id in addressed_failure_packet_ids:
        failure_artifact = find_artifact_by_type_and_artifact_id(
            "FAILURE_PACKET",
            failure_packet_id,
        )
        if failure_artifact is not None:
            link_artifacts(
                project_id=project_id,
                source_artifact_id=artifact.id,
                target_artifact_id=failure_artifact.id,
                relationship_type="ADDRESSES",
                now=now,
            )
    link_to_agent_design(
        project_id=project_id,
        agent_design_id=agent_design_id,
        artifact=artifact,
        now=now,
    )
    return fix_proposal


def get_run_or_404(project_id: str, run_id: str) -> RunRecord:
    run = _runs.get(run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run


def find_eval_result_for_run(
    *,
    project_id: str,
    run_id: str,
    eval_contract_id: str,
) -> Optional[EvalResult]:
    for eval_result in _eval_results.values():
        if (
            eval_result.project_id == project_id
            and eval_result.run_id == run_id
            and eval_result.eval_contract_id == eval_contract_id
        ):
            return eval_result
    return None


def failure_packets_for_eval(
    *,
    project_id: str,
    eval_result_id: str,
) -> List[FailurePacket]:
    return [
        failure_packet
        for failure_packet in _failure_packets.values()
        if failure_packet.project_id == project_id
        and failure_packet.eval_result_id == eval_result_id
    ]


def create_comparison_record(
    *,
    project_id: str,
    baseline_run: RunRecord,
    candidate_run: RunRecord,
    eval_contract_id: str,
    baseline_eval_result: EvalResult,
    candidate_eval_result: EvalResult,
    now: datetime,
) -> Comparison:
    baseline_packets = failure_packets_for_eval(
        project_id=project_id,
        eval_result_id=baseline_eval_result.id,
    )
    candidate_packets = failure_packets_for_eval(
        project_id=project_id,
        eval_result_id=candidate_eval_result.id,
    )
    candidate_failed_check_ids = {
        check.check_id for check in candidate_eval_result.checks if not check.passed
    }
    baseline_failed_check_ids = {
        check.check_id for check in baseline_eval_result.checks if not check.passed
    }
    fixed_failure_packet_ids = [
        packet.id
        for packet in baseline_packets
        if not set(packet.failed_check_ids) & candidate_failed_check_ids
    ]
    remaining_failure_packet_ids = [
        packet.id
        for packet in baseline_packets
        if set(packet.failed_check_ids) & candidate_failed_check_ids
    ]
    new_failure_packet_ids = [
        packet.id
        for packet in candidate_packets
        if bool(set(packet.failed_check_ids) - baseline_failed_check_ids)
    ]
    summary = (
        f"Comparison fixed {len(fixed_failure_packet_ids)} failure packet(s), "
        f"left {len(remaining_failure_packet_ids)} remaining, "
        f"and introduced {len(new_failure_packet_ids)} new failure packet(s)."
    )
    comparison_id = f"comparison_{uuid4().hex[:12]}"
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="COMPARISON",
        artifact_id=comparison_id,
        title="Version comparison",
        body=(
            f"Baseline run\n{baseline_run.id}\n\n"
            f"Candidate run\n{candidate_run.id}\n\n"
            f"Eval contract\n{eval_contract_id}\n\n"
            f"Summary\n{summary}\n\n"
            f"Fixed failures\n"
            + "\n".join(f"- {failure_id}" for failure_id in fixed_failure_packet_ids)
            + "\n\nRemaining failures\n"
            + "\n".join(f"- {failure_id}" for failure_id in remaining_failure_packet_ids)
            + "\n\nNew failures\n"
            + "\n".join(f"- {failure_id}" for failure_id in new_failure_packet_ids)
        ),
        source="comparison",
        agent_design_id=baseline_run.agent_design_id,
        now=now,
    )
    for artifact_id in baseline_run.artifact_ids + candidate_run.artifact_ids:
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=artifact_id,
            relationship_type="SUPPORTED_BY",
            now=now,
        )

    comparison = Comparison(
        id=comparison_id,
        project_id=project_id,
        agent_design_id=baseline_run.agent_design_id,
        baseline_version_id=baseline_run.agent_version_id,
        candidate_version_id=candidate_run.agent_version_id,
        baseline_run_id=baseline_run.id,
        candidate_run_id=candidate_run.id,
        baseline_eval_result_id=baseline_eval_result.id,
        candidate_eval_result_id=candidate_eval_result.id,
        fixed_failure_packet_ids=fixed_failure_packet_ids,
        new_failure_packet_ids=new_failure_packet_ids,
        remaining_failure_packet_ids=remaining_failure_packet_ids,
        summary=summary,
        artifact_ids=[artifact.id],
        created_at=now,
    )
    _comparisons[comparison.id] = comparison
    store.save_record("comparisons", comparison.id, comparison)
    return comparison


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
        allowed_tool_names=payload.allowed_tool_names or ["get_weather"],
        created_at=now,
        updated_at=now,
    )
    _agent_designs[agent.id] = agent
    store.save_record("agent_designs", agent.id, agent)

    artifact = sync_agent_design_artifact(agent, now)

    return AgentDesignCreated(agent=agent, artifact=artifact)


@app.get("/api/projects/{project_id}/agent-designs/{agent_id}")
def get_agent_design(project_id: str, agent_id: str) -> AgentDesign:
    get_project_or_404(project_id)
    return get_agent_design_or_404(project_id, agent_id)


@app.patch("/api/projects/{project_id}/agent-designs/{agent_id}")
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
            "updated_at": datetime.now(timezone.utc),
        }
    )
    _agent_designs[updated.id] = updated
    store.save_record("agent_designs", updated.id, updated)
    sync_agent_design_artifact(updated, updated.updated_at)
    return updated


@app.delete("/api/projects/{project_id}/agent-designs/{agent_id}", status_code=204)
def delete_agent_design(project_id: str, agent_id: str) -> Response:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, agent_id)
    delete_agent_design_records(project_id, agent_id)
    return Response(status_code=204)


@app.get("/api/projects/{project_id}/scenarios")
def list_scenarios(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[Scenario]:
    get_project_or_404(project_id)
    scenarios = [
        scenario
        for scenario in _scenarios.values()
        if scenario.project_id == project_id
        and (agent_design_id is None or scenario.agent_design_id == agent_design_id)
    ]
    return sorted(scenarios, key=lambda scenario: scenario.updated_at, reverse=True)


@app.post("/api/projects/{project_id}/scenarios", status_code=201)
def create_scenario(project_id: str, payload: ScenarioCreate) -> Scenario:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, payload.agent_design_id)
    if payload.default_eval_contract_id is not None:
        get_eval_contract_or_404(project_id, payload.default_eval_contract_id)

    now = datetime.now(timezone.utc)
    scenario = Scenario(
        id=f"scenario_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        name=payload.name.strip(),
        input=payload.input.strip(),
        setup_context=payload.setup_context.strip(),
        fixture_refs=payload.fixture_refs,
        default_eval_contract_id=payload.default_eval_contract_id,
        status=payload.status.strip(),
        created_at=now,
        updated_at=now,
    )
    _scenarios[scenario.id] = scenario
    store.save_record("scenarios", scenario.id, scenario)

    artifact = create_artifact(
        project_id=project_id,
        artifact_type="SCENARIO",
        artifact_id=scenario.id,
        title=scenario.name,
        body=(
            f"Input\n{scenario.input}\n\n"
            f"Setup context\n{scenario.setup_context or 'None'}\n\n"
            f"Default eval contract\n{scenario.default_eval_contract_id or 'None'}"
        ),
        source="scenario",
        agent_design_id=scenario.agent_design_id,
        now=now,
    )
    link_to_agent_design(
        project_id=project_id,
        agent_design_id=scenario.agent_design_id,
        artifact=artifact,
        now=now,
    )
    return scenario


@app.get("/api/projects/{project_id}/scenarios/{scenario_id}")
def get_scenario(project_id: str, scenario_id: str) -> Scenario:
    get_project_or_404(project_id)
    return get_scenario_or_404(project_id, scenario_id)


@app.get("/api/projects/{project_id}/judge-prompt-templates")
def list_judge_prompt_templates(project_id: str) -> List[JudgePromptTemplate]:
    get_project_or_404(project_id)
    templates = [
        template
        for template in _judge_prompt_templates.values()
        if template.project_id == project_id
    ]
    return sorted(templates, key=lambda template: template.updated_at, reverse=True)


@app.post("/api/projects/{project_id}/judge-prompt-templates", status_code=201)
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
        created_at=now,
        updated_at=now,
    )
    _judge_prompt_templates[template.id] = template
    store.save_record("judge_prompt_templates", template.id, template)
    create_artifact(
        project_id=project_id,
        artifact_type="JUDGE_PROMPT_TEMPLATE",
        artifact_id=template.id,
        title=template.name,
        body=(
            f"Description\n{template.description or 'None'}\n\n"
            f"Version\n{template.version}\n\n"
            f"Template\n{template.template}"
        ),
        source="judge-prompt-template",
        agent_design_id=None,
        now=now,
    )
    return template


@app.get("/api/projects/{project_id}/judge-prompt-templates/{judge_prompt_template_id}")
def get_judge_prompt_template(
    project_id: str,
    judge_prompt_template_id: str,
) -> JudgePromptTemplate:
    get_project_or_404(project_id)
    return get_judge_prompt_template_or_404(project_id, judge_prompt_template_id)


@app.get("/api/projects/{project_id}/gates")
def list_gate_definitions(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[GateDefinition]:
    get_project_or_404(project_id)
    gates = [
        gate
        for gate in _gate_definitions.values()
        if gate.project_id == project_id
        and (agent_design_id is None or gate.agent_design_id == agent_design_id)
    ]
    return sorted(gates, key=lambda gate: gate.updated_at, reverse=True)


@app.post("/api/projects/{project_id}/gates", status_code=201)
def create_gate_definition(project_id: str, payload: GateDefinitionCreate) -> GateDefinition:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, payload.agent_design_id)
    now = datetime.now(timezone.utc)
    gate = GateDefinition(
        id=f"gate_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        name=payload.name.strip(),
        criteria=payload.criteria,
        required_artifact_types=payload.required_artifact_types,
        threshold=payload.threshold.strip(),
        blocking_failure_statuses=payload.blocking_failure_statuses,
        approval_mode=payload.approval_mode,
        status=payload.status.strip(),
        created_at=now,
        updated_at=now,
    )
    _gate_definitions[gate.id] = gate
    store.save_record("gate_definitions", gate.id, gate)
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="GATE",
        artifact_id=gate.id,
        title=gate.name,
        body=(
            "Criteria\n"
            + ("\n".join(f"- {criterion}" for criterion in gate.criteria) or "None")
            + "\n\nRequired artifacts\n"
            + (
                "\n".join(f"- {artifact_type}" for artifact_type in gate.required_artifact_types)
                or "None"
            )
            + f"\n\nThreshold\n{gate.threshold}\n\nApproval mode\n{gate.approval_mode}"
        ),
        source="gate-definition",
        agent_design_id=gate.agent_design_id,
        now=now,
    )
    link_to_agent_design(
        project_id=project_id,
        agent_design_id=gate.agent_design_id,
        artifact=artifact,
        now=now,
    )
    return gate


@app.get("/api/projects/{project_id}/gates/{gate_id}")
def get_gate_definition(project_id: str, gate_id: str) -> GateDefinition:
    get_project_or_404(project_id)
    return get_gate_definition_or_404(project_id, gate_id)


@app.get("/api/projects/{project_id}/gate-decisions")
def list_gate_decisions(
    project_id: str,
    agent_design_id: Optional[str] = None,
    gate_id: Optional[str] = None,
) -> List[GateDecision]:
    get_project_or_404(project_id)
    decisions = [
        decision
        for decision in _gate_decisions.values()
        if decision.project_id == project_id
        and (agent_design_id is None or decision.agent_design_id == agent_design_id)
        and (gate_id is None or decision.gate_id == gate_id)
    ]
    return sorted(decisions, key=lambda decision: decision.created_at, reverse=True)


@app.post("/api/projects/{project_id}/gates/{gate_id}/decisions", status_code=201)
def create_gate_decision(
    project_id: str,
    gate_id: str,
    payload: GateDecisionCreate,
) -> GateDecision:
    get_project_or_404(project_id)
    gate = get_gate_definition_or_404(project_id, gate_id)
    return create_gate_decision_record(
        project_id=project_id,
        gate=gate,
        payload=payload,
        now=datetime.now(timezone.utc),
    )


@app.get("/api/projects/{project_id}/gate-decisions/{decision_id}")
def get_gate_decision(project_id: str, decision_id: str) -> GateDecision:
    get_project_or_404(project_id)
    return get_gate_decision_or_404(project_id, decision_id)


@app.get("/api/projects/{project_id}/eval-contracts")
def list_eval_contracts(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[EvalContract]:
    get_project_or_404(project_id)
    contracts = [
        contract
        for contract in _eval_contracts.values()
        if contract.project_id == project_id
        and (agent_design_id is None or contract.agent_design_id == agent_design_id)
    ]
    return sorted(contracts, key=lambda contract: contract.updated_at, reverse=True)


@app.post("/api/projects/{project_id}/eval-contracts", status_code=201)
def create_eval_contract(project_id: str, payload: EvalContractCreate) -> EvalContract:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, payload.agent_design_id)
    if payload.scenario_id is not None:
        scenario = get_scenario_or_404(project_id, payload.scenario_id)
        if scenario.agent_design_id != payload.agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Eval contract scenario must belong to the same agent design.",
            )
    if payload.judge_prompt_template_id is not None:
        get_judge_prompt_template_or_404(project_id, payload.judge_prompt_template_id)

    now = datetime.now(timezone.utc)
    contract = EvalContract(
        id=f"contract_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        scenario_id=payload.scenario_id,
        version=payload.version.strip(),
        expected_behavior=payload.expected_behavior,
        required_evidence=payload.required_evidence,
        required_tools=payload.required_tools,
        forbidden_tools=payload.forbidden_tools,
        forbidden_behavior=payload.forbidden_behavior,
        output_requirements=payload.output_requirements,
        checks=payload.checks,
        judge_prompt_template_id=payload.judge_prompt_template_id,
        pass_criteria=payload.pass_criteria.strip(),
        status=payload.status.strip(),
        created_at=now,
        updated_at=now,
    )
    _eval_contracts[contract.id] = contract
    store.save_record("eval_contracts", contract.id, contract)

    check_lines = "\n".join(
        f"- {check.get('id', 'unnamed_check')}: {check.get('type', 'unspecified')}"
        for check in contract.checks
    )
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="EVAL_CONTRACT",
        artifact_id=contract.id,
        title=contract.name,
        body=(
            f"Description\n{contract.description or 'None'}\n\n"
            f"Expected behavior\n"
            + "\n".join(f"- {item}" for item in contract.expected_behavior)
            + "\n\nRequired tools\n"
            + "\n".join(f"- {tool}" for tool in contract.required_tools)
            + "\n\nChecks\n"
            + (check_lines or "None")
            + f"\n\nPass criteria\n{contract.pass_criteria}"
        ),
        source="eval-contract",
        agent_design_id=contract.agent_design_id,
        now=now,
    )
    link_to_agent_design(
        project_id=project_id,
        agent_design_id=contract.agent_design_id,
        artifact=artifact,
        now=now,
    )
    if contract.judge_prompt_template_id is not None:
        prompt_artifact = find_artifact_by_type_and_artifact_id(
            "JUDGE_PROMPT_TEMPLATE",
            contract.judge_prompt_template_id,
        )
        if prompt_artifact is not None:
            link_artifacts(
                project_id=project_id,
                source_artifact_id=artifact.id,
                target_artifact_id=prompt_artifact.id,
                relationship_type="USES",
                now=now,
            )
    return contract


@app.get("/api/projects/{project_id}/eval-contracts/{contract_id}")
def get_eval_contract(project_id: str, contract_id: str) -> EvalContract:
    get_project_or_404(project_id)
    return get_eval_contract_or_404(project_id, contract_id)


@app.get("/api/projects/{project_id}/agent-designs/{agent_id}/versions")
def list_agent_versions(project_id: str, agent_id: str) -> List[AgentVersion]:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, agent_id)
    versions = [
        version
        for version in _agent_versions.values()
        if version.project_id == project_id and version.agent_design_id == agent_id
    ]
    return sorted(versions, key=lambda version: version.created_at)


@app.post("/api/projects/{project_id}/agent-designs/{agent_id}/versions", status_code=201)
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
        created_at=now,
        updated_at=now,
    )
    _agent_versions[version.id] = version
    store.save_record("agent_versions", version.id, version)

    artifact = create_artifact(
        project_id=project_id,
        artifact_type="AGENT_VERSION",
        artifact_id=version.id,
        title=f"{agent.name} {version.version_label}",
        body=(
            f"Instructions\n{version.instructions}\n\n"
            f"Parent version\n{version.parent_version_id or 'None'}\n\n"
            f"Status\n{version.status}"
        ),
        source="agent-version",
        agent_design_id=agent.id,
        now=now,
    )
    link_to_agent_design(
        project_id=project_id,
        agent_design_id=agent.id,
        artifact=artifact,
        now=now,
    )
    return version


@app.get("/api/projects/{project_id}/agent-designs/{agent_id}/versions/{version_id}")
def get_agent_version(project_id: str, agent_id: str, version_id: str) -> AgentVersion:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, agent_id)
    version = get_agent_version_or_404(project_id, version_id)
    if version.agent_design_id != agent_id:
        raise HTTPException(status_code=404, detail="Agent version not found.")
    return version


@app.get("/api/projects/{project_id}/runs")
def list_runs(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[RunRecord]:
    get_project_or_404(project_id)
    runs = [
        run
        for run in _runs.values()
        if run.project_id == project_id
        and (agent_design_id is None or run.agent_design_id == agent_design_id)
    ]
    return sorted(runs, key=lambda run: run.completed_at, reverse=True)


@app.post("/api/projects/{project_id}/runs", status_code=201)
def create_run(project_id: str, payload: RunCreate) -> RunRecord:
    get_project_or_404(project_id)
    agent = get_agent_design_or_404(project_id, payload.agent_design_id)
    scenario = get_scenario_or_404(project_id, payload.scenario_id)
    if scenario.agent_design_id != agent.id:
        raise HTTPException(
            status_code=400,
            detail="Run scenario must belong to the selected agent design.",
        )

    version: Optional[AgentVersion] = None
    if payload.agent_version_id is not None:
        version = get_agent_version_or_404(project_id, payload.agent_version_id)
        if version.agent_design_id != agent.id:
            raise HTTPException(
                status_code=400,
                detail="Run version must belong to the selected agent design.",
            )

    if payload.eval_contract_id is not None:
        contract = get_eval_contract_or_404(project_id, payload.eval_contract_id)
        if contract.agent_design_id != agent.id:
            raise HTTPException(
                status_code=400,
                detail="Run eval contract must belong to the selected agent design.",
            )
        if contract.scenario_id is not None and contract.scenario_id != scenario.id:
            raise HTTPException(
                status_code=400,
                detail="Run eval contract must match the selected scenario.",
            )

    instructions = version.instructions if version is not None else agent.intent
    runner_result, artifact = run_agent_with_runner(
        project_id=project_id,
        agent=agent,
        instructions=instructions,
        scenario_input=scenario.input,
        mode=payload.mode,
    )
    run = RunRecord(
        id=runner_result.id,
        project_id=project_id,
        agent_design_id=agent.id,
        agent_version_id=version.id if version is not None else None,
        scenario_id=scenario.id,
        eval_contract_id=payload.eval_contract_id,
        mode=runner_result.mode,
        provider="openai" if runner_result.mode == "live" else "mock",
        model=None,
        input=runner_result.scenario_input,
        output=runner_result.response,
        status="completed",
        artifact_ids=[artifact.id],
        started_at=runner_result.created_at,
        completed_at=runner_result.created_at,
    )
    _runs[run.id] = run
    store.save_record("runs", run.id, run)
    if runner_result.trace_id and runner_result.trace_url:
        create_trace_ref_record(
            project_id=project_id,
            payload=TraceRefCreate(
                provider="langfuse",
                external_trace_id=runner_result.trace_id,
                run_id=run.id,
                url=runner_result.trace_url,
                metadata={
                    "runner_mode": run.mode,
                    "provider": run.provider,
                    "agent_version_id": run.agent_version_id,
                    "scenario_id": run.scenario_id,
                    "eval_contract_id": run.eval_contract_id,
                },
                related_artifact_ids=run.artifact_ids,
            ),
            now=datetime.now(timezone.utc),
        )
    return run


@app.get("/api/projects/{project_id}/runs/{run_id}")
def get_run(project_id: str, run_id: str) -> RunRecord:
    get_project_or_404(project_id)
    return get_run_or_404(project_id, run_id)


@app.get("/api/projects/{project_id}/trace-refs")
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


@app.post("/api/projects/{project_id}/trace-refs", status_code=201)
def create_trace_ref(project_id: str, payload: TraceRefCreate) -> TraceRef:
    get_project_or_404(project_id)
    return create_trace_ref_record(
        project_id=project_id,
        payload=payload,
        now=datetime.now(timezone.utc),
    )


@app.get("/api/projects/{project_id}/trace-refs/{trace_ref_id}")
def get_trace_ref(project_id: str, trace_ref_id: str) -> TraceRef:
    get_project_or_404(project_id)
    return get_trace_ref_or_404(project_id, trace_ref_id)


@app.post("/api/projects/{project_id}/runs/{run_id}/evaluate", status_code=201)
def evaluate_run(
    project_id: str,
    run_id: str,
    payload: RunEvaluateCreate,
) -> EvalResult:
    get_project_or_404(project_id)
    run = get_run_or_404(project_id, run_id)

    contract_id = payload.eval_contract_id or run.eval_contract_id
    if contract_id is None:
        raise HTTPException(status_code=400, detail="Run evaluation requires an eval contract.")
    contract = get_eval_contract_or_404(project_id, contract_id)
    if contract.agent_design_id != run.agent_design_id:
        raise HTTPException(
            status_code=400,
            detail="Eval contract must belong to the same agent design as the run.",
        )
    if contract.scenario_id is not None and contract.scenario_id != run.scenario_id:
        raise HTTPException(
            status_code=400,
            detail="Eval contract must match the run scenario.",
        )

    run_artifact = (
        get_artifact_or_404(project_id, run.artifact_ids[0])
        if run.artifact_ids
        else None
    )
    run_artifact_body = run_artifact.body if run_artifact is not None else run.output
    evidence_artifact_ids = [run_artifact.id] if run_artifact is not None else []
    checks = [
        evaluate_contract_check(
            check=check,
            run=run,
            evidence_artifact_ids=evidence_artifact_ids,
            run_artifact_body=run_artifact_body,
        )
        for check in contract.checks
    ]
    score = sum(1 for check in checks if check.passed)
    passed = score == len(checks)
    now = datetime.now(timezone.utc)
    eval_id = f"eval_{uuid4().hex[:12]}"
    check_lines = "\n".join(
        f"- {check.check_id}: {'pass' if check.passed else 'fail'} - {check.comment}"
        for check in checks
    )
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="EVAL_RESULT",
        artifact_id=eval_id,
        title=f"Eval: {contract.name}",
        body=(
            f"Contract\n{contract.name}\n\n"
            f"Run\n{run.id}\n\n"
            f"Score\n{score}/{len(checks)}\n\n"
            f"Result\n{'Passed' if passed else 'Failed'}\n\n"
            f"Checks\n{check_lines or 'No checks defined'}"
        ),
        source=f"judge:{payload.judge_mode}",
        agent_design_id=run.agent_design_id,
        now=now,
    )
    if run_artifact is not None:
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=run_artifact.id,
            relationship_type="GENERATED_FROM",
            now=now,
        )
    contract_artifact = find_artifact_by_type_and_artifact_id("EVAL_CONTRACT", contract.id)
    if contract_artifact is not None:
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=contract_artifact.id,
            relationship_type="SUPPORTED_BY",
            now=now,
        )
    judge_output_id = f"judge_{uuid4().hex[:12]}"
    judge_output_text = "\n".join(
        f"{check.check_id}: {'pass' if check.passed else 'fail'} ({check.comment})"
        for check in checks
    ) or "No deterministic checks defined."
    judge_model: Optional[str] = None
    token_usage: Dict[str, object] = {}
    cost_estimate: Optional[float] = None
    if payload.judge_mode == "live":
        template = (
            get_judge_prompt_template_or_404(project_id, contract.judge_prompt_template_id)
            if contract.judge_prompt_template_id is not None
            else None
        )
        prompt = build_live_judge_prompt(
            contract=contract,
            run=run,
            checks=checks,
            template=template,
        )
        try:
            judge_output_text, judge_model, token_usage = run_live_judge(prompt)
        except RuntimeError as exc:
            detail = str(exc)
            status_code = 400 if "OPENAI_API_KEY" in detail else 502
            raise HTTPException(status_code=status_code, detail=detail) from exc
        cost_estimate = estimate_live_judge_cost(token_usage)

    judge_artifact = create_artifact(
        project_id=project_id,
        artifact_type="JUDGE_OUTPUT",
        artifact_id=judge_output_id,
        title=f"Judge: {contract.name}",
        body=judge_output_text,
        source=f"judge:{payload.judge_mode}",
        agent_design_id=run.agent_design_id,
        now=now,
    )
    link_artifacts(
        project_id=project_id,
        source_artifact_id=artifact.id,
        target_artifact_id=judge_artifact.id,
        relationship_type="SUPPORTED_BY",
        now=now,
    )
    judge_output = JudgeOutput(
        id=judge_output_id,
        project_id=project_id,
        eval_result_id=eval_id,
        judge_prompt_template_id=contract.judge_prompt_template_id,
        mode=payload.judge_mode,
        model=judge_model,
        input_summary=f"Run {run.id} evaluated against {contract.id}.",
        output=judge_output_text,
        token_usage=token_usage,
        cost_estimate=cost_estimate,
        artifact_ids=[judge_artifact.id],
        created_at=now,
    )
    _judge_outputs[judge_output.id] = judge_output
    store.save_record("judge_outputs", judge_output.id, judge_output)

    eval_result = EvalResult(
        id=eval_id,
        project_id=project_id,
        run_id=run.id,
        eval_contract_id=contract.id,
        judge_prompt_template_id=contract.judge_prompt_template_id,
        mode=payload.judge_mode,
        score=score,
        passed=passed,
        checks=checks,
        judge_output_ids=[judge_output.id],
        artifact_ids=[artifact.id, judge_artifact.id],
        created_at=now,
    )
    _eval_results[eval_result.id] = eval_result
    store.save_record("eval_results", eval_result.id, eval_result)
    failed_check_ids = [check.check_id for check in checks if not check.passed]
    if failed_check_ids:
        create_failure_packet_record(
            project_id=project_id,
            agent_design_id=run.agent_design_id,
            agent_version_id=run.agent_version_id,
            run_id=run.id,
            eval_result_id=eval_result.id,
            eval_contract_id=contract.id,
            failed_check_ids=failed_check_ids,
            title=f"Failed eval: {contract.name}",
            diagnosis=(
                "The run failed one or more eval contract checks: "
                + ", ".join(failed_check_ids)
            ),
            severity="medium",
            evidence_artifact_ids=eval_result.artifact_ids,
            recommended_fix="Review the failed checks and propose a bounded agent change.",
            status="open",
            now=now,
        )
    return eval_result


@app.get("/api/projects/{project_id}/eval-results/{eval_result_id}")
def get_eval_result(project_id: str, eval_result_id: str) -> EvalResult:
    get_project_or_404(project_id)
    return get_eval_result_or_404(project_id, eval_result_id)


@app.get("/api/projects/{project_id}/eval-results")
def list_eval_results(
    project_id: str,
    run_id: Optional[str] = None,
    eval_contract_id: Optional[str] = None,
) -> List[EvalResult]:
    get_project_or_404(project_id)
    eval_results = [
        eval_result
        for eval_result in _eval_results.values()
        if eval_result.project_id == project_id
        and (run_id is None or eval_result.run_id == run_id)
        and (
            eval_contract_id is None
            or eval_result.eval_contract_id == eval_contract_id
        )
    ]
    return sorted(eval_results, key=lambda eval_result: eval_result.created_at, reverse=True)


@app.get("/api/projects/{project_id}/failure-packets")
def list_failure_packets(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[FailurePacket]:
    get_project_or_404(project_id)
    failure_packets = [
        failure_packet
        for failure_packet in _failure_packets.values()
        if failure_packet.project_id == project_id
        and (
            agent_design_id is None
            or failure_packet.agent_design_id == agent_design_id
        )
    ]
    return sorted(
        failure_packets,
        key=lambda failure_packet: failure_packet.updated_at,
        reverse=True,
    )


@app.post("/api/projects/{project_id}/failure-packets", status_code=201)
def create_failure_packet(
    project_id: str,
    payload: FailurePacketCreate,
) -> FailurePacket:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, payload.agent_design_id)
    run = _runs.get(payload.run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found.")
    eval_result = get_eval_result_or_404(project_id, payload.eval_result_id)
    contract = get_eval_contract_or_404(project_id, payload.eval_contract_id)
    if (
        run.agent_design_id != payload.agent_design_id
        or eval_result.run_id != run.id
        or contract.agent_design_id != payload.agent_design_id
    ):
        raise HTTPException(
            status_code=400,
            detail="Failure packet references must belong to the same evaluated run.",
        )
    for evidence_artifact_id in payload.evidence_artifact_ids:
        get_artifact_or_404(project_id, evidence_artifact_id)

    return create_failure_packet_record(
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        agent_version_id=payload.agent_version_id,
        run_id=payload.run_id,
        eval_result_id=payload.eval_result_id,
        eval_contract_id=payload.eval_contract_id,
        failed_check_ids=payload.failed_check_ids,
        title=payload.title.strip(),
        diagnosis=payload.diagnosis.strip(),
        severity=payload.severity.strip(),
        evidence_artifact_ids=payload.evidence_artifact_ids,
        recommended_fix=payload.recommended_fix.strip(),
        status=payload.status.strip(),
        now=datetime.now(timezone.utc),
    )


@app.get("/api/projects/{project_id}/failure-packets/{failure_packet_id}")
def get_failure_packet(project_id: str, failure_packet_id: str) -> FailurePacket:
    get_project_or_404(project_id)
    return get_failure_packet_or_404(project_id, failure_packet_id)


@app.patch("/api/projects/{project_id}/failure-packets/{failure_packet_id}")
def update_failure_packet(
    project_id: str,
    failure_packet_id: str,
    payload: FailurePacketUpdate,
) -> FailurePacket:
    get_project_or_404(project_id)
    existing = get_failure_packet_or_404(project_id, failure_packet_id)
    updated = existing.model_copy(
        update={
            "title": payload.title.strip() if payload.title is not None else existing.title,
            "diagnosis": (
                payload.diagnosis.strip()
                if payload.diagnosis is not None
                else existing.diagnosis
            ),
            "severity": (
                payload.severity.strip()
                if payload.severity is not None
                else existing.severity
            ),
            "recommended_fix": (
                payload.recommended_fix.strip()
                if payload.recommended_fix is not None
                else existing.recommended_fix
            ),
            "status": payload.status.strip() if payload.status is not None else existing.status,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    _failure_packets[updated.id] = updated
    store.save_record("failure_packets", updated.id, updated)
    return updated


@app.get("/api/projects/{project_id}/fix-proposals")
def list_fix_proposals(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[FixProposal]:
    get_project_or_404(project_id)
    fix_proposals = [
        fix_proposal
        for fix_proposal in _fix_proposals.values()
        if fix_proposal.project_id == project_id
        and (
            agent_design_id is None
            or fix_proposal.agent_design_id == agent_design_id
        )
    ]
    return sorted(
        fix_proposals,
        key=lambda fix_proposal: fix_proposal.updated_at,
        reverse=True,
    )


@app.post("/api/projects/{project_id}/fix-proposals", status_code=201)
def create_fix_proposal(
    project_id: str,
    payload: FixProposalCreate,
) -> FixProposal:
    get_project_or_404(project_id)
    validate_fix_proposal_references(
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        target_version_id=payload.target_version_id,
        addressed_failure_packet_ids=payload.addressed_failure_packet_ids,
        validation_contract_ids=payload.validation_contract_ids,
    )
    return create_fix_proposal_record(
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        target_version_id=payload.target_version_id,
        title=payload.title.strip(),
        rationale=payload.rationale.strip(),
        proposed_changes=payload.proposed_changes,
        addressed_failure_packet_ids=payload.addressed_failure_packet_ids,
        validation_contract_ids=payload.validation_contract_ids,
        status=payload.status.strip(),
        now=datetime.now(timezone.utc),
    )


@app.get("/api/projects/{project_id}/fix-proposals/{fix_proposal_id}")
def get_fix_proposal(project_id: str, fix_proposal_id: str) -> FixProposal:
    get_project_or_404(project_id)
    return get_fix_proposal_or_404(project_id, fix_proposal_id)


@app.patch("/api/projects/{project_id}/fix-proposals/{fix_proposal_id}")
def update_fix_proposal(
    project_id: str,
    fix_proposal_id: str,
    payload: FixProposalUpdate,
) -> FixProposal:
    get_project_or_404(project_id)
    existing = get_fix_proposal_or_404(project_id, fix_proposal_id)
    target_version_id = existing.target_version_id
    addressed_failure_packet_ids = existing.addressed_failure_packet_ids
    validation_contract_ids = existing.validation_contract_ids
    if payload.addressed_failure_packet_ids is not None:
        addressed_failure_packet_ids = payload.addressed_failure_packet_ids
    if payload.validation_contract_ids is not None:
        validation_contract_ids = payload.validation_contract_ids
    validate_fix_proposal_references(
        project_id=project_id,
        agent_design_id=existing.agent_design_id,
        target_version_id=target_version_id,
        addressed_failure_packet_ids=addressed_failure_packet_ids,
        validation_contract_ids=validation_contract_ids,
    )
    updated = existing.model_copy(
        update={
            "title": payload.title.strip() if payload.title is not None else existing.title,
            "rationale": (
                payload.rationale.strip()
                if payload.rationale is not None
                else existing.rationale
            ),
            "proposed_changes": (
                payload.proposed_changes
                if payload.proposed_changes is not None
                else existing.proposed_changes
            ),
            "addressed_failure_packet_ids": addressed_failure_packet_ids,
            "validation_contract_ids": validation_contract_ids,
            "status": payload.status.strip() if payload.status is not None else existing.status,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    _fix_proposals[updated.id] = updated
    store.save_record("fix_proposals", updated.id, updated)
    return updated


@app.post("/api/projects/{project_id}/comparisons", status_code=201)
def create_comparison(
    project_id: str,
    payload: ComparisonCreate,
) -> Comparison:
    get_project_or_404(project_id)
    baseline_run = get_run_or_404(project_id, payload.baseline_run_id)
    candidate_run = get_run_or_404(project_id, payload.candidate_run_id)
    contract = get_eval_contract_or_404(project_id, payload.eval_contract_id)
    if baseline_run.agent_design_id != candidate_run.agent_design_id:
        raise HTTPException(
            status_code=400,
            detail="Comparison runs must belong to the same agent design.",
        )
    if contract.agent_design_id != baseline_run.agent_design_id:
        raise HTTPException(
            status_code=400,
            detail="Comparison eval contract must belong to the same agent design.",
        )
    if baseline_run.scenario_id != candidate_run.scenario_id:
        raise HTTPException(
            status_code=400,
            detail="Comparison runs must use the same scenario.",
        )
    if contract.scenario_id is not None and contract.scenario_id != baseline_run.scenario_id:
        raise HTTPException(
            status_code=400,
            detail="Comparison eval contract must match the compared scenario.",
        )

    baseline_eval_result = find_eval_result_for_run(
        project_id=project_id,
        run_id=baseline_run.id,
        eval_contract_id=contract.id,
    )
    candidate_eval_result = find_eval_result_for_run(
        project_id=project_id,
        run_id=candidate_run.id,
        eval_contract_id=contract.id,
    )
    if baseline_eval_result is None or candidate_eval_result is None:
        raise HTTPException(
            status_code=400,
            detail="Comparison requires both runs to be evaluated against the contract.",
        )

    return create_comparison_record(
        project_id=project_id,
        baseline_run=baseline_run,
        candidate_run=candidate_run,
        eval_contract_id=contract.id,
        baseline_eval_result=baseline_eval_result,
        candidate_eval_result=candidate_eval_result,
        now=datetime.now(timezone.utc),
    )


@app.get("/api/projects/{project_id}/comparisons")
def list_comparisons(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[Comparison]:
    get_project_or_404(project_id)
    comparisons = [
        comparison
        for comparison in _comparisons.values()
        if comparison.project_id == project_id
        and (
            agent_design_id is None
            or comparison.agent_design_id == agent_design_id
        )
    ]
    return sorted(comparisons, key=lambda comparison: comparison.created_at, reverse=True)


@app.get("/api/projects/{project_id}/comparisons/{comparison_id}")
def get_comparison(project_id: str, comparison_id: str) -> Comparison:
    get_project_or_404(project_id)
    return get_comparison_or_404(project_id, comparison_id)


@app.post("/api/projects/{project_id}/agent-designs/{agent_id}/runs", status_code=201)
def run_agent_design(
    project_id: str,
    agent_id: str,
    payload: AgentRunCreate,
) -> AgentRunResult:
    get_project_or_404(project_id)
    agent = get_agent_design_or_404(project_id, agent_id)
    runner_result, artifact = run_agent_with_runner(
        project_id=project_id,
        agent=agent,
        instructions=agent.intent,
        scenario_input=payload.scenario_input,
        mode=payload.mode,
    )

    return AgentRunResult(
        id=runner_result.id,
        project_id=project_id,
        agent_design_id=agent.id,
        mode=runner_result.mode,
        scenario_input=runner_result.scenario_input,
        response=runner_result.response,
        tool_calls=[tool.model_dump() for tool in runner_result.tool_calls],
        evidence=runner_result.evidence,
        trace_id=runner_result.trace_id,
        trace_url=runner_result.trace_url,
        artifact=artifact,
        created_at=runner_result.created_at,
    )


@app.get("/api/projects/{project_id}/tools")
def list_tool_definitions(project_id: str) -> List[ToolDefinition]:
    get_project_or_404(project_id)
    tools = [tool for tool in _tool_definitions.values() if tool.project_id == project_id]
    return sorted(tools, key=lambda tool: tool.name)


@app.post("/api/projects/{project_id}/tools", status_code=201)
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
    upsert_tool_definition_artifact(tool, now)
    return tool


@app.patch("/api/projects/{project_id}/tools/{tool_id}")
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
    upsert_tool_definition_artifact(updated, now)
    return updated


@app.post("/api/projects/{project_id}/artifacts/{artifact_id}/evaluate", status_code=201)
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


CONTEXT_PACK_ARTIFACT_TYPES: Dict[str, set[str]] = {
    "AGENT_PROMPT_REVIEW": {
        "AGENT_DESIGN",
        "AGENT_VERSION",
        "EVAL_CONTRACT",
        "JUDGE_PROMPT_TEMPLATE",
        "GATE",
        "TRACE_REF",
    },
    "SIDE_BY_SIDE_VERSION_COMPARISON": {
        "COMPARISON",
        "EVAL_RESULT",
        "JUDGE_OUTPUT",
        "FAILURE_PACKET",
        "FIX_PROPOSAL",
        "RUN_RESULT",
        "TRACE_REF",
    },
    "FIX_PROPOSAL_GENERATION": {
        "FAILURE_PACKET",
        "EVAL_RESULT",
        "JUDGE_OUTPUT",
        "FIX_PROPOSAL",
        "EVAL_CONTRACT",
        "RUN_RESULT",
        "TRACE_REF",
    },
    "GATE_DECISION_REVIEW": {
        "GATE",
        "GATE_DECISION",
        "COMPARISON",
        "EVAL_RESULT",
        "JUDGE_OUTPUT",
        "FAILURE_PACKET",
        "TRACE_REF",
    },
}


def assemble_context_pack_artifacts(
    *,
    project_id: str,
    agent_design_id: Optional[str],
    purpose: str,
) -> List[ArtifactRecord]:
    artifacts = list_project_artifacts(
        project_id=project_id,
        agent_design_id=agent_design_id,
    )
    allowed_types = CONTEXT_PACK_ARTIFACT_TYPES.get(purpose.strip().upper())
    if allowed_types is None:
        return artifacts
    return [artifact for artifact in artifacts if artifact.artifact_type in allowed_types]


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
    return (
        f"{purpose} context includes {len(artifacts)} evidence artifacts "
        f"({counts}). Key artifacts: {titles}."
    )


@app.post("/api/projects/{project_id}/context-packs")
def build_context_pack(project_id: str, payload: ContextPackCreate) -> ContextPack:
    get_project_or_404(project_id)
    agent = _agent_designs.get(payload.agent_design_id) if payload.agent_design_id else None
    if payload.agent_design_id is not None and (
        agent is None or agent.project_id != project_id
    ):
        raise HTTPException(status_code=404, detail="Agent design not found.")

    purpose = payload.purpose.strip().upper()
    artifacts = assemble_context_pack_artifacts(
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        purpose=purpose,
    )
    return ContextPack(
        id=f"context_{uuid4().hex[:12]}",
        project_id=project_id,
        purpose=purpose,
        agent_design_id=payload.agent_design_id,
        artifacts=artifacts,
        created_at=datetime.now(timezone.utc),
    )


@app.post("/api/projects/{project_id}/evidence-summaries", status_code=201)
def create_evidence_summary(
    project_id: str,
    payload: EvidenceSummaryCreate,
) -> EvidenceSummary:
    get_project_or_404(project_id)
    agent = _agent_designs.get(payload.agent_design_id) if payload.agent_design_id else None
    if payload.agent_design_id is not None and (
        agent is None or agent.project_id != project_id
    ):
        raise HTTPException(status_code=404, detail="Agent design not found.")

    purpose = payload.purpose.strip().upper()
    summary_type = payload.summary_type.strip().upper()
    artifacts = assemble_context_pack_artifacts(
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        purpose=purpose,
    )
    cache_key = context_pack_cache_key(
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        purpose=purpose,
        summary_type=summary_type,
        mode=payload.mode,
        artifacts=artifacts,
    )
    cached_summary = _evidence_summaries.get(cache_key)
    if cached_summary is not None:
        return cached_summary.model_copy(update={"cache_hit": True})

    provider = "platform"
    model = "deterministic-evidence-summary"
    token_usage: Dict[str, object] = {}
    cost_estimate: Optional[float] = None
    if payload.mode == "live":
        prompt = build_evidence_summary_prompt(
            purpose=purpose,
            summary_type=summary_type,
            artifacts=artifacts,
        )
        try:
            summary, model, token_usage = run_live_evidence_summary(prompt)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        provider = "openai"
        cost_estimate = estimate_live_judge_cost(token_usage)
    else:
        summary = build_deterministic_evidence_summary(
            purpose=purpose,
            artifacts=artifacts,
        )

    evidence_summary = EvidenceSummary(
        id=f"summary_{uuid4().hex[:12]}",
        project_id=project_id,
        purpose=purpose,
        agent_design_id=payload.agent_design_id,
        summary_type=summary_type,
        mode=payload.mode,
        provider=provider,
        model=model,
        summary=summary,
        supporting_artifact_ids=[artifact.id for artifact in artifacts],
        token_usage=token_usage,
        cost_estimate=cost_estimate,
        cache_key=cache_key,
        cache_hit=False,
        created_at=datetime.now(timezone.utc),
    )
    _evidence_summaries[cache_key] = evidence_summary
    store.save_record("evidence_summaries", cache_key, evidence_summary)
    return evidence_summary
