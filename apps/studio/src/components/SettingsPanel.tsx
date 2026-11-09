import { useEffect, useState } from "react";

import { useOnboarding } from "../onboarding/context";
import { useStudio, type ConnectionReport } from "../state/StudioContext";
import { useSettings } from "../state/settings/SettingsContext";
import { AboutSection } from "./settings/sections/AboutSection";
import { ConnectionsSection } from "./settings/sections/ConnectionsSection";
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
  const { settings, saveSettings } = useSettings();
  const {
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
      <DataSection
        brief={brief}
        openSetup={openSetup}
        displayName={displayName}
        setDisplayName={setDisplayName}
        closeSetup={closeSetup}
        clearChat={clearChat}
        refreshCanvas={refreshCanvas}
      />

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

      <UpdatesSection tourEnabled={tourEnabled} restartTour={restartTour} />

      <AboutSection settings={settings} capabilities={capabilities} />

      <InstallSection />
    </div>
  );
}
