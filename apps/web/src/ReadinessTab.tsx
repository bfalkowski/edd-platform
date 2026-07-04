import { useState } from "react";
import { createGateDecision, createGateDefinition } from "./api";
import type { AgentDesign, EddFlowState, GateDecision, GateDefinition } from "./types";

type ReadinessTabProps = {
  projectId: string;
  selectedAgent: AgentDesign;
  latestGate: GateDefinition | null;
  latestGateDecision: GateDecision | null;
  eddFlow: EddFlowState;
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

  async function handleRunPromotionGate() {
    if (!latestGate || !eddFlow.candidateEval || !eddFlow.comparison) {
      return;
    }
    setError(null);
    setActivity("Running promotion gate.");
    setIsGateBusy(true);
    try {
      const decision = await createGateDecision(projectId, latestGate.id, {
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
          disabled={isGateBusy || !eddFlow.candidateEval || !eddFlow.comparison}
        >
          {latestGateDecision ? "Run again" : "Run gate"}
        </button>
      )}
    </section>
  );
}
