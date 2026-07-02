import type {
  AgentDesign,
  AgentRunResult,
  AgentSuggestion,
  AgentVersion,
  ArtifactLink,
  ArtifactRecord,
  Comparison,
  ContextPack,
  DiscoveryPromotionResult,
  EddFlowState,
  EvalContract,
  EvalMethod,
  EvalResult,
  EvalRunResult,
  FailureMode,
  FailurePacket,
  FixProposal,
  GateDecision,
  GateDefinition,
  LangfuseObjectRef,
  NewAgentResponse,
  OutcomeAgentResponse,
  Project,
  ReviewAnnotation,
  ReviewCorpus,
  ReviewItem,
  ReviewNote,
  ReviewSamplingPlan,
  RunRecord,
  Scenario,
  ServiceStatus,
  ServiceStatusResponse,
  TestShape,
  ToolDefinition,
  ToolDefinitionCreate,
} from "./types";
import { setupContextFromTestShape, testShapeLabels } from "./helpers";

const apiBase = "/api";

export async function responseError(response: Response, fallback: string): Promise<Error> {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") {
      return new Error(`${payload.detail} (HTTP ${response.status})`);
    }
    if (Array.isArray(payload.detail)) {
      const msg = payload.detail.map((d: { loc?: string[]; msg?: string }) =>
        [d.loc?.join("."), d.msg].filter(Boolean).join(": ")
      ).join("; ");
      return new Error(`${msg} (HTTP ${response.status})`);
    }
  } catch {
    // Use the fallback below when the API returns a non-JSON error body.
  }
  return new Error(`${fallback} (HTTP ${response.status})`);
}

export async function listProjects(): Promise<Project[]> {
  const response = await fetch(`${apiBase}/projects`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load projects.");
  }
  return response.json();
}

export async function listServices(): Promise<ServiceStatus[]> {
  const response = await fetch(`${apiBase}/services`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load service status.");
  }
  const payload = (await response.json()) as ServiceStatusResponse;
  return payload.services;
}

export async function listAgentDesigns(projectId: string): Promise<AgentDesign[]> {
  const response = await fetch(`${apiBase}/projects/${projectId}/agent-designs`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load agent designs.");
  }
  return response.json();
}

export async function createAgentDesign(
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

export async function createAgentDesignFromOutcome(
  projectId: string,
  outcome: string,
  name?: string,
): Promise<OutcomeAgentResponse> {
  const response = await fetch(`${apiBase}/projects/${projectId}/agent-designs/from-outcome`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ outcome, name: name || undefined }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to draft agent from outcome.");
  }
  return response.json();
}

