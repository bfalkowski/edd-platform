import { PanelRight } from "lucide-react";
import { useEffect, useState } from "react";
import { listEvalResults, listFailurePackets, listRuns } from "./api";
import { evidenceRunIndex, groupEvidence, RUN_PAGE_SIZE } from "./evidenceGroups";
import { artifactRoleLabel, traceUrlFromArtifact } from "./helpers";
import { JudgeReviewPanel } from "./JudgeReviewPanel";
import type { ArtifactRecord, EvalResult, FailurePacket, RunRecord } from "./types";

type EvidenceTabProps = {
  projectId: string;
  agentId: string;
  onReviewed: () => Promise<void>;
  evidenceArtifacts: ArtifactRecord[];
  isLoadingContext: boolean;
  onReviewArtifact: (artifactId: string) => void;
};

/** "claude-haiku-5-5 · 3.2s" for a run output, or null when the run used no model. */
function runMeta(run: RunRecord | undefined): string | null {
  if (!run?.model) {
    return null;
  }
  const seconds = (Date.parse(run.completed_at) - Date.parse(run.started_at)) / 1000;
  return `${run.model} · ${seconds.toFixed(1)}s`;
}

export function EvidenceTab({
  projectId,
  agentId,
  onReviewed,
  evidenceArtifacts,
  isLoadingContext,
  onReviewArtifact,
}: EvidenceTabProps) {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [evalResults, setEvalResults] = useState<EvalResult[]>([]);
  const [failurePackets, setFailurePackets] = useState<FailurePacket[]>([]);
  const [shownRunCount, setShownRunCount] = useState(RUN_PAGE_SIZE);

  useEffect(() => {
    listRuns(projectId, agentId).then(setRuns).catch(() => setRuns([]));
    listEvalResults(projectId).then(setEvalResults).catch(() => setEvalResults([]));
    listFailurePackets(projectId, agentId)
      .then(setFailurePackets)
      .catch(() => setFailurePackets([]));
  }, [projectId, agentId, evidenceArtifacts.length]);

  useEffect(() => setShownRunCount(RUN_PAGE_SIZE), [agentId]);

  const runsById = new Map(runs.map((run) => [run.id, run]));
  const { agentArtifacts, runGroups } = groupEvidence(
    evidenceArtifacts,
    evidenceRunIndex(runs, evalResults, failurePackets),
  );
  const shownRunGroups = runGroups.slice(0, shownRunCount);
  const olderRunCount = runGroups.length - shownRunGroups.length;

  const renderRow = (artifact: ArtifactRecord) => {
    const traceUrl = traceUrlFromArtifact(artifact);
    // A run output artifact records its run's id as artifact_id.
    const meta =
      artifact.artifact_type === "RUN_RESULT" ? runMeta(runsById.get(artifact.artifact_id)) : null;
    return (
      <div className="workflow-evidence-row" key={artifact.id}>
        <button
          className="workflow-evidence-item"
          type="button"
          onClick={() => onReviewArtifact(artifact.id)}
        >
          <span>{artifactRoleLabel(artifact.artifact_type)}</span>
          <strong>{artifact.title}</strong>
          <PanelRight size={17} />
          {meta ? <small className="workflow-evidence-meta">{meta}</small> : null}
        </button>
        {traceUrl ? (
          <a className="workflow-trace-link" href={traceUrl} target="_blank" rel="noreferrer">
            Open trace
          </a>
        ) : null}
      </div>
    );
  };

  return (
    <section className="workflow-evidence-panel workspace-tab-panel">
      <div className="workflow-evidence-header">
        <div>
          <p className="artifact-type">Evidence</p>
          <h3>Proof artifacts</h3>
        </div>
        <span>{evidenceArtifacts.length} saved</span>
      </div>
      <JudgeReviewPanel projectId={projectId} agentId={agentId} onReviewed={onReviewed} />
      <div className="workflow-evidence-list">
        {isLoadingContext ? <p className="muted-copy">Loading evidence...</p> : null}
        {!isLoadingContext && evidenceArtifacts.length === 0 ? (
          <p className="muted-copy">No proof artifacts yet.</p>
        ) : null}
        {agentArtifacts.length > 0 ? (
          <section className="workflow-evidence-group" aria-label="Agent artifacts">
            <h4>Agent</h4>
            {agentArtifacts.map(renderRow)}
          </section>
        ) : null}
        {shownRunGroups.map((group) => (
          <section className="workflow-evidence-group" aria-label="Run evidence" key={group.runId}>
            <h4>
              Run
              <small>{new Date(group.artifacts[0].created_at).toLocaleString()}</small>
            </h4>
            {group.artifacts.map(renderRow)}
          </section>
        ))}
        {olderRunCount > 0 ? (
          <button
            className="secondary-button"
            type="button"
            onClick={() => setShownRunCount((count) => count + RUN_PAGE_SIZE)}
          >
            Show older runs ({olderRunCount} more)
          </button>
        ) : null}
      </div>
    </section>
  );
}
