/**
 * The notice recorder, as pure functions.
 *
 * Ordering, dedupe, and capping are the rules most likely to be wrong and the
 * cheapest to test, so they live here where a test needs no DOM and no store.
 * The provider is the thin persistence shell around these.
 */

import type { Notice, NoticeInput } from "./types";

/** How many notices the history keeps. Older entries fall off the end. */
export const NOTICE_CAP = 200;

/** Two raises of the same statement inside this window are one notice. */
export const NOTICE_DEDUPE_MS = 60_000;

export const EMPTY_NOTICES: Notice[] = [];

let counter = 0;

function newId(): string {
  counter += 1;
  return `notice-${counter}`;
}

/**
 * Append a notice, newest first.
 *
 * The same `(severity, title, detail)` raised again inside `NOTICE_DEDUPE_MS`
 * is the same notice — a retry loop must not paint ten copies of one warning —
 * so the existing row is returned untouched. Anything else is a new fact and
 * goes on the front, with the oldest entries dropped past `NOTICE_CAP`.
 */
export function recordNotice(list: Notice[], input: NoticeInput): Notice[] {
  const duplicate = list.some(
    (notice) =>
      notice.severity === input.severity &&
      notice.title === input.title &&
      notice.detail === input.detail &&
      input.at - notice.at <= NOTICE_DEDUPE_MS,
  );
  if (duplicate) {
    return list;
  }
  const notice: Notice = { ...input, id: newId(), read: false };
  const next = [notice, ...list];
  return next.length > NOTICE_CAP ? next.slice(0, NOTICE_CAP) : next;
}

/** Dismiss one row, permanently. */
export function dismissNotice(list: Notice[], id: string): Notice[] {
  return list.filter((notice) => notice.id !== id);
}

/** Mark every row read without removing it. */
export function markAllRead(list: Notice[]): Notice[] {
  return list.map((notice) => (notice.read ? notice : { ...notice, read: true }));
}

export function unreadCount(list: Notice[]): number {
  return list.reduce((total, notice) => total + (notice.read ? 0 : 1), 0);
}

/**
 * The notices grouped by calendar day, newest group first, each group's rows
 * newest first. The label is the day the notice was raised.
 */
export function groupNoticesByDay(
  list: Notice[],
  now: Date = new Date(),
): { day: string; label: string; items: Notice[] }[] {
  const groups = new Map<string, Notice[]>();
  for (const notice of list) {
    const key = new Date(notice.at).toDateString();
    const bucket = groups.get(key);
    if (bucket) {
      bucket.push(notice);
    } else {
      groups.set(key, [notice]);
    }
  }
  return [...groups.entries()].map(([day, items]) => ({
    day,
    label: dayLabel(items[0].at, now),
    items,
  }));
}

function dayLabel(at: number, now: Date): string {
  const raised = new Date(at);
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfRaised = new Date(
    raised.getFullYear(),
    raised.getMonth(),
    raised.getDate(),
  ).getTime();
  const dayMs = 24 * 60 * 60 * 1000;
  const diff = Math.round((startOfToday - startOfRaised) / dayMs);
  if (diff <= 0) {
    return "Today";
  }
  if (diff === 1) {
    return "Yesterday";
  }
  return raised.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}
