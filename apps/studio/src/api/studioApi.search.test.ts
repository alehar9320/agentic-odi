/**
 * ALH-195 (M2-02.2) — the landscape asks the sidecar to narrow the library.
 *
 * The URL is the contract ALH-194 fixed: one parameter per narrowing
 * dimension, `theme_ids` repeated for a multi-theme OR, and the envelope
 * returned exactly as the sidecar answered it. A count the browser recomputed
 * on the way through is how a facet row disagrees with its own results.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchOutcomeSearch } from "./studioApi";

afterEach(() => {
  vi.unstubAllGlobals();
});

function mockSidecar(body: unknown): { url: string }[] {
  const calls: { url: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      calls.push({ url: String(input) });
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  return calls;
}

describe("fetchOutcomeSearch", () => {
  it("spells every narrowing dimension the query has, and pages it", async () => {
    const calls = mockSidecar({ items: [], total: 0, facets: {} });

    await fetchOutcomeSearch("http://mcp", {
      text: "three days",
      stage: "execute",
      themeIds: ["t-1", "t-2"],
      confidence: "scored",
      minScore: 8,
      maxScore: 12,
      limit: 50,
      offset: 50,
    });

    expect(calls[0]?.url).toBe(
      "/api/outcomes/search?mcp_url=http%3A%2F%2Fmcp&text=three+days&stage=execute" +
        "&theme_ids=t-1&theme_ids=t-2&confidence=scored&min_score=8&max_score=12&limit=50&offset=50",
    );
  });

  it("leaves a dimension out of the URL rather than sending an empty one", async () => {
    const envelope = {
      items: [{ id: "O-1", opportunity_score: 14 }],
      total: 1,
      facets: { stage: { execute: 1 }, theme: {}, confidence: { scored: 1, unscored: 0 } },
    };
    const calls = mockSidecar(envelope);

    await expect(fetchOutcomeSearch("http://mcp", { limit: 50 })).resolves.toEqual(envelope);

    expect(calls[0]?.url).toBe("/api/outcomes/search?mcp_url=http%3A%2F%2Fmcp&limit=50");
  });

  it("carries the score band's zero as a bound, not as an absent filter", async () => {
    const calls = mockSidecar({ items: [], total: 0, facets: {} });

    await fetchOutcomeSearch("http://mcp", { minScore: 0, maxScore: 10 });

    expect(calls[0]?.url).toBe("/api/outcomes/search?mcp_url=http%3A%2F%2Fmcp&min_score=0&max_score=10");
  });
});
