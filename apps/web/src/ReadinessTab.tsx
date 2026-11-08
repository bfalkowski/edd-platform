import { useState } from "react";
import { createGateDecision, createGateDefinition } from "./api";
import { suiteComparisonIsCurrent } from "./suite";
import { SuiteComparisonTable } from "./SuiteComparisonTable";
import { useSuiteResults } from "./useSuiteResults";
import type { AgentDesign, EddFlowState, GateDecision, GateDefinition, SavedTest } from "./types";

type ReadinessTabProps = {
  projectId: string;
  selectedAgent: AgentDesign;
  latestGate: GateDefinition | null;
  latestGateDecision: GateDecision | null;
  eddFlow: EddFlowState;
  savedTests: SavedTest[];
  setGates: (updater: (items: GateDefinition[]) => GateDefinition[]) => void;
  setGateDecisions: (updater: (items: GateDecision[]) => GateDecision[]) => void;
  setError: (message: string | null) => void;
  setActivity: (message: string | null) => void;
  refreshContext: () => Promise<void>;
  refreshReadiness: () => Promise<void>;
};

export function ReadinessTab({
  projectId,
  selectedAgent,
  latestGate,
  latestGateDecision,
  eddFlow,
  savedTests,
  setGates,
  setGateDecisions,
  setError,
  setActivity,
  refreshContext,
  refreshReadiness,
}: ReadinessTabProps) {
  const [isGateBusy, setIsGateBusy] = useState(false);

  async function handleCreatePromotionGate() {
    setError(null);
    setActivity("Creating promotion gate.");
    setIsGateBusy(true);
    try {
      const gate = await createGateDefinition(projectId, selectedAgent.id);
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

  const suiteVersions = [eddFlow.baselineVersion, eddFlow.candidateVersion].filter(
    (version): version is NonNullable<typeof version> => Boolean(version),
  );
  const [suiteResults] = useSuiteResults(
    projectId,
    selectedAgent.id,
    suiteVersions,
    savedTests,
    setError,
  );
  // A suite comparison judges every test, so the gate uses it when there is one,
  // but only while it still matches the saved tests and their latest results.
  const suiteComparison = eddFlow.suiteComparison;
  const suiteRow =
    suiteComparison?.tests?.find((row) => row.scenario_id === eddFlow.scenario?.id) ??
    suiteComparison?.tests?.[0];
  const suiteIsCurrent =
    suiteComparison && eddFlow.baselineVersion && eddFlow.candidateVersion
      ? suiteComparisonIsCurrent(
          suiteComparison,
          suiteResults[eddFlow.baselineVersion.id],
          suiteResults[eddFlow.candidateVersion.id],
        )
      : undefined;
  const gateEvidence = suiteComparison
    ? suiteRow && suiteIsCurrent
      ? { comparison_id: suiteComparison.id, eval_result_id: suiteRow.candidate_eval_result_id }
      : null
    : eddFlow.candidateEval && eddFlow.comparison
      ? { comparison_id: eddFlow.comparison.id, eval_result_id: eddFlow.candidateEval.id }
      : null;

  async function handleRunPromotionGate() {
    if (!latestGate || !gateEvidence) {
      return;
    }
    setError(null);
    setActivity("Running promotion gate.");
    setIsGateBusy(true);
    try {
      const decision = await createGateDecision(projectId, latestGate.id, gateEvidence);
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

  return (
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
          disabled={isGateBusy || !gateEvidence}
        >
          {latestGateDecision ? "Run again" : "Run gate"}
        </button>
      )}
      {suiteComparison && eddFlow.baselineVersion && eddFlow.candidateVersion ? (
        <SuiteComparisonTable
          comparison={suiteComparison}
          savedTests={savedTests}
          baselineLabel={eddFlow.baselineVersion.version_label}
          candidateLabel={eddFlow.candidateVersion.version_label}
          isCurrent={suiteIsCurrent}
          eyebrow="Gate evidence"
        />
      ) : null}
    </section>
  );
}
