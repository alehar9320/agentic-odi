import { describe, expect, it } from "vitest";

import type { Signal } from "../types";
import {
  bucketSignalsByDay,
  countSignalsInRange,
  formatRangeLabel,
  resolveRange,
} from "./dashboard";

function signal(overrides: Partial<Signal> = {}): Signal {
  return {
    id: "SIG-1",
    kind: "outcome_scored",
    title: "Scored an outcome",
    severity: "info",
    created_at: "2026-11-10T09:00:00Z",
    suppressed: false,
    fingerprint: "fp-1",
    ...overrides,
  };
}

describe("resolveRange", () => {
  it("covers the whole of today for the today preset", () => {
    const now = new Date(2026, 10, 10, 15, 30);
    const { from, to } = resolveRange("today", now);
    expect(from?.getHours()).toBe(0);
    expect(from?.getMinutes()).toBe(0);
    expect(to?.getDate()).toBe(11);
    expect(to?.getHours()).toBe(0);
  });

  it("spans seven days for the week preset", () => {
    const now = new Date(2026, 10, 10, 9, 0);
    const { from, to } = resolveRange("week", now);
    expect(from?.getDate()).toBe(4);
    expect(to?.getDate()).toBe(11);
  });

  it("leaves all time unbounded", () => {
    expect(resolveRange("all")).toEqual({ from: null, to: null });
  });
});

describe("formatRangeLabel", () => {
  it("names every range without a dash standing in for a number", () => {
    expect(formatRangeLabel("today")).toBe("Today");
    expect(formatRangeLabel("week")).toBe("Last 7 days");
    expect(formatRangeLabel("custom")).toBe("Custom range");
    expect(formatRangeLabel("all")).toBe("All time");
  });
});

describe("countSignalsInRange", () => {
  it("counts only the requested kind inside the window", () => {
    const signals = [
      signal({ id: "a", kind: "outcome_scored", created_at: "2026-11-10T08:00:00Z" }),
      signal({ id: "b", kind: "outcome_scored", created_at: "2026-11-10T20:00:00Z" }),
      signal({ id: "c", kind: "evidence_ingested", created_at: "2026-11-10T20:00:00Z" }),
      signal({ id: "d", kind: "outcome_scored", created_at: "2026-11-01T20:00:00Z" }),
    ];
    const { from, to } = resolveRange("today", new Date(2026, 10, 10, 12, 0));
    expect(countSignalsInRange(signals, "outcome_scored", from, to)).toBe(2);
  });

  it("counts every signal of a kind when the window is unbounded", () => {
    const signals = [
      signal({ id: "a" }),
      signal({ id: "b", created_at: "2020-01-01T00:00:00Z" }),
    ];
    expect(countSignalsInRange(signals, "outcome_scored", null, null)).toBe(2);
  });
});

describe("bucketSignalsByDay", () => {
  it("zero-fills every day in the window rather than skipping empty ones", () => {
    const signals = [
      signal({ id: "a", created_at: new Date(2026, 10, 8, 10, 0).toISOString() }),
      signal({ id: "b", created_at: new Date(2026, 10, 10, 10, 0).toISOString() }),
    ];
    const from = new Date(2026, 10, 8);
    const to = new Date(2026, 10, 11);
    const buckets = bucketSignalsByDay(signals, from, to);
    expect(buckets.map((bucket) => bucket.count)).toEqual([1, 0, 1]);
    expect(buckets[0].label).toBe("Nov 8");
  });

  it("returns an empty axis only when there is no window and nothing to draw", () => {
    expect(bucketSignalsByDay([], null, null)).toEqual([]);
  });

  it("zero-fills a bounded window that has no signals at all", () => {
    // The days really held zero signals, so a flat zero line is honest here —
    // unlike an unbounded range, which has no axis to draw.
    const buckets = bucketSignalsByDay([], new Date(2026, 10, 8), new Date(2026, 10, 10));
    expect(buckets.map((bucket) => bucket.count)).toEqual([0, 0]);
  });

  it("takes the span from the signals when the window is unbounded", () => {
    const signals = [
      signal({ id: "a", created_at: new Date(2026, 10, 8, 10, 0).toISOString() }),
      signal({ id: "b", created_at: new Date(2026, 10, 10, 10, 0).toISOString() }),
    ];
    const buckets = bucketSignalsByDay(signals, null, null);
    expect(buckets.map((bucket) => bucket.count)).toEqual([1, 0, 1]);
  });

  it("ignores a signal whose timestamp will not parse", () => {
    const signals = [signal({ id: "a", created_at: "not-a-date" })];
    expect(bucketSignalsByDay(signals, null, null)).toEqual([]);
  });
});
