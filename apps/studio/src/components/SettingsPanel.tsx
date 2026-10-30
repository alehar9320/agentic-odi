import { useEffect } from "react";

import { useStudio } from "../state/StudioContext";
import { AppearanceSection } from "./settings/sections/AppearanceSection";
import { AdvancedSection } from "./settings/sections/AdvancedSection";
import { ConnectionsSection } from "./settings/sections/ConnectionsSection";
import { DataSection } from "./settings/sections/DataSection";
import { ModelSection } from "./settings/sections/ModelSection";

const SECTIONS = [
  ["settings-model", "Model"],
  ["settings-data", "Data"],
  ["settings-appearance", "Appearance"],
  ["settings-connections", "Connections"],
  ["settings-advanced", "Advanced"],
] as const;

export function SettingsPanel() {
  const {
    settings,
    saveSettings,
    displayName,
    setDisplayName,
    brief,
    openSetup,
    canvasState,
    refreshCanvas,
    closeSetup,
    clearChat,
    llmHealth,
    models,
    modelsLoading,
    modelsMessage,
    refreshModels,
    mcpReachable,
    connectors,
    connectorsError,
    refreshConnectors,
    addConnector,
    deleteConnector,
    openCustomize,
    sidecarReachable,
    capabilities,
  } = useStudio();

  useEffect(() => {
    void refreshConnectors();
  }, [refreshConnectors]);

  return (
    <div className="settings">
      <nav className="settings__nav" aria-label="Settings sections">
        {SECTIONS.map(([id, label]) => (
          <button
            key={id}
            type="button"
            className="settings__nav-link"
            onClick={() => {
              const section = document.getElementById(id);
              section?.focus({ preventScroll: true });
              section?.scrollIntoView({ block: "start", behavior: "smooth" });
            }}
          >
            {label}
          </button>
        ))}
      </nav>
      <ModelSection
        sectionId="settings-model"
        settings={settings}
        saveSettings={saveSettings}
        models={models}
        modelsLoading={modelsLoading}
        modelsMessage={modelsMessage}
        refreshModels={() => refreshModels()}
        allowModelLookup
        llmHealth={llmHealth}
        capabilities={capabilities}
      />
      <DataSection
        sectionId="settings-data"
        brief={brief}
        openSetup={openSetup}
        canvas={canvasState.data}
        refreshCanvas={refreshCanvas}
        startNewConversation={() => {
          closeSetup();
          clearChat();
        }}
      />
      <AppearanceSection
        sectionId="settings-appearance"
        settings={settings}
        saveSettings={saveSettings}
        displayName={displayName}
        setDisplayName={setDisplayName}
      />
      <ConnectionsSection
        sectionId="settings-connections"
        connectors={connectors}
        connectorsError={connectorsError}
        refreshConnectors={refreshConnectors}
        addConnector={addConnector}
        deleteConnector={deleteConnector}
        openCustomize={() => openCustomize({ tab: "connectors" })}
        sidecarReachable={sidecarReachable}
        mcpReachable={mcpReachable}
        llmHealth={llmHealth}
        capabilities={capabilities}
        showModelStatus
        settings={settings}
        saveSettings={saveSettings}
      />
      <AdvancedSection sectionId="settings-advanced" />
    </div>
  );
}
