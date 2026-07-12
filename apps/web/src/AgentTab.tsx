import { FormEvent, useEffect, useState } from "react";
import { updateAgentDesign } from "./api";
import type { AgentDesign, GeneratedToolState, ToolDefinition } from "./types";

type AgentTabProps = {
  projectId: string;
  selectedAgent: AgentDesign;
  approvedTools: ToolDefinition[];
  draftTools: ToolDefinition[];
  enabledToolDefinitions: ToolDefinition[];
  generatedToolStates: GeneratedToolState[];
  activity: string | null;
  error: string | null;
  onAgentUpdated: (updated: AgentDesign) => void;
  setError: (message: string | null) => void;
  setActivity: (message: string | null) => void;
  onManageTools: () => void;
};

export function AgentTab({
  projectId,
  selectedAgent,
  approvedTools,
  draftTools,
  enabledToolDefinitions,
  generatedToolStates,
  activity,
  error,
  onAgentUpdated,
  setError,
  setActivity,
  onManageTools,
}: AgentTabProps) {
  const [agentEditName, setAgentEditName] = useState("");
  const [agentEditIntent, setAgentEditIntent] = useState("");
  const [isSavingAgent, setIsSavingAgent] = useState(false);

  useEffect(() => {
    setAgentEditName(selectedAgent.name);
    setAgentEditIntent(selectedAgent.intent);
  }, [selectedAgent]);

  const agentProfileChanged =
    agentEditName.trim() !== selectedAgent.name || agentEditIntent.trim() !== selectedAgent.intent;

  async function handleSaveAgentProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setActivity(null);
    setIsSavingAgent(true);
    try {
      const updated = await updateAgentDesign(projectId, selectedAgent.id, {
        name: agentEditName.trim(),
        intent: agentEditIntent.trim(),
      });
      onAgentUpdated(updated);
      setActivity("Agent profile saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update agent design.");
    } finally {
      setIsSavingAgent(false);
    }
  }

  return (
    <section className="agent-designer-panel workspace-tab-panel">
      <form className="agent-profile-form" onSubmit={handleSaveAgentProfile}>
        <div className="section-heading-row">
          <div>
            <p className="artifact-type">Agent design</p>
            <h2>{selectedAgent.name}</h2>
          </div>
          <span className="muted-chip">{selectedAgent.status}</span>
        </div>
        <label className="compact-label">
          <span>Agent name</span>
          <input
            value={agentEditName}
            onChange={(event) => setAgentEditName(event.target.value)}
            required
          />
        </label>
        <label className="compact-label">
          <span>Core instruction</span>
          <textarea
            value={agentEditIntent}
            onChange={(event) => setAgentEditIntent(event.target.value)}
            required
          />
        </label>
        <div className="agent-profile-actions">
          {activity ? <p className="activity-text">{activity}</p> : null}
          {error ? <p className="error-text">{error}</p> : null}
          <button
            className="primary-button"
            type="submit"
            disabled={
              isSavingAgent ||
              !agentProfileChanged ||
              !agentEditName.trim() ||
              !agentEditIntent.trim()
            }
          >
            {isSavingAgent ? "Saving" : "Save agent"}
          </button>
        </div>
      </form>
      <aside className="agent-tool-summary" aria-label="Agent tools">
        <div>
          <p className="artifact-type">Tools</p>
          <h3>
            {selectedAgent.allowed_tool_names.length === 0
              ? "No tools enabled"
              : `${selectedAgent.allowed_tool_names.length} enabled`}
          </h3>
          <p>
            {approvedTools.length} approved · {draftTools.length} draft
          </p>
        </div>
        <div className="tool-chip-row">
          {enabledToolDefinitions.length === 0 ? (
            <span className="muted-chip">None enabled</span>
          ) : (
            enabledToolDefinitions.slice(0, 4).map((tool) => (
              <span className="tool-chip" key={tool.id}>
                {tool.name}
              </span>
            ))
          )}
          {selectedAgent.allowed_tool_names.length > enabledToolDefinitions.length ? (
            <span className="muted-chip">
              +{selectedAgent.allowed_tool_names.length - enabledToolDefinitions.length}
            </span>
          ) : null}
        </div>
        {generatedToolStates.length > 0 ? (
          <div className="generated-tool-lifecycle">
            <p className="artifact-type">Generated tools</p>
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
        ) : null}
        <button className="secondary-button" type="button" onClick={onManageTools}>
          Manage tools
        </button>
      </aside>
    </section>
  );
}
