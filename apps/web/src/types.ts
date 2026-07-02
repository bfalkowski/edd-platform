export type AgentDesign = {
  id: string;
  project_id: string;
  name: string;
  intent: string;
  status: string;
  allowed_tool_names: string[];
  created_at: string;
  updated_at: string;
};

export type Project = {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
};

export type ServiceStatus = {
  id: string;
  name: string;
  status: "online" | "offline" | "configured" | "not_configured";
  configured: boolean;
  url: string | null;
  description: string;
};

export type ServiceStatusResponse = {
  services: ServiceStatus[];
  updated_at: string;
};

export type ToolDefinition = {
  id: string;
  project_id: string;
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown> | null;
  output_description: string;
  implementation_kind: "http" | "python" | "mcp" | "builtin" | "mock";
  implementation_key: string;
  config_schema: Record<string, unknown>;
  mock_response: string | null;
  status: "draft" | "approved";
  created_at: string;
  updated_at: string;
};

export type ToolDefinitionCreate = {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown> | null;
  output_description: string;
  implementation_kind: "http" | "python" | "mcp" | "builtin" | "mock";
  implementation_key: string;
  config_schema: Record<string, unknown>;
  mock_response: string | null;
};

export type EvalMethod = "phrase" | "tool" | "rubric";
export type TestShape = "single_turn" | "conversation" | "trace_replay";

export type ExternalArtifactRef = {
  provider: string;
  ref_type: string;
  external_id: string;
  url: string | null;
  label: string;
  metadata: Record<string, unknown>;
};

export type ArtifactRecord = {
  id: string;
  project_id: string;
  artifact_type: string;
  artifact_id: string;
  title: string;
  body: string;
  source: string;
  agent_design_id: string | null;
  external_refs: ExternalArtifactRef[];
  created_at: string;
  updated_at: string;
};

export type ArtifactLink = {
  id: string;
  project_id: string;
  source_artifact_id: string;
  target_artifact_id: string;
  relationship_type: string;
  created_at: string;
};

export type NewAgentResponse = {
  agent: AgentDesign;
  artifact: ArtifactRecord;
};

export type OutcomeAgentResponse = NewAgentResponse & {
  version: AgentVersion;
  scenario: Scenario;
  eval_contract: EvalContract;
  draft_tools: ToolDefinition[];
};

export type ContextPack = {
  id: string;
  project_id: string;
  purpose: string;
  agent_design_id: string | null;
  artifacts: ArtifactRecord[];
  created_at: string;
};

export type AgentRunResult = {
  id: string;
  project_id: string;
  agent_design_id: string;
  mode: string;
  scenario_input: string;
  response: string;
  tool_calls: { name: string; input?: string; output: string }[];
  evidence: string[];
  trace_id: string | null;
  trace_url: string | null;
  artifact: ArtifactRecord;
  trace_artifact: ArtifactRecord | null;
  artifact_ids: string[];
  created_at: string;
};

export type EvalRunResult = {
  id: string;
  project_id: string;
  agent_design_id: string;
  run_artifact_id: string;
  mode: string;
  score: number;
  passed: boolean;
  checks: { id: string; passed: boolean; comment: string }[];
  artifact: ArtifactRecord;
  created_at: string;
};

