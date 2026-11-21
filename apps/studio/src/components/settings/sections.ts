/**
 * The five named Settings sections, declared as data.
 *
 * The panel renders one section at a time behind an index built from this list,
 * so adding a section is a row here rather than another branch in the panel.
 * `id` doubles as the section's anchor and as the value remembered between
 * visits; `label` names the index button; `blurb` says what the section is for.
 */

export interface SettingsSection {
  id: string;
  label: string;
  blurb: string;
}

export const SETTINGS_SECTIONS: readonly SettingsSection[] = [
  {
    id: "settings-model",
    label: "Model",
    blurb: "The endpoint, key, and model the studio talks to.",
  },
  {
    id: "settings-connections",
    label: "Connections",
    blurb: "The bridge, the services it reaches, and the connectors you installed.",
  },
  {
    id: "settings-data",
    label: "Data",
    blurb: "Your context, your name, and the actions that start fresh.",
  },
  {
    id: "settings-updates",
    label: "Updates",
    blurb: "The running version, software updates, and the install prompt.",
  },
  {
    id: "settings-about",
    label: "About",
    blurb: "What this build is, and how the studio works.",
  },
];

export const DEFAULT_SETTINGS_SECTION = SETTINGS_SECTIONS[0].id;

/** Where the open section is remembered. Per browser, not per config. */
export const SETTINGS_SECTION_KEY = "studio.settings.section";

export function isSettingsSection(value: string | null): value is string {
  return value !== null && SETTINGS_SECTIONS.some((section) => section.id === value);
}

/** The remembered section, or Model when nothing usable was stored. */
export function readSettingsSection(): string {
  try {
    const stored = window.localStorage.getItem(SETTINGS_SECTION_KEY);
    return isSettingsSection(stored) ? stored : DEFAULT_SETTINGS_SECTION;
  } catch {
    return DEFAULT_SETTINGS_SECTION;
  }
}

export function rememberSettingsSection(id: string): void {
  try {
    window.localStorage.setItem(SETTINGS_SECTION_KEY, id);
  } catch {
    /* storage unavailable: the choice still holds for this session */
  }
}
