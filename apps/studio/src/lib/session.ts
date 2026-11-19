/**
 * The studio's last focused subject, kept in the browser so a refresh or a
 * closed tab reopens on the same job, step, or outcome. The schema mirrors the
 * three ODI entities a session can sit on; evidence has no slot, so focusing
 * evidence does not overwrite the stored context.
 */
export interface StudioSession {
  job_id: string | null;
  step_id: string | null;
  outcome_id: string | null;
}

export const SESSION_KEY = "studio.session";

function sessionStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function asId(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

export function loadSession(): StudioSession | null {
  const storage = sessionStorage();
  if (!storage) {
    return null;
  }
  let raw: string | null;
  try {
    raw = storage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
  if (!raw) {
    return null;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof parsed !== "object" || parsed === null) {
    return null;
  }
  const record = parsed as Record<string, unknown>;
  return {
    job_id: asId(record.job_id),
    step_id: asId(record.step_id),
    outcome_id: asId(record.outcome_id),
  };
}

export function saveSession(session: StudioSession): void {
  const storage = sessionStorage();
  if (!storage) {
    return;
  }
  try {
    storage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    // Storage denied or full: the session is a convenience, not state.
  }
}

export function clearSession(): void {
  const storage = sessionStorage();
  if (!storage) {
    return;
  }
  try {
    storage.removeItem(SESSION_KEY);
  } catch {
    // Storage denied or full: nothing to clear.
  }
}
