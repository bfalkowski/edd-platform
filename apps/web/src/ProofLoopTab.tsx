import {
  createAgentVersion,
  createComparison,
  createFixProposal,
  createProjectRun,
  createReviewNote,
  diagnoseFailure,
  evaluateRun,
  generateFixProposal,
} from "./api";
import { failurePacketsForEval, renderScenarioInput, testShapeFromSetupContext, testShapeLabels } from "./helpers";
import type {
  AgentDesign,
  ArtifactLink,
  ArtifactRecord,
  EddFlowState,
  EvalResult,
  GeneratedDesignSummary,
  GeneratedToolState,
  ProofLoopCtx,
} from "./types";

const runMode = "live" as const;

const initialProofLoopCtx: ProofLoopCtx = {
  judgeOutputText: null,
  analysisNoteText: "",
  analysisFailureMode: "",
  analysisSeverity: "medium",
  analysisNote: null,
  generatedInstructions: null,
  generatedRationale: "",
};

type ProofLoopTabProps = {
  projectId: string;
  selectedAgent: AgentDesign;
  eddFlow: EddFlowState;
  setEddFlow: (updater: (flow: EddFlowState) => EddFlowState) => void;
  selectedGeneratedDesign: GeneratedDesignSummary | null;
  generatedToolStates: GeneratedToolState[];
  generatedVersionArtifact: ArtifactRecord | undefined;
  generatedScenarioArtifact: ArtifactRecord | undefined;
  generatedContractArtifact: ArtifactRecord | undefined;
  baselineRunArtifact: ArtifactRecord | undefined;
  baselineEvalArtifact: ArtifactRecord | undefined;
  baselineTraceUrl: string | null;
  analysisTargetArtifactId: string;
  failedBaselineChecks: EvalResult["checks"];
  testOutOfSync: boolean;
  currentJudgeMode: "deterministic" | "live";
  proofLoopCtx: ProofLoopCtx;
  setProofLoopCtx: (updater: (ctx: ProofLoopCtx) => ProofLoopCtx) => void;
  isFlowBusy: boolean;
  setIsFlowBusy: (value: boolean) => void;
  isSavingAnalysis: boolean;
  setIsSavingAnalysis: (value: boolean) => void;
  isGeneratingFix: boolean;
  setIsGeneratingFix: (value: boolean) => void;
  isDiagnosing: boolean;
  setIsDiagnosing: (value: boolean) => void;
  activity: string | null;
  error: string | null;
  setError: (message: string | null) => void;
  setActivity: (message: string | null) => void;
  refreshContext: () => Promise<void>;
  onReviewArtifact: (artifactId: string) => Promise<void>;
  setReviewArtifact: (artifact: ArtifactRecord | null) => void;
  setReviewLinks: (links: ArtifactLink[]) => void;
  onOpenNewScenarioEditor: () => void;
  onOpenScenarioEditor: () => void;
  onViewEvidence: () => void;
};

