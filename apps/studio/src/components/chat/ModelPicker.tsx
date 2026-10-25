import { useStudio } from "../../state/StudioContext";

/**
 * Model selection where the model is actually in view: the composer's status
 * line. A native select keeps keyboard and screen-reader behaviour for free, and
 * the configured name is always an option — a provider that publishes no
 * catalog, or a hand-typed model, never disappears from the control.
 */
export function ModelPicker({ offline }: { offline: boolean }) {
  const { settings, saveSettings, models, modelsLoading, modelsMessage } = useStudio();

  if (offline) {
    return <span className="composer__status is-offline">Local guidance</span>;
  }

  if (models.length === 0) {
    return (
      <span
        className="composer__status"
        title={
          modelsMessage ?? (modelsLoading ? "Asking the endpoint which models it serves…" : undefined)
        }
      >
        {settings.model_name}
      </span>
    );
  }

  const custom = models.includes(settings.model_name) ? null : settings.model_name;

  return (
    <span className="composer__model">
      <select
        className="composer__model-select"
        aria-label="Model"
        value={settings.model_name}
        onChange={(event) => saveSettings({ ...settings, model_name: event.target.value })}
      >
        {custom ? <option value={custom}>{custom}</option> : null}
        {models.map((model) => (
          <option key={model} value={model}>
            {model}
          </option>
        ))}
      </select>
      <span className="composer__model-caret" aria-hidden="true">
        ▾
      </span>
    </span>
  );
}
