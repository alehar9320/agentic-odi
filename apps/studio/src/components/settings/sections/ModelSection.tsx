import { useState } from "react";

import type { Capability } from "../../../bff/capabilities/registry";
import type { StudioConfig } from "../../../types";
import { StatusRow } from "./StatusRow";

export function ModelSection({
  settings,
  saveSettings,
  models,
  modelsLoading,
  modelsMessage,
  refreshModels,
  allowModelLookup = false,
  headingId = "settings-model-heading",
  sectionId,
  idPrefix = "settings",
  llmHealth,
  capabilities = [],
}: {
  settings: StudioConfig;
  saveSettings: (config: StudioConfig) => void;
  models: string[];
  modelsLoading: boolean;
  modelsMessage: string | null;
  refreshModels: () => Promise<void>;
  allowModelLookup?: boolean;
  headingId?: string;
  sectionId?: string;
  idPrefix?: string;
  llmHealth: { healthy: boolean | null; message: string };
  capabilities?: Capability[];
}) {
  const [showApiKey, setShowApiKey] = useState(false);

  function update<K extends keyof StudioConfig>(key: K, value: StudioConfig[K]): void {
    saveSettings({ ...settings, [key]: value });
  }

  return (
    <section id={sectionId} className="settings__section" aria-labelledby={headingId} tabIndex={sectionId ? -1 : undefined}>
      <h3 className="settings__title" id={headingId}>Model</h3>
      <dl className="connection-list" aria-label="Model status">
        <StatusRow
          label="Model"
          status={llmHealth.healthy === null ? "unknown" : llmHealth.healthy ? "reachable" : "offline"}
        />
        {capabilities
          .filter((item) => item.id === "endpoint-model" || item.id === "sidecar-llm")
          .map((item) => (
            <StatusRow key={item.id} label={item.label} status={item.status} reason={item.reason} />
          ))}
      </dl>
      <div className="field">
        <label htmlFor={`${idPrefix}-base-url`}>Base URL</label>
        <input
          id={`${idPrefix}-base-url`}
          className="input"
          value={settings.base_url}
          spellCheck={false}
          onChange={(event) => update("base_url", event.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor={`${idPrefix}-api-key`}>API key</label>
        <div className="field__row">
          <input
            id={`${idPrefix}-api-key`}
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
      </div>
      <div className="field">
        <label htmlFor={`${idPrefix}-model-name`}>
          Model <span className="field__hint">pick from your endpoint, or type one</span>
        </label>
        <input
          id={`${idPrefix}-model-name`}
          className="input"
          list={models.length ? `${idPrefix}-model-options` : undefined}
          value={settings.model_name}
          spellCheck={false}
          onChange={(event) => update("model_name", event.target.value)}
        />
        {models.length ? (
          <datalist id={`${idPrefix}-model-options`}>
            {models.map((model) => (
              <option key={model} value={model} />
            ))}
          </datalist>
        ) : null}
        {allowModelLookup ? (
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
              <span className="muted">Type the model name — {modelsMessage}</span>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
