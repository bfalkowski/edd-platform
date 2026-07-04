import { useState } from "react";
import {
  createAgentSuggestion,
  createReviewAnnotation,
  createReviewCorpus,
  createReviewItem,
  syncLangfuseComments,
  updateAgentSuggestionStatus,
  updateReviewAnnotation,
} from "./api";
import { traceUrlFromArtifact } from "./helpers";
import type {
  AgentDesign,
  AgentSuggestion,
  ArtifactRecord,
  FailureMode,
  ReviewAnnotation,
  ReviewCorpus,
  ReviewItem,
} from "./types";

type ErrorAnalysisTabProps = {
  projectId: string;
  selectedAgent: AgentDesign;
  activeReviewCorpus: ReviewCorpus | null;
  reviewItems: ReviewItem[];
  reviewAnnotations: ReviewAnnotation[];
  failureModes: FailureMode[];
  agentSuggestions: AgentSuggestion[];
  selectedReviewItemId: string | null;
  setSelectedReviewItemId: (value: string | null) => void;
  error: string | null;
  evidenceArtifacts: ArtifactRecord[];
  setError: (message: string | null) => void;
  setActivity: (message: string | null) => void;
  refreshContext: () => Promise<void>;
  refreshDiscoveryState: () => Promise<void>;
};

