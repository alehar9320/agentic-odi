import { describe, expect, it } from "vitest";

import type { CanvasData } from "../types";
import {
  LOCAL_BOARD_NOTE,
  canvasHasRecords,
  canvasStatus,
  isBrowserCanvas,
  isSimulatedCanvas,
  savedAtTime,
  savedCopyCaption,
} from "./canvasProvenance";

function canvas(overrides: Partial<CanvasData> = {}): CanvasData {
  return {
    jobs: [],
    steps: [],
    outcomes: [],
    source: "local",
    ...overrides,
  };
}

describe("canvas provenance", () => {
  it("treats seed provenance as simulated", () => {
    const data = canvas({
      source: "seed",
      provenance: {
        kind: "seed",
        reason: "mcp_unreachable",
        generated_at: "2026-10-29T10:00:00+00:00",
        record_counts: { jobs: 1, steps: 8, outcomes: 5, evidence: 0 },
      },
    });

    expect(isSimulatedCanvas(data)).toBe(true);
    expect(canvasStatus(data)).toEqual({
      label: "OFFLINE",
      detail: "sample data — the MCP server could not be reached",
    });
  });

  it("labels a seed canvas that is not an outage as DEMO", () => {
    const data = canvas({
      source: "seed",
      provenance: {
        kind: "seed",
        reason: "demo",
        generated_at: "2026-10-29T10:00:00+00:00",
        record_counts: { jobs: 1, steps: 8, outcomes: 5, evidence: 0 },
      },
    });

    expect(canvasStatus(data)?.label).toBe("DEMO");
  });

  it("falls back to source for a cache written before provenance existed", () => {
    expect(isSimulatedCanvas(canvas({ source: "seed" }))).toBe(true);
    expect(isSimulatedCanvas(canvas({ source: "mcp" }))).toBe(false);
  });

  it("has no label for live, empty, or missing canvases", () => {
    expect(canvasStatus(canvas({ source: "mcp" }))).toBeNull();
    expect(canvasStatus(null)).toBeNull();
  });

  /**
   * A live board in IndexedDB and a live board on a sidecar both carry
   * `provenance.kind === "live"`, so only `source` separates them — and the
   * receipt that promises where a capture went has to read the one that does.
   */
  it("names the browser store from the source, not from liveness", () => {
    expect(
      isBrowserCanvas(
        canvas({
          source: "local",
          provenance: {
            kind: "live",
            reason: "local_store",
            generated_at: "2026-11-01T10:00:00+00:00",
            record_counts: { jobs: 1, steps: 0, outcomes: 1, evidence: 0 },
          },
        }),
      ),
    ).toBe(true);
    expect(isBrowserCanvas(canvas({ source: "mcp" }))).toBe(false);
    expect(isBrowserCanvas(canvas({ source: "seed" }))).toBe(false);
    expect(isBrowserCanvas(null)).toBe(false);
  });

  it("says the browser, in one clause every receipt can reuse", () => {
    expect(LOCAL_BOARD_NOTE).toBe("Saved in this browser.");
  });
});

describe("canvas records", () => {
  it("is true only when the canvas holds something to draw", () => {
    expect(canvasHasRecords(null)).toBe(false);
    expect(canvasHasRecords(canvas())).toBe(false);
    expect(canvasHasRecords(canvas({ jobs: [{ id: "JOB-1", name: "Deploy" }] }))).toBe(true);
    expect(canvasHasRecords(canvas({ steps: [{ id: "S-1", name: "Define" }] }))).toBe(true);
    expect(
      canvasHasRecords(canvas({ outcomes: [{ id: "O-1", statement: "Minimize the wait" }] })),
    ).toBe(true);
  });
});

describe("saved copy caption", () => {
  const now = Date.parse("2026-11-01T12:00:00.000Z");
  const saved = (generatedAt: string) =>
    canvas({
      provenance: {
        kind: "live",
        reason: "store",
        generated_at: generatedAt,
        record_counts: { jobs: 1, steps: 0, outcomes: 0, evidence: 0 },
      },
    });

  it("reads the timestamp from the canvas provenance", () => {
    expect(savedAtTime(saved("2026-11-01T11:56:00.000Z"))).toBe(now - 4 * 60_000);
    expect(savedAtTime(canvas())).toBeNull();
    expect(savedAtTime(null)).toBeNull();
  });

  it("names minutes, hours, and days", () => {
    expect(savedCopyCaption(saved("2026-11-01T11:56:00.000Z"), now)).toBe("Saved 4 minutes ago");
    expect(savedCopyCaption(saved("2026-11-01T11:00:00.000Z"), now)).toBe("Saved 1 hour ago");
    expect(savedCopyCaption(saved("2026-10-30T12:00:00.000Z"), now)).toBe("Saved 2 days ago");
  });

  it("says just now for a copy saved under a minute ago", () => {
    expect(savedCopyCaption(saved("2026-11-01T11:59:30.000Z"), now)).toBe("Saved just now");
  });

  it("claims no time the cache does not carry", () => {
    expect(savedCopyCaption(canvas(), now)).toBe("Saved copy on this device");
    expect(savedCopyCaption(saved("not-a-date"), now)).toBe("Saved copy on this device");
  });

  it("never claims a copy from the future is fresh", () => {
    expect(savedCopyCaption(saved("2026-11-01T13:00:00.000Z"), now)).toBe("Saved just now");
  });
});
