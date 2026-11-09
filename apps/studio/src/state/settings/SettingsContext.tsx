/* eslint-disable react-refresh/only-export-components -- context module intentionally exports the hook and constants alongside the provider */
import { createContext, useContext, useMemo, type ReactNode } from "react";

import type { StudioConfig, StudioTheme } from "../../types";

/**
 * Settings and theme: the two things a person changes in Settings, split from
 * the rest of the studio so a theme change does not re-render a toast or
 * landscape consumer, and a toast does not re-render a settings consumer.
 */
export interface SettingsContextValue {
  settings: StudioConfig;
  saveSettings: (config: StudioConfig) => void;
  theme: StudioTheme;
  setTheme: (theme: StudioTheme) => void;
}

const SettingsContext = createContext<SettingsContextValue | null>(null);

type SettingsProviderProps = {
  children: ReactNode;
} & SettingsContextValue;

export function SettingsProvider({
  children,
  settings,
  saveSettings,
  theme,
  setTheme,
}: SettingsProviderProps) {
  const value = useMemo<SettingsContextValue>(
    () => ({ settings, saveSettings, theme, setTheme }),
    [settings, saveSettings, theme, setTheme],
  );
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings(): SettingsContextValue {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error("useSettings must be used within a SettingsProvider");
  }
  return context;
}
