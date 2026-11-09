import { afterEach, describe, expect, it, vi } from "vitest";

import { formatRelativeTime } from "./relativeTime";

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
