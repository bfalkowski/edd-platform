import { PanelRight } from "lucide-react";
import { useEffect, useState } from "react";
import { listRuns } from "./api";
import { artifactRoleLabel, traceUrlFromArtifact } from "./helpers";
import { JudgeReviewPanel } from "./JudgeReviewPanel";
import type { ArtifactRecord, RunRecord } from "./types";

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
  const [runsById, setRunsById] = useState<Map<string, RunRecord>>(new Map());

  useEffect(() => {
    listRuns(projectId, agentId)
      .then((runs) => setRunsById(new Map(runs.map((run) => [run.id, run]))))
      .catch(() => setRunsById(new Map()));
  }, [projectId, agentId, evidenceArtifacts.length]);

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
        {evidenceArtifacts.map((artifact) => {
          const traceUrl = traceUrlFromArtifact(artifact);
          // A run output artifact records its run's id as artifact_id.
          const meta =
            artifact.artifact_type === "RUN_RESULT"
              ? runMeta(runsById.get(artifact.artifact_id))
              : null;
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
  );
}
