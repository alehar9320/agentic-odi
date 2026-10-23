import { useStudio } from "../../state/StudioContext";
import type { WorkspacePanelId } from "../../types";
import { PanelLeftIcon, PlusIcon, SettingsIcon, SparkIcon } from "../icons";
import { WORKSPACE_PANELS } from "../workspace/panels";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onNavigate: () => void;
  onHome: () => void;
}

export function Sidebar({ collapsed, onToggle, onNavigate, onHome }: SidebarProps) {
  const {
    activePanel,
    openPanel,
    closePanel,
    clearChat,
    openSetup,
    closeSetup,
    brief,
    llmHealth,
    mcpReachable,
    settings,
    canvas,
  } = useStudio();

  const counts: Partial<Record<WorkspacePanelId, number>> = {
    landscape: canvas?.outcomes.length ?? 0,
    jobmap: canvas?.steps.length ?? 0,
  };

  function go(panel: WorkspacePanelId) {
    if (activePanel === panel) {
      closePanel();
    } else {
      openPanel(panel);
    }
    onNavigate();
  }

  function newConversation() {
    clearChat();
    closePanel();
    closeSetup();
    onNavigate();
  }

  const modelLabel = llmHealth.healthy === false ? "Local studio mode" : settings.model_name;

  return (
    <aside className={`sidebar${collapsed ? " sidebar--collapsed" : ""}`} aria-label="Studio">
      <div className="sidebar__top">
        <button
          type="button"
          className="brand brand--home"
          onClick={onHome}
          aria-label="Go to home"
          title="Home"
        >
          <span className="brand__mark" aria-hidden="true">
            ◍
          </span>
          <span className="brand__wordmark">Living Studio</span>
        </button>
        <button
          type="button"
          className="icon-button sidebar__toggle"
          onClick={onToggle}
          aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          aria-expanded={!collapsed}
          title={collapsed ? "Expand navigation" : "Collapse navigation"}
        >
          <PanelLeftIcon size={17} />
        </button>
      </div>

      <button
        type="button"
        className="sidebar__new"
        onClick={newConversation}
        title="New conversation"
      >
        <PlusIcon size={16} />
        <span className="sidebar__new-label">New conversation</span>
      </button>

      <nav className="sidebar__nav" aria-label="Workspace">
        <p className="sidebar__label" id="workspace-label">
          Workspace
        </p>
        <button
          type="button"
          className={`nav-item${brief ? "" : " nav-item--nudge"}`}
          onClick={() => {
            openSetup();
            onNavigate();
          }}
          title="Your product, audience, and job"
        >
          <span className="nav-item__icon">
            <SparkIcon size={16} />
          </span>
          <span className="nav-item__label">Your context</span>
          {!brief && <span className="nav-item__dot" aria-hidden="true" />}
        </button>
        {WORKSPACE_PANELS.map((panel) => {
          const count = counts[panel.id] ?? 0;
          const active = activePanel === panel.id;
          return (
            <button
              key={panel.id}
              type="button"
              className={`nav-item${active ? " is-active" : ""}`}
              aria-current={active ? "page" : undefined}
              onClick={() => go(panel.id)}
              title={panel.label}
            >
              <span className="nav-item__icon">{panel.icon}</span>
              <span className="nav-item__label">{panel.label}</span>
              {count > 0 && <span className="nav-item__count">{count}</span>}
            </button>
          );
        })}
      </nav>

      <div className="sidebar__spacer" />

      <div className="sidebar__status" aria-label="Connection status">
        <button
          type="button"
          className="status-row"
          onClick={() => {
            openPanel("settings");
            onNavigate();
          }}
          title={llmHealth.message}
        >
          <span
            className={`status-dot${llmHealth.healthy === false ? " is-warn" : ""}${
              llmHealth.healthy === null ? " is-unknown" : ""
            }`}
          />
          <span className="status-row__text">{modelLabel}</span>
        </button>
        <button
          type="button"
          className="status-row"
          onClick={() => {
            openPanel("settings");
            onNavigate();
          }}
          title={mcpReachable ? "MCP server reachable" : "MCP server not reachable"}
        >
          <span className={`status-dot${mcpReachable ? "" : " is-unknown"}`} />
          <span className="status-row__text">MCP {mcpReachable ? "connected" : "offline"}</span>
        </button>
      </div>

      <button
        type="button"
        className={`nav-item sidebar__settings${activePanel === "settings" ? " is-active" : ""}`}
        onClick={() => go("settings")}
        title="Settings"
      >
        <span className="nav-item__icon">
          <SettingsIcon size={17} />
        </span>
        <span className="nav-item__label">Settings</span>
      </button>
    </aside>
  );
}
