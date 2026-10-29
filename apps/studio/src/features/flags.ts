/**
 * Feature flags for the studio client.
 *
 * A flag is resolved once per read, highest precedence first:
 *
 *   1. `?flags=<name>:<value>`      — QA and demos without a rebuild
 *   2. `localStorage["studio.flags.<name>"]`
 *   3. the flag's build-time env variable
 *   4. the flag's declared default
 *
 * Unknown values fall through to the next source, so a typo in a query string
 * can never silently change behaviour.
 */

export type FeatureFlagName = "firstRunWizard";

export interface FeatureFlagDefinition {
  name: FeatureFlagName;
  description: string;
  envVar: string;
  defaultEnabled: boolean;
}

export const FEATURE_FLAGS: Record<FeatureFlagName, FeatureFlagDefinition> = {
  firstRunWizard: {
    name: "firstRunWizard",
    description: "The optional four-step product tour, opened from the home stage or Settings.",
    envVar: "VITE_STUDIO_FIRST_RUN_WIZARD",
    defaultEnabled: true,
  },
};

export const FLAG_STORAGE_PREFIX = "studio.flags.";
export const FLAG_QUERY_PARAM = "flags";

export type FlagSource = "query" | "storage" | "env" | "default";

export interface ResolvedFlag {
  enabled: boolean;
  source: FlagSource;
  raw: string | null;
}

export interface FlagSources {
  env?: string | null;
  stored?: string | null;
  query?: string | null;
}

const TRUTHY = new Set(["1", "true", "on", "yes", "enabled"]);
const FALSY = new Set(["0", "false", "off", "no", "disabled"]);

export function parseFlagValue(raw: string | null | undefined): boolean | null {
  if (raw === null || raw === undefined) {
    return null;
  }
  const normalized = raw.trim().toLowerCase();
  if (TRUTHY.has(normalized)) {
    return true;
  }
  if (FALSY.has(normalized)) {
    return false;
  }
  return null;
}

function readEnvFlag(definition: FeatureFlagDefinition): string | null {
  const env = import.meta.env as Record<string, unknown>;
  const raw = env[definition.envVar];
  if (raw === undefined || raw === null) {
    return null;
  }
  return String(raw);
}

function readStoredFlag(definition: FeatureFlagDefinition): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage.getItem(`${FLAG_STORAGE_PREFIX}${definition.name}`);
  } catch {
    // Private browsing modes can deny storage access.
    return null;
  }
}

/** `?flags=firstRunWizard:off,otherFlag:on` */
function readQueryFlag(definition: FeatureFlagDefinition): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  const params = new URLSearchParams(window.location.search);
  for (const group of params.getAll(FLAG_QUERY_PARAM)) {
    for (const pair of group.split(",")) {
      const separator = pair.indexOf(":");
      if (separator === -1) {
        continue;
      }
      if (pair.slice(0, separator).trim() !== definition.name) {
        continue;
      }
      const value = pair.slice(separator + 1).trim();
      if (value) {
        return value;
      }
    }
  }
  return null;
}

function defaultSources(definition: FeatureFlagDefinition): Required<FlagSources> {
  return {
    query: readQueryFlag(definition),
    stored: readStoredFlag(definition),
    env: readEnvFlag(definition),
  };
}

export function resolveFlag(name: FeatureFlagName, sources?: FlagSources): ResolvedFlag {
  const definition = FEATURE_FLAGS[name];
  const resolved = sources ?? defaultSources(definition);

  const candidates: { source: FlagSource; raw: string | null | undefined }[] = [
    { source: "query", raw: resolved.query },
    { source: "storage", raw: resolved.stored },
    { source: "env", raw: resolved.env },
  ];

  for (const candidate of candidates) {
    const parsed = parseFlagValue(candidate.raw);
    if (parsed !== null) {
      return { enabled: parsed, source: candidate.source, raw: candidate.raw ?? null };
    }
  }

  return { enabled: definition.defaultEnabled, source: "default", raw: null };
}

export function isFeatureEnabled(name: FeatureFlagName, sources?: FlagSources): boolean {
  return resolveFlag(name, sources).enabled;
}

/** Persist a local override. Pass `null` to fall back to env/default. */
export function setFeatureOverride(name: FeatureFlagName, enabled: boolean | null): void {
  if (typeof window === "undefined") {
    return;
  }
  const key = `${FLAG_STORAGE_PREFIX}${name}`;
  try {
    if (enabled === null) {
      window.localStorage.removeItem(key);
      return;
    }
    window.localStorage.setItem(key, enabled ? "on" : "off");
  } catch {
    // Storage is an optimisation; the flag still resolves from env/default.
  }
}

export function clearFeatureOverride(name: FeatureFlagName): void {
  setFeatureOverride(name, null);
}