export function ErrorAnalysisTab({
  projectId,
  selectedAgent,
  activeReviewCorpus,
  reviewItems,
  reviewAnnotations,
  failureModes,
  agentSuggestions,
  selectedReviewItemId,
  setSelectedReviewItemId,
  error,
  evidenceArtifacts,
  setError,
  setActivity,
  refreshContext,
  refreshDiscoveryState,
}: ErrorAnalysisTabProps) {
  const [isDiscoveryBusy, setIsDiscoveryBusy] = useState(false);
  const [discoveryStep, setDiscoveryStep] = useState<"corpus" | "review" | "confirm" | "done">(
    "corpus",
  );
  const [showDiscoveryIntro, setShowDiscoveryIntro] = useState(
    () => typeof window !== "undefined" && !window.localStorage.getItem("edd.discoveryIntroDismissed"),
  );
  const [syncResult, setSyncResult] = useState<{ imported: number } | null>(null);

  const selectedReviewItem =
    reviewItems.find((item) => item.id === selectedReviewItemId) ?? reviewItems[0] ?? null;
  const reviewedItemCount = reviewItems.filter((item) => item.status === "reviewed").length;
  const acceptedAnnotationCount = reviewAnnotations.filter(
    (annotation) => annotation.status === "accepted",
  ).length;

  function dismissDiscoveryIntro() {
    setShowDiscoveryIntro(false);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("edd.discoveryIntroDismissed", "1");
    }
  }

  async function ensureReviewCorpus(): Promise<ReviewCorpus> {
    if (activeReviewCorpus) {
      return activeReviewCorpus;
    }
    return createReviewCorpus(projectId, selectedAgent.id, `${selectedAgent.name} review corpus`);
  }

  async function handleCreateReviewCorpus() {
    setError(null);
    setActivity("Creating review corpus.");
    setIsDiscoveryBusy(true);
    try {
      await createReviewCorpus(projectId, selectedAgent.id, `${selectedAgent.name} review corpus`);
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
    const reviewableArtifactTypes = new Set(["RUN_RESULT", "TRACE_REF", "EVAL_RESULT", "JUDGE_OUTPUT"]);
    const reviewableArtifacts = evidenceArtifacts.filter(
      (artifact) =>
        artifact.agent_design_id === selectedAgent.id &&
        reviewableArtifactTypes.has(artifact.artifact_type) &&
        !artifact.source.includes(":mock"),
    );
    if (reviewableArtifacts.length === 0) {
      setError("Run a live agent before adding evidence to the review corpus — mock runs aren't reviewed.");
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
          createReviewItem(projectId, {
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

  async function handleSyncLangfuseComments() {
    if (!activeReviewCorpus) return;
    setError(null);
    setSyncResult(null);
    setIsDiscoveryBusy(true);
    try {
      const result = await syncLangfuseComments(projectId, activeReviewCorpus.id);
      await refreshDiscoveryState();
      setSyncResult({ imported: result.imported_count });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sync Langfuse comments.");
    } finally {
      setIsDiscoveryBusy(false);
    }
  }

  async function handleCreateSuggestion() {
    if (!selectedReviewItem) {
      return;
    }
    setError(null);
    setActivity("Creating suggestion.");
    setIsDiscoveryBusy(true);
    try {
      const mode = failureModes[0] ?? null;
      await createAgentSuggestion(projectId, {
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
    setError(null);
    setIsDiscoveryBusy(true);
    try {
      await updateAgentSuggestionStatus(projectId, suggestion.id, status);
      if (status === "accepted") {
        await createReviewAnnotation(projectId, {
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

  return (
    <section className="error-analysis-workspace workspace-tab-panel discovery-wizard">
      <div className="error-analysis-intro">
        <div>
          <p className="artifact-type">Error analysis</p>
          <h3>{activeReviewCorpus?.name ?? "Discovery review"}</h3>
          <p>
            {discoveryStep === "corpus"
              ? "Start by building a corpus of traces and evidence to review."
              : discoveryStep === "review"
                ? "Step through each item, write a note on what you observe, and tag it with a failure mode."
                : discoveryStep === "confirm"
                  ? "Confirm or dismiss the failure modes that came out of this review."
                  : "Review complete. Here's what you found."}
          </p>
        </div>
        <div className="analysis-scope-card">
          <span>Active analysis</span>
          <strong>{selectedAgent.name}</strong>
          <small>
            {activeReviewCorpus
              ? `${activeReviewCorpus.source} corpus · ${activeReviewCorpus.status}`
              : "Create a corpus to begin"}
          </small>
        </div>
      </div>

      {showDiscoveryIntro ? (
        <div className="discovery-intro-card">
          <button
            className="discovery-intro-dismiss"
            type="button"
            onClick={dismissDiscoveryIntro}
            aria-label="Dismiss"
          >
            ×
          </button>
          <h4>What this does</h4>
          <ol>
            <li>
              <strong>Build a review set.</strong> Gather the traces and runs you want to
              read through.
            </li>
            <li>
              <strong>Review &amp; code.</strong> Read what your agent actually did, item by
              item, and write a note on anything that looks wrong.
            </li>
            <li>
              <strong>Confirm modes.</strong> Turn recurring notes into named failure modes
              — accept the ones that are real, dismiss the ones that aren't.
            </li>
            <li>
              <strong>Done.</strong> Confirmed failure modes become evidence you can use to
              write a fix in the Proof loop tab.
            </li>
          </ol>
        </div>
      ) : null}

      <div className="discovery-steps">
        {(
          [
            ["corpus", "Build corpus"],
            ["review", "Review & code"],
            ["confirm", "Confirm modes"],
            ["done", "Done"],
          ] as const
        ).map(([key, label], i, arr) => {
          const currentIdx = arr.findIndex(([k]) => k === discoveryStep);
          return (
            <div
              key={key}
              className={[
                "discovery-step",
                i < currentIdx ? "done" : "",
                i === currentIdx ? "active" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <span className="discovery-step-dot">{i < currentIdx ? "✓" : i + 1}</span>
              <span className="discovery-step-label">{label}</span>
            </div>
          );
        })}
      </div>

      {discoveryStep === "corpus" ? (
        <section className="discovery-step-panel">
          <div className="analysis-lane-card">
            <div>
              <span>Review set</span>
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
                disabled={isDiscoveryBusy || Boolean(activeReviewCorpus)}
              >
                Create review set
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={handleAddCurrentEvidenceToCorpus}
                disabled={isDiscoveryBusy}
              >
                Pull in new runs
              </button>
            </div>
          </div>

          {reviewItems.length > 0 ? (
            <div className="discovery-corpus-table" role="table" aria-label="Review set items">
              <div className="discovery-corpus-row discovery-corpus-head" role="row">
                <span role="columnheader">Item</span>
                <span role="columnheader">Source</span>
                <span role="columnheader">Status</span>
                <span role="columnheader">Notes</span>
              </div>
              {reviewItems.map((item) => (
                <div className="discovery-corpus-row" role="row" key={item.id}>
                  <span role="cell">{item.title}</span>
                  <span role="cell">{item.source_kind}</span>
                  <span role="cell">
                    <span
                      className={
                        item.status === "reviewed"
                          ? "discovery-status-badge reviewed"
                          : "discovery-status-badge open"
                      }
                    >
                      {item.status}
                    </span>
                  </span>
                  <span role="cell">
                    {
                      reviewAnnotations.filter(
                        (annotation) => annotation.review_item_id === item.id,
                      ).length
                    }
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted-copy">
              No items yet. Create a review set or pull in evidence from past runs to begin.
            </p>
          )}

          <div className="discovery-step-actions">
            <button
              className="primary-button"
              type="button"
              onClick={() => setDiscoveryStep("review")}
              disabled={!activeReviewCorpus || reviewItems.length === 0}
            >
              Start reviewing
            </button>
          </div>
        </section>
      ) : null}

      {discoveryStep === "review" ? (
        <section className="discovery-step-panel">
          <div className="discovery-step-actions discovery-step-actions-top">
            <button className="secondary-button" type="button" onClick={() => setDiscoveryStep("corpus")}>
              Back
            </button>
            <div style={{ display: "flex", gap: "10px" }}>
              <button
                className="secondary-button"
                type="button"
                onClick={handleSyncLangfuseComments}
                disabled={isDiscoveryBusy || !activeReviewCorpus}
              >
                Sync Langfuse comments
              </button>
              <button
                className="primary-button"
                type="button"
                onClick={() => setDiscoveryStep("confirm")}
              >
                Continue to confirm modes
              </button>
            </div>
          </div>

          {syncResult !== null ? (
            <p className={syncResult.imported > 0 ? "activity-text" : "muted-copy"}>
              {syncResult.imported > 0
                ? `Pulled in ${syncResult.imported} comment${syncResult.imported === 1 ? "" : "s"} from Langfuse.`
                : "No new comments found. Make sure review items have a linked Langfuse trace and that Langfuse is running."}
            </p>
          ) : null}
          {error ? <p className="error-text">{error}</p> : null}

          <div className="discovery-corpus-table" role="table" aria-label="Review items">
            <div className="discovery-corpus-row discovery-corpus-head" role="row">
              <span role="columnheader">Trace</span>
              <span role="columnheader">Status</span>
              <span role="columnheader">Comments</span>
              <span role="columnheader"></span>
            </div>
            {reviewItems.length === 0 ? (
              <p className="muted-copy" style={{ padding: "12px 16px" }}>
                No items yet — sync Langfuse comments to populate.
              </p>
            ) : null}
            {reviewItems.map((item) => {
              const itemAnnotations = reviewAnnotations.filter(
                (a) => a.review_item_id === item.id,
              );
              const traceUrl = item.langfuse_ref?.url ?? null;
              const isExpanded = selectedReviewItemId === item.id;
              return (
                <div key={item.id}>
                  <div
                    className={`discovery-corpus-row discovery-review-row${isExpanded ? " expanded" : ""}`}
                    role="row"
                  >
                    <button
                      className="discovery-row-title"
                      type="button"
                      onClick={() =>
                        setSelectedReviewItemId(isExpanded ? null : item.id)
                      }
                    >
                      {item.title}
                    </button>
                    <span role="cell">
                      <span
                        className={
                          item.status === "reviewed"
                            ? "discovery-status-badge reviewed"
                            : "discovery-status-badge open"
                        }
                      >
                        {item.status}
                      </span>
                    </span>
                    <span role="cell">{itemAnnotations.length}</span>
                    <span role="cell">
                      {traceUrl ? (
                        <a
                          href={traceUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="discovery-trace-link"
                        >
                          Open trace ↗
                        </a>
                      ) : null}
                    </span>
                  </div>
                  {isExpanded ? (
                    <div className="discovery-annotation-rows">
                      {itemAnnotations.length === 0 ? (
                        <p className="muted-copy">
                          No comments synced yet — add a comment in Langfuse then sync.
                        </p>
                      ) : (
                        itemAnnotations.map((annotation) => (
                          <div className="discovery-annotation-row" key={annotation.id}>
                            <p className="discovery-annotation-body">{annotation.body}</p>
                            <select
                              className="discovery-mode-select"
                              value={annotation.failure_mode_id ?? ""}
                              onChange={async (e) => {
                                await updateReviewAnnotation(projectId, annotation.id, {
                                  failure_mode_id: e.target.value || null,
                                });
                                await refreshDiscoveryState();
                              }}
                            >
                              <option value="">Assign failure mode…</option>
                              {failureModes.map((mode) => (
                                <option key={mode.id} value={mode.id}>
                                  {mode.name}
                                </option>
                              ))}
                            </select>
                          </div>
                        ))
                      )}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      {discoveryStep === "confirm" ? (
        <section className="discovery-step-panel">
          <div className="discovery-step-actions discovery-step-actions-top">
            <button className="secondary-button" type="button" onClick={() => setDiscoveryStep("review")}>
              Back
            </button>
            <button className="primary-button" type="button" onClick={() => setDiscoveryStep("done")}>
              Finish review
            </button>
          </div>

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

          <section className="axial-code-panel">
            <div className="section-title-row">
              <div>
                <p className="artifact-type">Suggestions</p>
                <h4>Agent-proposed modes</h4>
              </div>
            </div>
            <div className="trace-comment-list">
              {agentSuggestions.filter((suggestion) => suggestion.status === "pending").length === 0 ? (
                <p className="muted-copy">No pending suggestions.</p>
              ) : (
                agentSuggestions
                  .filter((suggestion) => suggestion.status === "pending")
                  .map((suggestion) => (
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
        </section>
      ) : null}

      {discoveryStep === "done" ? (
        <section className="discovery-step-panel discovery-done-panel">
          <div className="analysis-stats">
            <span>
              <strong>{reviewItems.length}</strong>
              items reviewed
            </span>
            <span>
              <strong>{acceptedAnnotationCount}</strong>
              notes
            </span>
            <span>
              <strong>{failureModes.length}</strong>
              modes confirmed
            </span>
          </div>
          <p className="mode-table-note">
            Confirmed failure modes are ready to use as evidence for fix proposals in the
            Proof loop tab.
          </p>
          <div className="discovery-step-actions">
            <button className="secondary-button" type="button" onClick={() => setDiscoveryStep("confirm")}>
              Back
            </button>
            <button
              className="primary-button"
              type="button"
              onClick={() => setDiscoveryStep("review")}
            >
              Review more items
            </button>
          </div>
        </section>
      ) : null}
    </section>
  );
}
