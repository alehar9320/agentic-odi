/**
 * Remember which overnight briefing the reader has already dismissed.
 *
 * The mark is per `run_id` + `created_at` and lives in localStorage: it is
 * per-browser reading state, like the changelog acknowledgement, not something
 * the store owns. The briefing itself is served by the sidecar; the "I have
 * read this one" is not.
 *
 * Keying on ``run_id`` alone is not enough: a cron work item reuses one id on
 * every run, so a single dismissal would hide every later briefing for that
 * work item. Combining ``run_id`` with ``created_at`` keys each briefing
 * instance.
 */

export const BRIEFING_DISMISSED_KEY = "agentic-odi.briefing.dismissed";

/** Only the most recent run ids matter; nobody scrolls back further than this. */
const MAX_REMEMBERED = 50;

/** Build the storage key for one briefing instance. */
export function dismissalKey(runId: string, createdAt: string): string {
  return `${runId}:${createdAt}`;
}

export function readDismissedKeys(): string[] {
  try {
    const raw = window.localStorage.getItem(BRIEFING_DISMISSED_KEY);
    if (!raw) {
      return [];
    }
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((value): value is string => typeof value === "string");
  } catch {
    return [];
  }
}

/** Record one briefing instance as dismissed and return the merged list. */
export function markBriefingDismissed(runId: string, createdAt: string): string[] {
  const key = dismissalKey(runId, createdAt);
  const merged = [...new Set([...readDismissedKeys(), key])];
  const next = merged.slice(-MAX_REMEMBERED);
  try {
    window.localStorage.setItem(BRIEFING_DISMISSED_KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable: the card still hides for this session */
  }
  return next;
}

export function isBriefingDismissed(runId: string, createdAt: string): boolean {
  return readDismissedKeys().includes(dismissalKey(runId, createdAt));
}
