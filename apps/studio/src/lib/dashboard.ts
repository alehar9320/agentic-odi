/**
 * The dashboard's arithmetic, kept out of the component so the range maths and
 * the zero-fill are testable on their own.
 *
 * Nothing here invents a number. A bucket with no signals is a real `0`, and a
 * range with no boundaries counts every signal the store returned.
 */

import type { Signal } from "../types";

export type DashboardRange = "today" | "week" | "all" | "custom";

/** A resolved window. Both ends are inclusive; `null` means unbounded. */
export interface ResolvedRange {
  from: Date | null;
  to: Date | null;
}

/** Midnight at the start of the reader's day, in their own timezone. */
function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

/**
 * The window a preset names. `all` has no boundaries — it is the whole store,
 * not a guess at how far back the store goes.
 */
export function resolveRange(range: DashboardRange, now: Date = new Date()): ResolvedRange {
  if (range === "today") {
    const from = startOfDay(now);
    const to = new Date(from.getTime());
    to.setDate(to.getDate() + 1);
    return { from, to };
  }
  if (range === "week") {
    const from = startOfDay(now);
    from.setDate(from.getDate() - 6);
    const to = new Date(startOfDay(now).getTime());
    to.setDate(to.getDate() + 1);
    return { from, to };
  }
  return { from: null, to: null };
}

/** The shortest honest label for a window, used on the trend caption. */
export function formatRangeLabel(range: DashboardRange): string {
  switch (range) {
    case "today":
      return "Today";
    case "week":
      return "Last 7 days";
    case "custom":
      return "Custom range";
    default:
      return "All time";
  }
}

function parseTime(iso: string): number | null {
  const time = new Date(iso).getTime();
  return Number.isNaN(time) ? null : time;
}

/** A signal counts when its timestamp parses and falls inside the window. */
function signalInRange(signal: Signal, from: Date | null, to: Date | null): boolean {
  const time = parseTime(signal.created_at);
  if (time == null) {
    return false;
  }
  if (from && time < from.getTime()) {
    return false;
  }
  if (to && time >= to.getTime()) {
    return false;
  }
  return true;
}

/** How many signals carry a `kind` inside the window. */
export function countSignalsInRange(
  signals: ReadonlyArray<Signal>,
  kind: Signal["kind"],
  from: Date | null,
  to: Date | null,
): number {
  return signals.filter((signal) => signal.kind === kind && signalInRange(signal, from, to)).length;
}

/** One column of the trend: a day label and how many signals landed on it. */
export interface SignalBucket {
  label: string;
  count: number;
}

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

function dayKey(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

function shortLabel(date: Date): string {
  return `${MONTHS[date.getMonth()]} ${date.getDate()}`;
}

/**
 * Signals per day across the window, one bucket per day and no day skipped.
 * A day with no signals is a real zero — an empty axis is honest, a fabricated
 * spike is not. When the window is unbounded the span is taken from the
 * signals themselves; with no signals at all there is no axis to draw.
 */
export function bucketSignalsByDay(
  signals: ReadonlyArray<Signal>,
  from: Date | null,
  to: Date | null,
): SignalBucket[] {
  const counts = new Map<string, number>();
  let earliest: number | null = null;
  let latest: number | null = null;

  for (const signal of signals) {
    const time = parseTime(signal.created_at);
    if (time == null) {
      continue;
    }
    if (from && time < from.getTime()) {
      continue;
    }
    if (to && time >= to.getTime()) {
      continue;
    }
    const key = dayKey(new Date(time));
    counts.set(key, (counts.get(key) ?? 0) + 1);
    if (earliest == null || time < earliest) {
      earliest = time;
    }
    if (latest == null || time > latest) {
      latest = time;
    }
  }

  const start = from ?? (earliest == null ? null : new Date(earliest));
  const endExclusive = to ?? (latest == null ? null : new Date(startOfDay(new Date(latest)).getTime() + 86400000));
  if (!start || !endExclusive) {
    return [];
  }

  const buckets: SignalBucket[] = [];
  const cursor = startOfDay(start);
  // `to` is exclusive, so the last day drawn is the one just before it.
  const last = startOfDay(new Date(endExclusive.getTime() - 1));
  while (cursor.getTime() <= last.getTime()) {
    const key = dayKey(cursor);
    buckets.push({ label: shortLabel(cursor), count: counts.get(key) ?? 0 });
    cursor.setDate(cursor.getDate() + 1);
  }
  return buckets;
}
