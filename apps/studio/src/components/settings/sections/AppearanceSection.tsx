import type { StudioConfig, StudioTheme } from "../../../types";
import { MoonIcon, SunIcon } from "../../icons";

export function AppearanceSection({
  settings,
  saveSettings,
  displayName,
  setDisplayName,
  headingId = "settings-appearance-heading",
  sectionId,
  idPrefix = "settings",
}: {
  settings: StudioConfig;
  saveSettings: (config: StudioConfig) => void;
  displayName: string;
  setDisplayName: (name: string) => void;
  headingId?: string;
  sectionId?: string;
  idPrefix?: string;
}) {
  const theme: StudioTheme = settings.theme === "light" ? "light" : "dark";
  const nextTheme: StudioTheme = theme === "dark" ? "light" : "dark";

  return (
    <section id={sectionId} className="settings__section" aria-labelledby={headingId} tabIndex={sectionId ? -1 : undefined}>
      <h3 className="settings__title" id={headingId}>Appearance</h3>
      <div className="field">
        <label htmlFor={`${idPrefix}-display-name`}>
          Your name <span className="field__hint">optional — used in the greeting</span>
        </label>
        <input
          id={`${idPrefix}-display-name`}
          className="input"
          value={displayName}
          placeholder="Ada"
          autoComplete="given-name"
          onChange={(event) => setDisplayName(event.target.value)}
        />
      </div>
      <div className="field">
        <span className="field__hint">Theme</span>
        <button
          type="button"
          className="button button--ghost settings__theme-toggle"
          aria-label={`Switch to ${nextTheme} theme`}
          onClick={() => saveSettings({ ...settings, theme: nextTheme })}
        >
          {theme === "dark" ? <SunIcon size={16} /> : <MoonIcon size={16} />}
          Use {nextTheme} theme
        </button>
      </div>
    </section>
  );
}
