import {
  Clock3,
  MoreHorizontal,
  PanelLeft,
  PanelRight,
  PencilLine,
  Play,
  Search,
  Trash2,
  X,
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

type ArtifactRecord = {
  id: string;
  project_id: string;
  artifact_type: string;
  artifact_id: string;
  title: string;
  body: string;
  source: string;
  agent_design_id: string | null;
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
  tool_calls: { name: string; output: string }[];
  evidence: string[];
  artifact: ArtifactRecord;
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

const apiBase = "/api";

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

async function deleteAgentDesign(projectId: string, agentDesignId: string): Promise<void> {
  const response = await fetch(`${apiBase}/projects/${projectId}/agent-designs/${agentDesignId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw await responseError(response, "Unable to delete agent design.");
  }
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
): Promise<AgentRunResult> {
  const response = await fetch(`${apiBase}/projects/${projectId}/agent-designs/${agentDesignId}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_input: scenarioInput, mode }),
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

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [project, setProject] = useState<Project | null>(null);
  const [agents, setAgents] = useState<AgentDesign[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [intent, setIntent] = useState("");
  const [scenarioInput, setScenarioInput] = useState(
    "A customer reports a failed deployment and asks what to do next.",
  );
  const [runMode, setRunMode] = useState<"mock" | "live">("mock");
  const [contextPack, setContextPack] = useState<ContextPack | null>(null);
  const [reviewArtifact, setReviewArtifact] = useState<ArtifactRecord | null>(null);
  const [reviewLinks, setReviewLinks] = useState<ArtifactLink[]>([]);
  const [openAgentMenuId, setOpenAgentMenuId] = useState<string | null>(null);
  const [deleteCandidate, setDeleteCandidate] = useState<AgentDesign | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingContext, setIsLoadingContext] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [evaluatingArtifactId, setEvaluatingArtifactId] = useState<string | null>(null);
  const [activity, setActivity] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listProjects()
      .then((projects) => {
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

  const selectedAgent = useMemo(
    () => agents.find((agent) => agent.id === selectedId) ?? null,
    [agents, selectedId],
  );
  const artifactsById = useMemo(() => {
    return new Map((contextPack?.artifacts ?? []).map((artifact) => [artifact.id, artifact]));
  }, [contextPack]);

  useEffect(() => {
    if (!project) {
      setContextPack(null);
      return;
    }
    setIsLoadingContext(true);
    buildContextPack(project.id, selectedId ?? undefined)
      .then(setContextPack)
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoadingContext(false));
  }, [project, selectedId]);

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
      setReviewArtifact(null);
      setReviewLinks([]);
      setName("");
      setIntent("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create agent design.");
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
        setContextPack(null);
        setReviewArtifact(null);
        setReviewLinks([]);
        setActivity(null);
      }
      setDeleteCandidate(null);
      setOpenAgentMenuId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete agent design.");
    }
  }

  async function handleRunAgent() {
    if (!project || !selectedAgent) {
      return;
    }
    setError(null);
    setActivity(runMode === "live" ? "Running live OpenAI scenario." : "Running mock scenario.");
    setIsRunning(true);
    try {
      const run = await runAgentDesign(
        project.id,
        selectedAgent.id,
        scenarioInput.trim(),
        runMode,
      );
      setActivity("Stored run evidence.");
      setContextPack((pack) =>
        pack
          ? { ...pack, artifacts: [run.artifact, ...pack.artifacts] }
          : pack,
      );
      await handleReviewArtifact(run.artifact.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run agent scenario.");
      setActivity("Run failed.");
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load artifact.");
    }
  }

  return (
    <div
      className={[
        sidebarOpen ? "app-shell" : "app-shell sidebar-collapsed",
        reviewArtifact ? "review-open" : "",
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
              setReviewArtifact(null);
              setReviewLinks([]);
              setActivity(null);
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
                    setOpenAgentMenuId(null);
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
        ) : null}
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h1>{selectedAgent?.name ?? "New agent"}</h1>
            <p>
              {selectedAgent?.intent ??
                project?.description ??
                "Describe an agent and persist the first platform design."}
            </p>
          </div>
          <span className="status-pill">Platform: local</span>
        </header>

        <section className={selectedAgent ? "canvas canvas-workspace" : "canvas"}>
          {!selectedAgent ? (
            <form className="intent-form" onSubmit={handleCreate}>
              <p className="eyebrow">Start from intent</p>
              <h2>What agent are we building?</h2>
              <label>
                Agent name
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Customer Service Triage Agent"
                  required
                />
              </label>
              <label>
                Agent intent
                <textarea
                  value={intent}
                  onChange={(event) => setIntent(event.target.value)}
                  placeholder="Determine why an issue escalated, gather evidence, and recommend a safe next action."
                  required
                />
              </label>
              <button className="primary-button" type="submit">
                Create agent
              </button>
              {error ? <p className="error-text">{error}</p> : null}
            </form>
          ) : null}

          <section className={selectedAgent ? "evidence-panel evidence-workspace" : "evidence-panel"}>
            <p className="eyebrow">Evidence context</p>
            <h2>{selectedAgent ? "Evidence artifacts" : "Ready for the first design"}</h2>
            {!selectedAgent ? (
              <p className="muted-copy">
                Create an agent design to begin collecting targets, judge prompts, gates, runs,
                and evidence.
              </p>
            ) : null}
            {selectedAgent ? (
              <div className="artifact-stack">
                <section className="run-playground">
                  <div>
                    <p className="artifact-type">Agent playground</p>
                    <h3>Run a scenario</h3>
                    <p>
                      Execute this design in mock mode or live OpenAI mode and store the output as run evidence.
                    </p>
                  </div>
                  <div className="run-mode-control" aria-label="Run mode">
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
                  <label>
                    Scenario input
                    <textarea
                      value={scenarioInput}
                      onChange={(event) => setScenarioInput(event.target.value)}
                    />
                  </label>
                  <button
                    className="primary-button"
                    type="button"
                    onClick={handleRunAgent}
                    disabled={isRunning}
                  >
                    <Play size={18} />
                    {isRunning ? "Running" : runMode === "live" ? "Run live" : "Run mock"}
                  </button>
                  {activity ? <p className="activity-text">{activity}</p> : null}
                  {error ? <p className="error-text">{error}</p> : null}
                </section>
                <div className="context-pack-meta">
                  <span>Context pack</span>
                  <strong>{contextPack?.purpose.replaceAll("_", " ") ?? "Preparing"}</strong>
                </div>
                {isLoadingContext ? <p className="muted-copy">Loading evidence...</p> : null}
                {!isLoadingContext && (contextPack?.artifacts.length ?? 0) === 0 ? (
                  <p className="muted-copy">No artifacts recorded for this design yet.</p>
                ) : null}
                {(contextPack?.artifacts ?? []).map((artifact) => (
                  <article className="artifact-card" key={artifact.id}>
                    <div>
                      <p className="artifact-type">{artifact.artifact_type.replaceAll("_", " ")}</p>
                      <h3>{artifact.title}</h3>
                      <p>{artifact.body}</p>
                    </div>
                    <div className="artifact-actions">
                      {artifact.artifact_type === "RUN_RESULT" ? (
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() => handleEvaluateArtifact(artifact)}
                          disabled={evaluatingArtifactId === artifact.id}
                        >
                          {evaluatingArtifactId === artifact.id ? "Evaluating" : "Evaluate"}
                        </button>
                      ) : null}
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => handleReviewArtifact(artifact.id)}
                      >
                        <PanelRight size={18} />
                        Review
                      </button>
                    </div>
                    <dl>
                      <div>
                        <dt>Source</dt>
                        <dd>{artifact.source}</dd>
                      </div>
                      <div>
                        <dt>Updated</dt>
                        <dd>{new Date(artifact.updated_at).toLocaleString()}</dd>
                      </div>
                    </dl>
                  </article>
                ))}
              </div>
            ) : null}
          </section>
        </section>
      </main>
      {reviewArtifact ? (
        <aside className="review-panel" aria-label="Artifact review">
          <div className="review-panel-header">
            <div>
              <p className="eyebrow">{reviewArtifact.artifact_type.replaceAll("_", " ")}</p>
              <h2>{reviewArtifact.title}</h2>
            </div>
            <button
              className="icon-button"
              type="button"
              aria-label="Close review panel"
              onClick={() => {
                setReviewArtifact(null);
                setReviewLinks([]);
              }}
            >
              <X size={22} />
            </button>
          </div>

          <div className="review-panel-body">
            <section>
              <h3>Evidence</h3>
              <p>{reviewArtifact.body}</p>
            </section>
            <section>
              <h3>Related evidence</h3>
              {reviewLinks.length === 0 ? (
                <p>No related artifacts yet.</p>
              ) : (
                <ul className="related-list">
                  {reviewLinks.map((link) => {
                    const direction =
                      link.source_artifact_id === reviewArtifact.id ? "points to" : "linked from";
                    const relatedId =
                      link.source_artifact_id === reviewArtifact.id
                        ? link.target_artifact_id
                        : link.source_artifact_id;
                    const relatedArtifact = artifactsById.get(relatedId);
                    return (
                      <li key={link.id}>
                        <strong>{link.relationship_type.replaceAll("_", " ")}</strong>
                        <span>{direction}</span>
                        <b>{relatedArtifact?.title ?? relatedId}</b>
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
                <dt>Artifact id</dt>
                <dd>{reviewArtifact.id}</dd>
              </div>
              <div>
                <dt>Project</dt>
                <dd>{reviewArtifact.project_id}</dd>
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