export type Scenario = {
  id: string;
  project_id: string;
  agent_design_id: string;
  name: string;
  input: string;
  setup_context: string;
  fixture_refs: string[];
  default_eval_contract_id: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type EvalContract = {
  id: string;
  project_id: string;
  agent_design_id: string;
  name: string;
  description: string;
  scenario_id: string | null;
  version: string;
  expected_behavior: string[];
  required_evidence: string[];
  required_tools: string[];
  forbidden_tools: string[];
  forbidden_behavior: string[];
  output_requirements: string[];
  checks: { id: string; type: string; value?: string; tool?: string }[];
  judge_prompt_template_id: string | null;
  pass_criteria: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type AgentVersion = {
  id: string;
  project_id: string;
  agent_design_id: string;
  version_label: string;
  parent_version_id: string | null;
  instructions: string;
  tool_policy: Record<string, unknown>;
  source_fix_proposal_id: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type RunRecord = {
  id: string;
  project_id: string;
  agent_design_id: string;
  agent_version_id: string | null;
  scenario_id: string;
  eval_contract_id: string | null;
  mode: string;
  provider: string | null;
  model: string | null;
  input: string;
  output: string;
  status: string;
  artifact_ids: string[];
  started_at: string;
  completed_at: string;
};

export type EvalResult = {
  id: string;
  project_id: string;
  run_id: string;
  eval_contract_id: string;
  mode: string;
  score: number;
  passed: boolean;
  checks: {
    check_id: string;
    check_type: string;
    passed: boolean;
    observed: string;
    expected: string;
    evidence_artifact_ids: string[];
    comment: string;
  }[];
  judge_output_ids: string[];
  artifact_ids: string[];
  created_at: string;
};

export type FailurePacket = {
  id: string;
  project_id: string;
  agent_design_id: string;
  agent_version_id: string | null;
  run_id: string;
  eval_result_id: string;
  eval_contract_id: string;
  failed_check_ids: string[];
  title: string;
  diagnosis: string;
  severity: string;
  evidence_artifact_ids: string[];
  recommended_fix: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type ReviewNote = {
  id: string;
  project_id: string;
  target_artifact_id: string;
  body: string;
  author: string;
  metadata: Record<string, unknown>;
  artifact_ids: string[];
  created_at: string;
};

export type LangfuseObjectRef = {
  trace_id: string | null;
  observation_id: string | null;
  object_type: "TRACE" | "OBSERVATION";
  url: string | null;
  queue_id: string | null;
  score_ids: string[];
  metadata: Record<string, unknown>;
};

export type ReviewCorpus = {
  id: string;
  project_id: string;
  agent_design_id: string;
  name: string;
  description: string;
  source: string;
  langfuse_queue_id: string | null;
  langfuse_score_config_ids: string[];
  status: string;
  artifact_ids: string[];
  created_at: string;
  updated_at: string;
};

export type ReviewItem = {
  id: string;
  project_id: string;
  agent_design_id: string;
  corpus_id: string;
  source_kind: string;
  source_id: string;
  title: string;
  content: string;
  langfuse_ref: LangfuseObjectRef | null;
  metadata: Record<string, unknown>;
  status: string;
  created_at: string;
  updated_at: string;
};

export type FailureMode = {
  id: string;
  project_id: string;
  agent_design_id: string;
  name: string;
  description: string;
  root_cause: string;
  severity: string;
  status: string;
  langfuse_score_name: string | null;
  example_annotation_ids: string[];
  created_at: string;
  updated_at: string;
};

export type ReviewAnnotation = {
  id: string;
  project_id: string;
  agent_design_id: string;
  corpus_id: string;
  review_item_id: string;
  body: string;
  quote: string;
  author: string;
  failure_mode_id: string | null;
  suggestion_id: string | null;
  langfuse_score_id: string | null;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type AgentSuggestion = {
  id: string;
  project_id: string;
  agent_design_id: string;
  corpus_id: string;
  review_item_id: string;
  failure_mode_id: string | null;
  body: string;
  quote: string;
  rationale: string;
  confidence: number | null;
  source: string;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ReviewSamplingCandidate = {
  review_item_id: string;
  title: string;
  reason: string;
  source_kind: string;
  status: string;
  failure_mode_id: string | null;
  score: number;
};

export type ReviewSamplingPlan = {
  corpus_id: string;
  project_id: string;
  agent_design_id: string;
  coverage: {
    total_items: number;
    reviewed_items: number;
    unreviewed_items: number;
    accepted_annotations: number;
    failure_modes: number;
    pending_suggestions: number;
  };
  breadth_candidates: ReviewSamplingCandidate[];
  depth_candidates: ReviewSamplingCandidate[];
  recoding_prompts: ReviewSamplingCandidate[];
  generated_suggestions: AgentSuggestion[];
  rationale: string;
};

export type DiscoveryPromotionResult = {
  annotation: ReviewAnnotation;
  review_item: ReviewItem;
  failure_mode: FailureMode | null;
  scenario: Scenario | null;
  eval_contract: EvalContract | null;
  failure_packet: FailurePacket | null;
  artifact_ids: string[];
};

export type FixProposal = {
  id: string;
  project_id: string;
  agent_design_id: string;
  target_version_id: string | null;
  title: string;
  rationale: string;
  proposed_changes: Record<string, unknown>[];
  addressed_failure_packet_ids: string[];
  validation_contract_ids: string[];
  artifact_ids: string[];
  status: string;
  created_at: string;
  updated_at: string;
};

export type Comparison = {
  id: string;
  project_id: string;
  agent_design_id: string;
  baseline_version_id: string | null;
  candidate_version_id: string | null;
  baseline_run_id: string;
  candidate_run_id: string;
  baseline_eval_result_id: string;
  candidate_eval_result_id: string;
  fixed_failure_packet_ids: string[];
  new_failure_packet_ids: string[];
  remaining_failure_packet_ids: string[];
  summary: string;
  artifact_ids: string[];
  created_at: string;
};

export type GateDefinition = {
  id: string;
  project_id: string;
  agent_design_id: string;
  name: string;
  criteria: string[];
  required_artifact_types: string[];
  threshold: string;
  blocking_failure_statuses: string[];
  approval_mode: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type GateDecision = {
  id: string;
  project_id: string;
  gate_id: string;
  agent_design_id: string;
  eval_result_id: string | null;
  comparison_id: string | null;
  decision: "passed" | "blocked";
  rationale: string;
  missing_artifact_types: string[];
  blocking_failure_packet_ids: string[];
  evidence_artifact_ids: string[];
  decided_by: string;
  created_at: string;
};

export type EddFlowState = {
  baselineVersion?: AgentVersion;
  candidateVersion?: AgentVersion;
  scenario?: Scenario;
  contract?: EvalContract;
  baselineRun?: RunRecord;
  candidateRun?: RunRecord;
  baselineEval?: EvalResult;
  candidateEval?: EvalResult;
  failurePackets: FailurePacket[];
  fixProposal?: FixProposal;
  comparison?: Comparison;
};

export type GeneratedDesignSummary = {
  agentId: string;
  artifact: ArtifactRecord;
  version: AgentVersion;
  scenario: Scenario;
  contract: EvalContract;
  draftTools: ToolDefinition[];
  enabledToolNames: string[];
  generatedToolNames: string[];
};
