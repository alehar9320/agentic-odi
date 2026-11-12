/* eslint-disable react-refresh/only-export-components -- context module intentionally exports the hook alongside the provider */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import type { StudioConfig, StudioTheme } from "../../types";
import { resolveTheme } from "../../lib/theme";

export const SETTINGS_KEY = "studio.settings";

export const EMPTY_CONFIG: StudioConfig = {
  base_url: "http://localhost:8001/v1",
  api_key: "local",
  model_name: "local-tools-model",
  mcp_url: "http://localhost:8000/mcp",
};

/** The one field that must never reach a browser store again. */
function withoutSecret(config: StudioConfig): StudioConfig {
  return { ...config, api_key: "" };
}

/** The key a previous version left in `studio.settings`, if any. Read once so it
 *  can be handed to the sidecar's write-only store and then deleted. */
export function readLegacyApiKey(): string | null {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) {
      return null;
    }
    const stored = JSON.parse(raw) as Partial<StudioConfig>;
    const value = typeof stored.api_key === "string" ? stored.api_key : "";
    // The shipped default is not a secret and never needs migrating.
    return value && value !== EMPTY_CONFIG.api_key ? value : null;
  } catch {
    return null;
  }
}

/** Rewrite the store without the key. Idempotent; safe to call after a failed
 *  migration because the key is gone from the browser either way. */
export function clearLegacyApiKey(): void {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) {
      return;
    }
    const stored = JSON.parse(raw) as Partial<StudioConfig>;
    if (!("api_key" in stored)) {
      return;
    }
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(withoutSecret(stored as StudioConfig)));
  } catch {
    /* storage unavailable */
  }
}

function loadSettings(): StudioConfig {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) {
      const stored = JSON.parse(raw) as Partial<StudioConfig>;
      // A stored key is deliberately not read into state: it belongs to the
      // sidecar now, and a page script must not be able to read it back.
      return { ...EMPTY_CONFIG, ...withoutSecret(stored as StudioConfig) };
    }
  } catch {
    /* ignore malformed cache */
  }
  return EMPTY_CONFIG;
}

/** Subscribes to settings and theme together. A theme change re-renders settings
 *  consumers, but the studio root does not subscribe to theme directly, so a
 *  theme change does not re-render the chat surfaces. */
const SettingsContext = createContext<{
  settings: StudioConfig;
  saveSettings: (config: StudioConfig) => void;
  theme: StudioTheme;
  setTheme: (theme: StudioTheme) => void;
} | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<StudioConfig>(loadSettings);
  const theme = useMemo<StudioTheme>(() => resolveTheme(settings.theme), [settings.theme]);

  const saveSettings = useCallback((config: StudioConfig) => {
    setSettings(config);
    try {
      // The model key is the sidecar's to hold; it is written there, never here.
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(withoutSecret(config)));
    } catch {
      /* storage unavailable */
    }
  }, []);

  const setTheme = useCallback((next: StudioTheme) => {
    saveSettings({ ...settings, theme: next });
  }, [settings, saveSettings]);

  // The theme lives on <html> so every surface, portal, and native control
  // follows one class instead of each component tracking its own copy.
  const appliedTheme = useRef<StudioTheme | null>(null);
  useEffect(() => {
    const root = document.documentElement;
    const previous = appliedTheme.current;
    appliedTheme.current = theme;
    root.classList.toggle("theme-light", theme === "light");
    root.classList.toggle("theme-dark", theme === "dark");
    root.style.colorScheme = theme;

    // Only a change the person made cross-fades; the first paint is already the
    // right colour (see index.html). Reduced motion swaps instantly, and the
    // stylesheet's own reduce rule shortens the fade if it somehow runs.
    if (previous === null || previous === theme) {
      return;
    }
    const reduceMotion =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) {
      return;
    }
    root.classList.add("theme-fading");
    const timer = window.setTimeout(() => root.classList.remove("theme-fading"), 140);
    return () => {
      window.clearTimeout(timer);
      root.classList.remove("theme-fading");
    };
  }, [theme]);

  const value = useMemo(() => ({ settings, saveSettings, theme, setTheme }), [
    settings,
    saveSettings,
    theme,
    setTheme,
  ]);

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings() {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error("useSettings must be used within a SettingsProvider");
  }
  return context;
}
