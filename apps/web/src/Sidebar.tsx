import { Clock3, ExternalLink, MoreHorizontal, PanelLeft, PencilLine, Play, Search, Trash2 } from "lucide-react";
import type { AgentDesign, ServiceStatus } from "./types";

type SidebarProps = {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  projectName: string;
  wizardOpen: boolean;
  selectedAgent: AgentDesign | null;
  onNewAgent: () => void;
  services: ServiceStatus[];
  isLoading: boolean;
  agents: AgentDesign[];
  selectedId: string | null;
  onSelectAgent: (agent: AgentDesign) => void;
  openAgentMenuId: string | null;
  onToggleAgentMenu: (agentId: string) => void;
  onTryScenario: (agent: AgentDesign) => void;
  onRequestDeleteAgent: (agent: AgentDesign) => void;
};

export function Sidebar({
  sidebarOpen,
  onToggleSidebar,
  projectName,
  wizardOpen,
  selectedAgent,
  onNewAgent,
  services,
  isLoading,
  agents,
  selectedId,
  onSelectAgent,
  openAgentMenuId,
  onToggleAgentMenu,
  onTryScenario,
  onRequestDeleteAgent,
}: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand-row">
        <div className="brand-mark">E</div>
        {sidebarOpen ? <strong>{projectName}</strong> : null}
        <button
          className="icon-button"
          type="button"
          aria-label="Toggle sidebar"
          onClick={onToggleSidebar}
        >
          <PanelLeft size={21} />
        </button>
      </div>

      <nav className="primary-nav" aria-label="Primary">
        <button
          className={wizardOpen || !selectedAgent ? "nav-item active" : "nav-item"}
          type="button"
          onClick={onNewAgent}
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
        <>
          <section className="service-list" aria-label="Service status">
            <p className="section-label">Services</p>
            {services.length === 0 ? <p className="empty-list">Checking services...</p> : null}
            {services.map((service) => {
              const content = (
                <>
                  <span className={`service-dot ${service.status}`} aria-hidden="true" />
                  <span className="service-copy">
                    <strong>{service.name}</strong>
                    <small>{service.status.replace("_", " ")}</small>
                  </span>
                  {service.url ? <ExternalLink size={15} /> : null}
                </>
              );
              return service.url ? (
                <a
                  className="service-row"
                  href={service.url}
                  key={service.id}
                  rel="noreferrer"
                  target="_blank"
                  title={service.description}
                >
                  {content}
                </a>
              ) : (
                <div className="service-row" key={service.id} title={service.description}>
                  {content}
                </div>
              );
            })}
          </section>

          <section className="agent-list" aria-label="Agent designs">
            <p className="section-label">Agents</p>
            {isLoading ? <p className="empty-list">Loading...</p> : null}
            {!isLoading && agents.length === 0 ? <p className="empty-list">No agents yet</p> : null}
            {agents.map((agent) => (
              <div
                className={agent.id === selectedId ? "agent-row selected" : "agent-row"}
                key={agent.id}
              >
                <button className="agent-select" type="button" onClick={() => onSelectAgent(agent)}>
                  <span>{agent.name}</span>
                </button>
                <button
                  className="agent-menu-button"
                  type="button"
                  aria-label={`Open actions for ${agent.name}`}
                  onClick={() => onToggleAgentMenu(agent.id)}
                >
                  <MoreHorizontal size={21} />
                </button>
                {openAgentMenuId === agent.id ? (
                  <div className="agent-menu" role="menu">
                    <button
                      className="agent-menu-item"
                      type="button"
                      role="menuitem"
                      onClick={() => onTryScenario(agent)}
                    >
                      <Play size={18} />
                      <span>
                        Try scenario
                        <small>Ad hoc run</small>
                      </span>
                    </button>
                    <button
                      className="agent-menu-item danger"
                      type="button"
                      role="menuitem"
                      onClick={() => onRequestDeleteAgent(agent)}
                    >
                      <Trash2 size={18} />
                      Delete
                    </button>
                  </div>
                ) : null}
              </div>
            ))}
          </section>
        </>
      ) : null}
    </aside>
  );
}
