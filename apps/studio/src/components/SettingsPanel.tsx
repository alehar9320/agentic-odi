import { useState } from "react";

import { useOnboarding } from "../onboarding/context";
import { useStudio } from "../state/StudioContext";
import type { ConnectorPreset, StudioConfig } from "../types";
import { FailurePanel } from "./FailurePanel";
import { UpdateSettings } from "../updater";

const PRESET_AREAS: ConnectorPreset["area"][] = [
  "voice-of-customer",
  "quantitative-data",
  "market-intelligence",
  "strategy-alignment",
  "knowledge-output",
];

const AREA_LABELS: Record<ConnectorPreset["area"], string> = {
  "voice-of-customer": "Voice of customer & qualitative research",
  "quantitative-data": "Quantitative data & opportunity scoring",
  "market-intelligence": "Market & competitive intelligence",
  "strategy-alignment": "Product strategy & backlog alignment",
  "knowledge-output": "Strategy & knowledge management output",
};

export function SettingsPanel() {
  const {
    settings,
    saveSettings,
    displayName,
    setDisplayName,
    brief,
    openSetup,
    clearChat,
    refreshCanvas,
    llmHealth,
    mcpReachable,
    connectors,
    connectorsError,
    presets,
    presetError,
    refreshPresets,
    refreshConnectors,
    addConnector,
    deleteConnector,
    sidecarReachable,
    capabilities,
    settingsSummary,
  } = useStudio();
  const { enabled: tourEnabled, restart: restartTour } = useOnboarding();
  const [showApiKey, setShowApiKey] = useState(false);

  function update<K extends keyof StudioConfig>(key: K, value: StudioConfig[K]): void {
    saveSettings({ ...settings, [key]: value });
  }

  const presetGroups = PRESET_AREAS.map((area) => ({
    area,
    label: AREA_LABELS[area],
    presets: presets.filter((preset) => preset.area === area),
  })).filter((group) => group.presets.length > 0);

  return (
    <div className="settings">
      <div className="settings__context">
        <div>
          <p className="settings__context-label">Your context</p>
          <p className="settings__context-value">
            {brief?.job_statement
              ? `${brief.product_name || "Your product"} — ${brief.job_statement}`
              : "Not set yet. The studio starts every reply from this."}
          </p>
        </div>
        <button type="button" className="button button--ghost" onClick={openSetup}>
          {brief ? "Edit context" : "Set up context"}
        </button>
      </div>

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
        <div className="field__row">
          <input
            id="api-key"
            className="input"
            type={showApiKey ? "text" : "password"}
            autoComplete="off"
            value={settings.api_key}
            onChange={(event) => update("api_key", event.target.value)}
          />
          <button
            type="button"
            className="quiet-action"
            aria-label={showApiKey ? "Hide API key" : "Show API key"}
            onClick={() => setShowApiKey((visible) => !visible)}
          >
            {showApiKey ? "Hide" : "Show"}
          </button>
        </div>
        {!settings.api_key && settingsSummary?.has_api_key && (
          <p className="field__hint">
            Stored on this machine as {settingsSummary.masked}. Typing here replaces it; the studio
            never reads it back.
          </p>
        )}
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
          <span
            className={`status-dot${sidecarReachable === false ? " is-warn" : sidecarReachable === null ? " is-unknown" : ""}`}
          />
          <span>Sidecar</span>
          <span className="connection-list__value">
            {sidecarReachable === false ? "unavailable" : sidecarReachable === null ? "unknown" : "reachable"}
          </span>
        </li>
        <li>
          <span className={`status-dot${mcpReachable ? "" : " is-unknown"}`} />
          <span>Local FastMCP server</span>
          <span className="connection-list__value">{mcpReachable ? "connected" : "offline"}</span>
        </li>
      </ul>
      <p className="muted">
        Only the model and MCP server above are live. No data source is connected yet — add one
        from the presets below.
      </p>

      <h3 className="settings__title">Capabilities</h3>
      <ul className="connection-list">
        {capabilities.map((capability) => (
          <li key={capability.id}>
            <span
              className={`status-dot${
                capability.status === "available" ? "" : " is-warn"
              }`}
            />
            <span>{capability.label}</span>
            <span className="connection-list__value">
              {capability.status === "available" ? "available" : "unavailable"}
              {capability.reason ? ` — ${capability.reason}` : ""}
            </span>
          </li>
        ))}
      </ul>

      {sidecarReachable === false ? (
        <p className="muted">
          Connectors require the local sidecar. Data and conversation still work
          without it; connect a sidecar to add MCP or REST data sources.
        </p>
      ) : (
        <>
          <h3 className="settings__title">Connectors</h3>
          {connectorsError ? (
            <FailurePanel
              error={connectorsError}
              retryText="reload"
              onRetry={() => void refreshConnectors()}
            />
          ) : connectors.length === 0 ? (
            <p className="muted">No connectors registered. Pick a preset to add one.</p>
          ) : (
            <ul className="connection-list">
              {connectors.map((connector) => (
                <li key={connector.name}>
                  <span className="connection-list__value">
                    {connector.name} · {connector.kind}
                    {connector.enabled ? "" : " (disabled)"}
                  </span>
                  <button
                    type="button"
                    className="button button--ghost"
                    aria-label={`Remove ${connector.name}`}
                    onClick={() => void deleteConnector(connector.name)}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
          <h4 className="settings__title">Add a data source</h4>
          {presetError ? (
            <FailurePanel
              error={presetError}
              retryText="reload"
              onRetry={() => void refreshPresets()}
            />
          ) : presetGroups.length === 0 ? (
            <p className="muted">No presets available.</p>
          ) : (
            <div className="settings__presets">
              {presetGroups.map((group) => (
                <section
                  key={group.area}
                  className="settings__preset-group"
                  aria-label={group.label}
                >
                  <h5 className="settings__preset-title">{group.label}</h5>
                  <ul className="connection-list">
                    {group.presets.map((preset) => (
                      <li key={preset.id}>
                        <span className="connection-list__value">
                          {preset.label}{" "}
                          <code className="settings__preset-id">{preset.id}</code>
                          {" · "}
                          {preset.auth === "oauth" ? "OAuth" : "No auth"}
                        </span>
                        <button
                          type="button"
                          className="button button--ghost"
                          aria-label={`Connect ${preset.label}`}
                          onClick={() => void addConnector({ preset: preset.id })}
                        >
                          Connect
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          )}
          </>
      )}

      <div className="settings__actions">
        <button type="button" className="button" onClick={clearChat}>
          Start a new conversation
        </button>
        <button type="button" className="button button--ghost" onClick={() => void refreshCanvas()}>
          Sync canvas
        </button>
      </div>

      {tourEnabled ? (
        <div className="settings__tour">
          <h3 className="settings__title">Getting started</h3>
          <p className="muted">A four-step tour of what the studio can do, and where to begin.</p>
          <button type="button" className="button button--ghost" onClick={restartTour}>
            Replay the welcome tour
          </button>
        </div>
      ) : null}

      <UpdateSettings />

      <details className="disclosure">
        <summary>How the studio works</summary>
        <p>
          The Living Studio replaces backlogs and ticket accounting with a canvas of human intent.
          Point at an outcome, then talk about it: every bet traces back to evidence, and impact is
          simulated before code gets written.
        </p>
      </details>
    </div>
  );
}
