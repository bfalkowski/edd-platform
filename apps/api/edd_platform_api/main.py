from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional
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
    openai_config_from_env,
    run_mock_agent,
    run_openai_agent,
)


class AgentDesignCreate(BaseModel):
    name: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    allowed_tool_names: List[str] = Field(default_factory=list)


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
    output_description: str
    implementation_key: str
    status: Literal["draft", "approved"]
    created_at: datetime
    updated_at: datetime


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


class AgentRunResult(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    mode: str
    scenario_input: str
    response: str
    tool_calls: List[Dict[str, str]]
    evidence: List[str]
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
    judge_mode: Literal["deterministic"] = "deterministic"


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
_agent_versions: Dict[str, AgentVersion] = store.load_collection("agent_versions", AgentVersion)
_runs: Dict[str, RunRecord] = store.load_collection("runs", RunRecord)
_eval_results: Dict[str, EvalResult] = store.load_collection("eval_results", EvalResult)
_judge_outputs: Dict[str, JudgeOutput] = store.load_collection("judge_outputs", JudgeOutput)
_failure_packets: Dict[str, FailurePacket] = store.load_collection("failure_packets", FailurePacket)
_artifacts: Dict[str, ArtifactRecord] = store.load_collection("artifacts", ArtifactRecord)
_artifact_links: Dict[str, ArtifactLink] = store.load_collection("artifact_links", ArtifactLink)
_tool_definitions: Dict[str, ToolDefinition] = store.load_collection("tool_definitions", ToolDefinition)
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
    output_description="Current temperature and conditions.",
    implementation_key="local_weather_fixture",
    status="approved",
    created_at=seeded_at,
    updated_at=seeded_at,
)
if default_tool.id not in _tool_definitions:
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


def get_failure_packet_or_404(project_id: str, failure_packet_id: str) -> FailurePacket:
    failure_packet = _failure_packets.get(failure_packet_id)
    if failure_packet is None or failure_packet.project_id != project_id:
        raise HTTPException(status_code=404, detail="Failure packet not found.")
    return failure_packet


def find_agent_design_artifact(agent_id: str) -> Optional[ArtifactRecord]:
    for artifact in _artifacts.values():
        if artifact.artifact_type == "AGENT_DESIGN" and artifact.artifact_id == agent_id:
            return artifact
    return None


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


def approved_tools_for_agent(project_id: str, agent: AgentDesign) -> List[RunnerToolDefinition]:
    allowed = set(agent.allowed_tool_names)
    return [
        RunnerToolDefinition(
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_schema,
            output_description=tool.output_description,
            implementation_key=tool.implementation_key,
            status=tool.status,
        )
        for tool in _tool_definitions.values()
        if tool.project_id == project_id and tool.status == "approved" and tool.name in allowed
    ]


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
    return get_agent_design_or_404(project_id, agent_id)


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
    return run


@app.get("/api/projects/{project_id}/runs/{run_id}")
def get_run(project_id: str, run_id: str) -> RunRecord:
    get_project_or_404(project_id)
    run = _runs.get(run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run


@app.post("/api/projects/{project_id}/runs/{run_id}/evaluate", status_code=201)
def evaluate_run(
    project_id: str,
    run_id: str,
    payload: RunEvaluateCreate,
) -> EvalResult:
    get_project_or_404(project_id)
    run = _runs.get(run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found.")

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
        model=None,
        input_summary=f"Run {run.id} evaluated against {contract.id}.",
        output=judge_output_text,
        token_usage={},
        cost_estimate=None,
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
        artifact=artifact,
        created_at=runner_result.created_at,
    )


@app.get("/api/projects/{project_id}/tools")
def list_tool_definitions(project_id: str) -> List[ToolDefinition]:
    get_project_or_404(project_id)
    tools = [tool for tool in _tool_definitions.values() if tool.project_id == project_id]
    return sorted(tools, key=lambda tool: tool.name)


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
