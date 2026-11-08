import { SCENES } from "./content";
import {
  ONBOARDING_VERSION,
  createOnboardingState,
  type OnboardingState,
  type OnboardingStatus,
  type SkipReason,
} from "./machine";

/**
 * Versioned, defensive persistence for the tour. A malformed or outdated record
 * behaves exactly like a first run, never like a crash.
 */

export const ONBOARDING_STORAGE_KEY = "studio.onboarding";

export type OnboardingStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

const STATUSES: OnboardingStatus[] = ["pending", "active", "done", "skipped"];
const SKIP_REASONS: SkipReason[] = ["not-now", "dismissed"];

function browserStorage(): OnboardingStorage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function parseState(raw: string): OnboardingState | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof parsed !== "object" || parsed === null) {
    return null;
  }

  const candidate = parsed as Record<string, unknown>;
  if (candidate.version !== ONBOARDING_VERSION) {
    return null;
  }
  if (!STATUSES.includes(candidate.status as OnboardingStatus)) {
    return null;
  }
  if (
    typeof candidate.scene !== "number" ||
    !Number.isInteger(candidate.scene) ||
    candidate.scene < 0 ||
    candidate.scene >= SCENES.length
  ) {
    return null;
  }
  // A reason belongs only to a skipped tour, and must be one we wrote.
  if (candidate.reason !== null && !SKIP_REASONS.includes(candidate.reason as SkipReason)) {
    return null;
  }
  if (candidate.status === "skipped" && candidate.reason === null) {
    return null;
  }
  if (candidate.status !== "skipped" && candidate.reason !== null) {
    return null;
  }

  return createOnboardingState({
    status: candidate.status as OnboardingStatus,
    scene: candidate.scene,
    reason: (candidate.reason as SkipReason | null) ?? null,
  });
}

export function readOnboardingState(
  storage: OnboardingStorage | null = browserStorage(),
): OnboardingState | null {
  if (!storage) {
    return null;
  }
  try {
    const raw = storage.getItem(ONBOARDING_STORAGE_KEY);
    return raw ? parseState(raw) : null;
  } catch {
    return null;
  }
}

export function writeOnboardingState(
  state: OnboardingState,
  storage: OnboardingStorage | null = browserStorage(),
): void {
  if (!storage) {
    return;
  }
  try {
    storage.setItem(ONBOARDING_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Storage full or denied: the tour still works for this session.
  }
}

export function clearOnboardingState(
  storage: OnboardingStorage | null = browserStorage(),
): void {
  if (!storage) {
    return;
  }
  try {
    storage.removeItem(ONBOARDING_STORAGE_KEY);
  } catch {
    // Nothing to do.
  }
}
