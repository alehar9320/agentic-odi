import { MAX_NOTICES, DEDUPE_WINDOW_MS, type NoticeSeverity, type StoredNotice } from "../bff/store/types";

export interface ActivityState {
  notices: StoredNotice[];
}

export const EMPTY_ACTIVITY_STATE: ActivityState = { notices: [] };

/**
 * Record a notice in the activity history.
 *
 * - Caps at MAX_NOTICES (200) entries, newest first.
 * - Dedupes the same (severity, title, detail) raised within DEDUPE_WINDOW_MS (60s).
 * - Never throws; failures are swallowed by the caller.
 */
export function recordNotice(
  state: ActivityState,
  notice: Omit<StoredNotice, "id" | "dismissed" | "at">,
  now = Date.now(),
): ActivityState {
  const isoNow = new Date(now).toISOString();

  // Check for duplicate within the dedupe window
  const isDuplicate = state.notices.some((existing) => {
    if (
      existing.severity === notice.severity &&
      existing.title === notice.title &&
      existing.detail === notice.detail
    ) {
      const existingTime = new Date(existing.at).getTime();
      return now - existingTime < DEDUPE_WINDOW_MS;
    }
    return false;
  });

  if (isDuplicate) {
    return state;
  }

  const id = `${notice.severity}-${now}-${Math.random().toString(36).slice(2, 9)}`;
  const newNotice: StoredNotice = {
    ...notice,
    id,
    at: isoNow,
    dismissed: false,
  };

  // Prepend new notice and cap
  const notices = [newNotice, ...state.notices].slice(0, MAX_NOTICES);
  return { notices };
}

/**
 * Mark a notice as dismissed.
 */
export function dismissNotice(state: ActivityState, id: string): ActivityState {
  const notices = state.notices.map((notice) =>
    notice.id === id ? { ...notice, dismissed: true } : notice,
  );
  return { notices };
}

/**
 * Permanently remove a dismissed notice from history.
 */
export function deleteNotice(state: ActivityState, id: string): ActivityState {
  const notices = state.notices.filter((notice) => notice.id !== id);
  return { notices };
}

/**
 * Get notices grouped by day for display.
 */
export function groupNoticesByDay(notices: StoredNotice[]): { label: string; items: StoredNotice[] }[] {
  const groups = new Map<string, StoredNotice[]>();

  for (const notice of notices) {
    const date = new Date(notice.at);
    const label = date.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
    if (!groups.has(label)) {
      groups.set(label, []);
    }
    groups.get(label)!.push(notice);
  }

  return [...groups.entries()].map(([label, items]) => ({ label, items }));
}

/**
 * Severity weight for sorting (not used here since we preserve time order).
 */
export function severityWeight(severity: NoticeSeverity): number {
  const weights: Record<NoticeSeverity, number> = {
    critical: 4,
    warning: 3,
    info: 2,
    success: 1,
  };
  return weights[severity];
}

/**
 * Get the display label for a severity.
 */
export function severityLabel(severity: NoticeSeverity): string {
  return severity.charAt(0).toUpperCase() + severity.slice(1);
}