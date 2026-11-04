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

function asId(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

export function loadSession(): StudioSession | null {
  const raw = localStorage.getItem(SESSION_KEY);
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
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  localStorage.removeItem(SESSION_KEY);
}
