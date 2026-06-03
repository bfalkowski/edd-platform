import {
  Clock3,
  MoreHorizontal,
  PanelLeft,
  PanelRight,
  PencilLine,
  Play,
  Search,
  Trash2,
  X,
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
      name: "EDD proof scenario",
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
      name: "EDD proof contract",
      description: "Checks whether the candidate behavior includes the bounded fix.",
      scenario_id: scenarioId,
      expected_behavior: [
        "Use the scenario as evidence.",
        `Include the bounded fix phrase: ${requiredPhrase}.`,
      ],
      required_evidence: ["scenario"],
      checks: [
        {
          id: "includes_bounded_fix_phrase",
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
      title: `Add bounded phrase: ${requiredPhrase}`,
      rationale: "The baseline failed the explicit eval contract check.",
      proposed_changes: [
        {
          surface: "instructions",
          change: `Include the phrase: ${requiredPhrase}.`,
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
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [intent, setIntent] = useState("");
  const [scenarioInput, setScenarioInput] = useState(
    "A customer reports a failed deployment and asks what to do next.",
  );
  const [requiredPhrase, setRequiredPhrase] = useState("bounded resolution");
  const [runMode, setRunMode] = useState<"mock" | "live">("mock");
  const [contextPack, setContextPack] = useState<ContextPack | null>(null);
  const [eddFlow, setEddFlow] = useState<EddFlowState>({ failurePackets: [] });
  const [reviewArtifact, setReviewArtifact] = useState<ArtifactRecord | null>(null);
  const [reviewLinks, setReviewLinks] = useState<ArtifactLink[]>([]);
  const [openAgentMenuId, setOpenAgentMenuId] = useState<string | null>(null);
  const [deleteCandidate, setDeleteCandidate] = useState<AgentDesign | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingContext, setIsLoadingContext] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isFlowBusy, setIsFlowBusy] = useState(false);
  const [evaluatingArtifactId, setEvaluatingArtifactId] = useState<string | null>(null);
  const [activity, setActivity] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  const selectedAgent = useMemo(
    () => agents.find((agent) => agent.id === selectedId) ?? null,
    [agents, selectedId],
  );
  const artifactsById = useMemo(() => {
    return new Map((contextPack?.artifacts ?? []).map((artifact) => [artifact.id, artifact]));
  }, [contextPack]);

  useEffect(() => {
    if (!project) {
      setContextPack(null);
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
    ])
      .then(([pack, flow]) => {
        if (!isCurrent) {
          return;
        }
        setContextPack(pack);
        setEddFlow(flow);
        const phrase = flow.contract?.checks.find((check) => check.value)?.value;
        if (phrase) {
          setRequiredPhrase(phrase);
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
        setActivity(null);
      }
      setDeleteCandidate(null);
      setOpenAgentMenuId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete agent design.");
    }
  }

  async function handleRunAgent() {
    if (!project || !selectedAgent) {
      return;
    }
    setError(null);
    setActivity(runMode === "live" ? "Running live OpenAI scenario." : "Running mock scenario.");
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
      await handleReviewArtifact(run.artifact.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run agent scenario.");
      setActivity("Run failed.");
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

  async function reviewFirstArtifact(artifactIds: string[]) {
    if (artifactIds[0]) {
      await handleReviewArtifact(artifactIds[0]);
    }
  }

  async function handleInitializeEddFlow() {
    if (!project || !selectedAgent) {
      return;
    }
    setError(null);
    setActivity("Creating baseline, scenario, and eval contract.");
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
      setActivity("EDD proof is ready for the baseline run.");
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
    setActivity("Running baseline v0.");
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
      setActivity("Stored baseline run evidence.");
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
    setActivity("Evaluating baseline v0.");
    setIsFlowBusy(true);
    try {
      const baselineEval = await evaluateRun(project.id, eddFlow.baselineRun.id);
      const failurePackets = await listFailurePackets(project.id, selectedAgent.id);
      setEddFlow((flow) => ({ ...flow, baselineEval, failurePackets }));
      setActivity(
        baselineEval.passed ? "Baseline passed the contract." : "Baseline failure packet recorded.",
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
    setActivity("Creating bounded fix proposal.");
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
    setActivity("Creating candidate v1 from the fix.");
    setIsFlowBusy(true);
    try {
      const candidateVersion = await createAgentVersion(project.id, selectedAgent.id, {
        version_label: "v1",
        parent_version_id: eddFlow.baselineVersion.id,
        source_fix_proposal_id: eddFlow.fixProposal.id,
        instructions: `${selectedAgent.intent} Include the phrase: ${requiredPhrase.trim()}.`,
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
    setActivity("Running candidate v1.");
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
      setActivity("Stored candidate run evidence.");
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
    setActivity("Evaluating candidate v1.");
    setIsFlowBusy(true);
    try {
      const candidateEval = await evaluateRun(project.id, eddFlow.candidateRun.id);
      setEddFlow((flow) => ({ ...flow, candidateEval }));
      setActivity(candidateEval.passed ? "Candidate passed the contract." : "Candidate still fails.");
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
    setActivity("Comparing baseline and candidate evidence.");
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
      label: "Setup",
      done: Boolean(eddFlow.baselineVersion && eddFlow.scenario && eddFlow.contract),
      detail: eddFlow.contract ? eddFlow.contract.name : "Create v0, scenario, and contract",
    },
    {
      label: "Run v0",
      done: Boolean(eddFlow.baselineRun),
      detail: eddFlow.baselineRun?.id ?? "Baseline run evidence",
    },
    {
      label: "Eval v0",
      done: Boolean(eddFlow.baselineEval),
      detail: eddFlow.baselineEval
        ? `${eddFlow.baselineEval.score}/${eddFlow.baselineEval.checks.length} checks`
        : "Failure packet evidence",
    },
    {
      label: "Fix",
      done: Boolean(eddFlow.fixProposal),
      detail: eddFlow.fixProposal?.title ?? "Bounded proposal",
    },
    {
      label: "Version v1",
      done: Boolean(eddFlow.candidateVersion),
      detail: eddFlow.candidateVersion?.version_label ?? "Candidate behavior",
    },
    {
      label: "Run v1",
      done: Boolean(eddFlow.candidateRun),
      detail: eddFlow.candidateRun?.id ?? "Candidate run evidence",
    },
    {
      label: "Eval v1",
      done: Boolean(eddFlow.candidateEval),
      detail: eddFlow.candidateEval
        ? `${eddFlow.candidateEval.score}/${eddFlow.candidateEval.checks.length} checks`
        : "Candidate result",
    },
    {
      label: "Compare",
      done: Boolean(eddFlow.comparison),
      detail: eddFlow.comparison?.summary ?? "Improvement evidence",
    },
  ];

  return (
    <div
      className={[
        sidebarOpen ? "app-shell" : "app-shell sidebar-collapsed",
        reviewArtifact ? "review-open" : "",
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
            <h1>{selectedAgent?.name ?? "New agent"}</h1>
            <p>
              {selectedAgent?.intent ??
                project?.description ??
                "Describe an agent and persist the first platform design."}
            </p>
          </div>
          <span className="status-pill">Platform: local</span>
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
            <p className="eyebrow">Evidence context</p>
            <h2>{selectedAgent ? "Evidence artifacts" : "Ready for the first design"}</h2>
            {!selectedAgent ? (
              <p className="muted-copy">
                Create an agent design to begin collecting targets, judge prompts, gates, runs,
                and evidence.
              </p>
            ) : null}
            {selectedAgent ? (
              <div className="artifact-stack">
                <section className="run-playground">
                  <div>
                    <p className="artifact-type">Agent playground</p>
                    <h3>Run a scenario</h3>
                    <p>
                      Execute this design in mock mode or live OpenAI mode and store the output as run evidence.
                    </p>
                    <p className="tool-list">
                      Tools: {selectedAgent.allowed_tool_names.join(", ") || "none"}
                    </p>
                  </div>
                  <div className="run-mode-control" aria-label="Run mode">
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
                    {isRunning ? "Running" : runMode === "live" ? "Run live" : "Run mock"}
                  </button>
                  {activity ? <p className="activity-text">{activity}</p> : null}
                  {error ? <p className="error-text">{error}</p> : null}
                </section>
                <section className="edd-loop-panel">
                  <div className="edd-loop-header">
                    <div>
                      <p className="artifact-type">Eval-driven design</p>
                      <h3>Prove an improvement</h3>
                      <p>
                        Turn one failed baseline check into a bounded fix, candidate version,
                        and comparison artifact.
                      </p>
                    </div>
                    <label className="compact-label">
                      Required phrase
                      <input
                        value={requiredPhrase}
                        onChange={(event) => setRequiredPhrase(event.target.value)}
                        disabled={Boolean(eddFlow.contract)}
                      />
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
                  <div className="loop-actions">
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={handleInitializeEddFlow}
                      disabled={isFlowBusy || Boolean(eddFlow.contract)}
                    >
                      Create setup
                    </button>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={handleRunBaseline}
                      disabled={isFlowBusy || !eddFlow.contract || Boolean(eddFlow.baselineRun)}
                    >
                      Run v0
                    </button>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={handleEvaluateBaseline}
                      disabled={
                        isFlowBusy || !eddFlow.baselineRun || Boolean(eddFlow.baselineEval)
                      }
                    >
                      Evaluate v0
                    </button>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={handleCreateFixProposal}
                      disabled={
                        isFlowBusy ||
                        !eddFlow.baselineEval ||
                        eddFlow.failurePackets.length === 0 ||
                        Boolean(eddFlow.fixProposal)
                      }
                    >
                      Create fix
                    </button>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={handleCreateCandidate}
                      disabled={isFlowBusy || !eddFlow.fixProposal || Boolean(eddFlow.candidateVersion)}
                    >
                      Create v1
                    </button>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={handleRunCandidate}
                      disabled={isFlowBusy || !eddFlow.candidateVersion || Boolean(eddFlow.candidateRun)}
                    >
                      Run v1
                    </button>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={handleEvaluateCandidate}
                      disabled={
                        isFlowBusy || !eddFlow.candidateRun || Boolean(eddFlow.candidateEval)
                      }
                    >
                      Evaluate v1
                    </button>
                    <button
                      className="primary-button"
                      type="button"
                      onClick={handleCompareRuns}
                      disabled={
                        isFlowBusy ||
                        !eddFlow.baselineEval ||
                        !eddFlow.candidateEval ||
                        Boolean(eddFlow.comparison)
                      }
                    >
                      Compare
                    </button>
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
                </section>
                <div className="context-pack-meta">
                  <span>Context pack</span>
                  <strong>{contextPack?.purpose.replaceAll("_", " ") ?? "Preparing"}</strong>
                </div>
                {isLoadingContext ? <p className="muted-copy">Loading evidence...</p> : null}
                {!isLoadingContext && (contextPack?.artifacts.length ?? 0) === 0 ? (
                  <p className="muted-copy">No artifacts recorded for this design yet.</p>
                ) : null}
                {(contextPack?.artifacts ?? []).map((artifact) => (
                  <article className="artifact-card" key={artifact.id}>
                    <div>
                      <p className="artifact-type">{artifact.artifact_type.replaceAll("_", " ")}</p>
                      <h3>{artifact.title}</h3>
                      <p>{artifact.body}</p>
                    </div>
                    <div className="artifact-actions">
                      {artifact.artifact_type === "RUN_RESULT" ? (
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() => handleEvaluateArtifact(artifact)}
                          disabled={evaluatingArtifactId === artifact.id}
                        >
                          {evaluatingArtifactId === artifact.id ? "Evaluating" : "Evaluate"}
                        </button>
                      ) : null}
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => handleReviewArtifact(artifact.id)}
                      >
                        <PanelRight size={18} />
                        Review
                      </button>
                    </div>
                    <dl>
                      <div>
                        <dt>Source</dt>
                        <dd>{artifact.source}</dd>
                      </div>
                      <div>
                        <dt>Updated</dt>
                        <dd>{new Date(artifact.updated_at).toLocaleString()}</dd>
                      </div>
                    </dl>
                  </article>
                ))}
              </div>
            ) : null}
          </section>
        </section>
      </main>
      {reviewArtifact ? (
        <aside className="review-panel" aria-label="Artifact review">
          <div className="review-panel-header">
            <div>
              <p className="eyebrow">{reviewArtifact.artifact_type.replaceAll("_", " ")}</p>
              <h2>{reviewArtifact.title}</h2>
            </div>
            <button
              className="icon-button"
              type="button"
              aria-label="Close review panel"
              onClick={() => {
                setReviewArtifact(null);
                setReviewLinks([]);
              }}
            >
              <X size={22} />
            </button>
          </div>

          <div className="review-panel-body">
            <section>
              <h3>Evidence</h3>
              <p>{reviewArtifact.body}</p>
            </section>
            <section>
              <h3>Related evidence</h3>
              {reviewLinks.length === 0 ? (
                <p>No related artifacts yet.</p>
              ) : (
                <ul className="related-list">
                  {reviewLinks.map((link) => {
                    const direction =
                      link.source_artifact_id === reviewArtifact.id ? "points to" : "linked from";
                    const relatedId =
                      link.source_artifact_id === reviewArtifact.id
                        ? link.target_artifact_id
                        : link.source_artifact_id;
                    const relatedArtifact = artifactsById.get(relatedId);
                    return (
                      <li key={link.id}>
                        <strong>{link.relationship_type.replaceAll("_", " ")}</strong>
                        <span>{direction}</span>
                        <b>{relatedArtifact?.title ?? relatedId}</b>
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
                <dt>Artifact id</dt>
                <dd>{reviewArtifact.id}</dd>
              </div>
              <div>
                <dt>Project</dt>
                <dd>{reviewArtifact.project_id}</dd>
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
