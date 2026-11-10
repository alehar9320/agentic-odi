/**
 * Remember which overnight briefing the reader has already dismissed.
 *
 * The mark is per `run_id` and lives in localStorage: it is per-browser reading
 * state, like the changelog acknowledgement, not something the store owns. The
 * briefing itself is served by the sidecar; the "I have read this one" is not.
 */

export const BRIEFING_DISMISSED_KEY = "agentic-odi.briefing.dismissed";

/** Only the most recent run ids matter; nobody scrolls back further than this. */
const MAX_REMEMBERED = 50;

export function readDismissedRunIds(): string[] {
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

/** Record one run id as dismissed and return the merged list. */
export function markBriefingDismissed(runId: string): string[] {
  const merged = [...new Set([...readDismissedRunIds(), runId])];
  const next = merged.slice(-MAX_REMEMBERED);
  try {
    window.localStorage.setItem(BRIEFING_DISMISSED_KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable: the card still hides for this session */
  }
  return next;
}

export function isBriefingDismissed(runId: string): boolean {
  return readDismissedRunIds().includes(runId);
}
