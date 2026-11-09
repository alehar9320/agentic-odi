import { useEffect, useState } from "react";

import { useOnboarding } from "../onboarding/context";
import { useStudio, type ConnectionReport } from "../state/StudioContext";
import { AboutSection } from "./settings/sections/AboutSection";
import { ConnectionsSection } from "./settings/sections/ConnectionsSection";
import { ContextSection } from "./settings/sections/ContextSection";
import { DataSection } from "./settings/sections/DataSection";
import { InstallSection } from "./settings/sections/InstallSection";
import { ModelSection } from "./settings/sections/ModelSection";
import { UpdatesSection } from "./settings/sections/UpdatesSection";

/**
 * Settings is a frame, not a section. Each named section below is its own
 * module that reads its own source and reports its own failure, so a broken
 * connector fetch shows its error in Connections and leaves the model controls
 * beside it working.
 *
 * The one piece of state kept here is the connection survey: opening Settings
 * is the person asking what is connected. The answer belongs to the panel that
 * asked, so a passive read never restyles the window.
 */
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
    connectorsLoading,
    presets,
    presetError,
    presetsLoading,
    refreshPresets,
    refreshConnectors,
    addConnector,
    deleteConnector,
    openCustomize,
    sidecarReachable,
    capabilities,
    surveyConnections,
  } = useStudio();
  const { enabled: tourEnabled, restart: restartTour } = useOnboarding();

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

  return (
    <div className="settings">
      <ContextSection
        brief={brief}
        openSetup={openSetup}
        displayName={displayName}
        setDisplayName={setDisplayName}
        closeSetup={closeSetup}
        clearChat={clearChat}
        refreshCanvas={refreshCanvas}
      />

      <DataSection sidecarReachable={sidecarReachable} />

      <ModelSection
        settings={settings}
        saveSettings={saveSettings}
        models={models}
        modelsLoading={modelsLoading}
        modelsMessage={modelsMessage}
        refreshModels={refreshModels}
      />

      <ConnectionsSection
        settings={settings}
        saveSettings={saveSettings}
        modelHealthy={survey ? survey.llmHealthy : llmHealth.healthy}
        sidecarKnown={survey ? survey.sidecarReachable : sidecarReachable}
        mcpKnown={survey ? survey.mcpReachable : mcpReachable}
        capabilities={capabilities}
        connectors={connectors}
        connectorsError={connectorsError}
        connectorsLoading={connectorsLoading}
        presets={presets}
        presetError={presetError}
        presetsLoading={presetsLoading}
        refreshConnectors={refreshConnectors}
        refreshPresets={refreshPresets}
        addConnector={addConnector}
        deleteConnector={deleteConnector}
        openCustomize={openCustomize}
      />

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
        <div className="settings__tour">
          <h3 className="settings__title">Getting started</h3>
          <p className="muted">
            A three-scene tour on a sample brief, when you want one. It never opens by itself.
          </p>
          <button type="button" className="button button--ghost" onClick={restartTour}>
            Replay the tour
          </button>
        </div>
      ) : null}

      <UpdateSettings />

      <AboutSection settings={settings} capabilities={capabilities} />

      <InstallSection />
    </div>
  );
}
