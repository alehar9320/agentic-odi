import type { StudioConfig, StudioTheme } from "../../../types";

interface AppearanceSectionProps {
  settings: StudioConfig;
  saveSettings: (config: StudioConfig) => void;
}

const THEME_CHOICES: { value: StudioTheme; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

function pinnedTheme(theme: StudioConfig["theme"]): StudioTheme {
  // Anything the app never offered — a hand-edited value, a future option this
  // build does not know — defers to the operating system rather than painting nothing.
  return theme === "light" || theme === "dark" ? theme : "system";
}

/**
 * The palette control.
 *
 * Light and Dark pin the palette; System defers to the operating system and keeps
 * deferring, so a sunset switch lands on the studio the person asked for. System is
 * stored rather than deleted so the choice survives a reload and stays tellable
 * apart from a studio nobody has configured yet.
 */
export function AppearanceSection({ settings, saveSettings }: AppearanceSectionProps) {
  const pinned = pinnedTheme(settings.theme);

  return (
    <div className="settings__section">
      <h3 className="settings__title" id="settings-theme-heading">
        Theme
      </h3>
      <div className="theme-choices" role="radiogroup" aria-labelledby="settings-theme-heading">
        <div className="theme-choices__options">
          {THEME_CHOICES.map((choice) => (
            <label className="theme-choice" key={choice.value}>
              <input
                type="radio"
                name="theme"
                value={choice.value}
                checked={pinned === choice.value}
                onChange={() => saveSettings({ ...settings, theme: choice.value })}
              />
              <span>{choice.label}</span>
            </label>
          ))}
        </div>
        <p className="field__hint">
          Light and Dark keep their palette whatever the operating system does. System follows your
          operating system and switches when it does.
        </p>
      </div>
    </div>
  );
}