export async function deleteAgentDesign(projectId: string, agentDesignId: string): Promise<void> {
  const response = await fetch(`${apiBase}/projects/${projectId}/agent-designs/${agentDesignId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to delete agent design.");
  }
}

export async function updateAgentDesign(
  projectId: string,
  agentDesignId: string,
  payload: { name?: string; intent?: string; allowed_tool_names?: string[] },
): Promise<AgentDesign> {
  const response = await fetch(`${apiBase}/projects/${projectId}/agent-designs/${agentDesignId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to update agent design.");
  }
  return response.json();
}

export async function listToolDefinitions(projectId: string): Promise<ToolDefinition[]> {
  const response = await fetch(`${apiBase}/projects/${projectId}/tools`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load tools.");
  }
  return response.json();
}

export async function createToolDefinition(
  projectId: string,
  payload: ToolDefinitionCreate,
): Promise<ToolDefinition> {
  const response = await fetch(`${apiBase}/projects/${projectId}/tools`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to create tool definition.");
  }
  return response.json();
}

export async function updateToolDefinitionStatus(
  projectId: string,
  toolId: string,
  status: "draft" | "approved",
): Promise<ToolDefinition> {
  const response = await fetch(`${apiBase}/projects/${projectId}/tools/${toolId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to update tool status.");
  }
  return response.json();
}

export async function deleteToolDefinition(projectId: string, toolId: string): Promise<void> {
  const response = await fetch(`${apiBase}/projects/${projectId}/tools/${toolId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to delete tool.");
  }
}

export async function updateAgentDesignToolAllowlist(
  projectId: string,
  agentDesignId: string,
  allowedToolNames: string[],
): Promise<AgentDesign> {
  return updateAgentDesign(projectId, agentDesignId, { allowed_tool_names: allowedToolNames });
}

export async function buildContextPack(projectId: string, agentDesignId?: string): Promise<ContextPack> {
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

export async function loadArtifact(projectId: string, artifactId: string): Promise<ArtifactRecord> {
  const response = await fetch(`${apiBase}/projects/${projectId}/artifacts/${artifactId}`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load artifact.");
  }
  return response.json();
}

export async function loadArtifactLinks(projectId: string, artifactId: string): Promise<ArtifactLink[]> {
  const response = await fetch(`${apiBase}/projects/${projectId}/artifacts/${artifactId}/links`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load related evidence.");
  }
  return response.json();
}

export async function runAgentDesign(
  projectId: string,
  agentDesignId: string,
  scenarioInput: string,
  mode: "mock" | "live",
  target: "agent" | "url" = "agent",
  url?: string,
): Promise<AgentRunResult> {
  const response = await fetch(`${apiBase}/projects/${projectId}/agent-designs/${agentDesignId}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_input: scenarioInput, mode, target, url }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to run agent scenario.");
  }
  return response.json();
}

export async function evaluateArtifact(projectId: string, artifactId: string): Promise<EvalRunResult> {
  const response = await fetch(`${apiBase}/projects/${projectId}/artifacts/${artifactId}/evaluate`, {
    method: "POST",
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to evaluate run artifact.");
  }
  return response.json();
}

export async function createAgentVersion(
  projectId: string,
  agentDesignId: string,
  payload: {
    version_label?: string;
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

export async function createScenario(
  projectId: string,
  agentDesignId: string,
  input: string,
  shape: TestShape,
): Promise<Scenario> {
  const response = await fetch(`${apiBase}/projects/${projectId}/scenarios`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent_design_id: agentDesignId,
      name: `${testShapeLabels[shape]} test`,
      input,
      setup_context: setupContextFromTestShape(shape),
    }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to create scenario.");
  }
  return response.json();
}

export async function createEvalContract(
  projectId: string,
  agentDesignId: string,
  scenarioId: string,
  config: {
    method: EvalMethod;
    requiredPhrase?: string;
    requiredToolName?: string;
    rubric?: string;
  },
): Promise<EvalContract> {
  const checks = (() => {
    if (config.method === "phrase") {
      return [
        {
          id: "includes_required_phrase",
          type: "output_contains",
          value: config.requiredPhrase ?? "",
        },
      ];
    }
    if (config.method === "rubric") {
      return [
        {
          id: "satisfies_rubric",
          type: "rubric_judge",
          value: config.rubric ?? "",
        },
      ];
    }
    return [];
  })();
  const requiredTools = config.method === "tool" && config.requiredToolName ? [config.requiredToolName] : [];
  const expectedBehavior =
    config.method === "tool"
      ? [`Call ${config.requiredToolName} when answering this test case.`]
      : config.method === "rubric"
        ? [config.rubric ?? ""]
        : [`Include the required phrase: ${config.requiredPhrase}.`];
  const name =
    config.method === "tool"
      ? "Tool use"
      : config.method === "rubric"
        ? "Rubric judge"
        : "Required phrase";
  const response = await fetch(`${apiBase}/projects/${projectId}/eval-contracts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent_design_id: agentDesignId,
      name,
      description:
        config.method === "tool"
          ? "Checks whether the agent used the expected tool."
          : config.method === "rubric"
            ? "Judges whether the answer satisfies the rubric."
          : "Checks whether the response contains a required phrase.",
      scenario_id: scenarioId,
      expected_behavior: expectedBehavior,
      required_tools: requiredTools,
      checks,
    }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to create eval contract.");
  }
  return response.json();
}

export async function createProjectRun(
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

export async function evaluateRun(
  projectId: string,
  runId: string,
  judgeMode: "deterministic" | "live" = "deterministic",
): Promise<EvalResult> {
  const response = await fetch(`${apiBase}/projects/${projectId}/runs/${runId}/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ judge_mode: judgeMode }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to evaluate run.");
  }
  return response.json();
}

export async function listFailurePackets(
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

export async function createReviewNote(
  projectId: string,
  payload: {
    target_artifact_id: string;
    body: string;
    author?: string;
    metadata?: Record<string, unknown>;
  },
): Promise<ReviewNote> {
  const response = await fetch(`${apiBase}/projects/${projectId}/review-notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to save review note.");
  }
  return response.json();
}

export async function listReviewCorpora(
  projectId: string,
  agentDesignId: string,
): Promise<ReviewCorpus[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/review-corpora?agent_design_id=${agentDesignId}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load review corpora.");
  }
  return response.json();
}

export async function createReviewCorpus(
  projectId: string,
  agentDesignId: string,
  name: string,
): Promise<ReviewCorpus> {
  const response = await fetch(`${apiBase}/projects/${projectId}/review-corpora`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent_design_id: agentDesignId,
      name,
      description: "Open-coded evidence selected from EDD and Langfuse traces.",
      source: "mixed",
      status: "active",
    }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to create review corpus.");
  }
  return response.json();
}

export async function listReviewItems(
  projectId: string,
  corpusId: string,
): Promise<ReviewItem[]> {
  const response = await fetch(`${apiBase}/projects/${projectId}/review-items?corpus_id=${corpusId}`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load review items.");
  }
  return response.json();
}

export async function createReviewItem(
  projectId: string,
  payload: {
    corpus_id: string;
    source_kind: "artifact" | "run" | "eval_result" | "trace";
    source_id: string;
    title: string;
    content: string;
    langfuse_ref?: LangfuseObjectRef | null;
    metadata?: Record<string, unknown>;
    status?: string;
  },
): Promise<ReviewItem> {
  const response = await fetch(`${apiBase}/projects/${projectId}/review-items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to add review item.");
  }
  return response.json();
}

export async function listFailureModes(
  projectId: string,
  agentDesignId: string,
): Promise<FailureMode[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/failure-modes?agent_design_id=${agentDesignId}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load failure modes.");
  }
  return response.json();
}

export async function createFailureMode(
  projectId: string,
  agentDesignId: string,
  payload: { name: string; description: string; severity: string; status?: string },
): Promise<FailureMode> {
  const response = await fetch(`${apiBase}/projects/${projectId}/failure-modes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent_design_id: agentDesignId,
      ...payload,
      status: payload.status ?? "candidate",
    }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to create failure mode.");
  }
  return response.json();
}

