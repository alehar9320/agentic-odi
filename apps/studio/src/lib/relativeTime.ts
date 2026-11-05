/**
 * How long ago something happened, in the shortest honest phrasing.
 *
 * Shared by the signal inbox and the conversation history strip so both read
 * the same way. A value that will not parse is "Recently" rather than a crash
 * or a bare "NaN ago".
 */
export function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return "Recently";
  }
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

/** The three buckets the history strip and the transcript both separate by. */
export type DaySection = "today" | "yesterday" | "earlier";

/** Buckets in the only order they are ever shown. */
export const DAY_SECTION_ORDER: readonly DaySection[] = ["today", "yesterday", "earlier"];

const SECTION_LABEL: Record<DaySection, string> = {
  today: "Today",
  yesterday: "Yesterday",
  earlier: "Earlier",
};

/** Midnight of the day a moment falls on, in the reader's own timezone. */
function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

/** How many calendar days back a moment is; 0 for today, negative for ahead. */
function daysBack(date: Date, now: Date): number {
  return Math.round((startOfDay(now).getTime() - startOfDay(date).getTime()) / 86_400_000);
}

/**
 * Which day a timestamp belongs to, counted on the local calendar rather than
 * in 24-hour blocks: something said at 23:50 is "Yesterday" at 00:10, not
 * "23m ago" wearing a day heading that disagrees with it.
 */
export function daySection(isoString: string, now: Date = new Date()): DaySection {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return "earlier";
  }
  const back = daysBack(date, now);
  if (back <= 0) return "today";
  if (back === 1) return "yesterday";
  return "earlier";
}

/** The one word a history group is headed with. */
export function daySectionLabel(section: DaySection): string {
  return SECTION_LABEL[section];
}

export interface DayGroup<T> {
  section: DaySection;
  label: string;
  items: T[];
}

/**
 * Items gathered under Today / Yesterday / Earlier.
 *
 * Empty groups are dropped rather than rendered as a heading over nothing, and
 * the order is fixed, so a list that arrives out of order still reads forwards
 * and every item sits under exactly one heading.
 */
export function groupByDay<T>(
  items: readonly T[],
  isoOf: (item: T) => string,
  now: Date = new Date(),
): DayGroup<T>[] {
  const buckets = new Map<DaySection, T[]>();
  for (const item of items) {
    const section = daySection(isoOf(item), now);
    const bucket = buckets.get(section);
    if (bucket) {
      bucket.push(item);
    } else {
      buckets.set(section, [item]);
    }
  }

  return DAY_SECTION_ORDER.flatMap((section) => {
    const bucket = buckets.get(section);
    return bucket?.length ? [{ section, label: daySectionLabel(section), items: bucket }] : [];
  });
}

/**
 * What a divider between two days says. Beyond yesterday the date itself is
 * more use than the word "Earlier", and a different year is named.
 */
export function formatDayHeading(isoString: string, now: Date = new Date()): string {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return SECTION_LABEL.earlier;
  }
  const section = daySection(isoString, now);
  if (section !== "earlier") {
    return SECTION_LABEL[section];
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    ...(date.getFullYear() === now.getFullYear() ? {} : { year: "numeric" }),
  }).format(date);
}

/**
 * Whether a message opens a new calendar day in the transcript. The first
 * message never does: a divider above it separates nothing.
 */
export function startsNewDay(isoString: string, previousIso: string | undefined): boolean {
  if (!previousIso) {
    return false;
  }
  const date = new Date(isoString);
  const previous = new Date(previousIso);
  if (Number.isNaN(date.getTime()) || Number.isNaN(previous.getTime())) {
    return false;
  }
  return startOfDay(date).getTime() !== startOfDay(previous).getTime();
}
