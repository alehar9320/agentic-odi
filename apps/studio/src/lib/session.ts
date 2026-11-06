/**
 * The studio's last focused subject, kept in the browser so a refresh or a
 * closed tab reopens on the same job, step, or outcome. The schema mirrors the
 * three ODI entities a session can sit on; evidence has no slot, so focusing
 * evidence does not overwrite the stored context. ``conversation_id`` keeps the
 * last opened thread so a reload reopens the conversation the person left.
 */
export interface StudioSession {
  job_id: string | null;
  step_id: string | null;
  outcome_id: string | null;
  conversation_id: string | null;
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
    conversation_id: asId(record.conversation_id),
  };
}

export function saveSession(session: StudioSession): void {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  localStorage.removeItem(SESSION_KEY);
}

/** The conversation id the person last had open, persisted so a reload
 *  reopens the same thread. Returns ``null`` when none has been stored yet.
 */
export function loadStoredConversationId(): string | null {
  const session = loadSession();
  return session?.conversation_id ?? null;
}

/** Persist the conversation the person has just opened so it survives a
 *  reload. Merges into any existing session so the focused subject is kept.
 */
export function saveStoredConversationId(conversationId: string): void {
  const session = loadSession() ?? emptySession();
  session.conversation_id = conversationId;
  saveSession(session);
}

function emptySession(): StudioSession {
  return { job_id: null, step_id: null, outcome_id: null, conversation_id: null };
}
