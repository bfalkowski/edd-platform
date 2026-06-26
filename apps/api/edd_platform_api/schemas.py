from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class AgentDesignCreate(BaseModel):
    name: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    allowed_tool_names: List[str] = Field(default_factory=list)
    langfuse_prompt_name: Optional[str] = None
    langfuse_prompt_version: Optional[str] = None
    langfuse_prompt_label: Optional[str] = None


class AgentDesignUpdate(BaseModel):
    name: Optional[str] = None
    intent: Optional[str] = None
    allowed_tool_names: Optional[List[str]] = None
    status: Optional[str] = None
    langfuse_prompt_name: Optional[str] = None
    langfuse_prompt_version: Optional[str] = None
    langfuse_prompt_label: Optional[str] = None


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
    langfuse_prompt_name: Optional[str] = None
    langfuse_prompt_version: Optional[str] = None
    langfuse_prompt_label: Optional[str] = None
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
    langfuse_prompt_name: Optional[str] = None
    langfuse_prompt_version: Optional[str] = None
    langfuse_prompt_label: Optional[str] = None


class JudgePromptTemplate(BaseModel):
    id: str
    project_id: str
    name: str
    description: str
    template: str
    version: str
    status: str
    langfuse_prompt_name: Optional[str] = None
    langfuse_prompt_version: Optional[str] = None
    langfuse_prompt_label: Optional[str] = None
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
    langfuse_prompt_name: Optional[str] = None
    langfuse_prompt_version: Optional[str] = None
    langfuse_prompt_label: Optional[str] = None


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
    langfuse_prompt_name: Optional[str] = None
    langfuse_prompt_version: Optional[str] = None
    langfuse_prompt_label: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ExternalArtifactRef(BaseModel):
    provider: str = Field(min_length=1)
    ref_type: Literal["trace", "dataset", "dataset_item", "prompt", "score", "comment", "experiment"]
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
    target: Literal["agent", "url"] = "agent"
    url: Optional[str] = None


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


class ReviewNoteCreate(BaseModel):
    target_artifact_id: str = Field(min_length=1)
    body: str = Field(min_length=1)
    author: str = "platform"
    metadata: Dict[str, object] = Field(default_factory=dict)


class ReviewNote(BaseModel):
    id: str
    project_id: str
    target_artifact_id: str
    body: str
    author: str
    metadata: Dict[str, object]
    artifact_ids: List[str]
    created_at: datetime


class LangfuseObjectRef(BaseModel):
    trace_id: Optional[str] = None
    observation_id: Optional[str] = None
    object_type: Literal["TRACE", "OBSERVATION"] = "TRACE"
    url: Optional[str] = None
    queue_id: Optional[str] = None
    score_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, object] = Field(default_factory=dict)


class ReviewCorpusCreate(BaseModel):
    agent_design_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    source: Literal["edd", "langfuse", "mixed"] = "edd"
    langfuse_queue_id: Optional[str] = None
    langfuse_score_config_ids: List[str] = Field(default_factory=list)
    status: str = "draft"


class ReviewCorpusUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    langfuse_queue_id: Optional[str] = None
    langfuse_score_config_ids: Optional[List[str]] = None
    status: Optional[str] = None


