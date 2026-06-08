from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


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


class ExternalArtifactRef(BaseModel):
    provider: str = Field(min_length=1)
    ref_type: Literal["trace", "dataset", "dataset_item", "prompt", "score", "experiment"]
    external_id: str = Field(min_length=1)
    url: Optional[str] = None
    label: str = ""
    metadata: Dict[str, object] = Field(default_factory=dict)


class ArtifactRecord(BaseModel):
    id: str
    project_id: str
    artifact_type: str
    artifact_id: str
    title: str
    body: str
    source: str
    agent_design_id: Optional[str] = None
    external_refs: List[ExternalArtifactRef] = Field(default_factory=list)
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
    tool_calls: List[Dict[str, object]]
    evidence: List[str]
    trace_id: Optional[str] = None
    trace_url: Optional[str] = None
    artifact: ArtifactRecord
    trace_artifact: Optional[ArtifactRecord] = None
    artifact_ids: List[str]
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
    artifact_ids: List[str] = Field(default_factory=list)
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
