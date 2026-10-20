import { useStudio } from "../state/StudioContext";
import type { StudioConfig } from "../types";
import { useUpdater } from "./updater/useUpdater";

export function SettingsPanel() {
  const {
    settings,
    saveSettings,
    displayName,
    setDisplayName,
    clearChat,
    refreshCanvas,
    llmHealth,
    mcpReachable,
    pushToast,
  } = useStudio();
  const updater = useUpdater();

  function update<K extends keyof StudioConfig>(key: K, value: StudioConfig[K]): void {
    saveSettings({ ...settings, [key]: value });
  }

  return (
    <div className="settings">
      <div className="field">
        <label htmlFor="display-name">
          Your name <span className="field__hint">optional — used in the greeting</span>
        </label>
        <input
          id="display-name"
          className="input"
          value={displayName}
          placeholder="Ada"
          autoComplete="given-name"
          onChange={(event) => setDisplayName(event.target.value)}
        />
      </div>

      <h3 className="settings__title">Model</h3>
      <div className="field">
        <label htmlFor="base-url">Base URL</label>
        <input
          id="base-url"
          className="input"
          value={settings.base_url}
          spellCheck={false}
          onChange={(event) => update("base_url", event.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="api-key">API key</label>
        <input
          id="api-key"
          className="input"
          type="password"
          autoComplete="off"
          value={settings.api_key}
          onChange={(event) => update("api_key", event.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="model-name">Model</label>
        <input
          id="model-name"
          className="input"
          value={settings.model_name}
          spellCheck={false}
          onChange={(event) => update("model_name", event.target.value)}
        />
      </div>

      <h3 className="settings__title">Studio bridge</h3>
      <div className="field">
        <label htmlFor="mcp-url">MCP server URL</label>
        <input
          id="mcp-url"
          className="input"
          value={settings.mcp_url}
          spellCheck={false}
          onChange={(event) => update("mcp_url", event.target.value)}
        />
      </div>

      <ul className="connection-list">
        <li>
          <span
            className={`status-dot${llmHealth.healthy === false ? " is-warn" : ""}${
              llmHealth.healthy === null ? " is-unknown" : ""
            }`}
          />
          <span>Model</span>
          <span className="connection-list__value">
            {llmHealth.healthy === false ? "offline" : "reachable"}
          </span>
        </li>
        <li>
          <span className={`status-dot${mcpReachable ? "" : " is-unknown"}`} />
          <span>Local FastMCP server</span>
          <span className="connection-list__value">{mcpReachable ? "connected" : "offline"}</span>
        </li>
        <li>
          <span className="status-dot is-unknown" />
          <span>Gong transcripts</span>
          <span className="connection-list__value">not connected</span>
        </li>
        <li>
          <span className="status-dot is-unknown" />
          <span>Slack friction stream</span>
          <span className="connection-list__value">not connected</span>
        </li>
        <li>
          <span className="status-dot is-unknown" />
          <span>Product telemetry</span>
          <span className="connection-list__value">not connected</span>
        </li>
      </ul>

      <div className="settings__actions">
        <button type="button" className="button" onClick={clearChat}>
          Start a new conversation
        </button>
        <button type="button" className="button button--ghost" onClick={() => void refreshCanvas()}>
          Sync canvas
        </button>
      </div>

      <details className="disclosure">
        <summary>How the studio works</summary>
        <p>
          The Living Studio replaces backlogs and ticket accounting with a canvas of human intent.
          Point at an outcome, then talk about it: every bet traces back to evidence, and impact is
          simulated before code gets written.
        </p>
        <button
          type="button"
          className="button button--ghost"
          disabled={updater.checking}
          onClick={() => {
            void updater.check();
            if (updater.error) {
              pushToast("info", updater.error);
            }
          }}
        >
          {updater.checking ? "Checking for updates…" : "Check for updates"}
        </button>
        {updater.available && updater.version && (
          <span className="muted">v{updater.version}</span>
        )}
        {updater.progress !== null && (
          <span className="muted">{Math.round((updater.progress ?? 0) * 100)}%</span>
        )}
        {updater.error && <span className="muted">{updater.error}</span>}
      </details>
    </div>
  );
}