export async function listReviewAnnotations(
  projectId: string,
  corpusId: string,
): Promise<ReviewAnnotation[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/review-annotations?corpus_id=${corpusId}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load review annotations.");
  }
  return response.json();
}

export async function createReviewAnnotation(
  projectId: string,
  payload: {
    review_item_id: string;
    body: string;
    quote?: string;
    author?: "human" | "agent" | "platform";
    failure_mode_id?: string | null;
    status?: "accepted" | "suggested" | "dismissed";
    metadata?: Record<string, unknown>;
  },
): Promise<ReviewAnnotation> {
  const response = await fetch(`${apiBase}/projects/${projectId}/review-annotations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to save review annotation.");
  }
  return response.json();
}

export async function promoteReviewAnnotation(
  projectId: string,
  annotationId: string,
): Promise<DiscoveryPromotionResult> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/review-annotations/${annotationId}/promote`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ create_failure_packet: true, create_eval_case: true }),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to promote discovery finding.");
  }
  return response.json();
}

export async function updateReviewAnnotation(
  projectId: string,
  annotationId: string,
  payload: { failure_mode_id?: string | null },
): Promise<void> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/review-annotations/${annotationId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to update annotation.");
  }
}

export async function listAgentSuggestions(
  projectId: string,
  corpusId: string,
): Promise<AgentSuggestion[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/agent-suggestions?corpus_id=${corpusId}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load agent suggestions.");
  }
  return response.json();
}

export async function syncLangfuseComments(
  projectId: string,
  corpusId: string,
): Promise<{ imported_count: number; skipped_count: number }> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/review-corpora/${corpusId}/sync-langfuse-comments`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to sync Langfuse comments.");
  }
  return response.json();
}

export async function getReviewSamplingPlan(
  projectId: string,
  corpusId: string,
  createSuggestions = false,
): Promise<ReviewSamplingPlan> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/review-corpora/${corpusId}/sampling-plan?create_suggestions=${createSuggestions}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load sampling plan.");
  }
  return response.json();
}

export async function createAgentSuggestion(
  projectId: string,
  payload: {
    review_item_id: string;
    failure_mode_id?: string | null;
    body: string;
    quote?: string;
    rationale?: string;
    confidence?: number;
    status?: "pending" | "accepted" | "dismissed";
  },
): Promise<AgentSuggestion> {
  const response = await fetch(`${apiBase}/projects/${projectId}/agent-suggestions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to create agent suggestion.");
  }
  return response.json();
}

