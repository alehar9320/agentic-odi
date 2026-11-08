import { SCENES } from "./content";
import {
  ONBOARDING_VERSION,
  createOnboardingState,
  type OnboardingState,
  type OnboardingStatus,
  type SkipReason,
} from "./machine";

/**
 * Versioned, defensive persistence for the tour. A malformed, outdated, or
 * differently-shaped record behaves exactly like a first run, never like a
 * crash — including the four-step shape an older build wrote.
 */

export const ONBOARDING_STORAGE_KEY = "studio.onboarding";

export type OnboardingStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

const STATUSES: OnboardingStatus[] = ["pending", "open", "done", "skipped"];
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

function isSkipReason(value: unknown): value is SkipReason {
  return typeof value === "string" && (SKIP_REASONS as string[]).includes(value);
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
  // Only a skipped tour carries a reason; anything else is malformed.
  if (candidate.status === "skipped") {
    if (!isSkipReason(candidate.reason)) {
      return null;
    }
  } else if (candidate.reason !== null) {
    return null;
  }

  return createOnboardingState({
    status: candidate.status as OnboardingStatus,
    scene: candidate.scene,
    reason: isSkipReason(candidate.reason) ? candidate.reason : null,
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
