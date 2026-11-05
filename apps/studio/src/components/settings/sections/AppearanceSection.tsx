import type { StudioConfig, StudioThemePreference } from "../../../types";
import { storedPreference } from "../../../lib/theme";
import { useStudio } from "../../../state/StudioContext";

const CHOICES: { value: StudioThemePreference; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "Follow the system" },
];

interface AppearanceSectionProps {
  settings: StudioConfig;
  saveSettings: (config: StudioConfig) => void;
}

/**
 * Which palette the Studio paints, chosen once and kept.
 *
 * The three radios are the whole preference: a stored `light` or `dark` pins the
 * palette, `system` follows the operating system and keeps following it as it
 * moves. A reader who has never opened this control has no stored value at all,
 * which means the same thing as `system` — the dot sits there rather than
 * leaving an arrow-key group with no landing point. There is no local state: the
 * checked radio is the stored preference, so the control cannot claim a choice
 * persistence did not keep.
 */
export function AppearanceSection({ settings, saveSettings }: AppearanceSectionProps) {
  const theme = useStudio().theme;
  const stored = storedPreference(settings.theme);

  return (
    <div
      className="settings__section"
      aria-labelledby="settings-appearance-heading"
    >
      <h3 className="settings__title" id="settings-appearance-heading">
        Appearance
      </h3>
      <fieldset
        className="settings__theme"
        role="radiogroup"
      >
        <legend className="settings__theme-legend">Theme</legend>
        {CHOICES.map((choice) => (
          <label
            className="settings__theme-option"
            key={choice.value}
          >
            <input
              type="radio"
              name="studio-theme"
              value={choice.value}
              checked={stored === choice.value}
              onChange={() => saveSettings({ ...settings, theme: choice.value })}
            />
            {choice.label}
          </label>
        ))}
      </fieldset>
      <p className="settings__theme-palette muted">
        {stored === "system"
          ? `The operating system is showing ${theme}.`
          : `${theme === "light" ? "Light" : "Dark"} is on screen.`}
      </p>
    </div>
  );
}
