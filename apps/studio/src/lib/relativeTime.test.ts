import { afterEach, describe, expect, it, vi } from "vitest";

import {
  daySection,
  formatClockTime,
  formatDayHeading,
  formatRelativeTime,
  groupByDay,
  startsNewDay,
} from "./relativeTime";

describe("formatRelativeTime", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("reads a moment ago as Just now", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-22T10:00:00Z"));

    expect(formatRelativeTime("2026-10-22T09:59:30Z")).toBe("Just now");
  });

  it("counts minutes and hours before it counts days", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-22T10:00:00Z"));

    expect(formatRelativeTime("2026-10-22T09:15:00Z")).toBe("45m ago");
    expect(formatRelativeTime("2026-10-22T04:00:00Z")).toBe("6h ago");
    expect(formatRelativeTime("2026-10-19T10:00:00Z")).toBe("3d ago");
  });

  it("says Recently instead of crashing on an unparseable value", () => {
    expect(formatRelativeTime("not a date")).toBe("Recently");
  });
});

describe("history day buckets (#694 D13)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("counts days on the local calendar, not in 24-hour blocks", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 9, 22, 0, 10));

    const lateLastNight = new Date(2026, 9, 21, 23, 50).toISOString();
    const justAfterMidnight = new Date(2026, 9, 22, 0, 5).toISOString();
    const lastWeek = new Date(2026, 9, 15, 9, 0).toISOString();

    expect(daySection(justAfterMidnight)).toBe("today");
    expect(daySection(lateLastNight)).toBe("yesterday");
    expect(daySection(lastWeek)).toBe("earlier");
    expect(daySection("not a date")).toBe("earlier");
  });

  it("groups in day order, dropping empty days, one bucket per item", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 9, 22, 10, 0));

    const items = [
      { id: "late", at: new Date(2026, 9, 21, 23, 0).toISOString() },
      { id: "morning", at: new Date(2026, 9, 22, 9, 0).toISOString() },
      { id: "noon", at: new Date(2026, 9, 22, 12, 0).toISOString() },
    ];

    const groups = groupByDay(items, (item) => item.at);

    expect(groups.map((group) => group.label)).toEqual(["Today", "Yesterday"]);
    expect(groups[0].items.map((item) => item.id)).toEqual(["morning", "noon"]);
    expect(groups[1].items.map((item) => item.id)).toEqual(["late"]);
    expect(groups.flatMap((group) => group.items)).toHaveLength(items.length);
  });
});

describe("transcript day headings (#694 D14)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("names today and yesterday, and dates anything older", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 9, 22, 10, 0));

    expect(formatDayHeading(new Date(2026, 9, 22, 9, 0).toISOString())).toBe("Today");
    expect(formatDayHeading(new Date(2026, 9, 21, 9, 0).toISOString())).toBe("Yesterday");

    const older = formatDayHeading(new Date(2026, 8, 3, 9, 0).toISOString());
    expect(older).not.toBe("Today");
    expect(older).not.toBe("Yesterday");
    expect(older).toContain("3");
  });

  it("only separates two messages that fall on different days", () => {
    const beforeMidnight = new Date(2026, 9, 21, 23, 50).toISOString();
    const afterMidnight = new Date(2026, 9, 22, 0, 5).toISOString();
    const sameEvening = new Date(2026, 9, 21, 22, 0).toISOString();

    expect(startsNewDay(beforeMidnight, undefined)).toBe(false);
    expect(startsNewDay(sameEvening, beforeMidnight)).toBe(false);
    expect(startsNewDay(afterMidnight, beforeMidnight)).toBe(true);
  });
});

describe("clock time (#694 D15)", () => {
  it("reads a clock time and refuses to invent one", () => {
    expect(formatClockTime(new Date(2026, 9, 22, 14, 5).toISOString())).toMatch(/\d/);
    expect(formatClockTime("not a date")).toBe("");
  });
});
