import { useEffect, useRef, useState } from "react";

import { useStudio, type ConnectionReport } from "../state/StudioContext";
import {
  SETTINGS_SECTIONS,
  readSettingsSection,
  rememberSettingsSection,
} from "./settings/sections";
import { AboutSection } from "./settings/sections/AboutSection";
import { ConnectionsSection } from "./settings/sections/ConnectionsSection";
import { ContextSection } from "./settings/sections/ContextSection";
import { DataSection } from "./settings/sections/DataSection";
import { InstallSection } from "./settings/sections/InstallSection";
import { ModelSection } from "./settings/sections/ModelSection";
import { UpdatesSection } from "./settings/sections/UpdatesSection";

/**
 * Settings is five named sections behind an index, not one scroll.
 *
 * The sections are declared as data in `settings/sections.ts`, and this panel
 * renders the open one and marks it in the index, so "where do I change the
 * model?" is one click rather than a scroll. The open section is remembered per
 * browser, and an id that is no longer a section falls back to Model.
 *
 * Each section is still its own module that reads its own source and reports
 * its own failure, so a broken connector fetch shows its error in Connections
 * and leaves the model controls working when Model is opened.
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

  const [section, setSection] = useState(() => readSettingsSection());
  const paneRef = useRef<HTMLDivElement>(null);
  // Focus follows a deliberate jump, never the initial render — the lens header
  // already takes focus when Settings opens.
  const jumped = useRef(false);

  useEffect(() => {
    if (jumped.current) {
      paneRef.current?.focus();
    }
  }, [section]);

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

  function openSection(id: string) {
    jumped.current = true;
    setSection(id);
    rememberSettingsSection(id);
  }

  const active =
    SETTINGS_SECTIONS.find((candidate) => candidate.id === section) ?? SETTINGS_SECTIONS[0];

  return (
    <div className="settings">
      <nav className="settings__index" aria-label="Settings sections">
        {SETTINGS_SECTIONS.map((candidate) => (
          <button
            key={candidate.id}
            type="button"
            className={`settings__index-link${candidate.id === active.id ? " is-active" : ""}`}
            aria-current={candidate.id === active.id ? "true" : undefined}
            title={candidate.blurb}
            onClick={() => openSection(candidate.id)}
          >
            {candidate.label}
          </button>
        ))}
      </nav>

      <div className="settings__pane" data-section={active.id} ref={paneRef} tabIndex={-1}>
        <p className="settings__blurb">{active.blurb}</p>

        {active.id === "settings-model" ? (
          <ModelSection
            settings={settings}
            saveSettings={saveSettings}
            models={models}
            modelsLoading={modelsLoading}
            modelsMessage={modelsMessage}
            refreshModels={refreshModels}
          />
        ) : null}

        {active.id === "settings-connections" ? (
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
        ) : null}

        {active.id === "settings-data" ? (
          <>
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
          </>
        ) : null}

        {active.id === "settings-updates" ? (
          <>
            <UpdatesSection />
            <InstallSection />
          </>
        ) : null}

        {active.id === "settings-about" ? (
          <AboutSection settings={settings} capabilities={capabilities} />
        ) : null}
      </div>
    </div>
  );
}
