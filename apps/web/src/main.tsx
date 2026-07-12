import { PanelRight, Play, Search, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { Wizard, WizardState, fetchAgentWizardState } from "./Wizard";
import { Sidebar } from "./Sidebar";
import { AgentTab } from "./AgentTab";
import { EvidenceTab } from "./EvidenceTab";
import { ReadinessTab } from "./ReadinessTab";
import { ErrorAnalysisTab } from "./ErrorAnalysisTab";
import { ProofLoopTab } from "./ProofLoopTab";
import type {
  AgentDesign,
  AgentSuggestion,
  ArtifactLink,
  ArtifactRecord,
  ContextPack,
  EddFlowState,
  EvalMethod,
  FailureMode,
  GateDecision,
  GateDefinition,
  GeneratedDesignSummary,
  Project,
  ProofLoopCtx,
  ReviewAnnotation,
  ReviewCorpus,
  ReviewItem,
  ReviewSamplingPlan,
  Scenario,
  ServiceStatus,
  TestShape,
  ToolDefinition,
} from "./types";
import {
  buildContextPack,
  createAgentDesign,
  createAgentDesignFromOutcome,
  createAgentVersion,
  createEvalContract,
  createScenario,
  createToolDefinition,
  deleteAgentDesign,
  deleteToolDefinition,
  evaluateArtifact,
  getReviewSamplingPlan,
  hydrateEddFlow,
  listAgentDesigns,
  listAgentSuggestions,
  listFailureModes,
  listGateDecisions,
  listGateDefinitions,
  listProjects,
  listReviewAnnotations,
  listReviewCorpora,
  listReviewItems,
  listServices,
  listToolDefinitions,
  loadArtifact,
  loadArtifactLinks,
  runAgentDesign,
  updateAgentDesignToolAllowlist,
  updateFixProposal,
  updateToolDefinitionStatus,
} from "./api";
import {
  defaultInputForTestShape,
  defaultRubricForTestShape,
  defaultRubricText,
  defaultScenarioInput,
  defaultToolInputSchema,
  defaultToolOutputSchema,
  artifactRoleLabel,
  externalRefDetail,
  externalRefLabel,
  inferExpectedResponse,
  isDefaultRubricText,
  isDefaultTestInput,
  parseArtifactFields,
  parseJsonObject,
  proofArtifactIds,
  proofRunIds,
  relatedEvidenceLabel,
  testShapeFromSetupContext,
  testShapeInputHelp,
  testShapeInputLabels,
  toolImplementationKey,
  traceUrlFromArtifact,
  wizardStateFromFlow,
} from "./helpers";

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
  const runMode = "live" as const;
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
  const initialProofLoopCtx: ProofLoopCtx = {
    judgeOutputText: null,
    analysisNoteText: "",
    analysisFailureMode: "",
    analysisSeverity: "medium",
    analysisNote: null,
    generatedInstructions: null,
    generatedRationale: "",
  };
  const [proofLoopCtx, setProofLoopCtx] = useState<ProofLoopCtx>(initialProofLoopCtx);
  // Destructure for use in JSX / handlers without touching call sites
  const {
    judgeOutputText,
    analysisNoteText,
    analysisFailureMode,
    analysisSeverity,
    analysisNote,
    generatedInstructions,
    generatedRationale,
  } = proofLoopCtx;
  // Busy-flag states stay separate (they are not phase data)
  const [isSavingAnalysis, setIsSavingAnalysis] = useState(false);
  const [isGeneratingFix, setIsGeneratingFix] = useState(false);
  const [isDiagnosing, setIsDiagnosing] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardResumeState, setWizardResumeState] = useState<Partial<WizardState> | undefined>(undefined);
  const [reviewCorpora, setReviewCorpora] = useState<ReviewCorpus[]>([]);
  const [reviewItems, setReviewItems] = useState<ReviewItem[]>([]);
  const [reviewAnnotations, setReviewAnnotations] = useState<ReviewAnnotation[]>([]);
  const [failureModes, setFailureModes] = useState<FailureMode[]>([]);
  const [agentSuggestions, setAgentSuggestions] = useState<AgentSuggestion[]>([]);
  const [samplingPlan, setSamplingPlan] = useState<ReviewSamplingPlan | null>(null);
  const [selectedReviewItemId, setSelectedReviewItemId] = useState<string | null>(null);
  const [samplingPlanExpanded, setSamplingPlanExpanded] = useState(false);
  const [fixEditText, setFixEditText] = useState("");
  const [isSavingFix, setIsSavingFix] = useState(false);

  /** Reset all proof-loop ephemeral context to initial values (single canonical reset). */
  function resetProofLoopCtx() {
    setProofLoopCtx(initialProofLoopCtx);
  }

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
  const [updatingTools, setUpdatingTools] = useState(false);
  const [isDraftingAgent, setIsDraftingAgent] = useState(false);
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
          if (items.length === 0) {
            setWizardOpen(true);
          } else {
            setSelectedId(items[0]?.id ?? null);
          }
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
  const reviewTraceUrl = reviewArtifact ? traceUrlFromArtifact(reviewArtifact) : null;
  const reviewFields = reviewArtifact ? parseArtifactFields(reviewArtifact.body) : [];
  const reviewExternalRefs = reviewArtifact?.external_refs ?? [];
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
    plan: ReviewSamplingPlan | null;
  }> {
    if (!agent) {
      return { corpora: [], items: [], annotations: [], modes: [], suggestions: [], plan: null };
    }
    const [corpora, modes] = await Promise.all([
      listReviewCorpora(projectId, agent.id),
      listFailureModes(projectId, agent.id),
    ]);
    const corpus = corpora[0];
    if (!corpus) {
      return { corpora, items: [], annotations: [], modes, suggestions: [], plan: null };
    }
    const [items, annotations, suggestions, plan] = await Promise.all([
      listReviewItems(projectId, corpus.id),
      listReviewAnnotations(projectId, corpus.id),
      listAgentSuggestions(projectId, corpus.id),
      getReviewSamplingPlan(projectId, corpus.id),
    ]);
    return { corpora, items, annotations, modes, suggestions, plan };
  }

  function applyDiscoveryState(state: {
    corpora: ReviewCorpus[];
    items: ReviewItem[];
    annotations: ReviewAnnotation[];
    modes: FailureMode[];
    suggestions: AgentSuggestion[];
    plan: ReviewSamplingPlan | null;
  }) {
    setReviewCorpora(state.corpora);
    setReviewItems(state.items);
    setReviewAnnotations(state.annotations);
    setFailureModes(state.modes);
    setAgentSuggestions(state.suggestions);
    setSamplingPlan(state.plan);
    setSelectedReviewItemId((currentId) =>
      currentId && state.items.some((item) => item.id === currentId)
        ? currentId
        : state.items[0]?.id ?? null,
    );
  }

  async function refreshDiscoveryState() {
    if (!project) {
      applyDiscoveryState({
        corpora: [],
        items: [],
        annotations: [],
        modes: [],
        suggestions: [],
        plan: null,
      });
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
    resetProofLoopCtx();
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
      const drafted = await createAgentDesignFromOutcome(project.id, outcome, name.trim() || undefined);
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

  function handleToggleSidebar() {
    setSidebarOpen((value) => !value);
  }

  function handleNewAgentClick() {
    setSelectedId(null);
    setGeneratedDesign(null);
    setReviewArtifact(null);
    setReviewLinks([]);
    setToolsPanelOpen(false);
    setScratchPanelOpen(false);
    setActivity(null);
    setWorkspaceTab("proof");
    setWizardResumeState(undefined);
    setWizardOpen(true);
  }

  function handleSelectAgent(agent: AgentDesign) {
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
    if (project) {
      Promise.all([fetchAgentWizardState(project.id, agent.id), hydrateEddFlow(project.id, agent)])
        .then(([agentState, flow]) => {
          const resumeState = wizardStateFromFlow(project.id, agentState, flow);
          if (resumeState.step === "done") {
            // Agent passed — show workspace, not wizard
            setWizardOpen(false);
          } else {
            // Mid-flow — reopen wizard at the right step
            setWizardResumeState(resumeState);
            setWizardOpen(true);
          }
        })
        .catch(() => {
          // Agent exists but has no wizard state yet — show workspace
          setWizardOpen(false);
        });
    }
  }

  function handleToggleAgentMenu(agentId: string) {
    setOpenAgentMenuId((current) => (current === agentId ? null : agentId));
  }

  function handleTryScenario(agent: AgentDesign) {
    setSelectedId(agent.id);
    setGeneratedDesign((current) => (current?.agentId === agent.id ? current : null));
    setScratchPanelOpen(true);
    setReviewArtifact(null);
    setReviewLinks([]);
    setToolsPanelOpen(false);
    setScenarioEditorOpen(false);
    setOpenAgentMenuId(null);
  }

  function handleRequestDeleteAgent(agent: AgentDesign) {
    setDeleteCandidate(agent);
    setOpenAgentMenuId(null);
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

  async function handleDeleteTool(tool: ToolDefinition) {
    if (!project) {
      return;
    }
    if (!window.confirm(`Delete tool "${tool.name}"? This cannot be undone.`)) {
      return;
    }
    setError(null);
    setUpdatingTools(true);
    try {
      await deleteToolDefinition(project.id, tool.id);
      setTools((items) => items.filter((item) => item.id !== tool.id));
      if (selectedAgent) {
        setAgents((items) =>
          items.map((agent) =>
            agent.id === selectedAgent.id
              ? { ...agent, allowed_tool_names: agent.allowed_tool_names.filter((n) => n !== tool.name) }
              : agent,
          ),
        );
      }
      setActivity(`Deleted tool: ${tool.name}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete tool.");
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
      resetProofLoopCtx();
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

  return (
    <div
      className={[
        sidebarOpen ? "app-shell" : "app-shell sidebar-collapsed",
        reviewArtifact || toolsPanelOpen || scratchPanelOpen || scenarioEditorOpen ? "review-open" : "",
      ].join(" ")}
    >
      <Sidebar
        sidebarOpen={sidebarOpen}
        onToggleSidebar={handleToggleSidebar}
        projectName={project?.name ?? "EDD Platform"}
        wizardOpen={wizardOpen}
        selectedAgent={selectedAgent}
        onNewAgent={handleNewAgentClick}
        services={services}
        isLoading={isLoading}
        agents={agents}
        selectedId={selectedId}
        onSelectAgent={handleSelectAgent}
        openAgentMenuId={openAgentMenuId}
        onToggleAgentMenu={handleToggleAgentMenu}
        onTryScenario={handleTryScenario}
        onRequestDeleteAgent={handleRequestDeleteAgent}
      />

      <main className="workspace">
        {!selectedAgent ? (
          <header className="topbar">
            <div>
              <h1>New agent</h1>
            </div>
          </header>
        ) : null}

        <section className={selectedAgent && !wizardOpen ? "canvas canvas-workspace" : "canvas"}>
          {wizardOpen || !selectedAgent ? (
            <Wizard
              projectId={project?.id ?? "project_default"}
              resumeState={wizardResumeState}
              onAgentCreated={(agentId) => {
                // refresh sidebar without closing wizard — wizard continues
                if (project) {
                  listAgentDesigns(project.id).then((updated) => {
                    setAgents(updated);
                  });
                }
              }}
              onDone={(agentId) => {
                setWizardOpen(false);
                if (project) {
                  listAgentDesigns(project.id).then((updated) => {
                    setAgents(updated);
                    setSelectedId(agentId);
                    setWorkspaceTab("proof");
                  });
                }
              }}
            />
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
              </div>

              {workspaceTab === "agent" ? (
                <AgentTab
                  projectId={project?.id ?? "project_default"}
                  selectedAgent={selectedAgent}
                  approvedTools={approvedTools}
                  draftTools={draftTools}
                  enabledToolDefinitions={enabledToolDefinitions}
                  generatedToolStates={generatedToolStates}
                  activity={activity}
                  error={error}
                  onAgentUpdated={(updated) =>
                    setAgents((items) => items.map((agent) => (agent.id === updated.id ? updated : agent)))
                  }
                  setError={setError}
                  setActivity={setActivity}
                  onManageTools={() => {
                    setToolsPanelOpen(true);
                    setReviewArtifact(null);
                    setReviewLinks([]);
                    setScratchPanelOpen(false);
                    setScenarioEditorOpen(false);
                  }}
                />
              ) : null}

              {workspaceTab === "proof" ? (
                <ProofLoopTab
                  projectId={project?.id ?? "project_default"}
                  selectedAgent={selectedAgent}
                  eddFlow={eddFlow}
                  setEddFlow={setEddFlow}
                  selectedGeneratedDesign={selectedGeneratedDesign}
                  generatedToolStates={generatedToolStates}
                  generatedVersionArtifact={generatedVersionArtifact}
                  generatedScenarioArtifact={generatedScenarioArtifact}
                  generatedContractArtifact={generatedContractArtifact}
                  baselineRunArtifact={baselineRunArtifact}
                  baselineEvalArtifact={baselineEvalArtifact}
                  baselineTraceUrl={baselineTraceUrl}
                  analysisTargetArtifactId={analysisTargetArtifactId}
                  failedBaselineChecks={failedBaselineChecks}
                  testOutOfSync={testOutOfSync}
                  currentJudgeMode={currentJudgeMode}
                  proofLoopCtx={proofLoopCtx}
                  setProofLoopCtx={setProofLoopCtx}
                  isFlowBusy={isFlowBusy}
                  setIsFlowBusy={setIsFlowBusy}
                  isSavingAnalysis={isSavingAnalysis}
                  setIsSavingAnalysis={setIsSavingAnalysis}
                  isGeneratingFix={isGeneratingFix}
                  setIsGeneratingFix={setIsGeneratingFix}
                  isDiagnosing={isDiagnosing}
                  setIsDiagnosing={setIsDiagnosing}
                  activity={activity}
                  error={error}
                  setError={setError}
                  setActivity={setActivity}
                  refreshContext={refreshContext}
                  onReviewArtifact={handleReviewArtifact}
                  setReviewArtifact={setReviewArtifact}
                  setReviewLinks={setReviewLinks}
                  onOpenNewScenarioEditor={openNewScenarioEditor}
                  onOpenScenarioEditor={openScenarioEditor}
                  onViewEvidence={() => setWorkspaceTab("evidence")}
                />
              ) : null}

              {workspaceTab === "error-analysis" ? (
                <ErrorAnalysisTab
                  projectId={project?.id ?? "project_default"}
                  selectedAgent={selectedAgent}
                  activeReviewCorpus={activeReviewCorpus}
                  reviewItems={reviewItems}
                  reviewAnnotations={reviewAnnotations}
                  failureModes={failureModes}
                  agentSuggestions={agentSuggestions}
                  selectedReviewItemId={selectedReviewItemId}
                  setSelectedReviewItemId={setSelectedReviewItemId}
                  error={error}
                  evidenceArtifacts={evidenceArtifacts}
                  setError={setError}
                  setActivity={setActivity}
                  refreshContext={refreshContext}
                  refreshDiscoveryState={refreshDiscoveryState}
                />
              ) : null}

              {workspaceTab === "evidence" ? (
                <EvidenceTab
                  evidenceArtifacts={evidenceArtifacts}
                  isLoadingContext={isLoadingContext}
                  onReviewArtifact={handleReviewArtifact}
                />
              ) : null}

              {workspaceTab === "readiness" ? (
                <ReadinessTab
                  projectId={project?.id ?? "project_default"}
                  selectedAgent={selectedAgent}
                  latestGate={latestGate}
                  latestGateDecision={latestGateDecision}
                  eddFlow={eddFlow}
                  setGates={setGates}
                  setGateDecisions={setGateDecisions}
                  setError={setError}
                  setActivity={setActivity}
                  refreshContext={refreshContext}
                  refreshReadiness={refreshReadiness}
                />
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
                    <div className="tool-marketplace-item-row" key={tool.id}>
                      <button
                        className={isAllowed ? "tool-marketplace-item active" : "tool-marketplace-item"}
                        type="button"
                        onClick={() => handleToggleTool(tool.name)}
                        disabled={updatingTools}
                        aria-pressed={isAllowed}
                      >
                        <span>{isAllowed ? "Enabled" : "Available"}</span>
                        <strong>{tool.name}</strong>
                        <small>{tool.description}</small>
                      </button>
                      <button
                        className="tool-delete-button"
                        type="button"
                        title="Delete tool"
                        disabled={updatingTools}
                        onClick={() => handleDeleteTool(tool)}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
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
                  <div className="tool-marketplace-item-row" key={tool.id}>
                    <button
                      className="tool-marketplace-item draft"
                      type="button"
                      onClick={() => handleApproveAndEnableTool(tool)}
                      disabled={updatingTools}
                    >
                      <span>Draft</span>
                      <strong>{tool.name}</strong>
                      <small>{tool.description}</small>
                      <em>Approve and assign</em>
                    </button>
                    <button
                      className="tool-delete-button"
                      type="button"
                      title="Delete tool"
                      disabled={updatingTools}
                      onClick={() => handleDeleteTool(tool)}
                    >
                      ×
                    </button>
                  </div>
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
            {reviewExternalRefs.length > 0 ? (
              <section>
                <h3>External evidence</h3>
                <ul className="external-ref-list">
                  {reviewExternalRefs.map((ref) => (
                    <li key={`${ref.provider}:${ref.ref_type}:${ref.external_id}`}>
                      <div>
                        <strong>{externalRefLabel(ref)}</strong>
                        <span>{externalRefDetail(ref)}</span>
                      </div>
                      {ref.url ? (
                        <a
                          className="secondary-button external-ref-link"
                          href={ref.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {ref.ref_type === "trace" ? "Open trace" : "Open"}
                        </a>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
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
