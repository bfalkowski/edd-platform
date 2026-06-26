import {
  Clock3,
  ExternalLink,
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

type ServiceStatus = {
  id: string;
  name: string;
  status: "online" | "offline" | "configured" | "not_configured";
  configured: boolean;
  url: string | null;
  description: string;
};

type ServiceStatusResponse = {
  services: ServiceStatus[];
  updated_at: string;
};

type ToolDefinition = {
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

type ToolDefinitionCreate = {
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

type EvalMethod = "phrase" | "tool" | "rubric";
type TestShape = "single_turn" | "conversation" | "trace_replay";

type ArtifactRecord = {
  id: string;
  project_id: string;
  artifact_type: string;
  artifact_id: string;
  title: string;
  body: string;
  source: string;
  agent_design_id: string | null;
  external_refs: {
    provider: string;
    ref_type: string;
    external_id: string;
    url: string | null;
    label: string;
    metadata: Record<string, unknown>;
  }[];
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

type OutcomeAgentResponse = NewAgentResponse & {
  version: AgentVersion;
  scenario: Scenario;
  eval_contract: EvalContract;
  draft_tools: ToolDefinition[];
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
  tool_calls: { name: string; input?: string; output: string }[];
  evidence: string[];
  trace_id: string | null;
  trace_url: string | null;
  artifact: ArtifactRecord;
  trace_artifact: ArtifactRecord | null;
  artifact_ids: string[];
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

type ReviewNote = {
  id: string;
  project_id: string;
  target_artifact_id: string;
  body: string;
  author: string;
  metadata: Record<string, unknown>;
  artifact_ids: string[];
  created_at: string;
};

type LangfuseObjectRef = {
  trace_id: string | null;
  observation_id: string | null;
  object_type: "TRACE" | "OBSERVATION";
  url: string | null;
  queue_id: string | null;
  score_ids: string[];
  metadata: Record<string, unknown>;
};

type ReviewCorpus = {
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

type ReviewItem = {
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

type FailureMode = {
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

type ReviewAnnotation = {
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

type AgentSuggestion = {
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
  artifact_ids: string[];
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

type GeneratedDesignSummary = {
  agentId: string;
  artifact: ArtifactRecord;
  version: AgentVersion;
  scenario: Scenario;
  contract: EvalContract;
  draftTools: ToolDefinition[];
  enabledToolNames: string[];
  generatedToolNames: string[];
};

const apiBase = "/api";
const defaultScenarioInput = "What's the weather in Boston today?";
const defaultConversationInput = `Customer: My deployment failed after the release.
Agent: What error are you seeing?
Customer: The rollout says image pull backoff.`;
const defaultTraceReplayInput =
  "Paste the prior trace spans, messages, or evidence that should set up the next agent response.";
const defaultRubricText =
  "A good answer should directly answer the user request, avoid unsupported claims, and ask for missing details only when they are required.";
const defaultConversationRubricText =
  "A good observer output should review the latest customer turn in context, identify that sentiment or escalation risk is worsening, mention the image pull backoff blocker, avoid claiming the issue is fixed, and produce concise downstream-safe observer notes.";
const defaultTraceReplayRubricText =
  "A good answer should use the replayed evidence, preserve important context from the trace, and avoid inventing facts not present in the replay.";
const testShapeLabels: Record<TestShape, string> = {
  single_turn: "Single turn",
  conversation: "Conversation",
  trace_replay: "Trace replay",
};
const testShapeInputLabels: Record<TestShape, string> = {
  single_turn: "Prompt",
  conversation: "Conversation",
  trace_replay: "Replay context",
};
const testShapeInputHelp: Record<TestShape, string> = {
  single_turn: "Test one user request in isolation.",
  conversation: "Include prior messages plus the next user turn.",
  trace_replay: "Start from selected prior spans, messages, or evidence.",
};
function defaultInputForTestShape(shape: TestShape): string {
  if (shape === "conversation") {
    return defaultConversationInput;
  }
  if (shape === "trace_replay") {
    return defaultTraceReplayInput;
  }
  return defaultScenarioInput;
}
function conversationTurnsFromText(input: string): Array<{ speaker: string; text: string }> {
  const matches = Array.from(input.matchAll(/\b(Customer|Agent):\s*/g));
  if (matches.length === 0) {
    return [];
  }
  return matches
    .map((match, index) => {
      const start = (match.index ?? 0) + match[0].length;
      const end = matches[index + 1]?.index ?? input.length;
      return {
        speaker: match[1],
        text: input.slice(start, end).trim(),
      };
    })
    .filter((turn) => turn.text.length > 0);
}
function renderScenarioInput(input: string | undefined) {
  const text = input?.trim();
  if (!text) {
    return null;
  }
  const turns = conversationTurnsFromText(text);
  if (turns.length < 2) {
    return <p className="scenario-test-text">{text}</p>;
  }
  return (
    <div className="scenario-turns">
      {turns.map((turn, index) => (
        <p key={`${turn.speaker}-${index}`} className="scenario-turn">
          <strong>{turn.speaker}:</strong> {turn.text}
        </p>
      ))}
    </div>
  );
}
function defaultRubricForTestShape(shape: TestShape): string {
  if (shape === "conversation") {
    return defaultConversationRubricText;
  }
  if (shape === "trace_replay") {
    return defaultTraceReplayRubricText;
  }
  return defaultRubricText;
}
function isDefaultTestInput(input: string): boolean {
  return [defaultScenarioInput, defaultConversationInput, defaultTraceReplayInput].includes(input);
}
function isDefaultRubricText(rubric: string): boolean {
  return [defaultRubricText, defaultConversationRubricText, defaultTraceReplayRubricText].includes(rubric);
}
function setupContextFromTestShape(shape: TestShape): string {
  return `test_shape:${shape}`;
}
function testShapeFromSetupContext(setupContext?: string): TestShape {
  if (setupContext?.includes("test_shape:conversation")) {
    return "conversation";
  }
  if (setupContext?.includes("test_shape:trace_replay")) {
    return "trace_replay";
  }
  return "single_turn";
}
const defaultToolInputSchema = `{
  "type": "object",
  "properties": {
    "ticket_id": {
      "type": "string",
      "description": "External ticket identifier."
    },
    "customer_since": {
      "type": "string",
      "format": "date",
      "description": "ISO date, for example 2026-06-04."
    },
    "retry_count": {
      "type": "integer",
      "minimum": 0
    },
    "confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    },
    "priority": {
      "type": "string",
      "enum": ["low", "medium", "high"]
    },
    "include_history": {
      "type": "boolean"
    }
  },
  "required": ["ticket_id"]
}`;
const defaultToolOutputSchema = `{
  "type": "object",
  "properties": {
    "summary": {
      "type": "string"
    },
    "status": {
      "type": "string",
      "enum": ["open", "blocked", "resolved"]
    },
    "age_days": {
      "type": "integer"
    },
    "last_updated": {
      "type": "string",
      "format": "date-time"
    },
    "recommended_actions": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": ["summary", "status"]
}`;

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

async function listServices(): Promise<ServiceStatus[]> {
  const response = await fetch(`${apiBase}/services`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load service status.");
  }
  const payload = (await response.json()) as ServiceStatusResponse;
  return payload.services;
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

async function createAgentDesignFromOutcome(
  projectId: string,
  outcome: string,
): Promise<OutcomeAgentResponse> {
  const response = await fetch(`${apiBase}/projects/${projectId}/agent-designs/from-outcome`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ outcome }),
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to draft agent from outcome.");
  }
  return response.json();
}

async function deleteAgentDesign(projectId: string, agentDesignId: string): Promise<void> {
  const response = await fetch(`${apiBase}/projects/${projectId}/agent-designs/${agentDesignId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to delete agent design.");
  }
}

async function updateAgentDesign(
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

async function listToolDefinitions(projectId: string): Promise<ToolDefinition[]> {
  const response = await fetch(`${apiBase}/projects/${projectId}/tools`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load tools.");
  }
  return response.json();
}

async function createToolDefinition(
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

async function updateToolDefinitionStatus(
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

async function updateAgentDesignToolAllowlist(
  projectId: string,
  agentDesignId: string,
  allowedToolNames: string[],
): Promise<AgentDesign> {
  return updateAgentDesign(projectId, agentDesignId, { allowed_tool_names: allowedToolNames });
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

async function createScenario(
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

async function createEvalContract(
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

async function evaluateRun(
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

async function createReviewNote(
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

async function listReviewCorpora(
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

async function createReviewCorpus(
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

async function listReviewItems(
  projectId: string,
  corpusId: string,
): Promise<ReviewItem[]> {
  const response = await fetch(`${apiBase}/projects/${projectId}/review-items?corpus_id=${corpusId}`);
  if (!response.ok) {
    throw await responseError(response, "Unable to load review items.");
  }
  return response.json();
}

async function createReviewItem(
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

async function listFailureModes(
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

async function createFailureMode(
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

async function listReviewAnnotations(
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

async function createReviewAnnotation(
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

async function listAgentSuggestions(
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

async function createAgentSuggestion(
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

async function updateAgentSuggestionStatus(
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

async function updateFixProposal(
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
  const traceRef = artifact.external_refs.find(
    (ref) => ref.provider === "langfuse" && ref.ref_type === "trace" && ref.url,
  );
  if (traceRef?.url) {
    return traceRef.url;
  }
  const match = artifact.body.match(/URL\n(.+)/);
  return match?.[1]?.trim() ?? null;
}

function parseJsonObject(value: string, label: string): Record<string, unknown> {
  const parsed = JSON.parse(value);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON object.`);
  }
  return parsed as Record<string, unknown>;
}

function toolImplementationKey(name: string): string {
  const slug = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return `mock.${slug || "tool"}`;
}

function parseArtifactFields(body: string): { label: string; value: string }[] {
  const fields = body
    .split(/\n{2,}/)
    .map((block) => {
      const [label, ...valueLines] = block.split("\n");
      return {
        label: label.trim(),
        value: valueLines.join("\n").trim(),
      };
    })
    .filter((field) => field.label && field.value);

  return fields.length >= 2 ? fields : [];
}

function artifactRoleLabel(artifactType: string): string {
  const labels: Record<string, string> = {
    AGENT_DESIGN: "Agent design",
    AGENT_VERSION: "Agent version",
    COMPARISON: "Comparison",
    EVAL_CONTRACT: "Success criteria",
    EVAL_RESULT: "Eval result",
    FAILURE_PACKET: "Failure",
    FIX_PROPOSAL: "Fix proposal",
    GATE_DECISION: "Gate decision",
    JUDGE_OUTPUT: "Judge output",
    RUN_RESULT: "Run output",
    SCENARIO: "Scenario",
    TRACE_REF: "Trace",
  };
  return labels[artifactType] ?? artifactType.replaceAll("_", " ").toLowerCase();
}

function relatedEvidenceLabel(artifact: ArtifactRecord | undefined): string {
  if (!artifact) {
    return "Saved evidence";
  }
  if (artifact.artifact_type === "TRACE_REF") {
    return "Trace for this run";
  }
  if (artifact.artifact_type === "AGENT_DESIGN") {
    return "Agent design";
  }
  if (artifact.artifact_type === "RUN_RESULT") {
    return "Run output";
  }
  return artifactRoleLabel(artifact.artifact_type);
}

function proofFlowSummary(flow: EddFlowState): string {
  const parts = [
    flow.scenario ? "scenario" : null,
    flow.contract ? "success criteria" : null,
    flow.baselineVersion ? "original version" : null,
    flow.baselineRun ? "original run" : null,
    flow.baselineEval ? "original check" : null,
    flow.failurePackets.length > 0 ? "failure" : null,
    flow.fixProposal ? "fix" : null,
    flow.candidateVersion ? "candidate version" : null,
    flow.candidateRun ? "candidate run" : null,
    flow.candidateEval ? "candidate check" : null,
    flow.comparison ? "comparison" : null,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : "No proof evidence yet";
}

function proofArtifactIds(flow: EddFlowState): string[] {
  return [
    ...(flow.baselineRun?.artifact_ids ?? []),
    ...(flow.baselineEval?.artifact_ids ?? []),
    ...(flow.failurePackets.flatMap((packet) => packet.evidence_artifact_ids) ?? []),
    ...(flow.fixProposal?.artifact_ids ?? []),
    ...(flow.candidateRun?.artifact_ids ?? []),
    ...(flow.candidateEval?.artifact_ids ?? []),
    ...(flow.comparison?.artifact_ids ?? []),
  ];
}

function proofRunIds(flow: EddFlowState): string[] {
  return [
    flow.baselineRun?.id,
    flow.candidateRun?.id,
  ].filter((id): id is string => Boolean(id));
}

function failurePacketsForEval(flow: EddFlowState, evalResultId?: string): FailurePacket[] {
  if (!evalResultId) {
    return flow.failurePackets;
  }
  return flow.failurePackets.filter((packet) => packet.eval_result_id === evalResultId);
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
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [intent, setIntent] = useState("");
  const [manualCreateOpen, setManualCreateOpen] = useState(false);
  const [testShape, setTestShape] = useState<TestShape>("single_turn");
  const [scenarioInput, setScenarioInput] = useState(defaultScenarioInput);
  const [requiredPhrase, setRequiredPhrase] = useState("");
  const [evalMethod, setEvalMethod] = useState<EvalMethod>("rubric");
  const [rubricText, setRubricText] = useState(defaultRubricText);
  const [requiredToolName, setRequiredToolName] = useState("");
  const [runMode, setRunMode] = useState<"mock" | "live">("mock");
  const [scratchTarget, setScratchTarget] = useState<"agent" | "url">("agent");
  const [scratchUrl, setScratchUrl] = useState("https://example.com");
  const [workspaceTab, setWorkspaceTab] = useState<
    "agent" | "proof" | "error-analysis" | "evidence" | "readiness"
  >("proof");
  const [contextPack, setContextPack] = useState<ContextPack | null>(null);
  const [eddFlow, setEddFlow] = useState<EddFlowState>({ failurePackets: [] });
  const [generatedDesign, setGeneratedDesign] = useState<GeneratedDesignSummary | null>(null);
  const [gates, setGates] = useState<GateDefinition[]>([]);
  const [gateDecisions, setGateDecisions] = useState<GateDecision[]>([]);
  const [reviewArtifact, setReviewArtifact] = useState<ArtifactRecord | null>(null);
  const [reviewLinks, setReviewLinks] = useState<ArtifactLink[]>([]);
  const [analysisNote, setAnalysisNote] = useState<ReviewNote | null>(null);
  const [analysisNoteText, setAnalysisNoteText] = useState("");
  const [analysisFailureMode, setAnalysisFailureMode] = useState("");
  const [analysisSeverity, setAnalysisSeverity] = useState("medium");
  const [reviewCorpora, setReviewCorpora] = useState<ReviewCorpus[]>([]);
  const [reviewItems, setReviewItems] = useState<ReviewItem[]>([]);
  const [reviewAnnotations, setReviewAnnotations] = useState<ReviewAnnotation[]>([]);
  const [failureModes, setFailureModes] = useState<FailureMode[]>([]);
  const [agentSuggestions, setAgentSuggestions] = useState<AgentSuggestion[]>([]);
  const [selectedReviewItemId, setSelectedReviewItemId] = useState<string | null>(null);
  const [openCodeText, setOpenCodeText] = useState("");
  const [newFailureModeName, setNewFailureModeName] = useState("");
  const [newFailureModeDescription, setNewFailureModeDescription] = useState("");
  const [selectedFailureModeId, setSelectedFailureModeId] = useState("");
  const [isSavingAnalysis, setIsSavingAnalysis] = useState(false);
  const [isDiscoveryBusy, setIsDiscoveryBusy] = useState(false);
  const [fixEditText, setFixEditText] = useState("");
  const [isSavingFix, setIsSavingFix] = useState(false);
  const [toolsPanelOpen, setToolsPanelOpen] = useState(false);
  const [scenarioEditorOpen, setScenarioEditorOpen] = useState(false);
  const [toolSearch, setToolSearch] = useState("");
  const [toolFilter, setToolFilter] = useState<"all" | "enabled" | "available" | "draft">("all");
  const [toolComposerOpen, setToolComposerOpen] = useState(false);
  const [scratchPanelOpen, setScratchPanelOpen] = useState(false);
  const [openAgentMenuId, setOpenAgentMenuId] = useState<string | null>(null);
  const [deleteCandidate, setDeleteCandidate] = useState<AgentDesign | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingContext, setIsLoadingContext] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isFlowBusy, setIsFlowBusy] = useState(false);
  const [isGateBusy, setIsGateBusy] = useState(false);
  const [updatingTools, setUpdatingTools] = useState(false);
  const [isDraftingAgent, setIsDraftingAgent] = useState(false);
  const [isSavingAgent, setIsSavingAgent] = useState(false);
  const [evaluatingArtifactId, setEvaluatingArtifactId] = useState<string | null>(null);
  const [activity, setActivity] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scratchActivity, setScratchActivity] = useState<string | null>(null);
  const [scratchError, setScratchError] = useState<string | null>(null);
  const [scratchArtifact, setScratchArtifact] = useState<ArtifactRecord | null>(null);
  const [scratchTraceUrl, setScratchTraceUrl] = useState<string | null>(null);
  const [toolName, setToolName] = useState("");
  const [toolDescription, setToolDescription] = useState("");
  const [toolInputSchema, setToolInputSchema] = useState(defaultToolInputSchema);
  const [toolOutputSchema, setToolOutputSchema] = useState(defaultToolOutputSchema);
  const [toolOutputDescription, setToolOutputDescription] = useState("");
  const [toolMockResponse, setToolMockResponse] = useState("");
  const [agentEditName, setAgentEditName] = useState("");
  const [agentEditIntent, setAgentEditIntent] = useState("");

  useEffect(() => {
    Promise.all([listProjects(), listServices()])
      .then(([projects, serviceItems]) => {
        setServices(serviceItems);
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
  const selectedGeneratedDesign =
    generatedDesign && generatedDesign.agentId === selectedAgent?.id ? generatedDesign : null;
  useEffect(() => {
    setAgentEditName(selectedAgent?.name ?? "");
    setAgentEditIntent(selectedAgent?.intent ?? "");
  }, [selectedAgent]);

  const approvedTools = useMemo(
    () => tools.filter((tool) => tool.status === "approved"),
    [tools],
  );
  const draftTools = useMemo(
    () => tools.filter((tool) => tool.status === "draft"),
    [tools],
  );
  const enabledToolDefinitions = useMemo(() => {
    if (!selectedAgent) {
      return [];
    }
    return approvedTools.filter((tool) => selectedAgent.allowed_tool_names.includes(tool.name));
  }, [approvedTools, selectedAgent]);
  const generatedToolStates = useMemo(() => {
    if (!selectedAgent || !selectedGeneratedDesign) {
      return [];
    }
    return selectedGeneratedDesign.generatedToolNames.map((toolName) => {
      const tool =
        tools.find((item) => item.name === toolName) ??
        selectedGeneratedDesign.draftTools.find((item) => item.name === toolName) ??
        null;
      return {
        name: toolName,
        status: tool?.status ?? "unknown",
        implementationKind: tool?.implementation_kind ?? "unknown",
        enabled: selectedAgent.allowed_tool_names.includes(toolName),
      };
    });
  }, [selectedAgent, selectedGeneratedDesign, tools]);
  useEffect(() => {
    if (evalMethod !== "tool") {
      return;
    }
    if (enabledToolDefinitions.some((tool) => tool.name === requiredToolName)) {
      return;
    }
    setRequiredToolName(enabledToolDefinitions[0]?.name ?? "");
  }, [enabledToolDefinitions, evalMethod, requiredToolName]);

  const toolSearchQuery = toolSearch.trim().toLowerCase();
  const toolMatchesSearch = (tool: ToolDefinition) => {
    if (!toolSearchQuery) {
      return true;
    }
    return [tool.name, tool.description, tool.implementation_kind]
      .join(" ")
      .toLowerCase()
      .includes(toolSearchQuery);
  };
  const filteredApprovedTools = selectedAgent
    ? approvedTools.filter((tool) => {
        const isAllowed = selectedAgent.allowed_tool_names.includes(tool.name);
        if (toolFilter === "draft") {
          return false;
        }
        if (toolFilter === "enabled" && !isAllowed) {
          return false;
        }
        if (toolFilter === "available" && isAllowed) {
          return false;
        }
        return toolMatchesSearch(tool);
      })
    : [];
  const filteredDraftTools =
    toolFilter === "enabled" || toolFilter === "available"
      ? []
      : draftTools.filter(toolMatchesSearch);
  const agentProfileChanged =
    Boolean(selectedAgent) &&
    (agentEditName.trim() !== selectedAgent?.name || agentEditIntent.trim() !== selectedAgent?.intent);
  const latestGate = gates[0] ?? null;
  const latestGateDecision = gateDecisions[0] ?? null;
  const artifactsById = useMemo(() => {
    return new Map((contextPack?.artifacts ?? []).map((artifact) => [artifact.id, artifact]));
  }, [contextPack]);
  const artifactByRecordKey = useMemo(() => {
    return new Map(
      (contextPack?.artifacts ?? []).map((artifact) => [
        `${artifact.artifact_type}:${artifact.artifact_id}`,
        artifact,
      ]),
    );
  }, [contextPack]);
  const visibleArtifacts = contextPack?.artifacts ?? [];
  const currentProofArtifactIds = proofArtifactIds(eddFlow);
  const currentProofRunIdSet = new Set(proofRunIds(eddFlow));
  const currentProofArtifacts = currentProofArtifactIds
    .map((artifactId) => artifactsById.get(artifactId))
    .filter((artifact): artifact is ArtifactRecord => Boolean(artifact));
  const currentTraceArtifacts = visibleArtifacts.filter((artifact) => {
    if (artifact.artifact_type !== "TRACE_REF") {
      return false;
    }
    const runMatch = artifact.body.match(/Run\n(.+)/);
    return runMatch ? currentProofRunIdSet.has(runMatch[1].trim()) : false;
  });
  const evidenceArtifacts = [
    ...currentTraceArtifacts,
    ...currentProofArtifacts,
    ...visibleArtifacts.filter((artifact) => artifact.artifact_type === "TRACE_REF"),
    ...visibleArtifacts.filter((artifact) => artifact.artifact_type !== "TRACE_REF"),
  ].filter(
    (artifact, index, artifacts) =>
      artifacts.findIndex((candidate) => candidate.id === artifact.id) === index,
  );
  const activeReviewCorpus = reviewCorpora[0] ?? null;
  const selectedReviewItem =
    reviewItems.find((item) => item.id === selectedReviewItemId) ?? reviewItems[0] ?? null;
  const selectedReviewAnnotations = selectedReviewItem
    ? reviewAnnotations.filter((annotation) => annotation.review_item_id === selectedReviewItem.id)
    : [];
  const pendingSuggestions = selectedReviewItem
    ? agentSuggestions.filter(
        (suggestion) => suggestion.review_item_id === selectedReviewItem.id && suggestion.status === "pending",
      )
    : [];
  const reviewedItemCount = reviewItems.filter((item) => item.status === "reviewed").length;
  const acceptedAnnotationCount = reviewAnnotations.filter(
    (annotation) => annotation.status === "accepted",
  ).length;
  const selectedReviewTraceUrl = selectedReviewItem?.langfuse_ref?.url ?? null;
  const reviewTraceUrl = reviewArtifact ? traceUrlFromArtifact(reviewArtifact) : null;
  const reviewFields = reviewArtifact ? parseArtifactFields(reviewArtifact.body) : [];
  const generatedVersionArtifact = selectedGeneratedDesign
    ? artifactByRecordKey.get(`AGENT_VERSION:${selectedGeneratedDesign.version.id}`)
    : undefined;
  const generatedScenarioArtifact = selectedGeneratedDesign
    ? artifactByRecordKey.get(`SCENARIO:${selectedGeneratedDesign.scenario.id}`)
    : undefined;
  const generatedContractArtifact = selectedGeneratedDesign
    ? artifactByRecordKey.get(`EVAL_CONTRACT:${selectedGeneratedDesign.contract.id}`)
    : undefined;
  const baselineRunArtifact = eddFlow.baselineRun?.artifact_ids[0]
    ? artifactsById.get(eddFlow.baselineRun.artifact_ids[0])
    : undefined;
  const baselineEvalArtifact = eddFlow.baselineEval?.artifact_ids[0]
    ? artifactsById.get(eddFlow.baselineEval.artifact_ids[0])
    : undefined;
  const failedBaselineChecks =
    eddFlow.baselineEval?.checks.filter((check) => !check.passed) ?? [];
  const baselineTraceArtifact = currentTraceArtifacts.find((artifact) =>
    eddFlow.baselineRun ? artifact.body.includes(eddFlow.baselineRun.id) : false,
  );
  const baselineTraceUrl = baselineTraceArtifact ? traceUrlFromArtifact(baselineTraceArtifact) : null;
  const analysisTargetArtifactId =
    baselineTraceArtifact?.id ??
    eddFlow.baselineEval?.artifact_ids[0] ??
    eddFlow.baselineRun?.artifact_ids[0] ??
    "";
  const reviewFixProposal =
    reviewArtifact?.artifact_type === "FIX_PROPOSAL" && eddFlow.fixProposal?.id === reviewArtifact.artifact_id
      ? eddFlow.fixProposal
      : null;
  const connectedArtifacts = reviewArtifact
    ? reviewLinks.reduce<
        {
          artifact: ArtifactRecord;
          link: ArtifactLink;
          relationshipTypes: string[];
        }[]
      >((items, link) => {
        const relatedId =
          link.source_artifact_id === reviewArtifact.id
            ? link.target_artifact_id
            : link.source_artifact_id;
        const relatedArtifact = artifactsById.get(relatedId);
        if (!relatedArtifact) {
          return items;
        }
        const existing = items.find((item) => item.artifact?.id === relatedId);
        if (existing) {
          existing.relationshipTypes.push(link.relationship_type);
          return items;
        }
        items.push({
          artifact: relatedArtifact,
          link,
          relationshipTypes: [link.relationship_type],
        });
        return items;
      }, [])
    : [];
  useEffect(() => {
    const firstChange = reviewFixProposal?.proposed_changes[0]?.change;
    setFixEditText(typeof firstChange === "string" ? firstChange : "");
  }, [reviewFixProposal?.id]);

  const savedExpectedPhrase = eddFlow.contract?.checks.find((check) => check.value)?.value ?? "";
  const savedRequiredTool = eddFlow.contract?.checks.find((check) => check.tool)?.tool ?? "";
  const savedScenarioInput = eddFlow.scenario?.input ?? "";
  const canDefineTest =
    !isFlowBusy &&
    Boolean(scenarioInput.trim()) &&
    ((evalMethod === "phrase" && Boolean(requiredPhrase.trim())) ||
      (evalMethod === "tool" && Boolean(requiredToolName)) ||
      (evalMethod === "rubric" && Boolean(rubricText.trim())));
  const testOutOfSync = Boolean(
    eddFlow.contract &&
      (((evalMethod === "phrase" &&
        requiredPhrase.trim() &&
        savedExpectedPhrase &&
        savedExpectedPhrase !== requiredPhrase.trim()) ||
        (evalMethod === "tool" &&
          requiredToolName &&
          savedRequiredTool &&
          savedRequiredTool !== requiredToolName) ||
        (evalMethod === "rubric" &&
          rubricText.trim() &&
          savedExpectedPhrase &&
          savedExpectedPhrase !== rubricText.trim())) ||
        (scenarioInput.trim() &&
          savedScenarioInput &&
          savedScenarioInput !== scenarioInput.trim())),
  );

  async function loadDiscoveryState(
    projectId: string,
    agent: AgentDesign | null,
  ): Promise<{
    corpora: ReviewCorpus[];
    items: ReviewItem[];
    annotations: ReviewAnnotation[];
    modes: FailureMode[];
    suggestions: AgentSuggestion[];
  }> {
    if (!agent) {
      return { corpora: [], items: [], annotations: [], modes: [], suggestions: [] };
    }
    const [corpora, modes] = await Promise.all([
      listReviewCorpora(projectId, agent.id),
      listFailureModes(projectId, agent.id),
    ]);
    const corpus = corpora[0];
    if (!corpus) {
      return { corpora, items: [], annotations: [], modes, suggestions: [] };
    }
    const [items, annotations, suggestions] = await Promise.all([
      listReviewItems(projectId, corpus.id),
      listReviewAnnotations(projectId, corpus.id),
      listAgentSuggestions(projectId, corpus.id),
    ]);
    return { corpora, items, annotations, modes, suggestions };
  }

  function applyDiscoveryState(state: {
    corpora: ReviewCorpus[];
    items: ReviewItem[];
    annotations: ReviewAnnotation[];
    modes: FailureMode[];
    suggestions: AgentSuggestion[];
  }) {
    setReviewCorpora(state.corpora);
    setReviewItems(state.items);
    setReviewAnnotations(state.annotations);
    setFailureModes(state.modes);
    setAgentSuggestions(state.suggestions);
    setSelectedReviewItemId((currentId) =>
      currentId && state.items.some((item) => item.id === currentId)
        ? currentId
        : state.items[0]?.id ?? null,
    );
  }

  async function refreshDiscoveryState() {
    if (!project) {
      applyDiscoveryState({ corpora: [], items: [], annotations: [], modes: [], suggestions: [] });
      return;
    }
    const state = await loadDiscoveryState(project.id, selectedAgent);
    applyDiscoveryState(state);
  }

  useEffect(() => {
    if (!project) {
      setContextPack(null);
      setGates([]);
      setGateDecisions([]);
      return;
    }
    let isCurrent = true;
    setEddFlow({ failurePackets: [] });
    setAnalysisNote(null);
    setAnalysisNoteText("");
    setAnalysisFailureMode("");
    setAnalysisSeverity("medium");
    setOpenCodeText("");
    setNewFailureModeName("");
    setNewFailureModeDescription("");
    setSelectedFailureModeId("");
    setIsLoadingContext(true);
    Promise.all([
      buildContextPack(project.id, selectedId ?? undefined),
      selectedAgent
        ? hydrateEddFlow(project.id, selectedAgent)
        : Promise.resolve({ failurePackets: [] } as EddFlowState),
      selectedAgent ? listGateDefinitions(project.id, selectedAgent.id) : Promise.resolve([]),
      selectedAgent ? listGateDecisions(project.id, selectedAgent.id) : Promise.resolve([]),
      loadDiscoveryState(project.id, selectedAgent),
    ])
      .then(([pack, flow, loadedGates, loadedGateDecisions, discoveryState]) => {
        if (!isCurrent) {
          return;
        }
        setContextPack(pack);
        setEddFlow(flow);
        setGates(loadedGates);
        setGateDecisions(loadedGateDecisions);
        applyDiscoveryState(discoveryState);
        setScenarioInput(flow.scenario?.input ?? defaultScenarioInput);
        setTestShape(testShapeFromSetupContext(flow.scenario?.setup_context));
        const rubric = flow.contract?.checks.find((check) => check.type === "rubric_judge")?.value;
        const tool = flow.contract?.checks.find((check) => check.tool)?.tool;
        const phrase = flow.contract?.checks.find((check) => check.type === "output_contains")?.value;
        const inferredPhrase = selectedAgent ? inferExpectedResponse(selectedAgent) : "";
        if (rubric) {
          setEvalMethod("rubric");
          setRubricText(rubric);
        } else if (tool) {
          setEvalMethod("tool");
          setRequiredToolName(tool);
        } else if (phrase && phrase !== "bounded resolution") {
          setEvalMethod("phrase");
          setRequiredPhrase(phrase);
        } else if (inferredPhrase) {
          setEvalMethod("phrase");
          setRequiredPhrase(inferredPhrase);
        } else if (selectedAgent) {
          setEvalMethod("rubric");
          setRubricText(defaultRubricText);
          setRequiredPhrase("");
          setRequiredToolName("");
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
      setGeneratedDesign(null);
      setReviewArtifact(null);
      setReviewLinks([]);
      setToolsPanelOpen(false);
      setScratchPanelOpen(false);
      setScratchActivity(null);
      setScratchError(null);
      setScratchArtifact(null);
      setScratchTraceUrl(null);
      setWorkspaceTab("proof");
      setName("");
      setIntent("");
      setManualCreateOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create agent design.");
    }
  }

  async function handleDraftFromOutcome() {
    setError(null);
    setActivity(null);
    setIsDraftingAgent(true);

    try {
      if (!project) {
        throw new Error("No active project is available.");
      }
      const outcome = intent.trim();
      const drafted = await createAgentDesignFromOutcome(project.id, outcome);
      setAgents((items) => [drafted.agent, ...items]);
      setTools((items) => {
        const draftedById = new Map(drafted.draft_tools.map((tool) => [tool.id, tool]));
        return [
          ...drafted.draft_tools,
          ...items.filter((tool) => !draftedById.has(tool.id)),
        ];
      });
      setSelectedId(drafted.agent.id);
      setReviewArtifact(drafted.artifact);
      setReviewLinks([]);
      setToolsPanelOpen(false);
      setScratchPanelOpen(false);
      setScratchActivity(null);
      setScratchError(null);
      setScratchArtifact(null);
      setScratchTraceUrl(null);
      setWorkspaceTab("proof");
      setScenarioInput(drafted.scenario.input);
      setTestShape(testShapeFromSetupContext(drafted.scenario.setup_context));
      const draftedTool = drafted.eval_contract.checks.find((check) => check.tool)?.tool;
      const draftedRubric = drafted.eval_contract.checks.find(
        (check) => check.type === "rubric_judge",
      )?.value;
      if (draftedTool) {
        setEvalMethod("tool");
        setRequiredToolName(draftedTool);
      } else if (draftedRubric) {
        setEvalMethod("rubric");
        setRubricText(draftedRubric);
      }
      setEddFlow({
        baselineVersion: drafted.version,
        scenario: drafted.scenario,
        contract: drafted.eval_contract,
        failurePackets: [],
      });
      setGeneratedDesign({
        agentId: drafted.agent.id,
        artifact: drafted.artifact,
        version: drafted.version,
        scenario: drafted.scenario,
        contract: drafted.eval_contract,
        draftTools: drafted.draft_tools,
        enabledToolNames: drafted.agent.allowed_tool_names,
        generatedToolNames: Array.from(
          new Set([
            ...drafted.agent.allowed_tool_names,
            ...drafted.draft_tools.map((tool) => tool.name),
          ]),
        ),
      });
      setName("");
      setIntent("");
      setManualCreateOpen(false);
      const draftToolLabel =
        drafted.draft_tools.length === 1 ? "1 needed tool" : `${drafted.draft_tools.length} needed tools`;
      setActivity(
        drafted.draft_tools.length
          ? `Drafted v0, scenario, eval contract, and ${draftToolLabel}.`
          : "Drafted v0, scenario, and eval contract from the requested outcome.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to draft agent from outcome.");
    } finally {
      setIsDraftingAgent(false);
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
        setGeneratedDesign(null);
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
        setWorkspaceTab("proof");
      }
      setDeleteCandidate(null);
      setOpenAgentMenuId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete agent design.");
    }
  }

  async function handleSaveAgentProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!project || !selectedAgent) {
      return;
    }
    setError(null);
    setActivity(null);
    setIsSavingAgent(true);
    try {
      const updated = await updateAgentDesign(project.id, selectedAgent.id, {
        name: agentEditName.trim(),
        intent: agentEditIntent.trim(),
      });
      setAgents((items) => items.map((agent) => (agent.id === updated.id ? updated : agent)));
      setActivity("Agent profile saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update agent design.");
    } finally {
      setIsSavingAgent(false);
    }
  }

  function openScenarioEditor() {
    setScenarioEditorOpen(true);
    setToolsPanelOpen(false);
    setReviewArtifact(null);
    setReviewLinks([]);
    setScratchPanelOpen(false);
  }

  function openNewScenarioEditor() {
    setTestShape("single_turn");
    setScenarioInput(defaultScenarioInput);
    setRequiredPhrase("");
    setEvalMethod("rubric");
    setRequiredToolName(enabledToolDefinitions[0]?.name ?? "");
    setRubricText(defaultRubricText);
    openScenarioEditor();
  }

  function handleTestShapeChange(nextShape: TestShape) {
    if (testShape === nextShape) {
      return;
    }
    if (isDefaultTestInput(scenarioInput)) {
      setScenarioInput(defaultInputForTestShape(nextShape));
    }
    if (isDefaultRubricText(rubricText)) {
      setRubricText(defaultRubricForTestShape(nextShape));
    }
    setTestShape(nextShape);
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

  async function handleApproveAndEnableTool(tool: ToolDefinition) {
    if (!project || !selectedAgent) {
      return;
    }
    setError(null);
    setUpdatingTools(true);
    try {
      const approved = await updateToolDefinitionStatus(project.id, tool.id, "approved");
      setTools((items) =>
        items.map((item) => (item.id === approved.id ? approved : item)),
      );
      const allowed = Array.from(new Set([...selectedAgent.allowed_tool_names, approved.name]));
      const updatedAgent = await updateAgentDesignToolAllowlist(
        project.id,
        selectedAgent.id,
        allowed,
      );
      setAgents((items) =>
        items.map((agent) => (agent.id === updatedAgent.id ? updatedAgent : agent)),
      );
      setContextPack(await buildContextPack(project.id, updatedAgent.id));
      setActivity(`Approved and assigned ${approved.name}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to approve tool.");
    } finally {
      setUpdatingTools(false);
    }
  }

  async function handleCreateTool(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!project) {
      return;
    }
    setError(null);
    setUpdatingTools(true);
    try {
      const inputSchema = parseJsonObject(toolInputSchema, "Input schema");
      const outputSchema = toolOutputSchema.trim()
        ? parseJsonObject(toolOutputSchema, "Output schema")
        : null;
      const tool = await createToolDefinition(project.id, {
        name: toolName.trim(),
        description: toolDescription.trim(),
        input_schema: inputSchema,
        output_schema: outputSchema,
        output_description: toolOutputDescription.trim(),
        implementation_kind: "mock",
        implementation_key: toolImplementationKey(toolName),
        config_schema: {"type": "object", "properties": {}},
        mock_response: toolMockResponse.trim() || null,
      });
      setTools((items) => [tool, ...items.filter((item) => item.id !== tool.id)]);
      setToolName("");
      setToolDescription("");
      setToolInputSchema(defaultToolInputSchema);
      setToolOutputSchema(defaultToolOutputSchema);
      setToolOutputDescription("");
      setToolMockResponse("");
      setActivity(`Draft tool created: ${tool.name}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create tool definition.");
    } finally {
      setUpdatingTools(false);
    }
  }

  async function handleRunAdHocScenario() {
    if (!project || !selectedAgent) {
      return;
    }
    setActivity(null);
    setError(null);
    setScratchError(null);
    if (scratchTarget === "url" && !scratchUrl.trim()) {
      setScratchError("Enter a URL to call.");
      return;
    }
    setScratchActivity(
      scratchTarget === "url"
        ? "Calling URL directly."
        : runMode === "live"
          ? "Running live ad hoc scenario."
          : "Running mock ad hoc scenario.",
    );
    setScratchArtifact(null);
    setScratchTraceUrl(null);
    setIsRunning(true);
    try {
      const run = await runAgentDesign(
        project.id,
        selectedAgent.id,
        scenarioInput.trim(),
        runMode,
        scratchTarget,
        scratchTarget === "url" ? scratchUrl.trim() : undefined,
      );
      setActivity("Ad hoc evidence saved.");
      setContextPack((pack) =>
        pack
          ? {
              ...pack,
              artifacts: [
                run.artifact,
                ...(run.trace_artifact ? [run.trace_artifact] : []),
                ...pack.artifacts,
              ],
            }
          : pack,
      );
      setScratchArtifact(run.artifact);
      setScratchTraceUrl(run.trace_url);
      setScratchActivity("Ad hoc run saved.");
    } catch (err) {
      setScratchError(err instanceof Error ? err.message : "Unable to run ad hoc scenario.");
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


  async function handleSaveFixProposal() {
    if (!project || !reviewFixProposal) {
      return;
    }
    setError(null);
    setIsSavingFix(true);
    try {
      const updated = await updateFixProposal(project.id, reviewFixProposal.id, {
        proposed_changes: [
          {
            surface: "instructions",
            change: fixEditText.trim(),
          },
        ],
      });
      setEddFlow((flow) => ({ ...flow, fixProposal: updated }));
      setActivity("Fix proposal updated.");
      await refreshContext();
      await handleReviewArtifact(updated.artifact_ids[0]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update fix proposal.");
    } finally {
      setIsSavingFix(false);
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
      setScenarioEditorOpen(false);
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

  async function ensureReviewCorpus(): Promise<ReviewCorpus> {
    if (!project || !selectedAgent) {
      throw new Error("Select an agent before creating a review corpus.");
    }
    if (activeReviewCorpus) {
      return activeReviewCorpus;
    }
    return createReviewCorpus(project.id, selectedAgent.id, `${selectedAgent.name} review corpus`);
  }

  async function handleCreateReviewCorpus() {
    if (!project || !selectedAgent) {
      return;
    }
    setError(null);
    setActivity("Creating review corpus.");
    setIsDiscoveryBusy(true);
    try {
      await createReviewCorpus(project.id, selectedAgent.id, `${selectedAgent.name} review corpus`);
      await refreshDiscoveryState();
      await refreshContext();
      setActivity("Review corpus created.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create review corpus.");
      setActivity(null);
    } finally {
      setIsDiscoveryBusy(false);
    }
  }

  async function handleAddCurrentEvidenceToCorpus() {
    if (!project || !selectedAgent) {
      return;
    }
    const reviewableArtifacts = evidenceArtifacts.filter(
      (artifact) => artifact.agent_design_id === selectedAgent.id,
    );
    if (reviewableArtifacts.length === 0) {
      setError("Run or evaluate the agent before adding evidence to the review corpus.");
      return;
    }
    setError(null);
    setActivity("Adding evidence to the review corpus.");
    setIsDiscoveryBusy(true);
    try {
      const corpus = await ensureReviewCorpus();
      const existingSourceIds = new Set(reviewItems.map((item) => item.source_id));
      const nextArtifacts = reviewableArtifacts
        .filter((artifact) => !existingSourceIds.has(artifact.id))
        .slice(0, 8);
      await Promise.all(
        nextArtifacts.map((artifact) =>
          createReviewItem(project.id, {
            corpus_id: corpus.id,
            source_kind: "artifact",
            source_id: artifact.id,
            title: artifact.title,
            content: artifact.body,
            langfuse_ref: traceUrlFromArtifact(artifact)
              ? {
                  trace_id: artifact.external_refs.find((ref) => ref.ref_type === "trace")?.external_id ?? null,
                  observation_id: null,
                  object_type: "TRACE",
                  url: traceUrlFromArtifact(artifact),
                  queue_id: null,
                  score_ids: [],
                  metadata: { artifact_type: artifact.artifact_type },
                }
              : null,
            metadata: { artifact_type: artifact.artifact_type },
          }),
        ),
      );
      await refreshDiscoveryState();
      setActivity(
        nextArtifacts.length > 0
          ? `Added ${nextArtifacts.length} evidence item${nextArtifacts.length === 1 ? "" : "s"}.`
          : "Current evidence is already in the review corpus.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to add evidence to corpus.");
      setActivity(null);
    } finally {
      setIsDiscoveryBusy(false);
    }
  }

  async function handleSaveOpenCodeAnnotation() {
    if (!project || !selectedReviewItem) {
      return;
    }
    if (!openCodeText.trim()) {
      setError("Write an open-code note before saving.");
      return;
    }
    setError(null);
    setActivity("Saving open-code note.");
    setIsDiscoveryBusy(true);
    try {
      let failureModeId = selectedFailureModeId || null;
      if (!failureModeId && newFailureModeName.trim()) {
        if (!selectedAgent) {
          throw new Error("Select an agent before creating a failure mode.");
        }
        const mode = await createFailureMode(project.id, selectedAgent.id, {
          name: newFailureModeName.trim(),
          description:
            newFailureModeDescription.trim() ||
            `Open-coded from review item: ${selectedReviewItem.title}`,
          severity: "medium",
        });
        failureModeId = mode.id;
      }
      await createReviewAnnotation(project.id, {
        review_item_id: selectedReviewItem.id,
        body: openCodeText.trim(),
        author: "human",
        failure_mode_id: failureModeId,
        status: "accepted",
        metadata: { source: "error_analysis_tab" },
      });
      setOpenCodeText("");
      setNewFailureModeName("");
      setNewFailureModeDescription("");
      setSelectedFailureModeId("");
      await refreshDiscoveryState();
      await refreshContext();
      setActivity("Open-code note saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save open-code note.");
      setActivity(null);
    } finally {
      setIsDiscoveryBusy(false);
    }
  }

  async function handleCreateSuggestion() {
    if (!project || !selectedReviewItem) {
      return;
    }
    setError(null);
    setActivity("Creating suggestion.");
    setIsDiscoveryBusy(true);
    try {
      const mode = failureModes[0] ?? null;
      await createAgentSuggestion(project.id, {
        review_item_id: selectedReviewItem.id,
        failure_mode_id: mode?.id ?? null,
        body: mode
          ? `This item may fit ${mode.name}.`
          : "This item may contain a recurring failure pattern.",
        rationale: selectedReviewItem.content.slice(0, 180) || "Suggested from the selected review item.",
        confidence: mode ? 0.7 : 0.45,
      });
      await refreshDiscoveryState();
      setActivity("Suggestion created.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create suggestion.");
      setActivity(null);
    } finally {
      setIsDiscoveryBusy(false);
    }
  }

  async function handleResolveSuggestion(suggestion: AgentSuggestion, status: "accepted" | "dismissed") {
    if (!project) {
      return;
    }
    setError(null);
    setIsDiscoveryBusy(true);
    try {
      await updateAgentSuggestionStatus(project.id, suggestion.id, status);
      if (status === "accepted") {
        await createReviewAnnotation(project.id, {
          review_item_id: suggestion.review_item_id,
          body: suggestion.body,
          quote: suggestion.quote,
          author: "agent",
          failure_mode_id: suggestion.failure_mode_id,
          status: "suggested",
          metadata: { suggestion_id: suggestion.id, accepted_by: "human" },
        });
      }
      await refreshDiscoveryState();
      setActivity(status === "accepted" ? "Suggestion accepted." : "Suggestion dismissed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update suggestion.");
      setActivity(null);
    } finally {
      setIsDiscoveryBusy(false);
    }
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
    if (evalMethod === "phrase" && !requiredPhrase.trim()) {
      setError("Add the required phrase before defining the test.");
      return;
    }
    if (evalMethod === "tool" && !requiredToolName) {
      setError("Enable a tool on the Agent tab before defining a tool behavior test.");
      return;
    }
    if (evalMethod === "rubric" && !rubricText.trim()) {
      setError("Add a rubric before defining the test.");
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
      const scenario = await createScenario(project.id, selectedAgent.id, scenarioInput.trim(), testShape);
      const contract = await createEvalContract(
        project.id,
        selectedAgent.id,
        scenario.id,
        {
          method: evalMethod,
          requiredPhrase: requiredPhrase.trim(),
          requiredToolName,
          rubric: rubricText.trim(),
        },
      );
      setEddFlow({ baselineVersion, scenario, contract, failurePackets: [] });
      setAnalysisNote(null);
      setAnalysisNoteText("");
      setAnalysisFailureMode("");
      setAnalysisSeverity("medium");
      setActivity("Test is ready. Run the current version next.");
      setScenarioEditorOpen(false);
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
    setActivity(`Running ${eddFlow.baselineVersion.version_label}.`);
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
      setActivity(`${eddFlow.baselineVersion.version_label} answer saved.`);
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
    setActivity("Checking the current answer.");
    setIsFlowBusy(true);
    try {
      const baselineEval = await evaluateRun(project.id, eddFlow.baselineRun.id, currentJudgeMode);
      const failurePackets = await listFailurePackets(project.id, selectedAgent.id);
      setEddFlow((flow) => ({ ...flow, baselineEval, failurePackets }));
      setActivity(
        baselineEval.passed ? "Current answer passed." : "Current answer failed; evidence saved.",
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

  async function handleSaveAnalysisNote() {
    if (!project || !eddFlow.baselineEval || !analysisTargetArtifactId) {
      return;
    }
    if (!analysisNoteText.trim()) {
      setError("Add a brief failure note before proposing a fix.");
      return;
    }
    setError(null);
    setActivity("Saving failure analysis.");
    setIsSavingAnalysis(true);
    try {
      const note = await createReviewNote(project.id, {
        target_artifact_id: analysisTargetArtifactId,
        body: analysisNoteText.trim(),
        author: "platform",
        metadata: {
          failure_mode: analysisFailureMode.trim(),
          severity: analysisSeverity,
          eval_result_id: eddFlow.baselineEval.id,
          failed_check_ids: failedBaselineChecks.map((check) => check.check_id),
        },
      });
      setAnalysisNote(note);
      setActivity("Failure analysis saved.");
      await refreshContext();
      await reviewFirstArtifact(note.artifact_ids);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save failure analysis.");
      setActivity(null);
    } finally {
      setIsSavingAnalysis(false);
    }
  }

  async function handleCreateFixProposal() {
    const currentFailurePackets = failurePacketsForEval(eddFlow, eddFlow.baselineEval?.id);
    if (
      !project ||
      !selectedAgent ||
      !eddFlow.baselineVersion ||
      !eddFlow.contract ||
      currentFailurePackets.length === 0
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
        currentFailurePackets,
        eddFlow.contract.id,
        requiredPhrase.trim(),
      );
      setEddFlow((flow) => ({ ...flow, fixProposal }));
      setActivity("Fix proposal linked to failure evidence.");
      await refreshContext();
      await reviewFirstArtifact(fixProposal.artifact_ids);
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
    setActivity("Creating the next version.");
    setIsFlowBusy(true);
    try {
      const candidateVersion = await createAgentVersion(project.id, selectedAgent.id, {
        parent_version_id: eddFlow.baselineVersion.id,
        source_fix_proposal_id: eddFlow.fixProposal.id,
        instructions: candidateInstructions(requiredPhrase),
        status: "candidate",
      });
      setEddFlow((flow) => ({ ...flow, candidateVersion }));
      setActivity(`${candidateVersion.version_label} is ready to run.`);
      await refreshContext();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create next version.");
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
    setActivity(`Running ${eddFlow.candidateVersion.version_label}.`);
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
      setActivity(`${eddFlow.candidateVersion.version_label} answer saved.`);
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
    setActivity("Checking the new answer.");
    setIsFlowBusy(true);
    try {
      const candidateEval = await evaluateRun(project.id, eddFlow.candidateRun.id, currentJudgeMode);
      setEddFlow((flow) => ({ ...flow, candidateEval }));
      setActivity(candidateEval.passed ? "New version passed." : "New version still fails.");
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
    setActivity("Comparing version evidence.");
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

  async function handleContinueImprovement() {
    if (!eddFlow.candidateVersion || !eddFlow.candidateRun || !eddFlow.candidateEval) {
      return;
    }
    const nextFailurePackets = failurePacketsForEval(eddFlow, eddFlow.candidateEval.id);
    setEddFlow((flow) => ({
      baselineVersion: flow.candidateVersion,
      scenario: flow.scenario,
      contract: flow.contract,
      baselineRun: flow.candidateRun,
      baselineEval: flow.candidateEval,
      failurePackets: nextFailurePackets,
    }));
    setAnalysisNote(null);
    setAnalysisNoteText("");
    setAnalysisFailureMode("");
    setAnalysisSeverity("medium");
    setActivity(`Continuing from ${eddFlow.candidateVersion.version_label}.`);
    setReviewArtifact(null);
    setReviewLinks([]);
  }

  const baselinePassed = eddFlow.baselineEval?.passed === true;
  const improvementNeeded = eddFlow.baselineEval?.passed === false;
  const showFailureAnalysis = improvementNeeded && Boolean(eddFlow.baselineEval);
  const showNextActionPanel = Boolean(eddFlow.contract) && !(showFailureAnalysis && !analysisNote);
  const baselineLabel = eddFlow.baselineVersion?.version_label ?? "current";
  const activeEvalLabel =
    evalMethod === "phrase" ? "Exact text" : evalMethod === "tool" ? "Tool use" : "Rubric judge";
  const activeEvalSummary =
    evalMethod === "phrase"
      ? requiredPhrase || "No phrase set"
      : evalMethod === "tool"
        ? requiredToolName || "No tool selected"
        : rubricText || "No rubric set";
  const currentJudgeMode: "deterministic" | "live" =
    evalMethod === "rubric" ? "live" : "deterministic";
  const displayedRunMode = eddFlow.baselineRun?.mode ?? runMode;
  const displayedJudgeMode = eddFlow.baselineEval?.mode ?? currentJudgeMode;
  const hasSavedScenarioTest = Boolean(eddFlow.scenario && eddFlow.contract);
  const savedTestShape = testShapeFromSetupContext(eddFlow.scenario?.setup_context);
  const savedEvalCheck = eddFlow.contract?.checks[0];
  const savedContractUsesRubric =
    eddFlow.contract?.checks.some((check) => check.type === "rubric_judge") ?? false;
  const savedEvalLabel = savedEvalCheck
    ? savedEvalCheck.type === "rubric_judge"
      ? "Rubric judge"
      : savedEvalCheck.tool
        ? "Tool use"
        : "Exact text"
    : "";
  const savedEvalSummary =
    savedEvalCheck?.type === "rubric_judge"
      ? savedEvalCheck.value || "No rubric set"
      : savedEvalCheck?.tool
        ? savedEvalCheck.tool
        : savedEvalCheck?.value || "No criterion set";
  const deterministicRubricOnlyFailure = Boolean(
    eddFlow.baselineEval?.mode === "deterministic" &&
      savedContractUsesRubric &&
      failedBaselineChecks.length > 0 &&
      failedBaselineChecks.every(
        (check) =>
          check.check_type === "rubric_judge" ||
          check.check_id.toLowerCase().includes("rubric"),
      ),
  );
  const currentLoopAction = (() => {
    if (!eddFlow.contract) {
      return {
        eyebrow: "Next action",
        title: "Create a test case",
        detail: "Choose an input shape and judge method before running the agent.",
        label: "New test",
        onClick: openNewScenarioEditor,
        disabled: isFlowBusy,
      };
    }
    if (testOutOfSync) {
      return {
        eyebrow: "Next action",
        title: "Update the test",
        detail: "The saved test does not match the scenario or eval method shown above.",
        label: "Edit test",
        onClick: openScenarioEditor,
        disabled: isFlowBusy,
      };
    }
    if (!eddFlow.baselineRun) {
      return {
        eyebrow: selectedGeneratedDesign ? "Generated test ready" : "Next action",
        title: selectedGeneratedDesign ? `Run generated ${baselineLabel}` : `Run ${baselineLabel}`,
        detail: selectedGeneratedDesign
          ? "Run the generated first version against the generated scenario and success criteria."
          : "Capture how the current instructions answer the scenario.",
        label: selectedGeneratedDesign ? `Run ${baselineLabel}` : "Run current",
        onClick: handleRunBaseline,
        disabled: isFlowBusy,
      };
    }
    if (!eddFlow.baselineEval) {
      return {
        eyebrow: selectedGeneratedDesign ? "Run saved" : "Next action",
        title: selectedGeneratedDesign ? `Evaluate generated ${baselineLabel}` : `Check ${baselineLabel}`,
        detail: selectedGeneratedDesign
          ? "Judge the generated response against the generated contract and save pass/fail evidence."
          : "Judge the response against the saved eval method and record what failed.",
        label: selectedGeneratedDesign ? "Evaluate" : "Check answer",
        onClick: handleEvaluateBaseline,
        disabled: isFlowBusy,
      };
    }
    if (baselinePassed) {
      return {
        eyebrow: "Complete",
        title: `${baselineLabel} passed`,
        detail: "No fix is needed for this contract. Open the saved evidence to inspect the result.",
        label: "Done",
        onClick: undefined,
        disabled: true,
      };
    }
    if (improvementNeeded && !analysisNote) {
      return {
        eyebrow: "Next action",
        title: "Analyze the failed evidence",
        detail: "Name the failure mode before turning it into a targeted fix.",
        label: "Save analysis",
        onClick: handleSaveAnalysisNote,
        disabled: isFlowBusy || isSavingAnalysis || !analysisNoteText.trim() || !analysisTargetArtifactId,
      };
    }
    if (!eddFlow.fixProposal && eddFlow.failurePackets.length > 0) {
      return {
        eyebrow: "Next action",
        title: "Propose one fix",
        detail: "Use the failure evidence to suggest one targeted instruction change.",
        label: "Create fix",
        onClick: handleCreateFixProposal,
        disabled: isFlowBusy,
      };
    }
    if (!eddFlow.candidateVersion && eddFlow.fixProposal) {
      return {
        eyebrow: "Next action",
        title: "Create the next version",
        detail: "Apply the proposed fix to create a new agent version.",
        label: "Create version",
        onClick: handleCreateCandidate,
        disabled: isFlowBusy,
      };
    }
    if (!eddFlow.candidateRun && eddFlow.candidateVersion) {
      return {
        eyebrow: "Next action",
        title: `Run ${eddFlow.candidateVersion.version_label}`,
        detail: "Run the improved version against the same scenario.",
        label: "Run version",
        onClick: handleRunCandidate,
        disabled: isFlowBusy,
      };
    }
    if (!eddFlow.candidateEval && eddFlow.candidateRun) {
      return {
        eyebrow: "Next action",
        title: `Check ${eddFlow.candidateVersion?.version_label ?? "next version"}`,
        detail: "Judge the new response against the same success criteria.",
        label: "Check version",
        onClick: handleEvaluateCandidate,
        disabled: isFlowBusy,
      };
    }
    if (!eddFlow.comparison && eddFlow.baselineEval && eddFlow.candidateEval) {
      return {
        eyebrow: "Next action",
        title: "Compare versions",
        detail: "Show whether the new version fixed the failure or still needs work.",
        label: "Compare",
        onClick: handleCompareRuns,
        disabled: isFlowBusy,
      };
    }
    if (eddFlow.comparison && eddFlow.candidateVersion && eddFlow.candidateRun && eddFlow.candidateEval) {
      return {
        eyebrow: "Iteration complete",
        title: eddFlow.comparison.summary,
        detail: "Continue from this version if another bounded improvement is needed.",
        label: "Continue improving",
        onClick: handleContinueImprovement,
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
        reviewArtifact || toolsPanelOpen || scratchPanelOpen || scenarioEditorOpen ? "review-open" : "",
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
              setGeneratedDesign(null);
              setReviewArtifact(null);
              setReviewLinks([]);
              setToolsPanelOpen(false);
              setScratchPanelOpen(false);
              setActivity(null);
              setWorkspaceTab("proof");
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
          <>
          <section className="service-list" aria-label="Service status">
            <p className="section-label">Services</p>
            {services.length === 0 ? <p className="empty-list">Checking services...</p> : null}
            {services.map((service) => {
              const content = (
                <>
                  <span className={`service-dot ${service.status}`} aria-hidden="true" />
                  <span className="service-copy">
                    <strong>{service.name}</strong>
                    <small>{service.status.replace("_", " ")}</small>
                  </span>
                  {service.url ? <ExternalLink size={15} /> : null}
                </>
              );
              return service.url ? (
                <a
                  className="service-row"
                  href={service.url}
                  key={service.id}
                  rel="noreferrer"
                  target="_blank"
                  title={service.description}
                >
                  {content}
                </a>
              ) : (
                <div className="service-row" key={service.id} title={service.description}>
                  {content}
                </div>
              );
            })}
          </section>

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
                    setGeneratedDesign((current) =>
                      current?.agentId === agent.id ? current : null,
                    );
                    setOpenAgentMenuId(null);
                    setReviewArtifact(null);
                    setReviewLinks([]);
                    setToolsPanelOpen(false);
                    setScratchPanelOpen(false);
                    setScratchActivity(null);
                    setScratchError(null);
                    setScratchArtifact(null);
                    setScratchTraceUrl(null);
                    setWorkspaceTab("proof");
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
                        setGeneratedDesign((current) =>
                          current?.agentId === agent.id ? current : null,
                        );
                        setScratchPanelOpen(true);
                        setReviewArtifact(null);
                        setReviewLinks([]);
                        setToolsPanelOpen(false);
                        setScenarioEditorOpen(false);
                        setOpenAgentMenuId(null);
                      }}
                    >
                      <Play size={18} />
                      <span>
                        Try scenario
                        <small>Ad hoc run</small>
                      </span>
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
          </>
        ) : null}
      </aside>

      <main className="workspace">
        {!selectedAgent ? (
          <header className="topbar">
            <div>
              <h1>New agent</h1>
              <p>
                {project?.description ??
                  "Describe the outcome and persist the first platform design."}
              </p>
            </div>
          </header>
        ) : null}

        <section className={selectedAgent ? "canvas canvas-workspace" : "canvas"}>
          {!selectedAgent ? (
            <form className="intent-form" onSubmit={handleCreate}>
              <p className="eyebrow">Start from outcome</p>
              <h2>What result should the agent produce?</h2>
              <label>
                Desired outcome
                <textarea
                  value={intent}
                  onChange={(event) => setIntent(event.target.value)}
                  placeholder="Determine where the next Formula 1 race is."
                  required
                />
              </label>
              <div className="intent-actions">
                <button
                  className="primary-button"
                  type="button"
                  disabled={!intent.trim() || isDraftingAgent}
                  onClick={handleDraftFromOutcome}
                >
                  {isDraftingAgent ? "Drafting..." : "Draft from outcome"}
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setManualCreateOpen((open) => !open)}
                >
                  {manualCreateOpen ? "Hide manual fields" : "Create manually"}
                </button>
              </div>
              {manualCreateOpen ? (
                <div className="manual-create-fields">
                  <label>
                    Agent name
                    <input
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      placeholder="Customer Service Triage Agent"
                      required={manualCreateOpen}
                    />
                  </label>
                  <button
                    className="secondary-button"
                    type="submit"
                    disabled={!name.trim() || !intent.trim()}
                  >
                    Save manual agent
                  </button>
                </div>
              ) : null}
              {error ? <p className="error-text">{error}</p> : null}
            </form>
          ) : null}

          {selectedAgent ? (
            <section className="agent-workspace">
              <div className="workspace-tabbar">
                <div className="workspace-tabs" role="tablist" aria-label="Agent workspace">
                  <button
                    className={workspaceTab === "agent" ? "workspace-tab active" : "workspace-tab"}
                    type="button"
                    role="tab"
                    aria-selected={workspaceTab === "agent"}
                    onClick={() => setWorkspaceTab("agent")}
                  >
                    Agent
                  </button>
                  <button
                    className={workspaceTab === "proof" ? "workspace-tab active" : "workspace-tab"}
                    type="button"
                    role="tab"
                    aria-selected={workspaceTab === "proof"}
                    onClick={() => setWorkspaceTab("proof")}
                  >
                    Proof loop
                  </button>
                  <button
                    className={
                      workspaceTab === "error-analysis" ? "workspace-tab active" : "workspace-tab"
                    }
                    type="button"
                    role="tab"
                    aria-selected={workspaceTab === "error-analysis"}
                    onClick={() => setWorkspaceTab("error-analysis")}
                  >
                    Error analysis
                  </button>
                  <button
                    className={workspaceTab === "evidence" ? "workspace-tab active" : "workspace-tab"}
                    type="button"
                    role="tab"
                    aria-selected={workspaceTab === "evidence"}
                    onClick={() => setWorkspaceTab("evidence")}
                  >
                    Evidence
                    <span>{evidenceArtifacts.length}</span>
                  </button>
                  <button
                    className={workspaceTab === "readiness" ? "workspace-tab active" : "workspace-tab"}
                    type="button"
                    role="tab"
                    aria-selected={workspaceTab === "readiness"}
                    onClick={() => setWorkspaceTab("readiness")}
                  >
                    Readiness
                  </button>
                </div>
                <div className="run-mode-control workspace-run-mode" aria-label="Run mode">
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
              </div>

              {workspaceTab === "agent" ? (
                <section className="agent-designer-panel workspace-tab-panel">
                  <form className="agent-profile-form" onSubmit={handleSaveAgentProfile}>
                    <div className="section-heading-row">
                      <div>
                        <p className="artifact-type">Agent design</p>
                        <h2>{selectedAgent.name}</h2>
                      </div>
                      <span className="muted-chip">{selectedAgent.status}</span>
                    </div>
                    <label className="compact-label">
                      <span>Agent name</span>
                      <input
                        value={agentEditName}
                        onChange={(event) => setAgentEditName(event.target.value)}
                        required
                      />
                    </label>
                    <label className="compact-label">
                      <span>Core instruction</span>
                      <textarea
                        value={agentEditIntent}
                        onChange={(event) => setAgentEditIntent(event.target.value)}
                        required
                      />
                    </label>
                    <div className="agent-profile-actions">
                      {activity ? <p className="activity-text">{activity}</p> : null}
                      {error ? <p className="error-text">{error}</p> : null}
                      <button
                        className="primary-button"
                        type="submit"
                        disabled={
                          isSavingAgent ||
                          !agentProfileChanged ||
                          !agentEditName.trim() ||
                          !agentEditIntent.trim()
                        }
                      >
                        {isSavingAgent ? "Saving" : "Save agent"}
                      </button>
                    </div>
                  </form>
                  <aside className="agent-tool-summary" aria-label="Agent tools">
                    <div>
                      <p className="artifact-type">Tools</p>
                      <h3>
                        {selectedAgent.allowed_tool_names.length === 0
                          ? "No tools enabled"
                          : `${selectedAgent.allowed_tool_names.length} enabled`}
                      </h3>
                      <p>
                        {approvedTools.length} approved · {draftTools.length} draft
                      </p>
                    </div>
                    <div className="tool-chip-row">
                      {enabledToolDefinitions.length === 0 ? (
                        <span className="muted-chip">None enabled</span>
                      ) : (
                        enabledToolDefinitions.slice(0, 4).map((tool) => (
                          <span className="tool-chip" key={tool.id}>
                            {tool.name}
                          </span>
                        ))
                      )}
                      {selectedAgent.allowed_tool_names.length > enabledToolDefinitions.length ? (
                        <span className="muted-chip">
                          +{selectedAgent.allowed_tool_names.length - enabledToolDefinitions.length}
                        </span>
                      ) : null}
                    </div>
                    {generatedToolStates.length > 0 ? (
                      <div className="generated-tool-lifecycle">
                        <p className="artifact-type">Generated tools</p>
                        {generatedToolStates.map((tool) => (
                          <div className="generated-tool-row" key={tool.name}>
                            <strong>{tool.name}</strong>
                            <span>{tool.implementationKind}</span>
                            <span className="tool-state-chip">auto-created</span>
                            <span className="tool-state-chip">{tool.status}</span>
                            <span className={tool.enabled ? "tool-state-chip enabled" : "tool-state-chip"}>
                              {tool.enabled ? "enabled" : "not enabled"}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => {
                        setToolsPanelOpen(true);
                        setReviewArtifact(null);
                        setReviewLinks([]);
                        setScratchPanelOpen(false);
                        setScenarioEditorOpen(false);
                      }}
                    >
                      Manage tools
                    </button>
                  </aside>
                </section>
              ) : null}

              {workspaceTab === "proof" ? (
                <section className="edd-loop-panel proof-workspace-panel workspace-tab-panel">
                  <div className="edd-loop-copy">
                    <h3>{selectedGeneratedDesign ? "Generated lifecycle" : "Test cases"}</h3>
                    <p>
                      {selectedGeneratedDesign
                        ? "Review the generated design, run v0, then evaluate it against the generated contract."
                        : "Select a saved test, run it, then improve from failed evidence."}
                    </p>
                  </div>
                  {selectedGeneratedDesign ? (
                    <div className="generated-design-review">
                      <div className="generated-design-header">
                        <div>
                          <p className="artifact-type">Generated design</p>
                          <h4>{selectedAgent.name}</h4>
                          <p>
                            The platform created the first version, scenario, success criteria, and
                            tool policy from the requested outcome.
                          </p>
                        </div>
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() => {
                            setReviewArtifact(selectedGeneratedDesign.artifact);
                            setReviewLinks([]);
                          }}
                        >
                          Inspect design
                        </button>
                      </div>
                      <dl className="generated-design-grid">
                        <div>
                          <dt>Version</dt>
                          <dd>{selectedGeneratedDesign.version.version_label}</dd>
                          {generatedVersionArtifact ? (
                            <button
                              className="inline-evidence-button"
                              type="button"
                              onClick={() => {
                                setReviewArtifact(generatedVersionArtifact);
                                setReviewLinks([]);
                              }}
                            >
                              Inspect
                            </button>
                          ) : null}
                        </div>
                        <div>
                          <dt>Scenario</dt>
                          <dd>{selectedGeneratedDesign.scenario.name}</dd>
                          {generatedScenarioArtifact ? (
                            <button
                              className="inline-evidence-button"
                              type="button"
                              onClick={() => {
                                setReviewArtifact(generatedScenarioArtifact);
                                setReviewLinks([]);
                              }}
                            >
                              Inspect
                            </button>
                          ) : null}
                        </div>
                        <div>
                          <dt>Contract</dt>
                          <dd>{selectedGeneratedDesign.contract.name}</dd>
                          {generatedContractArtifact ? (
                            <button
                              className="inline-evidence-button"
                              type="button"
                              onClick={() => {
                                setReviewArtifact(generatedContractArtifact);
                                setReviewLinks([]);
                              }}
                            >
                              Inspect
                            </button>
                          ) : null}
                        </div>
                        <div>
                          <dt>Required tools</dt>
                          <dd>
                            {selectedGeneratedDesign.contract.required_tools.length > 0
                              ? selectedGeneratedDesign.contract.required_tools.join(", ")
                              : "None"}
                          </dd>
                        </div>
                      </dl>
                      <div className="generated-tool-review">
                        <div>
                          <span>Generated tool lifecycle</span>
                          {generatedToolStates.length > 0 ? (
                            <div className="generated-tool-row-list">
                              {generatedToolStates.map((tool) => (
                                <div className="generated-tool-row" key={tool.name}>
                                  <strong>{tool.name}</strong>
                                  <span>{tool.implementationKind}</span>
                                  <span className="tool-state-chip">auto-created</span>
                                  <span className="tool-state-chip">{tool.status}</span>
                                  <span className={tool.enabled ? "tool-state-chip enabled" : "tool-state-chip"}>
                                    {tool.enabled ? "enabled" : "not enabled"}
                                  </span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <strong>None</strong>
                          )}
                        </div>
                        <div>
                          <span>Draft tools</span>
                          <strong>
                            {selectedGeneratedDesign.draftTools.length > 0
                              ? selectedGeneratedDesign.draftTools.map((tool) => tool.name).join(", ")
                              : "None"}
                          </strong>
                        </div>
                        <div>
                          <span>Output requirements</span>
                          <strong>
                            {selectedGeneratedDesign.contract.output_requirements.join(", ")}
                          </strong>
                        </div>
                      </div>
                    </div>
                  ) : null}
                  <div className="proof-scenario-card">
                    {hasSavedScenarioTest ? (
                      <div className="scenario-test-summary">
                        <div>
                          <p className="artifact-type">
                            {selectedGeneratedDesign ? "Generated test" : "Selected test"}
                          </p>
                          <h4>{eddFlow.scenario?.name}</h4>
                          <span className="scenario-shape-pill">{testShapeLabels[savedTestShape]}</span>
                          {renderScenarioInput(eddFlow.scenario?.input)}
                        </div>
                        <dl>
                          <div>
                            <dt>Judge</dt>
                            <dd>{savedEvalLabel}</dd>
                          </div>
                          <div>
                            <dt>Criterion</dt>
                            <dd>{savedEvalSummary}</dd>
                          </div>
                          <div>
                            <dt>Latest result</dt>
                            <dd>
                              {eddFlow.baselineEval
                                ? eddFlow.baselineEval.passed
                                  ? "Passed"
                                  : "Failed"
                                : "Not run"}
                            </dd>
                          </div>
                        </dl>
                      </div>
                    ) : (
                      <div className="scenario-empty-state">
                        <p className="artifact-type">No selected test</p>
                        <h4>No test case yet</h4>
                        <p>Create a single-turn, conversation, or replay test. The draft opens in the right panel.</p>
                      </div>
                    )}
                    <div className="scenario-test-actions">
                      {!selectedGeneratedDesign ? (
                        <button className="secondary-button" type="button" onClick={openNewScenarioEditor}>
                          New test
                        </button>
                      ) : null}
                      {hasSavedScenarioTest ? (
                        <button className="secondary-button" type="button" onClick={openScenarioEditor}>
                          {selectedGeneratedDesign ? "Edit generated test" : "Edit test"}
                        </button>
                      ) : null}
                      {hasSavedScenarioTest ? (
                        <button
                          className="secondary-button compact-button"
                          type="button"
                          onClick={() => setWorkspaceTab("evidence")}
                        >
                          View evidence
                        </button>
                      ) : null}
                    </div>
                  </div>
                  {showNextActionPanel ? (
                    <div className="next-action-panel">
                      <div>
                        <p className="artifact-type">{currentLoopAction.eyebrow}</p>
                        <h4>{currentLoopAction.title}</h4>
                        <p>{currentLoopAction.detail}</p>
                        <div className="proof-mode-summary" aria-label="Run and judge modes">
                          <span>Run: {displayedRunMode === "live" ? "Live OpenAI" : "Mock"}</span>
                          <span>
                            Judge:{" "}
                            {displayedJudgeMode === "live" ? "Live rubric" : "Deterministic checks"}
                          </span>
                        </div>
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
                  ) : null}
                  {selectedGeneratedDesign && baselinePassed ? (
                    <div className="pass-evidence-panel">
                      <div className="pass-evidence-header">
                        <div>
                          <p className="artifact-type">Passed with evidence</p>
                          <h4>{baselineLabel} satisfied the generated contract</h4>
                          <p>
                            The run, judge result, tool policy, and trace evidence are saved for review.
                          </p>
                        </div>
                        {baselineTraceUrl ? (
                          <a
                            className="secondary-button trace-link"
                            href={baselineTraceUrl}
                            rel="noreferrer"
                            target="_blank"
                          >
                            Open trace
                          </a>
                        ) : null}
                      </div>
                      <div className="pass-evidence-grid">
                        <div>
                          <span>Version</span>
                          <strong>{selectedGeneratedDesign.version.version_label}</strong>
                        </div>
                        <div>
                          <span>Tools</span>
                          <strong>
                            {generatedToolStates.length > 0
                              ? generatedToolStates
                                  .filter((tool) => tool.enabled)
                                  .map((tool) => tool.name)
                                  .join(", ") || "None"
                              : selectedGeneratedDesign.contract.required_tools.join(", ") || "None"}
                          </strong>
                        </div>
                        <div>
                          <span>Run evidence</span>
                          {baselineRunArtifact ? (
                            <button
                              className="inline-evidence-button"
                              type="button"
                              onClick={() => {
                                setReviewArtifact(baselineRunArtifact);
                                setReviewLinks([]);
                              }}
                            >
                              Inspect run
                            </button>
                          ) : (
                            <strong>{eddFlow.baselineRun?.id ?? "Not saved"}</strong>
                          )}
                        </div>
                        <div>
                          <span>Judge evidence</span>
                          {baselineEvalArtifact ? (
                            <button
                              className="inline-evidence-button"
                              type="button"
                              onClick={() => {
                                setReviewArtifact(baselineEvalArtifact);
                                setReviewLinks([]);
                              }}
                            >
                              Inspect judge
                            </button>
                          ) : (
                            <strong>{displayedJudgeMode === "live" ? "Live rubric" : "Deterministic"}</strong>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : null}
                  {showFailureAnalysis ? (
                    <div className="failure-analysis-panel">
                      <div className="failure-analysis-summary">
                        <h4>Failed checks</h4>
                        {deterministicRubricOnlyFailure ? (
                          <p className="judge-mode-note">
                            This result only failed rubric checks under deterministic judging. Run the
                            live rubric judge to score the open-ended outcome.
                          </p>
                        ) : null}
                        <div className="failed-check-list">
                          {failedBaselineChecks.length === 0 ? (
                            <span>No failed checks were returned.</span>
                          ) : (
                            failedBaselineChecks.map((check) => (
                              <span key={check.check_id}>
                                <strong>{check.check_id}</strong>
                                {check.comment || check.observed}
                              </span>
                            ))
                          )}
                        </div>
                      </div>
                      <div className="failure-analysis-form">
                        <div className="analysis-field-row">
                          <label className="compact-label">
                            <span>Failure mode</span>
                            <input
                              value={analysisFailureMode}
                              onChange={(event) => setAnalysisFailureMode(event.target.value)}
                              placeholder="failed expected phrase"
                            />
                          </label>
                          <label className="compact-label">
                            <span>Severity</span>
                            <select
                              value={analysisSeverity}
                              onChange={(event) => setAnalysisSeverity(event.target.value)}
                            >
                              <option value="low">Low</option>
                              <option value="medium">Medium</option>
                              <option value="high">High</option>
                            </select>
                          </label>
                        </div>
                        <label className="compact-label">
                          <span>Review note</span>
                          <textarea
                            value={analysisNoteText}
                            onChange={(event) => setAnalysisNoteText(event.target.value)}
                            placeholder="The response did not satisfy the explicit success criteria because..."
                          />
                        </label>
                        {activity ? <p className="activity-text">{activity}</p> : null}
                        {error ? <p className="error-text">{error}</p> : null}
                        <div className="analysis-action-row">
                          {analysisNote ? (
                            <span className="saved-analysis-chip">Analysis saved</span>
                          ) : (
                            <span>Targeting current failure evidence</span>
                          )}
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={handleSaveAnalysisNote}
                            disabled={
                              isFlowBusy ||
                              isSavingAnalysis ||
                              !analysisNoteText.trim() ||
                              !analysisTargetArtifactId
                            }
                          >
                            Save analysis
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : null}
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
              ) : null}

              {workspaceTab === "error-analysis" ? (
                <section className="error-analysis-workspace workspace-tab-panel">
                  <div className="error-analysis-intro">
                    <div>
                      <p className="artifact-type">Error analysis</p>
                      <h3>{activeReviewCorpus?.name ?? "Discovery review"}</h3>
                      <p>
                        Review traces, runs, and evidence as a corpus. Save free-text notes,
                        organize confirmed failure modes, and keep agent suggestions separate
                        until they are accepted.
                      </p>
                    </div>
                    <div className="analysis-scope-card">
                      <span>Active analysis</span>
                      <strong>{selectedAgent?.name ?? "No agent selected"}</strong>
                      <small>
                        {activeReviewCorpus
                          ? `${activeReviewCorpus.source} corpus · ${activeReviewCorpus.status}`
                          : "Create a corpus to begin"}
                      </small>
                    </div>
                  </div>

                  <div className="analysis-flow-lanes">
                    <section className="analysis-lane-card">
                      <div>
                        <span>Review corpus</span>
                        <strong>{reviewItems.length} items</strong>
                        <small>
                          {reviewedItemCount} reviewed · {reviewItems.length - reviewedItemCount} open
                        </small>
                      </div>
                      <div className="analysis-run-actions">
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={handleCreateReviewCorpus}
                          disabled={isDiscoveryBusy || !selectedAgent || Boolean(activeReviewCorpus)}
                        >
                          Create corpus
                        </button>
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={handleAddCurrentEvidenceToCorpus}
                          disabled={isDiscoveryBusy || !selectedAgent}
                        >
                          Add evidence
                        </button>
                      </div>
                    </section>
                    <section className="analysis-lane-card">
                      <div>
                        <span>Failure modes</span>
                        <strong>{failureModes.length} modes</strong>
                        <small>
                          {acceptedAnnotationCount} accepted notes ·{" "}
                          {agentSuggestions.filter((suggestion) => suggestion.status === "pending").length} pending suggestions
                        </small>
                      </div>
                      <div className="analysis-run-actions">
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={handleCreateSuggestion}
                          disabled={isDiscoveryBusy || !selectedReviewItem}
                        >
                          Suggest
                        </button>
                        <button
                          className="primary-button"
                          type="button"
                          onClick={handleSaveOpenCodeAnnotation}
                          disabled={isDiscoveryBusy || !selectedReviewItem || !openCodeText.trim()}
                        >
                          Save note
                        </button>
                      </div>
                    </section>
                  </div>

                  <div className="analysis-stats">
                    <span>
                      <strong>{reviewItems.length}</strong>
                      items
                    </span>
                    <span>
                      <strong>{acceptedAnnotationCount}</strong>
                      notes
                    </span>
                    <span>
                      <strong>{failureModes.length}</strong>
                      modes
                    </span>
                  </div>

                  <div className="trace-review-layout">
                    <div className="trace-packet-list" aria-label="Trace review queue">
                      {reviewItems.length === 0 ? (
                        <p className="muted-copy">No review items yet.</p>
                      ) : null}
                      {reviewItems.map((item) => (
                        <button
                          className={
                            selectedReviewItem?.id === item.id
                              ? "trace-packet-item active"
                              : "trace-packet-item"
                          }
                          key={item.id}
                          type="button"
                          onClick={() => setSelectedReviewItemId(item.id)}
                        >
                          <span>{item.status}</span>
                          <strong>{item.title}</strong>
                          <small>
                            {item.source_kind} ·{" "}
                            {reviewAnnotations.filter((annotation) => annotation.review_item_id === item.id).length} notes
                          </small>
                        </button>
                      ))}
                    </div>

                    <article className="trace-review-packet">
                      {selectedReviewItem ? (
                        <>
                          <div className="trace-packet-header">
                            <div>
                              <p className="artifact-type">Review item</p>
                              <h4>{selectedReviewItem.title}</h4>
                            </div>
                            {selectedReviewTraceUrl ? (
                              <a href={selectedReviewTraceUrl} target="_blank" rel="noreferrer">
                                Open trace
                              </a>
                            ) : null}
                          </div>

                          <div className="trace-packet-grid">
                            <section>
                              <h5>Evidence</h5>
                              <p>{selectedReviewItem.content || "No content saved for this item."}</p>
                            </section>
                            <section>
                              <h5>Source</h5>
                              <p>
                                {selectedReviewItem.source_kind} · {selectedReviewItem.source_id}
                              </p>
                              {selectedReviewItem.langfuse_ref?.observation_id ? (
                                <p>Observation · {selectedReviewItem.langfuse_ref.observation_id}</p>
                              ) : null}
                            </section>
                            <section>
                              <h5>Accepted notes</h5>
                              <div className="trace-comment-list">
                                {selectedReviewAnnotations.length === 0 ? (
                                  <p>No notes saved yet.</p>
                                ) : (
                                  selectedReviewAnnotations.map((annotation) => (
                                    <p key={annotation.id}>
                                      <strong>{annotation.author}:</strong> {annotation.body}
                                    </p>
                                  ))
                                )}
                              </div>
                            </section>
                            <section>
                              <h5>Suggestions</h5>
                              <div className="trace-comment-list">
                                {pendingSuggestions.length === 0 ? (
                                  <p>No pending suggestions.</p>
                                ) : (
                                  pendingSuggestions.map((suggestion) => (
                                    <div className="suggestion-row" key={suggestion.id}>
                                      <p>
                                        <strong>EDD:</strong> {suggestion.body}
                                      </p>
                                      <div className="analysis-run-actions">
                                        <button
                                          className="secondary-button compact-button"
                                          type="button"
                                          onClick={() => handleResolveSuggestion(suggestion, "dismissed")}
                                          disabled={isDiscoveryBusy}
                                        >
                                          Dismiss
                                        </button>
                                        <button
                                          className="secondary-button compact-button"
                                          type="button"
                                          onClick={() => handleResolveSuggestion(suggestion, "accepted")}
                                          disabled={isDiscoveryBusy}
                                        >
                                          Accept
                                        </button>
                                      </div>
                                    </div>
                                  ))
                                )}
                              </div>
                            </section>
                          </div>
                        </>
                      ) : (
                        <p className="muted-copy">Select or add a review item to begin open coding.</p>
                      )}
                    </article>
                  </div>

                  <div className="coding-workspace">
                    <section className="open-code-panel">
                      <div className="section-title-row">
                        <div>
                          <p className="artifact-type">Open coding</p>
                          <h4>Reviewer notes</h4>
                        </div>
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={handleSaveOpenCodeAnnotation}
                          disabled={isDiscoveryBusy || !selectedReviewItem || !openCodeText.trim()}
                        >
                          Save note
                        </button>
                      </div>
                      <label className="compact-label">
                        <span>Note</span>
                        <textarea
                          value={openCodeText}
                          onChange={(event) => setOpenCodeText(event.target.value)}
                          placeholder="Describe the behavior you observe in this item."
                        />
                      </label>
                      <div className="analysis-field-row">
                        <label className="compact-label">
                          <span>Existing mode</span>
                          <select
                            value={selectedFailureModeId}
                            onChange={(event) => setSelectedFailureModeId(event.target.value)}
                          >
                            <option value="">No mode</option>
                            {failureModes.map((mode) => (
                              <option key={mode.id} value={mode.id}>
                                {mode.name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="compact-label">
                          <span>New mode</span>
                          <input
                            value={newFailureModeName}
                            onChange={(event) => setNewFailureModeName(event.target.value)}
                            placeholder="missing policy lookup"
                          />
                        </label>
                      </div>
                      <label className="compact-label">
                        <span>Mode definition</span>
                        <input
                          value={newFailureModeDescription}
                          onChange={(event) => setNewFailureModeDescription(event.target.value)}
                          placeholder="The agent answered without checking required evidence."
                        />
                      </label>
                    </section>

                    <section className="axial-code-panel">
                      <div className="section-title-row">
                        <div>
                          <p className="artifact-type">Failure modes</p>
                          <h4>Confirmed taxonomy</h4>
                        </div>
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={handleCreateSuggestion}
                          disabled={isDiscoveryBusy || !selectedReviewItem}
                        >
                          Suggest
                        </button>
                      </div>
                      <p className="mode-table-note">
                        Modes are first-class EDD records. Suggestions stay pending until accepted.
                      </p>
                      <div className="failure-mode-table">
                        {failureModes.length === 0 ? (
                          <p className="muted-copy">No failure modes yet.</p>
                        ) : null}
                        {failureModes.map((mode) => (
                          <div className="failure-mode-row" key={mode.id}>
                            <strong>{mode.name}</strong>
                            <span>{mode.status}</span>
                            <span>{mode.severity}</span>
                            <em>
                              {
                                reviewAnnotations.filter(
                                  (annotation) => annotation.failure_mode_id === mode.id,
                                ).length
                              }{" "}
                              notes
                            </em>
                            <small>{mode.langfuse_score_name ?? "EDD"}</small>
                          </div>
                        ))}
                      </div>
                    </section>
                  </div>
                </section>
              ) : null}

              {workspaceTab === "evidence" ? (
                <section className="workflow-evidence-panel workspace-tab-panel">
                  <div className="workflow-evidence-header">
                    <div>
                      <p className="artifact-type">Evidence</p>
                      <h3>Proof artifacts</h3>
                    </div>
                    <span>{evidenceArtifacts.length} saved</span>
                  </div>
                  <div className="workflow-evidence-list">
                    {isLoadingContext ? <p className="muted-copy">Loading evidence...</p> : null}
                    {!isLoadingContext && evidenceArtifacts.length === 0 ? (
                      <p className="muted-copy">No proof artifacts yet.</p>
                    ) : null}
                    {evidenceArtifacts.map((artifact) => {
                      const traceUrl = traceUrlFromArtifact(artifact);
                      return (
                        <div className="workflow-evidence-row" key={artifact.id}>
                          <button
                            className="workflow-evidence-item"
                            type="button"
                            onClick={() => handleReviewArtifact(artifact.id)}
                          >
                            <span>{artifactRoleLabel(artifact.artifact_type)}</span>
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
                </section>
              ) : null}

              {workspaceTab === "readiness" ? (
                <section className="readiness-panel workspace-tab-panel">
                  <div>
                    <p className="artifact-type">Promotion readiness</p>
                    <h3>
                      {latestGateDecision
                        ? latestGateDecision.decision === "passed"
                          ? "Ready"
                          : "Blocked"
                        : latestGate
                          ? "Gate ready"
                          : "No gate yet"}
                    </h3>
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
                </section>
              ) : null}
            </section>
          ) : null}
        </section>
      </main>
      {scratchPanelOpen && selectedAgent ? (
        <aside className="review-panel" aria-label="Try scenario">
          <div className="review-panel-header">
            <div>
              <p className="eyebrow">Ad hoc run</p>
              <h2>{selectedAgent.name}</h2>
            </div>
            <button
              className="icon-button review-toggle-button"
              type="button"
              aria-label="Close ad hoc run panel"
              onClick={() => setScratchPanelOpen(false)}
            >
              <PanelRight size={22} />
            </button>
          </div>

          <div className="review-panel-body">
            <section className="run-playground panel-run-playground">
              <div>
                <h3>{scratchTarget === "url" ? "Call a URL" : "Try a scenario"}</h3>
                <p>
                  {scratchTarget === "url"
                    ? "Call a website without the agent layer. The response is still saved as evidence and linked to a trace when Langfuse is configured."
                    : "Run this agent without advancing the proof loop. The output is still saved as evidence and linked to a trace when live tracing is enabled."}
                </p>
              </div>
              <div className="run-mode-control scratch-target-control" aria-label="Ad hoc target">
                <button
                  className={scratchTarget === "agent" ? "mode-option active" : "mode-option"}
                  type="button"
                  onClick={() => setScratchTarget("agent")}
                >
                  Agent
                </button>
                <button
                  className={scratchTarget === "url" ? "mode-option active" : "mode-option"}
                  type="button"
                  onClick={() => setScratchTarget("url")}
                >
                  URL
                </button>
              </div>
              {scratchTarget === "url" ? (
                <label>
                  URL
                  <input
                    type="url"
                    value={scratchUrl}
                    onChange={(event) => setScratchUrl(event.target.value)}
                    placeholder="https://example.com"
                  />
                </label>
              ) : (
                <label>
                  Scenario input
                  <textarea
                    value={scenarioInput}
                    onChange={(event) => setScenarioInput(event.target.value)}
                  />
                </label>
              )}
              <button
                className="primary-button"
                type="button"
                onClick={handleRunAdHocScenario}
                disabled={isRunning}
              >
                <Play size={18} />
                {isRunning ? "Running" : scratchTarget === "url" ? "Call URL" : "Run ad hoc"}
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
            <section className="tool-manager-controls">
              <div>
                <h3>Tool manager</h3>
                <p>
                  {selectedAgent.allowed_tool_names.length} enabled for {selectedAgent.name}.
                </p>
              </div>
              <label className="tool-search-field">
                <Search size={18} />
                <input
                  value={toolSearch}
                  onChange={(event) => setToolSearch(event.target.value)}
                  placeholder="Search tools"
                />
              </label>
              <div className="tool-filter-row" aria-label="Tool filter">
                {(["all", "enabled", "available", "draft"] as const).map((filter) => (
                  <button
                    className={toolFilter === filter ? "tool-filter active" : "tool-filter"}
                    type="button"
                    key={filter}
                    onClick={() => setToolFilter(filter)}
                  >
                    {filter}
                  </button>
                ))}
              </div>
            </section>
            {activity ? <p className="activity-text">{activity}</p> : null}
            {error ? <p className="error-text">{error}</p> : null}
            <section className="tool-marketplace-list">
              <div className="tool-section-title">
                <h3>Approved tools</h3>
                <span>{filteredApprovedTools.length}</span>
              </div>
              {filteredApprovedTools.length === 0 ? (
                <p>No approved tools match this view.</p>
              ) : (
                filteredApprovedTools.map((tool) => {
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
                      <em>{tool.implementation_kind}</em>
                    </button>
                  );
                })
              )}
            </section>
            {filteredDraftTools.length > 0 ? (
              <section className="tool-marketplace-list">
                <div className="tool-section-title">
                  <h3>Draft tools</h3>
                  <span>{filteredDraftTools.length}</span>
                </div>
                {filteredDraftTools.map((tool) => (
                  <button
                    className="tool-marketplace-item draft"
                    type="button"
                    key={tool.id}
                    onClick={() => handleApproveAndEnableTool(tool)}
                    disabled={updatingTools}
                  >
                    <span>Draft</span>
                    <strong>{tool.name}</strong>
                    <small>{tool.description}</small>
                    <em>Approve and assign</em>
                  </button>
                ))}
              </section>
            ) : null}
            <section className="tool-composer-section">
              <button
                className="secondary-button"
                type="button"
                onClick={() => setToolComposerOpen((open) => !open)}
              >
                {toolComposerOpen ? "Hide new draft" : "New tool draft"}
              </button>
              {toolComposerOpen ? (
                <form className="tool-definition-form" onSubmit={handleCreateTool}>
                  <div>
                    <p className="eyebrow">New draft</p>
                    <h3>Define tool schema</h3>
                    <p>
                      Start with the contract: inputs, outputs, and deterministic mock behavior.
                    </p>
                  </div>
                  <label>
                    Tool name
                    <input
                      value={toolName}
                      onChange={(event) => setToolName(event.target.value)}
                      placeholder="lookup_ticket"
                      required
                    />
                  </label>
                  <label>
                    Description
                    <textarea
                      value={toolDescription}
                      onChange={(event) => setToolDescription(event.target.value)}
                      placeholder="Look up a support ticket by id."
                      rows={3}
                      required
                    />
                  </label>
                  <label>
                    Input schema
                    <textarea
                      className="schema-editor"
                      value={toolInputSchema}
                      onChange={(event) => setToolInputSchema(event.target.value)}
                      rows={10}
                      spellCheck={false}
                      required
                    />
                  </label>
                  <label>
                    Output schema
                    <textarea
                      className="schema-editor"
                      value={toolOutputSchema}
                      onChange={(event) => setToolOutputSchema(event.target.value)}
                      rows={8}
                      spellCheck={false}
                    />
                  </label>
                  <label>
                    Output description
                    <input
                      value={toolOutputDescription}
                      onChange={(event) => setToolOutputDescription(event.target.value)}
                      placeholder="Ticket status and summary."
                      required
                    />
                  </label>
                  <label>
                    Mock response
                    <textarea
                      value={toolMockResponse}
                      onChange={(event) => setToolMockResponse(event.target.value)}
                      placeholder="Ticket is open and awaiting customer logs."
                      rows={3}
                    />
                  </label>
                  <button className="primary-button" type="submit" disabled={updatingTools}>
                    {updatingTools ? "Creating" : "Create draft"}
                  </button>
                </form>
              ) : null}
            </section>
          </div>
        </aside>
      ) : null}
      {scenarioEditorOpen && selectedAgent ? (
        <aside className="review-panel" aria-label="Test case editor">
          <div className="review-panel-header">
            <div>
              <p className="eyebrow">Test case</p>
              <h2>{eddFlow.contract ? "Edit test" : "New test"}</h2>
            </div>
            <button
              className="icon-button review-toggle-button"
              type="button"
              aria-label="Close test case editor"
              onClick={() => setScenarioEditorOpen(false)}
            >
              <PanelRight size={22} />
            </button>
          </div>

          <div className="review-panel-body">
            <section className="scenario-editor-section">
              <h3>Test shape</h3>
              <div className="eval-method-tabs" aria-label="Test shape">
                {[
                  { id: "single_turn", label: "Single turn" },
                  { id: "conversation", label: "Conversation" },
                  { id: "trace_replay", label: "Trace replay" },
                ].map((shape) => (
                  <button
                    className={testShape === shape.id ? "eval-method-tab active" : "eval-method-tab"}
                    type="button"
                    key={shape.id}
                    onClick={() => handleTestShapeChange(shape.id as TestShape)}
                  >
                    {shape.label}
                  </button>
                ))}
              </div>
              <label className="compact-label">
                <span>{testShapeInputLabels[testShape]}</span>
                <small>{testShapeInputHelp[testShape]}</small>
                <textarea
                  value={scenarioInput}
                  onChange={(event) => setScenarioInput(event.target.value)}
                />
              </label>
            </section>
            <section className="scenario-editor-section">
              <h3>Judge method</h3>
              <div className="eval-method-tabs" aria-label="Eval method">
                {[
                  { id: "rubric", label: "Rubric judge" },
                  { id: "tool", label: "Tool use" },
                  { id: "phrase", label: "Exact text" },
                ].map((method) => (
                  <button
                    className={evalMethod === method.id ? "eval-method-tab active" : "eval-method-tab"}
                    type="button"
                    key={method.id}
                    onClick={() => setEvalMethod(method.id as EvalMethod)}
                  >
                    {method.label}
                  </button>
                ))}
              </div>
              {evalMethod === "phrase" ? (
                <label className="compact-label">
                  <span>Required phrase</span>
                  <small>Deterministic contains check.</small>
                  <input
                    value={requiredPhrase}
                    onChange={(event) => setRequiredPhrase(event.target.value)}
                  />
                </label>
              ) : null}
              {evalMethod === "tool" ? (
                <label className="compact-label">
                  <span>Required tool</span>
                  <small>The run must call this enabled tool.</small>
                  <select
                    value={requiredToolName}
                    onChange={(event) => setRequiredToolName(event.target.value)}
                    disabled={enabledToolDefinitions.length === 0}
                  >
                    {enabledToolDefinitions.length === 0 ? (
                      <option value="">No enabled tools</option>
                    ) : (
                      enabledToolDefinitions.map((tool) => (
                        <option value={tool.name} key={tool.id}>
                          {tool.name}
                        </option>
                      ))
                    )}
                  </select>
                </label>
              ) : null}
              {evalMethod === "rubric" ? (
                <label className="compact-label">
                  <span>Rubric</span>
                  <small>Needs live judge scoring before pass/fail can be saved.</small>
                  <textarea
                    value={rubricText}
                    onChange={(event) => setRubricText(event.target.value)}
                  />
                </label>
              ) : null}
            </section>
            {activity ? <p className="activity-text">{activity}</p> : null}
            {error ? <p className="error-text">{error}</p> : null}
            <button
              className="primary-button"
              type="button"
              onClick={handleInitializeEddFlow}
              disabled={!canDefineTest}
            >
              Save test
            </button>
          </div>
        </aside>
      ) : null}
      {reviewArtifact ? (
        <aside className="review-panel" aria-label="Artifact review">
          <div className="review-panel-header">
            <div>
              <p className="eyebrow">{artifactRoleLabel(reviewArtifact.artifact_type)}</p>
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
            {reviewFixProposal ? (
              <section>
                <h3>Edit fix</h3>
                <label className="compact-label">
                  <span>Instruction change</span>
                  <textarea
                    value={fixEditText}
                    onChange={(event) => setFixEditText(event.target.value)}
                  />
                </label>
                <button
                  className="primary-button"
                  type="button"
                  onClick={handleSaveFixProposal}
                  disabled={isSavingFix || !fixEditText.trim()}
                >
                  Save
                </button>
              </section>
            ) : null}
            <section>
              <h3>Contents</h3>
              {reviewFields.length > 0 ? (
                <dl className="record-fields">
                  {reviewFields.map((field) => (
                    <div key={field.label}>
                      <dt>{field.label}</dt>
                      <dd>{field.value}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p>{reviewArtifact.body}</p>
              )}
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
              <h3>Related evidence</h3>
              {connectedArtifacts.length === 0 ? (
                <p>No related evidence yet.</p>
              ) : (
                <ul className="related-list">
                  {connectedArtifacts.map(({ artifact, link }) => {
                    const traceUrl = traceUrlFromArtifact(artifact);
                    return (
                      <li key={link.id}>
                        <button
                          className="related-record-button"
                          type="button"
                          onClick={() => handleReviewArtifact(artifact.id)}
                        >
                          <strong>{relatedEvidenceLabel(artifact)}</strong>
                          <span>{artifact.title}</span>
                        </button>
                        {traceUrl ? (
                          <a
                            className="secondary-button related-trace-link"
                            href={traceUrl}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Open trace
                          </a>
                        ) : null}
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
