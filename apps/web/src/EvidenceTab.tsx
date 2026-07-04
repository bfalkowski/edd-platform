import { PanelRight } from "lucide-react";
import { artifactRoleLabel, traceUrlFromArtifact } from "./helpers";
import type { ArtifactRecord } from "./types";

type EvidenceTabProps = {
  evidenceArtifacts: ArtifactRecord[];
  isLoadingContext: boolean;
  onReviewArtifact: (artifactId: string) => void;
};

export function EvidenceTab({ evidenceArtifacts, isLoadingContext, onReviewArtifact }: EvidenceTabProps) {
  return (
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
                onClick={() => onReviewArtifact(artifact.id)}
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
  );
}
