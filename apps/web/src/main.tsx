import {
  Clock3,
  MoreHorizontal,
  PanelLeft,
  PanelRight,
  PencilLine,
  Play,
  Search,
  Trash2,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type AgentDesign = {
  id: string;
  project_id: string;
  name: string;
  intent: string;
  status: string;
  allowed_tool_names: string[];
  created_at: string;
  updated_at: string;
};

type Project = {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
};

type ToolDefinition = {
  id: string;
  project_id: string;
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  output_description: string;
  implementation_key: string;
  status: "draft" | "approved";
  created_at: string;
  updated_at: string;
};

type ArtifactRecord = {
  id: string;
  project_id: string;
  artifact_type: string;
  artifact_id: string;
  title: string;
  body: string;
  source: string;
  agent_design_id: string | null;
  created_at: string;
  updated_at: string;
};

type ArtifactLink = {
  id: string;
  project_id: string;
  source_artifact_id: string;
  target_artifact_id: string;
  relationship_type: string;
  created_at: string;
};

type NewAgentResponse = {
  agent: AgentDesign;
  artifact: ArtifactRecord;
};

type ContextPack = {
  id: string;
  project_id: string;
  purpose: string;
  agent_design_id: string | null;
  artifacts: ArtifactRecord[];
  created_at: string;
};

type AgentRunResult = {
  id: string;
  project_id: string;
  agent_design_id: string;
  mode: string;
  scenario_input: string;
  response: string;
  tool_calls: { name: string; output: string }[];
  evidence: string[];
  trace_id: string | null;
  trace_url: string | null;
  artifact: ArtifactRecord;
  created_at: string;
};

type EvalRunResult = {
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

type Scenario = {
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

type EvalContract = {
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

type AgentVersion = {
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

type RunRecord = {
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

type EvalResult = {
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

type FailurePacket = {
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

type FixProposal = {
  id: string;
  project_id: string;
  agent_design_id: string;
  target_version_id: string | null;
  title: string;
  rationale: string;
  proposed_changes: Record<string, unknown>[];
  addressed_failure_packet_ids: string[];
  validation_contract_ids: string[];
  status: string;
  created_at: string;
  updated_at: string;
};

type Comparison = {
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

type GateDefinition = {
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

type GateDecision = {
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

type EddFlowState = {
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

const apiBase = "/api";

async function responseError(response: Response, fallback: string): Promise<Error> {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") {
      return new Error(payload.detail);
    }
  } catch {
    // Use the fallback below when the API returns a non-JSON error body.
  }
  return new Error(fallback);
}

async function listProjects(): Promise<Project[]> {
  const response = await fetch(`${apiBase}/projects`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load projects.");
  }
  return response.json();
}

async function listAgentDesigns(projectId: string): Promise<AgentDesign[]> {
  const response = await fetch(`${apiBase}/projects/${projectId}/agent-designs`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load agent designs.");
  }
  return response.json();
}

async function createAgentDesign(
  projectId: string,
  name: string,
  intent: string,
): Promise<AgentDesign> {
  const response = await fetch(`${apiBase}/projects/${projectId}/agent-designs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, intent }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to create agent design.");
  }
  const payload = (await response.json()) as NewAgentResponse;
  return payload.agent;
}

async function deleteAgentDesign(projectId: string, agentDesignId: string): Promise<void> {
  const response = await fetch(`${apiBase}/projects/${projectId}/agent-designs/${agentDesignId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to delete agent design.");
  }
}

async function listToolDefinitions(projectId: string): Promise<ToolDefinition[]> {
  const response = await fetch(`${apiBase}/projects/${projectId}/tools`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load tools.");
  }
  return response.json();
}

async function updateAgentDesignToolAllowlist(
  projectId: string,
  agentDesignId: string,
  allowedToolNames: string[],
): Promise<AgentDesign> {
  const response = await fetch(`${apiBase}/projects/${projectId}/agent-designs/${agentDesignId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ allowed_tool_names: allowedToolNames }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to update agent tools.");
  }
  return response.json();
}

async function buildContextPack(projectId: string, agentDesignId?: string): Promise<ContextPack> {
  const response = await fetch(`${apiBase}/projects/${projectId}/context-packs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      purpose: "AGENT_PROMPT_REVIEW",
      agent_design_id: agentDesignId ?? null,
    }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to build evidence context.");
  }
  return response.json();
}

async function loadArtifact(projectId: string, artifactId: string): Promise<ArtifactRecord> {
  const response = await fetch(`${apiBase}/projects/${projectId}/artifacts/${artifactId}`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load artifact.");
  }
  return response.json();
}

async function loadArtifactLinks(projectId: string, artifactId: string): Promise<ArtifactLink[]> {
  const response = await fetch(`${apiBase}/projects/${projectId}/artifacts/${artifactId}/links`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load related evidence.");
  }
  return response.json();
}

async function runAgentDesign(
  projectId: string,
  agentDesignId: string,
  scenarioInput: string,
  mode: "mock" | "live",
): Promise<AgentRunResult> {
  const response = await fetch(`${apiBase}/projects/${projectId}/agent-designs/${agentDesignId}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_input: scenarioInput, mode }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to run agent scenario.");
  }
  return response.json();
}

async function evaluateArtifact(projectId: string, artifactId: string): Promise<EvalRunResult> {
  const response = await fetch(`${apiBase}/projects/${projectId}/artifacts/${artifactId}/evaluate`, {
    method: "POST",
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to evaluate run artifact.");
  }
  return response.json();
}

async function createAgentVersion(
  projectId: string,
  agentDesignId: string,
  payload: {
    version_label: string;
    parent_version_id?: string;
    instructions: string;
    source_fix_proposal_id?: string;
    status?: string;
  },
): Promise<AgentVersion> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/agent-designs/${agentDesignId}/versions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to create agent version.");
  }
  return response.json();
}

async function createScenario(
  projectId: string,
  agentDesignId: string,
  input: string,
): Promise<Scenario> {
  const response = await fetch(`${apiBase}/projects/${projectId}/scenarios`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent_design_id: agentDesignId,
      name: "Test scenario",
      input,
    }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to create scenario.");
  }
  return response.json();
}

async function createEvalContract(
  projectId: string,
  agentDesignId: string,
  scenarioId: string,
  requiredPhrase: string,
): Promise<EvalContract> {
  const response = await fetch(`${apiBase}/projects/${projectId}/eval-contracts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent_design_id: agentDesignId,
      name: "Success criteria",
      description: "Checks whether the response matches the expected agent behavior.",
      scenario_id: scenarioId,
      expected_behavior: [
        `Answer with: ${requiredPhrase}.`,
      ],
      required_evidence: ["scenario"],
      checks: [
        {
          id: "includes_expected_response",
          type: "output_contains",
          value: requiredPhrase,
        },
      ],
    }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to create eval contract.");
  }
  return response.json();
}

async function createProjectRun(
  projectId: string,
  payload: {
    agent_design_id: string;
    agent_version_id?: string;
    scenario_id: string;
    eval_contract_id: string;
    mode: "mock" | "live";
  },
): Promise<RunRecord> {
  const response = await fetch(`${apiBase}/projects/${projectId}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to create run.");
  }
  return response.json();
}

async function evaluateRun(projectId: string, runId: string): Promise<EvalResult> {
  const response = await fetch(`${apiBase}/projects/${projectId}/runs/${runId}/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ judge_mode: "deterministic" }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to evaluate run.");
  }
  return response.json();
}

async function listFailurePackets(
  projectId: string,
  agentDesignId: string,
): Promise<FailurePacket[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/failure-packets?agent_design_id=${agentDesignId}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load failure packets.");
  }
  return response.json();
}

async function createFixProposal(
  projectId: string,
  agentDesignId: string,
  targetVersionId: string,
  failurePackets: FailurePacket[],
  contractId: string,
  requiredPhrase: string,
): Promise<FixProposal> {
  const response = await fetch(`${apiBase}/projects/${projectId}/fix-proposals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent_design_id: agentDesignId,
      target_version_id: targetVersionId,
      title: `Clarify expected response: ${requiredPhrase}`,
      rationale: "The baseline failed the explicit success criteria.",
      proposed_changes: [
        {
          surface: "instructions",
          change: candidateInstructions(requiredPhrase),
        },
      ],
      addressed_failure_packet_ids: failurePackets.map((packet) => packet.id),
      validation_contract_ids: [contractId],
    }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to create fix proposal.");
  }
  return response.json();
}

async function createComparison(
  projectId: string,
  baselineRunId: string,
  candidateRunId: string,
  evalContractId: string,
): Promise<Comparison> {
  const response = await fetch(`${apiBase}/projects/${projectId}/comparisons`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      baseline_run_id: baselineRunId,
      candidate_run_id: candidateRunId,
      eval_contract_id: evalContractId,
    }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to compare runs.");
  }
  return response.json();
}

async function listAgentVersions(projectId: string, agentDesignId: string): Promise<AgentVersion[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/agent-designs/${agentDesignId}/versions`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load agent versions.");
  }
  return response.json();
}

async function listScenarios(projectId: string, agentDesignId: string): Promise<Scenario[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/scenarios?agent_design_id=${agentDesignId}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load scenarios.");
  }
  return response.json();
}

async function listEvalContracts(projectId: string, agentDesignId: string): Promise<EvalContract[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/eval-contracts?agent_design_id=${agentDesignId}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load eval contracts.");
  }
  return response.json();
}

async function listRuns(projectId: string, agentDesignId: string): Promise<RunRecord[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/runs?agent_design_id=${agentDesignId}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load runs.");
  }
  return response.json();
}

async function listGateDefinitions(
  projectId: string,
  agentDesignId: string,
): Promise<GateDefinition[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/gates?agent_design_id=${agentDesignId}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load gates.");
  }
  return response.json();
}

async function createGateDefinition(
  projectId: string,
  agentDesignId: string,
): Promise<GateDefinition> {
  const response = await fetch(`${apiBase}/projects/${projectId}/gates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent_design_id: agentDesignId,
      name: "Promotion readiness",
      criteria: ["candidate eval evidence exists", "comparison evidence exists", "no open failures"],
      required_artifact_types: ["EVAL_RESULT", "COMPARISON"],
      threshold: "all_criteria_met",
      blocking_failure_statuses: ["open"],
      approval_mode: "manual",
    }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to create gate.");
  }
  return response.json();
}

async function listGateDecisions(
  projectId: string,
  agentDesignId: string,
): Promise<GateDecision[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/gate-decisions?agent_design_id=${agentDesignId}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load gate decisions.");
  }
  return response.json();
}

async function createGateDecision(
  projectId: string,
  gateId: string,
  payload: { eval_result_id?: string; comparison_id?: string },
): Promise<GateDecision> {
  const response = await fetch(`${apiBase}/projects/${projectId}/gates/${gateId}/decisions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to run gate.");
  }
  return response.json();
}

async function listEvalResults(projectId: string, runId: string): Promise<EvalResult[]> {
  const response = await fetch(`${apiBase}/projects/${projectId}/eval-results?run_id=${runId}`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load eval results.");
  }
  return response.json();
}

async function listFixProposals(projectId: string, agentDesignId: string): Promise<FixProposal[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/fix-proposals?agent_design_id=${agentDesignId}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load fix proposals.");
  }
  return response.json();
}

async function listComparisons(projectId: string, agentDesignId: string): Promise<Comparison[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/comparisons?agent_design_id=${agentDesignId}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load comparisons.");
  }
  return response.json();
}

function latestRunForVersion(
  runs: RunRecord[],
  versionId: string | undefined,
  scenarioId: string | undefined,
  contractId: string | undefined,
): RunRecord | undefined {
  if (!versionId || !scenarioId || !contractId) {
    return undefined;
  }
  return runs.find(
    (run) =>
      run.agent_version_id === versionId &&
      run.scenario_id === scenarioId &&
      run.eval_contract_id === contractId,
  );
}

function traceUrlFromArtifact(artifact: ArtifactRecord): string | null {
  if (artifact.artifact_type !== "TRACE_REF") {
    return null;
  }
  const match = artifact.body.match(/URL\n(.+)/);
  return match?.[1]?.trim() ?? null;
}

function inferExpectedResponse(agent: AgentDesign): string {
  const intent = agent.intent.trim();
  const patterns = [
    /^(?:always\s+)?(?:reply|respond|answer|say)\s+(?:with\s+)?["']?(.+?)["']?\.?$/i,
    /^(?:always\s+)?(?:return|output)\s+["']?(.+?)["']?\.?$/i,
  ];
  for (const pattern of patterns) {
    const match = intent.match(pattern);
    if (match?.[1]?.trim()) {
      return match[1].trim();
    }
  }
  return intent || agent.name;
}

function candidateInstructions(expectedResponse: string): string {
  return `Respond with: ${expectedResponse.trim()}`;
}

async function hydrateEddFlow(projectId: string, agent: AgentDesign): Promise<EddFlowState> {
  const [versions, scenarios, contracts, runs, failurePackets, fixProposals, comparisons] =
    await Promise.all([
      listAgentVersions(projectId, agent.id),
      listScenarios(projectId, agent.id),
      listEvalContracts(projectId, agent.id),
      listRuns(projectId, agent.id),
      listFailurePackets(projectId, agent.id),
      listFixProposals(projectId, agent.id),
      listComparisons(projectId, agent.id),
    ]);

  const comparison = comparisons[0];
  const baselineVersion =
    versions.find((version) => version.id === comparison?.baseline_version_id) ??
    versions.find((version) => version.status === "baseline") ??
    versions.find((version) => version.version_label === "v0");
  const candidateVersion =
    versions.find((version) => version.id === comparison?.candidate_version_id) ??
    versions.find((version) => version.source_fix_proposal_id) ??
    versions.find((version) => version.status === "candidate") ??
    versions.find((version) => version.version_label === "v1");
  const contract = contracts[0];
  const scenario =
    scenarios.find((item) => item.id === contract?.scenario_id) ??
    scenarios[0];
  const baselineRun =
    runs.find((run) => run.id === comparison?.baseline_run_id) ??
    latestRunForVersion(runs, baselineVersion?.id, scenario?.id, contract?.id);
  const candidateRun =
    runs.find((run) => run.id === comparison?.candidate_run_id) ??
    latestRunForVersion(runs, candidateVersion?.id, scenario?.id, contract?.id);
  const [baselineEvalResults, candidateEvalResults] = await Promise.all([
    baselineRun ? listEvalResults(projectId, baselineRun.id) : Promise.resolve([]),
    candidateRun ? listEvalResults(projectId, candidateRun.id) : Promise.resolve([]),
  ]);

  return {
    baselineVersion,
    candidateVersion,
    scenario,
    contract,
    baselineRun,
    candidateRun,
    baselineEval: baselineEvalResults[0],
    candidateEval: candidateEvalResults[0],
    failurePackets,
    fixProposal: fixProposals[0],
    comparison,
  };
}

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [project, setProject] = useState<Project | null>(null);
  const [agents, setAgents] = useState<AgentDesign[]>([]);
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [intent, setIntent] = useState("");
  const [scenarioInput, setScenarioInput] = useState(
    "A customer reports a failed deployment and asks what to do next.",
  );
  const [requiredPhrase, setRequiredPhrase] = useState("");
  const [runMode, setRunMode] = useState<"mock" | "live">("mock");
  const [contextPack, setContextPack] = useState<ContextPack | null>(null);
  const [eddFlow, setEddFlow] = useState<EddFlowState>({ failurePackets: [] });
  const [gates, setGates] = useState<GateDefinition[]>([]);
  const [gateDecisions, setGateDecisions] = useState<GateDecision[]>([]);
  const [reviewArtifact, setReviewArtifact] = useState<ArtifactRecord | null>(null);
  const [reviewLinks, setReviewLinks] = useState<ArtifactLink[]>([]);
  const [toolsPanelOpen, setToolsPanelOpen] = useState(false);
  const [scratchPanelOpen, setScratchPanelOpen] = useState(false);
  const [openAgentMenuId, setOpenAgentMenuId] = useState<string | null>(null);
  const [deleteCandidate, setDeleteCandidate] = useState<AgentDesign | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingContext, setIsLoadingContext] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isFlowBusy, setIsFlowBusy] = useState(false);
  const [isGateBusy, setIsGateBusy] = useState(false);
  const [updatingTools, setUpdatingTools] = useState(false);
  const [evaluatingArtifactId, setEvaluatingArtifactId] = useState<string | null>(null);
  const [activity, setActivity] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scratchActivity, setScratchActivity] = useState<string | null>(null);
  const [scratchError, setScratchError] = useState<string | null>(null);
  const [scratchArtifact, setScratchArtifact] = useState<ArtifactRecord | null>(null);
  const [scratchTraceUrl, setScratchTraceUrl] = useState<string | null>(null);

  useEffect(() => {
    listProjects()
      .then((projects) => {
        const activeProject = projects[0] ?? null;
        setProject(activeProject);
        if (!activeProject) {
          setAgents([]);
          return;
        }
        return listAgentDesigns(activeProject.id).then((items) => {
          setAgents(items);
          setSelectedId(items[0]?.id ?? null);
        });
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    if (!project) {
      setTools([]);
      return;
    }
    listToolDefinitions(project.id)
      .then(setTools)
      .catch((err: Error) => setError(err.message));
  }, [project]);

  const selectedAgent = useMemo(
    () => agents.find((agent) => agent.id === selectedId) ?? null,
    [agents, selectedId],
  );
  const approvedTools = useMemo(
    () => tools.filter((tool) => tool.status === "approved"),
    [tools],
  );
  const latestGate = gates[0] ?? null;
  const latestGateDecision = gateDecisions[0] ?? null;
  const artifactsById = useMemo(() => {
    return new Map((contextPack?.artifacts ?? []).map((artifact) => [artifact.id, artifact]));
  }, [contextPack]);
  const visibleArtifacts = contextPack?.artifacts ?? [];
  const evidencePreviewArtifacts = [
    ...visibleArtifacts.filter((artifact) => artifact.artifact_type === "TRACE_REF"),
    ...visibleArtifacts.filter((artifact) => artifact.artifact_type !== "TRACE_REF"),
  ].filter(
    (artifact, index, artifacts) =>
      artifacts.findIndex((candidate) => candidate.id === artifact.id) === index,
  ).slice(0, 4);
  const reviewTraceUrl = reviewArtifact ? traceUrlFromArtifact(reviewArtifact) : null;
  const savedExpectedPhrase = eddFlow.contract?.checks.find((check) => check.value)?.value ?? "";
  const testOutOfSync = Boolean(
    eddFlow.contract &&
      requiredPhrase.trim() &&
      savedExpectedPhrase &&
      savedExpectedPhrase !== requiredPhrase.trim(),
  );

  useEffect(() => {
    if (!project) {
      setContextPack(null);
      setGates([]);
      setGateDecisions([]);
      return;
    }
    let isCurrent = true;
    setEddFlow({ failurePackets: [] });
    setIsLoadingContext(true);
    Promise.all([
      buildContextPack(project.id, selectedId ?? undefined),
      selectedAgent
        ? hydrateEddFlow(project.id, selectedAgent)
        : Promise.resolve({ failurePackets: [] } as EddFlowState),
      selectedAgent ? listGateDefinitions(project.id, selectedAgent.id) : Promise.resolve([]),
      selectedAgent ? listGateDecisions(project.id, selectedAgent.id) : Promise.resolve([]),
    ])
      .then(([pack, flow, loadedGates, loadedGateDecisions]) => {
        if (!isCurrent) {
          return;
        }
        setContextPack(pack);
        setEddFlow(flow);
        setGates(loadedGates);
        setGateDecisions(loadedGateDecisions);
        const phrase = flow.contract?.checks.find((check) => check.value)?.value;
        const inferredPhrase = selectedAgent ? inferExpectedResponse(selectedAgent) : "";
        if (phrase && phrase !== "bounded resolution") {
          setRequiredPhrase(phrase);
        } else if (inferredPhrase) {
          setRequiredPhrase(inferredPhrase);
        } else if (selectedAgent) {
          setRequiredPhrase(inferExpectedResponse(selectedAgent));
        }
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoadingContext(false));
    return () => {
      isCurrent = false;
    };
  }, [project, selectedAgent, selectedId]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    try {
      if (!project) {
        throw new Error("No active project is available.");
      }
      const agent = await createAgentDesign(project.id, name.trim(), intent.trim());
      setAgents((items) => [agent, ...items]);
      setSelectedId(agent.id);
      setReviewArtifact(null);
      setReviewLinks([]);
      setToolsPanelOpen(false);
      setScratchPanelOpen(false);
      setScratchActivity(null);
      setScratchError(null);
      setScratchArtifact(null);
      setScratchTraceUrl(null);
      setName("");
      setIntent("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create agent design.");
    }
  }

  async function handleDeleteAgent() {
    if (!project || !deleteCandidate) {
      return;
    }
    setError(null);
    try {
      await deleteAgentDesign(project.id, deleteCandidate.id);
      setAgents((items) => items.filter((agent) => agent.id !== deleteCandidate.id));
      if (selectedId === deleteCandidate.id) {
        setSelectedId(null);
        setContextPack(null);
        setReviewArtifact(null);
        setReviewLinks([]);
        setToolsPanelOpen(false);
        setScratchPanelOpen(false);
        setActivity(null);
        setScratchActivity(null);
        setScratchError(null);
        setScratchArtifact(null);
        setScratchTraceUrl(null);
      }
      setDeleteCandidate(null);
      setOpenAgentMenuId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete agent design.");
    }
  }

  async function handleToggleTool(toolName: string) {
    if (!project || !selectedAgent) {
      return;
    }
    const allowed = new Set(selectedAgent.allowed_tool_names);
    if (allowed.has(toolName)) {
      allowed.delete(toolName);
    } else {
      allowed.add(toolName);
    }
    setError(null);
    setUpdatingTools(true);
    try {
      const updated = await updateAgentDesignToolAllowlist(
        project.id,
        selectedAgent.id,
        [...allowed],
      );
      setAgents((items) =>
        items.map((agent) => (agent.id === updated.id ? updated : agent)),
      );
      setContextPack(await buildContextPack(project.id, updated.id));
      setActivity("Tool policy updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update agent tools.");
    } finally {
      setUpdatingTools(false);
    }
  }

  async function handleRunAgent() {
    if (!project || !selectedAgent) {
      return;
    }
    setActivity(null);
    setError(null);
    setScratchError(null);
    setScratchActivity(runMode === "live" ? "Running live OpenAI scenario." : "Running mock scenario.");
    setScratchArtifact(null);
    setScratchTraceUrl(null);
    setIsRunning(true);
    try {
      const run = await runAgentDesign(
        project.id,
        selectedAgent.id,
        scenarioInput.trim(),
        runMode,
      );
      setActivity("Stored run evidence.");
      setContextPack((pack) =>
        pack
          ? { ...pack, artifacts: [run.artifact, ...pack.artifacts] }
          : pack,
      );
      setScratchArtifact(run.artifact);
      setScratchTraceUrl(run.trace_url);
      setScratchActivity("Scratch run saved.");
    } catch (err) {
      setScratchError(err instanceof Error ? err.message : "Unable to run agent scenario.");
      setScratchActivity(null);
    } finally {
      setIsRunning(false);
    }
  }

  async function handleEvaluateArtifact(artifact: ArtifactRecord) {
    if (!project) {
      return;
    }
    setError(null);
    setActivity("Evaluating run evidence.");
    setEvaluatingArtifactId(artifact.id);
    try {
      const evalResult = await evaluateArtifact(project.id, artifact.id);
      setActivity("Stored eval evidence.");
      setContextPack((pack) =>
        pack
          ? { ...pack, artifacts: [evalResult.artifact, ...pack.artifacts] }
          : pack,
      );
      await handleReviewArtifact(evalResult.artifact.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to evaluate run artifact.");
      setActivity(null);
    } finally {
      setEvaluatingArtifactId(null);
    }
  }

  async function handleReviewArtifact(artifactId: string) {
    if (!project) {
      return;
    }
    setError(null);
    try {
      const [artifact, links] = await Promise.all([
        loadArtifact(project.id, artifactId),
        loadArtifactLinks(project.id, artifactId),
      ]);
      setReviewArtifact(artifact);
      setReviewLinks(links);
      setToolsPanelOpen(false);
      setScratchPanelOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load artifact.");
    }
  }

  async function refreshContext() {
    if (!project) {
      return;
    }
    const pack = await buildContextPack(project.id, selectedId ?? undefined);
    setContextPack(pack);
  }

  async function refreshReadiness() {
    if (!project || !selectedAgent) {
      return;
    }
    const [loadedGates, loadedDecisions] = await Promise.all([
      listGateDefinitions(project.id, selectedAgent.id),
      listGateDecisions(project.id, selectedAgent.id),
    ]);
    setGates(loadedGates);
    setGateDecisions(loadedDecisions);
  }

  async function reviewFirstArtifact(artifactIds: string[]) {
    if (artifactIds[0]) {
      await handleReviewArtifact(artifactIds[0]);
    }
  }

  async function handleCreatePromotionGate() {
    if (!project || !selectedAgent) {
      return;
    }
    setError(null);
    setActivity("Creating promotion gate.");
    setIsGateBusy(true);
    try {
      const gate = await createGateDefinition(project.id, selectedAgent.id);
      setGates((items) => [gate, ...items]);
      setActivity("Promotion gate created.");
      await refreshContext();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create gate.");
      setActivity(null);
    } finally {
      setIsGateBusy(false);
    }
  }

  async function handleRunPromotionGate() {
    if (!project || !latestGate || !eddFlow.candidateEval || !eddFlow.comparison) {
      return;
    }
    setError(null);
    setActivity("Running promotion gate.");
    setIsGateBusy(true);
    try {
      const decision = await createGateDecision(project.id, latestGate.id, {
        eval_result_id: eddFlow.candidateEval.id,
        comparison_id: eddFlow.comparison.id,
      });
      setGateDecisions((items) => [decision, ...items]);
      setActivity("Promotion readiness recorded.");
      await refreshReadiness();
      await refreshContext();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run gate.");
      setActivity(null);
    } finally {
      setIsGateBusy(false);
    }
  }

  async function handleInitializeEddFlow() {
    if (!project || !selectedAgent) {
      return;
    }
    if (!requiredPhrase.trim()) {
      setError("Add the expected answer text before defining the test.");
      return;
    }
    setError(null);
    setActivity("Saving the scenario and success criteria.");
    setIsFlowBusy(true);
    try {
      const baselineVersion = await createAgentVersion(project.id, selectedAgent.id, {
        version_label: "v0",
        instructions: selectedAgent.intent,
        status: "baseline",
      });
      const scenario = await createScenario(project.id, selectedAgent.id, scenarioInput.trim());
      const contract = await createEvalContract(
        project.id,
        selectedAgent.id,
        scenario.id,
        requiredPhrase.trim(),
      );
      setEddFlow({ baselineVersion, scenario, contract, failurePackets: [] });
      setActivity("Test is ready. Run the original agent next.");
      await refreshContext();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to initialize EDD flow.");
      setActivity(null);
    } finally {
      setIsFlowBusy(false);
    }
  }

  async function handleRunBaseline() {
    if (!project || !selectedAgent || !eddFlow.baselineVersion || !eddFlow.scenario || !eddFlow.contract) {
      return;
    }
    setError(null);
    setActivity("Running the original agent.");
    setIsFlowBusy(true);
    try {
      const baselineRun = await createProjectRun(project.id, {
        agent_design_id: selectedAgent.id,
        agent_version_id: eddFlow.baselineVersion.id,
        scenario_id: eddFlow.scenario.id,
        eval_contract_id: eddFlow.contract.id,
        mode: runMode,
      });
      setEddFlow((flow) => ({ ...flow, baselineRun }));
      setActivity("Original answer saved.");
      await refreshContext();
      await reviewFirstArtifact(baselineRun.artifact_ids);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run baseline.");
      setActivity(null);
    } finally {
      setIsFlowBusy(false);
    }
  }

  async function handleEvaluateBaseline() {
    if (!project || !selectedAgent || !eddFlow.baselineRun) {
      return;
    }
    setError(null);
    setActivity("Checking the original answer.");
    setIsFlowBusy(true);
    try {
      const baselineEval = await evaluateRun(project.id, eddFlow.baselineRun.id);
      const failurePackets = await listFailurePackets(project.id, selectedAgent.id);
      setEddFlow((flow) => ({ ...flow, baselineEval, failurePackets }));
      setActivity(
        baselineEval.passed ? "Original answer passed." : "Original answer failed; evidence saved.",
      );
      await refreshContext();
      await reviewFirstArtifact(baselineEval.artifact_ids);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to evaluate baseline.");
      setActivity(null);
    } finally {
      setIsFlowBusy(false);
    }
  }

  async function handleCreateFixProposal() {
    if (
      !project ||
      !selectedAgent ||
      !eddFlow.baselineVersion ||
      !eddFlow.contract ||
      eddFlow.failurePackets.length === 0
    ) {
      return;
    }
    setError(null);
    setActivity("Creating one targeted fix.");
    setIsFlowBusy(true);
    try {
      const fixProposal = await createFixProposal(
        project.id,
        selectedAgent.id,
        eddFlow.baselineVersion.id,
        eddFlow.failurePackets,
        eddFlow.contract.id,
        requiredPhrase.trim(),
      );
      setEddFlow((flow) => ({ ...flow, fixProposal }));
      setActivity("Fix proposal linked to failure evidence.");
      await refreshContext();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create fix proposal.");
      setActivity(null);
    } finally {
      setIsFlowBusy(false);
    }
  }

  async function handleCreateCandidate() {
    if (!project || !selectedAgent || !eddFlow.baselineVersion || !eddFlow.fixProposal) {
      return;
    }
    setError(null);
    setActivity("Creating the candidate version.");
    setIsFlowBusy(true);
    try {
      const candidateVersion = await createAgentVersion(project.id, selectedAgent.id, {
        version_label: "v1",
        parent_version_id: eddFlow.baselineVersion.id,
        source_fix_proposal_id: eddFlow.fixProposal.id,
        instructions: candidateInstructions(requiredPhrase),
        status: "candidate",
      });
      setEddFlow((flow) => ({ ...flow, candidateVersion }));
      setActivity("Candidate v1 is ready to run.");
      await refreshContext();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create candidate version.");
      setActivity(null);
    } finally {
      setIsFlowBusy(false);
    }
  }

  async function handleRunCandidate() {
    if (!project || !selectedAgent || !eddFlow.candidateVersion || !eddFlow.scenario || !eddFlow.contract) {
      return;
    }
    setError(null);
    setActivity("Running the candidate agent.");
    setIsFlowBusy(true);
    try {
      const candidateRun = await createProjectRun(project.id, {
        agent_design_id: selectedAgent.id,
        agent_version_id: eddFlow.candidateVersion.id,
        scenario_id: eddFlow.scenario.id,
        eval_contract_id: eddFlow.contract.id,
        mode: runMode,
      });
      setEddFlow((flow) => ({ ...flow, candidateRun }));
      setActivity("Candidate answer saved.");
      await refreshContext();
      await reviewFirstArtifact(candidateRun.artifact_ids);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run candidate.");
      setActivity(null);
    } finally {
      setIsFlowBusy(false);
    }
  }

  async function handleEvaluateCandidate() {
    if (!project || !eddFlow.candidateRun) {
      return;
    }
    setError(null);
    setActivity("Checking the candidate answer.");
    setIsFlowBusy(true);
    try {
      const candidateEval = await evaluateRun(project.id, eddFlow.candidateRun.id);
      setEddFlow((flow) => ({ ...flow, candidateEval }));
      setActivity(candidateEval.passed ? "Candidate passed." : "Candidate still fails.");
      await refreshContext();
      await reviewFirstArtifact(candidateEval.artifact_ids);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to evaluate candidate.");
      setActivity(null);
    } finally {
      setIsFlowBusy(false);
    }
  }

  async function handleCompareRuns() {
    if (!project || !eddFlow.baselineRun || !eddFlow.candidateRun || !eddFlow.contract) {
      return;
    }
    setError(null);
    setActivity("Comparing original and candidate evidence.");
    setIsFlowBusy(true);
    try {
      const comparison = await createComparison(
        project.id,
        eddFlow.baselineRun.id,
        eddFlow.candidateRun.id,
        eddFlow.contract.id,
      );
      setEddFlow((flow) => ({ ...flow, comparison }));
      setActivity("Comparison evidence recorded.");
      await refreshContext();
      await reviewFirstArtifact(comparison.artifact_ids);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to compare runs.");
      setActivity(null);
    } finally {
      setIsFlowBusy(false);
    }
  }

  const loopSteps = [
    {
      label: "Define test",
      done: Boolean(eddFlow.baselineVersion && eddFlow.scenario && eddFlow.contract && !testOutOfSync),
      detail: testOutOfSync ? "Needs update" : "Scenario and success criteria",
    },
    {
      label: "Run original",
      done: Boolean(eddFlow.baselineRun),
      detail: eddFlow.baselineRun ? "Original response saved" : "Capture the starting behavior",
    },
    {
      label: "Check original",
      done: Boolean(eddFlow.baselineEval),
      detail: eddFlow.baselineEval
        ? `${eddFlow.baselineEval.score}/${eddFlow.baselineEval.checks.length} checks`
        : "Judge against the success criteria",
    },
    {
      label: "Propose fix",
      done: Boolean(eddFlow.fixProposal),
      detail: eddFlow.fixProposal ? "Fix linked to the failure" : "Suggest one targeted change",
    },
    {
      label: "Create candidate",
      done: Boolean(eddFlow.candidateVersion),
      detail: eddFlow.candidateVersion ? "New version ready" : "Apply the proposed fix",
    },
    {
      label: "Run candidate",
      done: Boolean(eddFlow.candidateRun),
      detail: eddFlow.candidateRun ? "Candidate response saved" : "Run the same scenario again",
    },
    {
      label: "Check candidate",
      done: Boolean(eddFlow.candidateEval),
      detail: eddFlow.candidateEval
        ? `${eddFlow.candidateEval.score}/${eddFlow.candidateEval.checks.length} checks`
        : "Judge the new response",
    },
    {
      label: "Compare",
      done: Boolean(eddFlow.comparison),
      detail: eddFlow.comparison?.summary ?? "Did the candidate improve?",
    },
  ];
  const currentLoopAction = (() => {
    if (!eddFlow.contract) {
      return {
        eyebrow: "Next",
        title: "Define the test",
        detail: "Save the scenario and the success criteria this agent will be judged against.",
        label: "Define test",
        onClick: handleInitializeEddFlow,
        disabled: isFlowBusy || !requiredPhrase.trim(),
      };
    }
    if (testOutOfSync) {
      return {
        eyebrow: "Next",
        title: "Redefine the test",
        detail: "The saved success criteria do not match the expected answer shown above.",
        label: "Redefine test",
        onClick: handleInitializeEddFlow,
        disabled: isFlowBusy || !requiredPhrase.trim(),
      };
    }
    if (!eddFlow.baselineRun) {
      return {
        eyebrow: "Next",
        title: "Run the original agent",
        detail: "Capture how the current instructions answer the scenario before any fix.",
        label: "Run original",
        onClick: handleRunBaseline,
        disabled: isFlowBusy,
      };
    }
    if (!eddFlow.baselineEval) {
      return {
        eyebrow: "Next",
        title: "Check the original answer",
        detail: "Judge the response against the success criteria and record what failed.",
        label: "Check answer",
        onClick: handleEvaluateBaseline,
        disabled: isFlowBusy,
      };
    }
    if (!eddFlow.fixProposal && eddFlow.failurePackets.length > 0) {
      return {
        eyebrow: "Next",
        title: "Propose one fix",
        detail: "Use the failure evidence to suggest one targeted instruction change.",
        label: "Create fix",
        onClick: handleCreateFixProposal,
        disabled: isFlowBusy,
      };
    }
    if (!eddFlow.candidateVersion && eddFlow.fixProposal) {
      return {
        eyebrow: "Next",
        title: "Create the candidate",
        detail: "Apply the proposed fix to create a new agent version.",
        label: "Create candidate",
        onClick: handleCreateCandidate,
        disabled: isFlowBusy,
      };
    }
    if (!eddFlow.candidateRun && eddFlow.candidateVersion) {
      return {
        eyebrow: "Next",
        title: "Run the candidate",
        detail: "Run the improved version against the same scenario.",
        label: "Run candidate",
        onClick: handleRunCandidate,
        disabled: isFlowBusy,
      };
    }
    if (!eddFlow.candidateEval && eddFlow.candidateRun) {
      return {
        eyebrow: "Next",
        title: "Check the candidate answer",
        detail: "Judge the new response against the same success criteria.",
        label: "Check candidate",
        onClick: handleEvaluateCandidate,
        disabled: isFlowBusy,
      };
    }
    if (!eddFlow.comparison && eddFlow.baselineEval && eddFlow.candidateEval) {
      return {
        eyebrow: "Next",
        title: "Compare original vs candidate",
        detail: "Show whether the new version fixed the failure or still needs work.",
        label: "Compare",
        onClick: handleCompareRuns,
        disabled: isFlowBusy,
      };
    }
    return {
      eyebrow: "Complete",
      title: "Improvement check complete",
      detail: eddFlow.comparison?.summary ?? "Open the saved evidence to inspect the result.",
      label: "Done",
      onClick: undefined,
      disabled: true,
    };
  })();

  return (
    <div
      className={[
        sidebarOpen ? "app-shell" : "app-shell sidebar-collapsed",
        reviewArtifact || toolsPanelOpen || scratchPanelOpen ? "review-open" : "",
      ].join(" ")}
    >
      <aside className="sidebar">
        <div className="brand-row">
          <div className="brand-mark">E</div>
          {sidebarOpen ? <strong>{project?.name ?? "EDD Platform"}</strong> : null}
          <button
            className="icon-button"
            type="button"
            aria-label="Toggle sidebar"
            onClick={() => setSidebarOpen((value) => !value)}
          >
            <PanelLeft size={21} />
          </button>
        </div>

        <nav className="primary-nav" aria-label="Primary">
          <button
            className={!selectedAgent ? "nav-item active" : "nav-item"}
            type="button"
            onClick={() => {
              setSelectedId(null);
              setReviewArtifact(null);
              setReviewLinks([]);
              setToolsPanelOpen(false);
              setScratchPanelOpen(false);
              setActivity(null);
            }}
          >
            <PencilLine size={22} />
            {sidebarOpen ? <span>New agent</span> : null}
          </button>
          <button className="nav-item muted" type="button">
            <Search size={22} />
            {sidebarOpen ? <span>Search</span> : null}
          </button>
          <button className="nav-item muted" type="button">
            <Clock3 size={22} />
            {sidebarOpen ? <span>Runs</span> : null}
          </button>
        </nav>

        {sidebarOpen ? (
          <section className="agent-list" aria-label="Agent designs">
            <p className="section-label">Agents</p>
            {isLoading ? <p className="empty-list">Loading...</p> : null}
            {!isLoading && agents.length === 0 ? <p className="empty-list">No agents yet</p> : null}
            {agents.map((agent) => (
              <div
                className={agent.id === selectedId ? "agent-row selected" : "agent-row"}
                key={agent.id}
              >
                <button
                  className="agent-select"
                  type="button"
                  onClick={() => {
                    setSelectedId(agent.id);
                    setOpenAgentMenuId(null);
                    setReviewArtifact(null);
                    setReviewLinks([]);
                    setToolsPanelOpen(false);
                    setScratchPanelOpen(false);
                    setScratchActivity(null);
                    setScratchError(null);
                    setScratchArtifact(null);
                    setScratchTraceUrl(null);
                  }}
                >
                  <span>{agent.name}</span>
                </button>
                <button
                  className="agent-menu-button"
                  type="button"
                  aria-label={`Open actions for ${agent.name}`}
                  onClick={() =>
                    setOpenAgentMenuId((current) => (current === agent.id ? null : agent.id))
                  }
                >
                  <MoreHorizontal size={21} />
                </button>
                {openAgentMenuId === agent.id ? (
                  <div className="agent-menu" role="menu">
                    <button
                      className="agent-menu-item"
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setSelectedId(agent.id);
                        setScratchPanelOpen(true);
                        setReviewArtifact(null);
                        setReviewLinks([]);
                        setToolsPanelOpen(false);
                        setOpenAgentMenuId(null);
                      }}
                    >
                      <Play size={18} />
                      Run scratch
                    </button>
                    <button
                      className="agent-menu-item danger"
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setDeleteCandidate(agent);
                        setOpenAgentMenuId(null);
                      }}
                    >
                      <Trash2 size={18} />
                      Delete
                    </button>
                  </div>
                ) : null}
              </div>
            ))}
          </section>
        ) : null}
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h1>{selectedAgent ? "Agent workspace" : "New agent"}</h1>
            <p>
              {selectedAgent
                ? "Create the agent, then test and improve it with saved evidence."
                : project?.description ??
                "Describe an agent and persist the first platform design."}
            </p>
          </div>
          <div className="topbar-actions">
            {selectedAgent ? (
              <div className="run-mode-control topbar-run-mode" aria-label="Run mode">
                <button
                  className={runMode === "mock" ? "mode-option active" : "mode-option"}
                  type="button"
                  onClick={() => setRunMode("mock")}
                >
                  Mock
                </button>
                <button
                  className={runMode === "live" ? "mode-option active" : "mode-option"}
                  type="button"
                  onClick={() => setRunMode("live")}
                >
                  Live OpenAI
                </button>
              </div>
            ) : null}
            <span className="status-pill">Platform: local</span>
          </div>
        </header>

        <section className={selectedAgent ? "canvas canvas-workspace" : "canvas"}>
          {!selectedAgent ? (
            <form className="intent-form" onSubmit={handleCreate}>
              <p className="eyebrow">Start from intent</p>
              <h2>What agent are we building?</h2>
              <label>
                Agent name
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Customer Service Triage Agent"
                  required
                />
              </label>
              <label>
                Agent intent
                <textarea
                  value={intent}
                  onChange={(event) => setIntent(event.target.value)}
                  placeholder="Determine why an issue escalated, gather evidence, and recommend a safe next action."
                  required
                />
              </label>
              <button className="primary-button" type="submit">
                Create agent
              </button>
              {error ? <p className="error-text">{error}</p> : null}
            </form>
          ) : null}

          <section className={selectedAgent ? "evidence-panel evidence-workspace" : "evidence-panel"}>
            <p className="eyebrow">{selectedAgent ? "Agent test workflow" : "Evidence context"}</p>
            <h2>{selectedAgent ? "Prove this agent gets better." : "Ready for the first design"}</h2>
            {!selectedAgent ? (
              <p className="muted-copy">
                Create an agent design to begin collecting targets, judge prompts, gates, runs,
                and evidence.
              </p>
            ) : null}
            {selectedAgent ? (
              <div className="artifact-stack">
                <section className="agent-setup-panel">
                  <div>
                    <p className="artifact-type">Created agent</p>
                    <h3>{selectedAgent.name}</h3>
                    <p>{selectedAgent.intent}</p>
                  </div>
                  <div className="agent-setup-tools">
                    <div>
                      <p className="artifact-type">Tools</p>
                      <p>
                        {selectedAgent.allowed_tool_names.length === 0
                          ? "No tools enabled for live execution."
                          : `${selectedAgent.allowed_tool_names.length} tool${
                              selectedAgent.allowed_tool_names.length === 1 ? "" : "s"
                            } enabled for live execution.`}
                      </p>
                      <div className="tool-chip-row">
                        {selectedAgent.allowed_tool_names.length === 0 ? (
                          <span className="muted-chip">None enabled</span>
                        ) : (
                          selectedAgent.allowed_tool_names.map((toolName) => (
                            <span className="tool-chip" key={toolName}>
                              {toolName}
                            </span>
                          ))
                        )}
                      </div>
                    </div>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => {
                        setToolsPanelOpen(true);
                        setReviewArtifact(null);
                        setReviewLinks([]);
                        setScratchPanelOpen(false);
                      }}
                    >
                      Manage tools
                    </button>
                  </div>
                </section>
                <section className="edd-loop-panel primary-workflow-panel">
                  <div className="edd-loop-header">
                    <div>
                      <p className="artifact-type">Before and after</p>
                      <h3>Run one scenario, fix one failure, compare the result.</h3>
                      <p>
                        The platform saves each run, check, failure, and fix as evidence so you
                        can see whether the agent actually improved.
                      </p>
                    </div>
                    <label className="compact-label">
                      <span>Success criteria</span>
                      <small>The answer should include this text.</small>
                      <input
                        value={requiredPhrase}
                        onChange={(event) => setRequiredPhrase(event.target.value)}
                      />
                      {eddFlow.contract ? (
                        <button
                          className="secondary-button compact-button"
                          type="button"
                          onClick={handleInitializeEddFlow}
                          disabled={isFlowBusy || !requiredPhrase.trim()}
                        >
                          Redefine test
                        </button>
                      ) : null}
                    </label>
                  </div>
                  <div className="loop-step-grid">
                    {loopSteps.map((step) => (
                      <div className={step.done ? "loop-step done" : "loop-step"} key={step.label}>
                        <span>{step.done ? "✓" : ""}</span>
                        <strong>{step.label}</strong>
                        <small>{step.detail}</small>
                      </div>
                    ))}
                  </div>
                  <div className="next-action-panel">
                    <div>
                      <p className="artifact-type">{currentLoopAction.eyebrow}</p>
                      <h4>{currentLoopAction.title}</h4>
                      <p>{currentLoopAction.detail}</p>
                      {activity ? <p className="activity-text">{activity}</p> : null}
                      {error ? <p className="error-text">{error}</p> : null}
                    </div>
                    {currentLoopAction.onClick ? (
                      <button
                        className="primary-button"
                        type="button"
                        onClick={currentLoopAction.onClick}
                        disabled={currentLoopAction.disabled}
                      >
                        {currentLoopAction.label}
                      </button>
                    ) : null}
                  </div>
                  {eddFlow.comparison ? (
                    <div className="comparison-summary">
                      <strong>{eddFlow.comparison.summary}</strong>
                      <span>
                        Fixed {eddFlow.comparison.fixed_failure_packet_ids.length} · Remaining{" "}
                        {eddFlow.comparison.remaining_failure_packet_ids.length} · New{" "}
                        {eddFlow.comparison.new_failure_packet_ids.length}
                      </span>
                    </div>
                  ) : null}
                  <div className="workflow-evidence-panel">
                    <div>
                      <p className="artifact-type">Saved evidence</p>
                      <h4>{visibleArtifacts.length} records</h4>
                      <p>Open the scenario, success criteria, run output, eval result, or trace.</p>
                    </div>
                    <div className="workflow-evidence-list">
                      {isLoadingContext ? <p className="muted-copy">Loading evidence...</p> : null}
                      {!isLoadingContext && evidencePreviewArtifacts.length === 0 ? (
                        <p className="muted-copy">No artifacts yet.</p>
                      ) : null}
                      {evidencePreviewArtifacts.map((artifact) => {
                        const traceUrl = traceUrlFromArtifact(artifact);
                        return (
                          <div className="workflow-evidence-row" key={artifact.id}>
                            <button
                              className="workflow-evidence-item"
                              type="button"
                              onClick={() => handleReviewArtifact(artifact.id)}
                            >
                              <span>{artifact.artifact_type.replaceAll("_", " ")}</span>
                              <strong>{artifact.title}</strong>
                              <PanelRight size={17} />
                            </button>
                            {traceUrl ? (
                              <a
                                className="workflow-trace-link"
                                href={traceUrl}
                                target="_blank"
                                rel="noreferrer"
                              >
                                Open trace
                              </a>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <div className="readiness-panel">
                    <div>
                      <p className="artifact-type">Promotion readiness</p>
                      <h4>
                        {latestGateDecision
                          ? latestGateDecision.decision === "passed"
                            ? "Ready"
                            : "Blocked"
                          : latestGate
                            ? "Gate ready"
                            : "No gate yet"}
                      </h4>
                      <p>
                        {latestGateDecision
                          ? latestGateDecision.rationale
                          : latestGate
                            ? "Run the gate after comparison evidence exists."
                            : "Create a gate to turn eval evidence into an explicit readiness decision."}
                      </p>
                    </div>
                    {!latestGate ? (
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={handleCreatePromotionGate}
                        disabled={isGateBusy}
                      >
                        Create gate
                      </button>
                    ) : (
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={handleRunPromotionGate}
                        disabled={isGateBusy || !eddFlow.candidateEval || !eddFlow.comparison}
                      >
                        {latestGateDecision ? "Run again" : "Run gate"}
                      </button>
                    )}
                  </div>
                </section>
              </div>
            ) : null}
          </section>
        </section>
      </main>
      {scratchPanelOpen && selectedAgent ? (
        <aside className="review-panel" aria-label="Scratch run">
          <div className="review-panel-header">
            <div>
              <p className="eyebrow">Scratch run</p>
              <h2>{selectedAgent.name}</h2>
            </div>
            <button
              className="icon-button review-toggle-button"
              type="button"
              aria-label="Close scratch run panel"
              onClick={() => setScratchPanelOpen(false)}
            >
              <PanelRight size={22} />
            </button>
          </div>

          <div className="review-panel-body">
            <section className="run-playground panel-run-playground">
              <div>
                <h3>Try a scenario</h3>
                <p>
                  Uses the page run mode above. This saves evidence but does not advance the
                  before/after improvement loop.
                </p>
              </div>
              <label>
                Scenario input
                <textarea
                  value={scenarioInput}
                  onChange={(event) => setScenarioInput(event.target.value)}
                />
              </label>
              <button
                className="primary-button"
                type="button"
                onClick={handleRunAgent}
                disabled={isRunning}
              >
                <Play size={18} />
                {isRunning ? "Running" : "Run scratch"}
              </button>
              {scratchActivity ? <p className="activity-text">{scratchActivity}</p> : null}
              {scratchError ? <p className="error-text">{scratchError}</p> : null}
              {scratchArtifact ? (
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => handleReviewArtifact(scratchArtifact.id)}
                >
                  <PanelRight size={18} />
                  View result
                </button>
              ) : null}
              {scratchTraceUrl ? (
                <a
                  className="secondary-button trace-link"
                  href={scratchTraceUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open trace
                </a>
              ) : null}
            </section>
          </div>
        </aside>
      ) : null}
      {toolsPanelOpen && selectedAgent ? (
        <aside className="review-panel" aria-label="Tool marketplace">
          <div className="review-panel-header">
            <div>
              <p className="eyebrow">Tools</p>
              <h2>Available tools</h2>
            </div>
            <button
              className="icon-button review-toggle-button"
              type="button"
              aria-label="Close tools panel"
              onClick={() => setToolsPanelOpen(false)}
            >
              <PanelRight size={22} />
            </button>
          </div>

          <div className="review-panel-body">
            <section>
              <h3>Enabled for this agent</h3>
              <p>
                Pick the approved tools this agent may call during live runs. Tool calls still
                execute through platform policy, not from the browser.
              </p>
            </section>
            <section className="tool-marketplace-list">
              {approvedTools.length === 0 ? (
                <p>No approved tools are available yet.</p>
              ) : (
                approvedTools.map((tool) => {
                  const isAllowed = selectedAgent.allowed_tool_names.includes(tool.name);
                  return (
                    <button
                      className={isAllowed ? "tool-marketplace-item active" : "tool-marketplace-item"}
                      type="button"
                      key={tool.id}
                      onClick={() => handleToggleTool(tool.name)}
                      disabled={updatingTools}
                      aria-pressed={isAllowed}
                    >
                      <span>{isAllowed ? "Enabled" : "Available"}</span>
                      <strong>{tool.name}</strong>
                      <small>{tool.description}</small>
                    </button>
                  );
                })
              )}
            </section>
          </div>
        </aside>
      ) : null}
      {reviewArtifact ? (
        <aside className="review-panel" aria-label="Artifact review">
          <div className="review-panel-header">
            <div>
              <p className="eyebrow">{reviewArtifact.artifact_type.replaceAll("_", " ")}</p>
              <h2>{reviewArtifact.title}</h2>
            </div>
            <button
              className="icon-button review-toggle-button"
              type="button"
              aria-label="Close review panel"
              onClick={() => {
                setReviewArtifact(null);
                setReviewLinks([]);
              }}
            >
              <PanelRight size={22} />
            </button>
          </div>

          <div className="review-panel-body">
            <section>
              <h3>Record</h3>
              <p>{reviewArtifact.body}</p>
              {reviewTraceUrl ? (
                <a
                  className="secondary-button trace-link"
                  href={reviewTraceUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open trace
                </a>
              ) : null}
            </section>
            <section>
              <h3>Connected records</h3>
              {reviewLinks.length === 0 ? (
                <p>No connected records yet.</p>
              ) : (
                <ul className="related-list">
                  {reviewLinks.map((link) => {
                    const relatedId =
                      link.source_artifact_id === reviewArtifact.id
                        ? link.target_artifact_id
                        : link.source_artifact_id;
                    const relatedArtifact = artifactsById.get(relatedId);
                    return (
                      <li key={link.id}>
                        <strong>{relatedArtifact?.title ?? "Saved record"}</strong>
                        <span>{link.relationship_type.replaceAll("_", " ").toLowerCase()}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
            <dl>
              <div>
                <dt>Source</dt>
                <dd>{reviewArtifact.source}</dd>
              </div>
              <div>
                <dt>Updated</dt>
                <dd>{new Date(reviewArtifact.updated_at).toLocaleString()}</dd>
              </div>
            </dl>
          </div>
        </aside>
      ) : null}
      {deleteCandidate ? (
        <div className="modal-backdrop" role="presentation">
          <section className="confirm-dialog" role="dialog" aria-modal="true">
            <h2>Delete agent?</h2>
            <p>
              This will delete <strong>{deleteCandidate.name}</strong> and its run evidence.
            </p>
            <div className="dialog-actions">
              <button
                className="secondary-button"
                type="button"
                onClick={() => setDeleteCandidate(null)}
              >
                Cancel
              </button>
              <button className="danger-button" type="button" onClick={handleDeleteAgent}>
                Delete
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
