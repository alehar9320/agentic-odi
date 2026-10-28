import { GOALS, GOAL_STEP_INDEX, STEPS, type GoalId } from "./content";
import {
  ONBOARDING_VERSION,
  createOnboardingState,
  type OnboardingState,
  type OnboardingStatus,
} from "./machine";

/**
 * Versioned, defensive persistence for the tour. A malformed or outdated record
 * behaves exactly like a first run, never like a crash.
 */

export const ONBOARDING_STORAGE_KEY = "studio.onboarding";

export type OnboardingStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

const STATUSES: OnboardingStatus[] = ["pending", "active", "done", "skipped"];
const GOAL_IDS = new Set<string>(GOALS.map((goal) => goal.id));

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

function isGoalId(value: unknown): value is GoalId {
  return typeof value === "string" && GOAL_IDS.has(value);
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
    typeof candidate.step !== "number" ||
    !Number.isInteger(candidate.step) ||
    candidate.step < 0 ||
    candidate.step >= STEPS.length
  ) {
    return null;
  }
  if (candidate.goal !== null && !isGoalId(candidate.goal)) {
    return null;
  }
  // Past the starting-point step, the tour always has a chosen goal.
  if (candidate.step > GOAL_STEP_INDEX && !isGoalId(candidate.goal)) {
    return null;
  }

  return createOnboardingState({
    status: candidate.status as OnboardingStatus,
    step: candidate.step,
    goal: (candidate.goal as GoalId | null) ?? null,
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
