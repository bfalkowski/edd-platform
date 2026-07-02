import type {
  AgentDesign,
  ArtifactRecord,
  EddFlowState,
  ExternalArtifactRef,
  FailurePacket,
  TestShape,
} from "./types";
import type { WizardState, fetchAgentWizardState } from "./Wizard";

export const defaultScenarioInput = "What's the weather in Boston today?";
export const defaultConversationInput = `Customer: My deployment failed after the release.
Agent: What error are you seeing?
Customer: The rollout says image pull backoff.`;
export const defaultTraceReplayInput =
  "Paste the prior trace spans, messages, or evidence that should set up the next agent response.";
export const defaultRubricText =
  "A good answer should directly answer the user request, avoid unsupported claims, and ask for missing details only when they are required.";
export const defaultConversationRubricText =
  "A good observer output should review the latest customer turn in context, identify that sentiment or escalation risk is worsening, mention the image pull backoff blocker, avoid claiming the issue is fixed, and produce concise downstream-safe observer notes.";
export const defaultTraceReplayRubricText =
  "A good answer should use the replayed evidence, preserve important context from the trace, and avoid inventing facts not present in the replay.";
export const testShapeLabels: Record<TestShape, string> = {
  single_turn: "Single turn",
  conversation: "Conversation",
  trace_replay: "Trace replay",
};
export const testShapeInputLabels: Record<TestShape, string> = {
  single_turn: "Prompt",
  conversation: "Conversation",
  trace_replay: "Replay context",
};
export const testShapeInputHelp: Record<TestShape, string> = {
  single_turn: "Test one user request in isolation.",
  conversation: "Include prior messages plus the next user turn.",
  trace_replay: "Start from selected prior spans, messages, or evidence.",
};
export function defaultInputForTestShape(shape: TestShape): string {
  if (shape === "conversation") {
    return defaultConversationInput;
  }
  if (shape === "trace_replay") {
    return defaultTraceReplayInput;
  }
  return defaultScenarioInput;
}
export function conversationTurnsFromText(input: string): Array<{ speaker: string; text: string }> {
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
export function renderScenarioInput(input: string | undefined) {
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
export function defaultRubricForTestShape(shape: TestShape): string {
  if (shape === "conversation") {
    return defaultConversationRubricText;
  }
  if (shape === "trace_replay") {
    return defaultTraceReplayRubricText;
  }
  return defaultRubricText;
}
export function isDefaultTestInput(input: string): boolean {
  return [defaultScenarioInput, defaultConversationInput, defaultTraceReplayInput].includes(input);
}
export function isDefaultRubricText(rubric: string): boolean {
  return [defaultRubricText, defaultConversationRubricText, defaultTraceReplayRubricText].includes(rubric);
}
export function setupContextFromTestShape(shape: TestShape): string {
  return `test_shape:${shape}`;
}
export function testShapeFromSetupContext(setupContext?: string): TestShape {
  if (setupContext?.includes("test_shape:conversation")) {
    return "conversation";
  }
  if (setupContext?.includes("test_shape:trace_replay")) {
    return "trace_replay";
  }
  return "single_turn";
}
export const defaultToolInputSchema = `{
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
export const defaultToolOutputSchema = `{
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

export function traceUrlFromArtifact(artifact: ArtifactRecord): string | null {
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

export function externalRefLabel(ref: ExternalArtifactRef): string {
  if (ref.label) {
    return ref.label;
  }
  if (ref.provider === "langfuse") {
    const labels: Record<string, string> = {
      comment: "Langfuse comment",
      dataset: "Langfuse dataset",
      dataset_item: "Langfuse dataset item",
      prompt: "Langfuse prompt",
      score: "Langfuse score",
      trace: "Langfuse trace",
    };
    return labels[ref.ref_type] ?? "Langfuse reference";
  }
  return `${ref.provider} ${ref.ref_type}`.trim();
}

export function externalRefDetail(ref: ExternalArtifactRef): string {
  const metadataLabel =
    ref.metadata["score_name"] ??
    ref.metadata["prompt_name"] ??
    ref.metadata["dataset_name"] ??
    ref.metadata["prompt_role"] ??
    ref.metadata["sync_mode"];
  if (typeof metadataLabel === "string" && metadataLabel.trim()) {
    return `${metadataLabel.trim()} · ${ref.external_id}`;
  }
  return ref.external_id;
}

export function parseJsonObject(value: string, label: string): Record<string, unknown> {
  const parsed = JSON.parse(value);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON object.`);
  }
  return parsed as Record<string, unknown>;
}

export function toolImplementationKey(name: string): string {
  const slug = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return `mock.${slug || "tool"}`;
}

export function parseArtifactFields(body: string): { label: string; value: string }[] {
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

export function artifactRoleLabel(artifactType: string): string {
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

export function relatedEvidenceLabel(artifact: ArtifactRecord | undefined): string {
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

export function proofFlowSummary(flow: EddFlowState): string {
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

export function proofArtifactIds(flow: EddFlowState): string[] {
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

export function proofRunIds(flow: EddFlowState): string[] {
  return [
    flow.baselineRun?.id,
    flow.candidateRun?.id,
  ].filter((id): id is string => Boolean(id));
}

export function failurePacketsForEval(flow: EddFlowState, evalResultId?: string): FailurePacket[] {
  if (!evalResultId) {
    return flow.failurePackets;
  }
  return flow.failurePackets.filter((packet) => packet.eval_result_id === evalResultId);
}

export function inferExpectedResponse(agent: AgentDesign): string {
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


export function wizardStateFromFlow(
  projectId: string,
  agentState: Awaited<ReturnType<typeof fetchAgentWizardState>>,
  flow: EddFlowState,
): Partial<WizardState> {
  const { baselineRun, baselineEval, candidateRun, candidateEval, comparison,
          failurePackets, fixProposal, baselineVersion, candidateVersion } = flow;

  const base = { projectId, agent: agentState, currentVersionId: baselineVersion?.id ?? null };

  if (comparison && candidateRun && candidateEval) {
    return {
      ...base, step: "compare",
      baselineRun: baselineRun ?? null, baselineEval: baselineEval ?? null,
      candidateRun, candidateEval, comparison,
      currentVersionId: candidateVersion?.id ?? null,
      iterationCount: 1,
    };
  }
  if (fixProposal) {
    const instructions = typeof fixProposal.proposed_changes[0]?.change === "string"
      ? fixProposal.proposed_changes[0].change as string
      : "";
    return {
      ...base, step: "fix",
      baselineRun: baselineRun ?? null, baselineEval: baselineEval ?? null,
      fix: { proposed_instructions: instructions, rationale: fixProposal.rationale ?? "" },
      fixEdited: instructions,
    };
  }
  if (baselineRun && baselineEval && (failurePackets?.length ?? 0) > 0) {
    return { ...base, step: "failure", baselineRun, baselineEval };
  }
  if (baselineRun && baselineEval) {
    return { ...base, step: "done", baselineRun, baselineEval };
  }
  return { ...base, step: "run" };
}