export function ProofLoopTab({
  projectId,
  selectedAgent,
  eddFlow,
  setEddFlow,
  selectedGeneratedDesign,
  generatedToolStates,
  generatedVersionArtifact,
  generatedScenarioArtifact,
  generatedContractArtifact,
  baselineRunArtifact,
  baselineEvalArtifact,
  baselineTraceUrl,
  analysisTargetArtifactId,
  failedBaselineChecks,
  testOutOfSync,
  currentJudgeMode,
  proofLoopCtx,
  setProofLoopCtx,
  isFlowBusy,
  setIsFlowBusy,
  isSavingAnalysis,
  setIsSavingAnalysis,
  isGeneratingFix,
  setIsGeneratingFix,
  isDiagnosing,
  setIsDiagnosing,
  activity,
  error,
  setError,
  setActivity,
  refreshContext,
  onReviewArtifact,
  setReviewArtifact,
  setReviewLinks,
  onOpenNewScenarioEditor,
  onOpenScenarioEditor,
  onViewEvidence,
}: ProofLoopTabProps) {
  const {
    judgeOutputText,
    analysisNoteText,
    analysisFailureMode,
    analysisSeverity,
    analysisNote,
    generatedInstructions,
    generatedRationale,
  } = proofLoopCtx;

  async function reviewFirstArtifact(artifactIds: string[]) {
    if (artifactIds[0]) {
      await onReviewArtifact(artifactIds[0]);
    }
  }

  async function handleRunBaseline() {
    if (!eddFlow.baselineVersion || !eddFlow.scenario || !eddFlow.contract) {
      return;
    }
    setError(null);
    setActivity(`Running ${eddFlow.baselineVersion.version_label}.`);
    setIsFlowBusy(true);
    try {
      const baselineRun = await createProjectRun(projectId, {
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
    if (!eddFlow.baselineRun) {
      return;
    }
    setError(null);
    setActivity("Checking the current answer.");
    setIsFlowBusy(true);
    try {
      const baselineEval = await evaluateRun(projectId, eddFlow.baselineRun.id, currentJudgeMode);
      setEddFlow((flow) => ({ ...flow, baselineEval }));
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

  async function handleDiagnoseFailure() {
    if (!eddFlow.baselineEval) return;
    setError(null);
    setIsDiagnosing(true);
    setActivity("Analyzing failure evidence...");
    try {
      const result = await diagnoseFailure(projectId, eddFlow.baselineEval.id);
      setProofLoopCtx((ctx) => ({
        ...ctx,
        judgeOutputText: result.judge_output,
        ...(result.failure_mode ? { analysisFailureMode: result.failure_mode } : {}),
        ...(result.severity ? { analysisSeverity: result.severity } : {}),
        ...(result.review_note ? { analysisNoteText: result.review_note } : {}),
      }));
      setActivity(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to diagnose failure.");
      setActivity(null);
    } finally {
      setIsDiagnosing(false);
    }
  }

  async function handleSaveAnalysisNote() {
    if (!eddFlow.baselineEval || !analysisTargetArtifactId) {
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
      const note = await createReviewNote(projectId, {
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
      setProofLoopCtx((ctx) => ({ ...ctx, analysisNote: note }));
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

  async function handleGenerateFix() {
    const currentFailurePackets = failurePacketsForEval(eddFlow, eddFlow.baselineEval?.id);
    if (!eddFlow.baselineVersion || !eddFlow.contract) {
      return;
    }
    setError(null);
    setActivity("Generating fix from failure evidence...");
    setIsGeneratingFix(true);
    try {
      const result = await generateFixProposal(
        projectId,
        selectedAgent.id,
        eddFlow.baselineVersion.id,
        currentFailurePackets,
        eddFlow.contract.id,
      );
      setProofLoopCtx((ctx) => ({
        ...ctx,
        generatedInstructions: result.proposed_instructions,
        generatedRationale: result.rationale,
      }));
      setActivity("Fix generated. Review and confirm to create v" +
        ((eddFlow.baselineVersion.version_label.match(/\d+/)?.[0] ?? 0) as number + 1) + ".");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to generate fix.");
      setActivity(null);
    } finally {
      setIsGeneratingFix(false);
    }
  }

  async function handleCreateFixProposal() {
    const currentFailurePackets = failurePacketsForEval(eddFlow, eddFlow.baselineEval?.id);
    if (!eddFlow.baselineVersion || !eddFlow.contract || !generatedInstructions) {
      return;
    }
    setError(null);
    setActivity("Saving fix proposal.");
    setIsFlowBusy(true);
    try {
      const fixProposal = await createFixProposal(
        projectId,
        selectedAgent.id,
        eddFlow.baselineVersion.id,
        currentFailurePackets,
        eddFlow.contract.id,
        generatedInstructions,
        generatedRationale,
      );
      setEddFlow((flow) => ({ ...flow, fixProposal }));
      setActivity("Fix proposal saved. Create the next version to apply it.");
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
    if (!eddFlow.baselineVersion || !eddFlow.fixProposal) {
      return;
    }
    const storedChange = eddFlow.fixProposal.proposed_changes[0]?.change;
    const instructionsToUse: string | null =
      generatedInstructions ?? (typeof storedChange === "string" ? storedChange : null);
    if (!instructionsToUse) return;
    setError(null);
    setActivity("Creating the next version.");
    setIsFlowBusy(true);
    try {
      const candidateVersion = await createAgentVersion(projectId, selectedAgent.id, {
        parent_version_id: eddFlow.baselineVersion.id,
        source_fix_proposal_id: eddFlow.fixProposal.id,
        instructions: instructionsToUse,
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
    if (!eddFlow.candidateVersion || !eddFlow.scenario || !eddFlow.contract) {
      return;
    }
    setError(null);
    setActivity(`Running ${eddFlow.candidateVersion.version_label}.`);
    setIsFlowBusy(true);
    try {
      const candidateRun = await createProjectRun(projectId, {
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
    if (!eddFlow.candidateRun) {
      return;
    }
    setError(null);
    setActivity("Checking the new answer.");
    setIsFlowBusy(true);
    try {
      const candidateEval = await evaluateRun(projectId, eddFlow.candidateRun.id, currentJudgeMode);
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
    if (!eddFlow.baselineRun || !eddFlow.candidateRun || !eddFlow.contract) {
      return;
    }
    setError(null);
    setActivity("Comparing version evidence.");
    setIsFlowBusy(true);
    try {
      const comparison = await createComparison(
        projectId,
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

  function handleContinueImprovement() {
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
    setProofLoopCtx(() => initialProofLoopCtx);
    setActivity(`Continuing from ${eddFlow.candidateVersion.version_label}.`);
    setReviewArtifact(null);
    setReviewLinks([]);
  }

  const baselinePassed = eddFlow.baselineEval?.passed === true;
  const improvementNeeded = eddFlow.baselineEval?.passed === false;
  const showFailureAnalysis = improvementNeeded && Boolean(eddFlow.baselineEval);
  const showNextActionPanel = Boolean(eddFlow.contract) && !(showFailureAnalysis && !analysisNote);
  const baselineLabel = eddFlow.baselineVersion?.version_label ?? "current";
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
        onClick: onOpenNewScenarioEditor,
        disabled: isFlowBusy,
      };
    }
    if (testOutOfSync) {
      return {
        eyebrow: "Next action",
        title: "Update the test",
        detail: "The saved test does not match the scenario or eval method shown above.",
        label: "Edit test",
        onClick: onOpenScenarioEditor,
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
    if (!eddFlow.fixProposal && eddFlow.failurePackets.length > 0 && !generatedInstructions) {
      return {
        eyebrow: "Next action",
        title: "Generate a fix",
        detail: "Claude will read the failure evidence and propose improved instructions.",
        label: "Generate fix",
        onClick: handleGenerateFix,
        disabled: isFlowBusy || isGeneratingFix,
      };
    }
    if (!eddFlow.fixProposal && generatedInstructions) {
      return {
        eyebrow: "Next action",
        title: "Confirm and save fix",
        detail: "Review the proposed instructions below, then save to lock them in.",
        label: "Save fix proposal",
        onClick: handleCreateFixProposal,
        disabled: isFlowBusy || !generatedInstructions.trim(),
      };
    }
    if (!eddFlow.candidateVersion && eddFlow.fixProposal) {
      return {
        eyebrow: "Next action",
        title: "Create the next version",
        detail: "Apply the saved fix to create a new agent version.",
        label: "Create version",
        onClick: handleCreateCandidate,
        disabled: isFlowBusy || (!generatedInstructions && !eddFlow.fixProposal?.proposed_changes[0]?.change),
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
      const candidatePassed = eddFlow.candidateEval.passed === true;
      if (candidatePassed) {
        return {
          eyebrow: "Iteration complete — passed",
          title: eddFlow.comparison.summary,
          detail: "The new version passed the success criteria. You can promote it or keep the evidence as-is.",
          label: "Done",
          onClick: undefined,
          disabled: true,
        };
      }
      return {
        eyebrow: "Iteration complete — still failing",
        title: eddFlow.comparison.summary,
        detail: "The new version still fails. Name the remaining failure below to propose another targeted fix.",
        label: "Try another fix",
        onClick: handleContinueImprovement,
        disabled: isFlowBusy,
      };
    }
    return {
      eyebrow: "Next action",
      title: "Continue the proof loop",
      detail: "",
      label: "Continue",
      onClick: undefined,
      disabled: true,
    };
  })();

  return (
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
            <button className="secondary-button" type="button" onClick={onOpenNewScenarioEditor}>
              New test
            </button>
          ) : null}
          {hasSavedScenarioTest ? (
            <button className="secondary-button" type="button" onClick={onOpenScenarioEditor}>
              {selectedGeneratedDesign ? "Edit generated test" : "Edit test"}
            </button>
          ) : null}
          {hasSavedScenarioTest ? (
            <button
              className="secondary-button compact-button"
              type="button"
              onClick={onViewEvidence}
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
              <span>Run: Live Anthropic</span>
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
      {generatedInstructions !== null && !eddFlow.fixProposal ? (
        <div className="generated-fix-panel">
          <div className="generated-fix-header">
            <p className="artifact-type">Generated fix</p>
            <h4>Proposed instructions for next version</h4>
            <p>Claude wrote these based on the failure evidence. Edit before saving.</p>
          </div>
          <label className="generated-fix-label">
            Proposed instructions
            <textarea
              className="generated-fix-textarea"
              value={generatedInstructions}
              onChange={(e) => setProofLoopCtx((ctx) => ({ ...ctx, generatedInstructions: e.target.value }))}
              rows={10}
            />
          </label>
          {generatedRationale ? (
            <p className="generated-fix-rationale">{generatedRationale}</p>
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
        <div className={analysisNote ? "failure-analysis-panel analysis-complete" : "failure-analysis-panel"}>
          <div className="failure-analysis-header">
            <div className="failure-step-eyebrow">
              {analysisNote ? (
                <span className="step-badge step-badge--done">✓ Analysis saved</span>
              ) : (
                <span className="step-badge step-badge--required">Required — complete before proposing a fix</span>
              )}
            </div>
            <h4>{analysisNote ? "Failure named" : "Name this failure"}</h4>
            {!analysisNote ? (
              <p className="failure-analysis-instruction">
                Review the evidence below, then fill in the form or click Auto-diagnose to let Claude pre-fill it.
              </p>
            ) : null}
          </div>
          <div className="failure-analysis-body">
            <div className="failure-analysis-summary">
              <p className="compact-section-label">Failed checks</p>
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
              {judgeOutputText ? (
                <details className="judge-output-details">
                  <summary>Judge reasoning</summary>
                  <p className="judge-output-text">{judgeOutputText}</p>
                </details>
              ) : null}
              {!analysisNote && !isDiagnosing ? (
                <button
                  className="secondary-button auto-diagnose-button"
                  type="button"
                  onClick={handleDiagnoseFailure}
                  disabled={isDiagnosing || isFlowBusy}
                >
                  Auto-diagnose
                </button>
              ) : null}
              {isDiagnosing ? <p className="activity-text">Analyzing failure evidence...</p> : null}
            </div>
            <div className="failure-analysis-form">
              <div className="analysis-field-row">
                <label className="compact-label">
                  <span>Failure mode</span>
                  <input
                    value={analysisFailureMode}
                    onChange={(event) => setProofLoopCtx((ctx) => ({ ...ctx, analysisFailureMode: event.target.value }))}
                    placeholder="e.g. missed rollback recommendation"
                    disabled={!!analysisNote}
                  />
                </label>
                <label className="compact-label">
                  <span>Severity</span>
                  <select
                    value={analysisSeverity}
                    onChange={(event) => setProofLoopCtx((ctx) => ({ ...ctx, analysisSeverity: event.target.value }))}
                    disabled={!!analysisNote}
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </label>
              </div>
              <label className="compact-label">
                <span>Review note <span className="required-marker">*</span></span>
                <textarea
                  value={analysisNoteText}
                  onChange={(event) => setProofLoopCtx((ctx) => ({ ...ctx, analysisNoteText: event.target.value }))}
                  placeholder="The response did not satisfy the success criteria because…"
                  disabled={!!analysisNote}
                />
              </label>
              {activity ? <p className="activity-text">{activity}</p> : null}
              {error ? <p className="error-text">{error}</p> : null}
              {!analysisNote ? (
                <div className="analysis-action-row">
                  <button
                    className="primary-button"
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
                  <span>Then: propose a targeted fix →</span>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
      {eddFlow.comparison ? (
        <div className={
          eddFlow.candidateEval?.passed
            ? "comparison-summary comparison-summary--passed"
            : "comparison-summary comparison-summary--failed"
        }>
          <div className="comparison-outcome">
            <span className="comparison-outcome-badge">
              {eddFlow.candidateEval?.passed ? "✓ Passed" : "✗ Still failing"}
            </span>
            <strong>{eddFlow.comparison.summary}</strong>
          </div>
          <span>
            Fixed {eddFlow.comparison.fixed_failure_packet_ids.length} · Remaining{" "}
            {eddFlow.comparison.remaining_failure_packet_ids.length} · New{" "}
            {eddFlow.comparison.new_failure_packet_ids.length}
          </span>
        </div>
      ) : null}
    </section>
  );
}
