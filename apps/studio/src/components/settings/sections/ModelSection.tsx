import { useState } from "react";

import type { StudioConfig } from "../../../types";
import { SavedField, SectionSaveLine } from "../SavedField";
import { useSectionSaves } from "../saves";
import { validateApiKey, validateBaseUrl, validateModelName } from "../validation";

interface ModelSectionProps {
  settings: StudioConfig;
  saveSettings: (config: StudioConfig) => void;
  models: string[];
  modelsLoading: boolean;
  modelsMessage: string | null;
  refreshModels: () => Promise<void> | void;
}

/**
 * The model endpoint, saved one field at a time.
 *
 * Each field writes on blur, so a value typed here survives leaving the panel,
 * and an endpoint the studio cannot parse is refused beside the field instead of
 * replacing a working one.
 */
export function ModelSection({
  settings,
  saveSettings,
  models,
  modelsLoading,
  modelsMessage,
  refreshModels,
}: ModelSectionProps) {
  const [showApiKey, setShowApiKey] = useState(false);
  const { report, summary } = useSectionSaves();

  const commit = (key: keyof StudioConfig) => (value: string) =>
    saveSettings({ ...settings, [key]: value });

  return (
    <div className="settings__section">
      <h3 className="settings__title" id="settings-model-heading">
        Model
      </h3>
      <SavedField
        id="base-url"
        label="Base URL"
        value={settings.base_url}
        spellCheck={false}
        validate={validateBaseUrl}
        onCommit={commit("base_url")}
        onStatusChange={(status) => report("base_url", status)}
      />
      <SavedField
        id="api-key"
        label="API key"
        value={settings.api_key}
        type={showApiKey ? "text" : "password"}
        autoComplete="off"
        validate={validateApiKey}
        onCommit={commit("api_key")}
        onStatusChange={(status) => report("api_key", status)}
        trailing={
          <button
            type="button"
            className="quiet-action"
            aria-label={showApiKey ? "Hide API key" : "Show API key"}
            onClick={() => setShowApiKey((visible) => !visible)}
          >
            {showApiKey ? "Hide" : "Show"}
          </button>
        }
      />
      <SavedField
        id="model-name"
        label={
          <>
            Model <span className="field__hint">pick from your endpoint, or type one</span>
          </>
        }
        value={settings.model_name}
        spellCheck={false}
        list={models.length ? "studio-model-options" : undefined}
        validate={validateModelName}
        onCommit={commit("model_name")}
        onStatusChange={(status) => report("model_name", status)}
        after={
          <>
            {models.length ? (
              <datalist id="studio-model-options">
                {models.map((model) => (
                  <option key={model} value={model} />
                ))}
              </datalist>
            ) : null}
            <div className="settings__model-state">
              <button
                type="button"
                className="quiet-action"
                disabled={modelsLoading}
                onClick={() => void refreshModels()}
              >
                {modelsLoading ? "Looking for models…" : "Find models"}
              </button>
              {models.length ? (
                <span className="muted">
                  {models.length} model{models.length === 1 ? "" : "s"} available
                </span>
              ) : modelsMessage ? (
                // The endpoint would not list what it serves; typing still works.
                <span className="muted">Type the model name — {modelsMessage}</span>
              ) : null}
            </div>
          </>
        }
      />
      <SectionSaveLine status={summary} />
    </div>
  );
}
