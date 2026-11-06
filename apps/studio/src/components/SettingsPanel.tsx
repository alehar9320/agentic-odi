import { useEffect, useState } from "react";

import { useOnboarding } from "../onboarding/context";
import { useStudio } from "../state/StudioContext";
import type { ConnectionReport } from "../state/StudioContext";
import type { ConnectorPreset } from "../types";
import { FailurePanel } from "./FailurePanel";
import { StatusDot } from "./status/StatusDot";
import { AboutSection } from "./settings/sections/AboutSection";
import { ConnectionsSection } from "./settings/sections/ConnectionsSection";
import { ModelSection } from "./settings/sections/ModelSection";
import { UpdatesSection } from "./settings/sections/UpdatesSection";
import { initInstall, isDismissed, isInstalled, offerInstall, dismissInstall } from "../install";

function InstallSection() {
  const canInstall = !isInstalled() && !isDismissed();
  return (
    <section className="settings__install" aria-labelledby="settings-install-heading">
      <h3 className="settings__title" id="settings-install-heading">
        Install
      </h3>
      <p className="muted">
        Open the Studio in its own window. The site works offline and the window
        keeps your place when you reopen it.
      </p>
      {canInstall ? (
        <button
          type="button"
          className="button button--ghost"
          onClick={() => {
            const offered = offerInstall();
            if (!offered) {
              dismissInstall();
            }
          }}
        >
          Install app
        </button>
      ) : null}
    </section>
  );
}

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
    closeSetup,
    clearChat,
    refreshCanvas,
    llmHealth,
    models,
    modelsLoading,
    modelsMessage,
    refreshModels,
    mcpReachable,
    connectors,
    connectorsError,
    presets,
    presetError,
    refreshPresets,
    refreshConnectors,
    addConnector,
    deleteConnector,
    openCustomize,
    sidecarReachable,
    capabilities,
    surveyConnections,
  } = useStudio();
  const { enabled: tourEnabled, openTour } = useOnboarding();

  // Opening Settings is the person asking what is connected, which is the first moment
  // a probe is owed to them. The answer is kept here, in the panel that asked: a passive
  // read of a settings page must not restyle the window, because the hosted studio
  // cannot reach a sidecar by design and its silence is not an outage to announce.
  const [survey, setSurvey] = useState<ConnectionReport | null>(null);
  useEffect(() => {
    let cancelled = false;
    void surveyConnections()
      .then((report) => {
        if (!cancelled) {
          setSurvey(report);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
    // Once per open: typing a URL must not re-probe per keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Offer the app install prompt once; dismissal is remembered.
  useEffect(() => {
    initInstall();
  }, []);

  const modelHealthy = survey ? survey.llmHealthy : llmHealth.healthy;
  const sidecarKnown = survey ? survey.sidecarReachable : sidecarReachable;
  const mcpKnown = survey ? survey.mcpReachable : mcpReachable;

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
          {brief?.v2mom?.vision && (
            <p className="settings__context-value">
              <strong>Vision:</strong> {brief.v2mom.vision}
            </p>
          )}
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

      <ModelSection
        settings={settings}
        saveSettings={saveSettings}
        models={models}
        modelsLoading={modelsLoading}
        modelsMessage={modelsMessage}
        refreshModels={refreshModels}
      />

      <ConnectionsSection settings={settings} saveSettings={saveSettings}>
        <ul className="connection-list">
          <li>
            <StatusDot
              tone={modelHealthy === false ? "warn" : modelHealthy === null ? "unknown" : "ok"}
            />
            <span>Model</span>
            <span className="connection-list__value">
              {modelHealthy === false
                ? "offline"
                : modelHealthy === null
                  ? "not checked"
                  : "reachable"}
            </span>
          </li>
          <li>
            <StatusDot
              tone={sidecarKnown === false ? "warn" : sidecarKnown === null ? "unknown" : "ok"}
            />
            <span>Sidecar</span>
            <span className="connection-list__value">
              {sidecarKnown === false ? "unavailable" : sidecarKnown === null ? "unknown" : "reachable"}
            </span>
          </li>
          <li>
            <StatusDot tone={mcpKnown ? "ok" : "unknown"} />
            <span>Local FastMCP server</span>
            <span className="connection-list__value">{mcpKnown ? "connected" : "offline"}</span>
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
              <StatusDot tone={capability.status === "available" ? "ok" : "warn"} />
              <span>{capability.label}</span>
              <span className="connection-list__value">
                {capability.status === "available" ? "available" : "unavailable"}
                {capability.reason ? ` — ${capability.reason}` : ""}
              </span>
            </li>
          ))}
        </ul>

        {sidecarKnown === false ? (
          <p className="muted">
            Connectors require the local sidecar. Data and conversation still work
            without it; connect a sidecar to add MCP or REST data sources.
          </p>
        ) : (
          <>
            <h3 className="settings__title">Connectors</h3>
            <button
              type="button"
              className="button settings__manage"
              onClick={() => openCustomize()}
            >
              Manage connectors
            </button>
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
      </ConnectionsSection>

      <div className="settings__actions">
        <button
          type="button"
          className="button"
          onClick={() => {
            closeSetup();
            clearChat();
          }}
        >
          Start a new conversation
        </button>
        <button type="button" className="button button--ghost" onClick={() => void refreshCanvas()}>
          Sync canvas
        </button>
      </div>

      {tourEnabled ? (
        <p className="settings__tour">
          <button type="button" className="button button--ghost" onClick={openTour}>
            Take the tour
          </button>
        </p>
      ) : null}

      <UpdatesSection />

      <AboutSection settings={settings} capabilities={capabilities} />
      <InstallSection />
    </div>
  );
}
