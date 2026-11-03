/**
 * ALH-197 (M2-03.2) — the landscape asks the sidecar to write an organisation run.
 *
 * One path serves the preview and the write, and only `dry_run` tells them apart, so a
 * fetcher that got that flag wrong would apply the change the person was still reading.
 * The whole request goes in the body: `search_outcomes` and the CLI send the same shape
 * the board does, and a surface that quietly dropped the narrowing would run on fewer
 * rows than the table counted.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applyBulkOutcomes,
  previewBulkOutcomes,
  undoBulkOutcomes,
  type BulkRequest,
} from "./studioApi";

afterEach(() => {
  vi.unstubAllGlobals();
});

interface Call {
  url: string;
  method: string;
  body: string;
}

function mockSidecar(body: unknown, status = 200): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({
        url: String(input),
        method: String(init?.method ?? "GET"),
        body: String(init?.body ?? ""),
      });
      return new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  return calls;
}

const REPORT = {
  requested: 2,
  changed: ["o-1", "o-2"],
  skipped: [{ id: "o-3", reason: "outcome not found" }],
  changes: [
    { outcome_id: "o-1", field: "theme_ids", from: [], to: ["t-1"] },
    { outcome_id: "o-2", field: "theme_ids", from: ["t-2"], to: ["t-2", "t-1"] },
  ],
  undo_token: null,
};

const RUN: BulkRequest = {
  mcpUrl: "http://mcp",
  outcomeIds: ["o-1", "o-2"],
  addThemeIds: ["t-1"],
  query: { text: "supplier" },
};

describe("previewBulkOutcomes", () => {
  it("posts the run to the bulk route with dry_run set", async () => {
    const calls = mockSidecar(REPORT);

    await expect(previewBulkOutcomes(RUN)).resolves.toEqual(REPORT);

    expect(calls[0]).toMatchObject({
      url: "/api/outcomes/bulk",
      method: "POST",
    });
    expect(JSON.parse(calls[0]!.body)).toEqual({
      mcp_url: "http://mcp",
      outcome_ids: ["o-1", "o-2"],
      add_theme_ids: ["t-1"],
      remove_theme_ids: [],
      add_tags: [],
      query: { text: "supplier" },
      dry_run: true,
    });
  });
});

describe("applyBulkOutcomes", () => {
  it("sends the same body with dry_run cleared, and keeps the token it answers with", async () => {
    const calls = mockSidecar({ ...REPORT, undo_token: "b-1" });

    const report = await applyBulkOutcomes(RUN);

    expect(JSON.parse(calls[0]!.body)).toMatchObject({ dry_run: false });
    expect(report.undo_token).toBe("b-1");
  });

  it("rejects with the server's own sentence when the run is refused", async () => {
    mockSidecar(
      {
        error: {
          code: "validation_error",
          message: "Nothing to change: name a theme, a stage, or a tag.",
          detail: null,
          suggestion: "Name at least one change.",
          retryable: false,
          request_id: "req-9",
        },
      },
      400,
    );

    await expect(
      applyBulkOutcomes({ ...RUN, addThemeIds: [], query: undefined }),
    ).rejects.toMatchObject({
      name: "StudioApiError",
      message: expect.stringContaining("Nothing to change"),
      error: { message: "Nothing to change: name a theme, a stage, or a tag." },
    });
  });
});

describe("undoBulkOutcomes", () => {
  it("posts the token back to the undo route", async () => {
    const calls = mockSidecar({ ...REPORT, changed: ["o-1"], changes: [] });

    await undoBulkOutcomes("http://mcp", "b-1");

    expect(calls[0]).toMatchObject({ url: "/api/outcomes/bulk/undo", method: "POST" });
    expect(JSON.parse(calls[0]!.body)).toEqual({ mcp_url: "http://mcp", token: "b-1" });
  });
});