export async function updateAgentSuggestionStatus(
  projectId: string,
  suggestionId: string,
  status: "accepted" | "dismissed",
): Promise<AgentSuggestion> {
  const response = await fetch(`${apiBase}/projects/${projectId}/agent-suggestions/${suggestionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to update agent suggestion.");
  }
  return response.json();
}

export async function diagnoseFailure(
  projectId: string,
  evalResultId: string,
): Promise<{ failure_mode: string; severity: string; review_note: string; judge_output: string }> {
  const response = await fetch(`${apiBase}/projects/${projectId}/failure-diagnosis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ eval_result_id: evalResultId }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to diagnose failure.");
  }
  return response.json();
}

export async function generateFixProposal(
  projectId: string,
  agentDesignId: string,
  targetVersionId: string,
  failurePackets: FailurePacket[],
  contractId: string,
): Promise<{ proposed_instructions: string; rationale: string }> {
  const response = await fetch(`${apiBase}/projects/${projectId}/fix-proposals/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent_design_id: agentDesignId,
      target_version_id: targetVersionId,
      addressed_failure_packet_ids: failurePackets.map((p) => p.id),
      validation_contract_id: contractId,
    }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to generate fix proposal.");
  }
  return response.json();
}

export async function updateContractRubric(
  projectId: string,
  contractId: string,
  rubric: string,
): Promise<EvalContract> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/eval-contracts/${contractId}/rubric`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rubric }),
    },
  );
  if (!response.ok) throw await responseError(response, "Failed to update rubric.");
  return response.json();
}

export async function createFixProposal(
  projectId: string,
  agentDesignId: string,
  targetVersionId: string,
  failurePackets: FailurePacket[],
  contractId: string,
  proposedInstructions: string,
  rationale: string,
): Promise<FixProposal> {
  const response = await fetch(`${apiBase}/projects/${projectId}/fix-proposals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent_design_id: agentDesignId,
      target_version_id: targetVersionId,
      title: "LLM-generated fix for failed evaluation",
      rationale,
      proposed_changes: [{ surface: "instructions", change: proposedInstructions }],
      addressed_failure_packet_ids: failurePackets.map((p) => p.id),
      validation_contract_ids: [contractId],
    }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to create fix proposal.");
  }
  return response.json();
}

export async function createComparison(
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

export async function listAgentVersions(projectId: string, agentDesignId: string): Promise<AgentVersion[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/agent-designs/${agentDesignId}/versions`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load agent versions.");
  }
  return response.json();
}

export async function listScenarios(projectId: string, agentDesignId: string): Promise<Scenario[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/scenarios?agent_design_id=${agentDesignId}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load scenarios.");
  }
  return response.json();
}

export async function listEvalContracts(projectId: string, agentDesignId: string): Promise<EvalContract[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/eval-contracts?agent_design_id=${agentDesignId}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load eval contracts.");
  }
  return response.json();
}

export async function listRuns(projectId: string, agentDesignId: string): Promise<RunRecord[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/runs?agent_design_id=${agentDesignId}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load runs.");
  }
  return response.json();
}

export async function listGateDefinitions(
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

export async function createGateDefinition(
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

export async function listGateDecisions(
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

export async function createGateDecision(
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

export async function listEvalResults(projectId: string, runId: string): Promise<EvalResult[]> {
  const response = await fetch(`${apiBase}/projects/${projectId}/eval-results?run_id=${runId}`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load eval results.");
  }
  return response.json();
}

export async function updateFixProposal(
  projectId: string,
  fixProposalId: string,
  payload: { rationale?: string; proposed_changes?: Record<string, unknown>[]; status?: string },
): Promise<FixProposal> {
  const response = await fetch(`${apiBase}/projects/${projectId}/fix-proposals/${fixProposalId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to update fix proposal.");
  }
  return response.json();
}

export async function listFixProposals(projectId: string, agentDesignId: string): Promise<FixProposal[]> {
  const response = await fetch(
    `${apiBase}/projects/${projectId}/fix-proposals?agent_design_id=${agentDesignId}`,
  );
  if (!response.ok) {
    throw await responseError(response, "Unable to load fix proposals.");
  }
  return response.json();
}

export async function listComparisons(projectId: string, agentDesignId: string): Promise<Comparison[]> {
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

export async function hydrateEddFlow(projectId: string, agent: AgentDesign): Promise<EddFlowState> {
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