class ReviewCorpus(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    name: str
    description: str
    source: str
    langfuse_queue_id: Optional[str] = None
    langfuse_score_config_ids: List[str]
    status: str
    artifact_ids: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ReviewItemCreate(BaseModel):
    corpus_id: str = Field(min_length=1)
    source_kind: Literal["artifact", "run", "eval_result", "trace"] = "artifact"
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = ""
    langfuse_ref: Optional[LangfuseObjectRef] = None
    metadata: Dict[str, object] = Field(default_factory=dict)
    status: str = "unreviewed"


class ReviewItemUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    metadata: Optional[Dict[str, object]] = None
    status: Optional[str] = None


class ReviewItem(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    corpus_id: str
    source_kind: str
    source_id: str
    title: str
    content: str
    langfuse_ref: Optional[LangfuseObjectRef] = None
    metadata: Dict[str, object]
    status: str
    created_at: datetime
    updated_at: datetime


class LangfuseReviewItemImport(BaseModel):
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = ""
    trace_id: Optional[str] = None
    observation_id: Optional[str] = None
    object_type: Literal["TRACE", "OBSERVATION"] = "TRACE"
    url: Optional[str] = None
    queue_id: Optional[str] = None
    score_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, object] = Field(default_factory=dict)


class LangfuseReviewItemsImportCreate(BaseModel):
    items: List[LangfuseReviewItemImport] = Field(default_factory=list)


class LangfuseReviewItemsImportResult(BaseModel):
    review_items: List[ReviewItem]
    imported_count: int
    skipped_count: int


class FailureModeCreate(BaseModel):
    agent_design_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    root_cause: str = ""
    severity: str = "medium"
    status: str = "candidate"
    langfuse_score_name: Optional[str] = None
    example_annotation_ids: List[str] = Field(default_factory=list)


class FailureModeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    root_cause: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    langfuse_score_name: Optional[str] = None
    example_annotation_ids: Optional[List[str]] = None


class FailureMode(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    name: str
    description: str
    root_cause: str
    severity: str
    status: str
    langfuse_score_name: Optional[str] = None
    example_annotation_ids: List[str]
    created_at: datetime
    updated_at: datetime


class ReviewAnnotationCreate(BaseModel):
    review_item_id: str = Field(min_length=1)
    body: str = Field(min_length=1)
    quote: str = ""
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    author: Literal["human", "agent", "platform"] = "human"
    failure_mode_id: Optional[str] = None
    suggestion_id: Optional[str] = None
    langfuse_score_id: Optional[str] = None
    status: Literal["accepted", "suggested", "dismissed"] = "accepted"
    metadata: Dict[str, object] = Field(default_factory=dict)


class ReviewAnnotationUpdate(BaseModel):
    body: Optional[str] = None
    quote: Optional[str] = None
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    failure_mode_id: Optional[str] = None
    langfuse_score_id: Optional[str] = None
    status: Optional[Literal["accepted", "suggested", "dismissed"]] = None
    metadata: Optional[Dict[str, object]] = None


class ReviewAnnotation(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    corpus_id: str
    review_item_id: str
    body: str
    quote: str
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    author: str
    failure_mode_id: Optional[str] = None
    suggestion_id: Optional[str] = None
    langfuse_score_id: Optional[str] = None
    status: str
    metadata: Dict[str, object]
    created_at: datetime
    updated_at: datetime


class LangfuseAnnotationImport(BaseModel):
    review_item_id: Optional[str] = None
    source_id: Optional[str] = None
    trace_id: Optional[str] = None
    observation_id: Optional[str] = None
    open_coding: str = Field(min_length=1)
    pass_fail: Optional[Literal["pass", "fail", "unknown"]] = None
    failure_mode_name: Optional[str] = None
    failure_mode_description: str = ""
    langfuse_score_id: Optional[str] = None
    metadata: Dict[str, object] = Field(default_factory=dict)


class LangfuseAnnotationsImportCreate(BaseModel):
    annotations: List[LangfuseAnnotationImport] = Field(default_factory=list)


class LangfuseAnnotationsImportResult(BaseModel):
    annotations: List[ReviewAnnotation]
    failure_modes: List[FailureMode]
    imported_count: int
    skipped_count: int


class AgentSuggestionCreate(BaseModel):
    review_item_id: str = Field(min_length=1)
    failure_mode_id: Optional[str] = None
    body: str = Field(min_length=1)
    quote: str = ""
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    rationale: str = ""
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    source: str = "agent"
    status: Literal["pending", "accepted", "dismissed"] = "pending"
    metadata: Dict[str, object] = Field(default_factory=dict)


class AgentSuggestionUpdate(BaseModel):
    failure_mode_id: Optional[str] = None
    body: Optional[str] = None
    quote: Optional[str] = None
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    rationale: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    status: Optional[Literal["pending", "accepted", "dismissed"]] = None
    metadata: Optional[Dict[str, object]] = None


class AgentSuggestion(BaseModel):
    id: str
    project_id: str
    agent_design_id: str
    corpus_id: str
    review_item_id: str
    failure_mode_id: Optional[str] = None
    body: str
    quote: str
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    rationale: str
    confidence: Optional[float] = None
    source: str
    status: str
    metadata: Dict[str, object]
    created_at: datetime
    updated_at: datetime


class ReviewSamplingCandidate(BaseModel):
    review_item_id: str
    title: str
    reason: str
    source_kind: str
    status: str
    failure_mode_id: Optional[str] = None
    score: int


class ReviewCoverageSummary(BaseModel):
    total_items: int
    reviewed_items: int
    unreviewed_items: int
    accepted_annotations: int
    failure_modes: int
    pending_suggestions: int


class ReviewSamplingPlan(BaseModel):
    corpus_id: str
    project_id: str
    agent_design_id: str
    coverage: ReviewCoverageSummary
    breadth_candidates: List[ReviewSamplingCandidate]
    depth_candidates: List[ReviewSamplingCandidate]
    recoding_prompts: List[ReviewSamplingCandidate]
    generated_suggestions: List[AgentSuggestion] = Field(default_factory=list)
    rationale: str


class ReviewFailureModeCount(BaseModel):
    failure_mode_id: str
    name: str
    severity: str
    accepted_annotations: int


class ReviewFailureRate(BaseModel):
    source_kind: str
    total_items: int
    reviewed_items: int
    failed_items: int
    failure_rate: float


class ReviewCorpusAnalysis(BaseModel):
    corpus_id: str
    project_id: str
    agent_design_id: str
    backend: Literal["polars"]
    coverage: ReviewCoverageSummary
    source_kind_counts: Dict[str, int]
    annotation_status_counts: Dict[str, int]
    pass_fail_counts: Dict[str, int]
    failure_mode_counts: List[ReviewFailureModeCount]
    failure_rates: List[ReviewFailureRate]
    rationale: str


class DiscoveryPromotionCreate(BaseModel):
    create_failure_packet: bool = True
    create_eval_case: bool = True
    failure_packet_status: str = "open"


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


class DiscoveryPromotionResult(BaseModel):
    annotation: ReviewAnnotation
    review_item: ReviewItem
    failure_mode: Optional[FailureMode] = None
    scenario: Optional[Scenario] = None
    eval_contract: Optional[EvalContract] = None
    failure_packet: Optional[FailurePacket] = None
    artifact_ids: List[str]


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


class OutcomeAgentCreate(BaseModel):
    outcome: str = Field(min_length=1)


class OutcomeAgentCreated(BaseModel):
    agent: AgentDesign
    artifact: ArtifactRecord
    version: AgentVersion
    scenario: Scenario
    eval_contract: EvalContract
    draft_tools: List[ToolDefinition] = Field(default_factory=list)


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
