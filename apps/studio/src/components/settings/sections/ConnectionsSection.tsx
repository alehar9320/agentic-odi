import { useState, type FormEvent } from "react";

import type { Capability } from "../../../bff/capabilities/registry";
import type { AddConnectorPayload, ConnectorListItem, StudioConfig } from "../../../types";
import { FailurePanel } from "../../FailurePanel";
import { StatusRow } from "./StatusRow";

export function ConnectionsSection({
  connectors,
  connectorsError,
  refreshConnectors,
  deleteConnector,
  addConnector,
  openCustomize,
  sidecarReachable,
  mcpReachable,
  llmHealth,
  capabilities,
  settings,
  saveSettings,
  allowManualAdd = false,
  showConnectionStatus = true,
  showModelStatus = false,
  showManageButton = true,
  heading = "Connections",
  headingId = "settings-connections-heading",
  sectionId,
  manualAddDisabledReason,
}: {
  connectors: ConnectorListItem[];
  connectorsError: { message: string; code: string; retryable: boolean } | null;
  refreshConnectors: () => Promise<void>;
  deleteConnector: (name: string) => Promise<void>;
  addConnector: (payload: AddConnectorPayload) => Promise<void>;
  openCustomize: () => void;
  sidecarReachable: boolean | null;
  mcpReachable: boolean;
  llmHealth: { healthy: boolean | null; message: string };
  capabilities: Capability[];
  settings: StudioConfig;
  saveSettings: (config: StudioConfig) => void;
  allowManualAdd?: boolean;
  showConnectionStatus?: boolean;
  showModelStatus?: boolean;
  showManageButton?: boolean;
  heading?: string;
  headingId?: string;
  sectionId?: string;
  manualAddDisabledReason?: string;
}) {
  const [manualOpen, setManualOpen] = useState(false);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const offline = sidecarReachable === false;
  const manualAddDisabled = offline || Boolean(connectorsError);
  const manualAddReason = manualAddDisabledReason ?? "Connectors need the sidecar";

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = name.trim();
    const trimmedUrl = url.trim();
    if (!trimmedName || !trimmedUrl) return;
    void addConnector({ name: trimmedName, url: trimmedUrl });
    setName("");
    setUrl("");
    setManualOpen(false);
  }

  return (
    <section id={sectionId} className="settings__section" aria-labelledby={headingId} tabIndex={sectionId ? -1 : undefined}>
      <h3 className="settings__title" id={headingId}>{heading}</h3>
      {showConnectionStatus ? (
        <>
          <div className="field">
            <label htmlFor="mcp-url">MCP server URL</label>
            <input
              id="mcp-url"
              className="input"
              value={settings.mcp_url}
              spellCheck={false}
              onChange={(event) => saveSettings({ ...settings, mcp_url: event.target.value })}
            />
          </div>
          <dl className="connection-list" aria-label="Connection status">
            {showModelStatus ? <StatusRow label="Model" status={llmHealth.healthy === null ? "unknown" : llmHealth.healthy ? "reachable" : "offline"} /> : null}
            <StatusRow label="Sidecar" status={sidecarReachable === null ? "unknown" : sidecarReachable ? "reachable" : "unavailable"} />
            <StatusRow label="Local FastMCP" status={mcpReachable ? "connected" : "offline"} />
            {capabilities
              .filter((item) => item.id !== "endpoint-model" && item.id !== "sidecar-llm" && item.id !== "sidecar-mcp")
              .map((item) => (
                <StatusRow key={item.id} label={item.label} status={item.status} reason={item.reason} />
              ))}
          </dl>
        </>
      ) : null}
      {offline ? (
        <FailurePanel
          error={{
            code: "mcp_unreachable",
            message: "Connectors need the sidecar. Data and conversation still work.",
            retryable: true,
            suggestion: "Start the sidecar, then retry the connector list.",
          }}
          onRetry={() => void refreshConnectors()}
        />
      ) : connectorsError ? (
        <FailurePanel error={connectorsError} onRetry={() => void refreshConnectors()} />
      ) : connectors.length === 0 ? (
        <p className="muted">No connectors registered.</p>
      ) : (
        <ul className="customize__list" aria-label="Installed connectors">
          {connectors.map((connector) => (
            <li key={connector.name} className="customize__row">
              <span className="customize__row-name">{connector.name}</span>
              <span className="customize__badge">{connector.kind}</span>
              {!connector.enabled ? <span className="customize__badge is-muted">disabled</span> : null}
              <button
                type="button"
                className="button button--ghost customize__remove"
                aria-label={`Remove ${connector.name}`}
                onClick={() => void deleteConnector(connector.name)}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      {showManageButton ? (
        <div className="settings__connection-actions">
          <button type="button" className="button settings__manage" onClick={openCustomize}>
            Manage connectors
          </button>
        </div>
      ) : null}
      {allowManualAdd ? (
        <details
          className="settings__manual-connector-disclosure"
          open={manualOpen || offline || Boolean(connectorsError)}
          onToggle={(event) => setManualOpen(event.currentTarget.open)}
        >
          <summary>Add by URL</summary>
          <form className="form settings__manual-connector" onSubmit={submit}>
            <div className="field">
              <label htmlFor={`${headingId}-connector-name`}>Connector name</label>
              <input
                id={`${headingId}-connector-name`}
                className="input"
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                disabled={manualAddDisabled}
                autoComplete="off"
              />
            </div>
            <div className="field">
              <label htmlFor={`${headingId}-connector-url`}>Connector URL</label>
              <input
                id={`${headingId}-connector-url`}
                className="input"
                type="url"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                required
                disabled={manualAddDisabled}
                placeholder="https://example.com/mcp"
                spellCheck={false}
              />
            </div>
            <button type="submit" className="button" disabled={manualAddDisabled || !name.trim() || !url.trim()}>
              Add connector
            </button>
            {manualAddDisabled ? <p className="muted">{manualAddReason ?? "Connectors are unavailable"}</p> : null}
          </form>
        </details>
      ) : null}
    </section>
  );
}
