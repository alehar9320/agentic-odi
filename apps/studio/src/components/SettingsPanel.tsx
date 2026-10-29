import { useState } from "react";

import { useStudio } from "../state/StudioContext";
import type { StudioConfig } from "../types";
import { useUpdater } from "./updater/useUpdater";

export function SettingsPanel() {
  const { settings, saveSettings, clearChat, refreshCanvas, pushToast } = useStudio();
  const [open, setOpen] = useState(false);
  const updater = useUpdater();

  function update<K extends keyof StudioConfig>(key: K, value: StudioConfig[K]): void {
    saveSettings({ ...settings, [key]: value });
  }

  return (
    <section className="settings-drawer" aria-label="Living Studio controls">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 className="section-title" style={{ margin: 0 }}>🎛️ Living Studio Controls</h2>
          <p className="caption" style={{ margin: "2px 0 0" }}>
            Ambient intelligence &amp; engine settings
          </p>
        </div>
        <button
          type="button"
          className="studio-button studio-button--ghost"
          aria-expanded={open}
          aria-controls="studio-controls-body"
          onClick={() => setOpen((prev) => !prev)}
        >
          {open ? "Collapse" : "Expand Settings"}
        </button>
      </div>

      {open && (
        <div id="studio-controls-body" style={{ marginTop: 16 }}>
          <div className="studio-field">
            <label htmlFor="base-url">LLM Base URL</label>
            <input
              id="base-url"
              className="studio-input"
              value={settings.base_url}
              onChange={(event) => update("base_url", event.target.value)}
            />
          </div>
          <div className="studio-field">
            <label htmlFor="api-key">LLM API Key</label>
            <input
              id="api-key"
              className="studio-input"
              type="password"
              autoComplete="off"
              value={settings.api_key}
              onChange={(event) => update("api_key", event.target.value)}
            />
          </div>
          <div className="studio-field">
            <label htmlFor="model-name">Model Alias</label>
            <input
              id="model-name"
              className="studio-input"
              value={settings.model_name}
              onChange={(event) => update("model_name", event.target.value)}
            />
          </div>
          <div className="studio-field">
            <label htmlFor="mcp-url">MCP Server URL</label>
            <input
              id="mcp-url"
              className="studio-input"
              value={settings.mcp_url}
              onChange={(event) => update("mcp_url", event.target.value)}
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 14 }}>
            <button type="button" className="studio-button studio-button--ghost" onClick={clearChat}>
              🧹 Clear Chat
            </button>
            <button
              type="button"
              className="studio-button"
              onClick={() => void refreshCanvas()}
            >
              🔄 Sync Canvas
            </button>
          </div>

          <h3 className="section-title" style={{ fontSize: "0.95rem" }}>
            ⚡ Connected MCP Sources
          </h3>
          <p className="caption">
            🟢 <strong>Local FastMCP Server</strong> (agentic-odi-mcp-server)<br />
            🟢 <strong>Gong Audio Transcript Bridge</strong> (simulated)<br />
            🟢 <strong>Slack Customer Friction Stream</strong> (simulated)<br />
            🟢 <strong>Product Telemetry / PostHog</strong> (simulated)
          </p>

          <details>
            <summary style={{ cursor: "pointer", fontWeight: 600, minHeight: 44, display: "flex", alignItems: "center" }}>
              ℹ️ About The Living Studio
            </summary>
            <p className="caption" style={{ marginTop: 8 }}>
              <strong>The Living Studio</strong> replaces backlogs with a <strong>Canvas of Human Intent</strong>.
            </p>
            <div style={{ marginTop: 8 }}>
              <button
                type="button"
                className="studio-button"
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
                <span className="source-badge">v{updater.version}</span>
              )}
            </div>
          </details>
        </div>
      )}
    </section>
  );
}
