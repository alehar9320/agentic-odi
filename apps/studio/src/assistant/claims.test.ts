import { describe, expect, it } from "vitest";

import type { Claim, ClaimCitation } from "../types";
import { buildClaimBlocks, citedCount, hideMarkers, splitBlocks } from "./claims";

function claim(
  index: number,
  text: string,
  status: Claim["status"] = "cited",
  evidence: ClaimCitation[] = [],
): Claim {
  return { index, text, status, evidence, reason: null };
}

const acme: ClaimCitation = { id: "E-1", name: "Call with Acme", source_name: "Gong" };

describe("hideMarkers", () => {
  it("removes a complete marker from the prose", () => {
    expect(hideMarkers("Three stalled. [[ev:E-1]] Next.")).toBe("Three stalled.  Next.");
  });

  it("removes a hypothesis tag", () => {
    expect(hideMarkers("Nobody said why. [[hypothesis]]")).toBe("Nobody said why. ");
  });

  it("holds back a marker split across two chunks", () => {
    expect(hideMarkers("Three stalled. [[ev:E-")).toBe("Three stalled. ");
    expect(hideMarkers("Nobody said why. [[hypoth")).toBe("Nobody said why. ");
  });

  it("leaves a bracket that is not a marker alone", () => {
    expect(hideMarkers("See [[notes]] for detail.")).toBe("See [[notes]] for detail.");
  });

  it("keeps a marker literal inside inline code and a fence", () => {
    expect(hideMarkers("Write `[[ev:E-1]]` yourself.")).toBe("Write `[[ev:E-1]]` yourself.");
    expect(hideMarkers("```\n[[ev:E-1]]\n```")).toBe("```\n[[ev:E-1]]\n```");
  });
});

describe("splitBlocks", () => {
  it("separates paragraphs, headings, code, and list items", () => {
    const blocks = splitBlocks("### Title\nOne.\n\nTwo.\n\n- item\n\n```\ncode\n```");

    expect(blocks.map((block) => block.kind)).toEqual(["heading", "paragraph", "paragraph", "list", "code"]);
    expect(blocks[4].items).toEqual(["code"]);
  });
});

describe("buildClaimBlocks", () => {
  it("puts each claim after the sentence it belongs to", () => {
    const content = "Three accounts stalled. [[ev:E-1]] Nobody said why. [[hypothesis]]";
    const blocks = buildClaimBlocks(content, [
      claim(0, "Three accounts stalled.", "cited", [acme]),
      claim(1, "Nobody said why.", "hypothesis"),
    ]);

    expect(blocks[0].kind).toBe("paragraph");
    expect(blocks[0].items[0].map((segment) => segment.claim?.index ?? null)).toEqual([
      0,
      null,
      1,
    ]);
    expect(blocks[0].items[0][1].text).toBe(" ");
  });

  it("leaves prose with no claim as plain text", () => {
    const blocks = buildClaimBlocks("Just a note.", []);

    expect(blocks[0].items[0]).toEqual([{ text: "Just a note.", claim: null }]);
  });

  it("does not attach a claim across a paragraph break", () => {
    const blocks = buildClaimBlocks("First paragraph.\n\nSecond paragraph.", [
      claim(0, "First paragraph."),
      claim(1, "Second paragraph."),
    ]);

    expect(blocks).toHaveLength(2);
    expect(blocks[0].items[0][0].claim?.index).toBe(0);
    expect(blocks[1].items[0][0].claim?.index).toBe(1);
  });
});

describe("citedCount", () => {
  it("counts cited claims", () => {
    expect(citedCount([claim(0, "One.", "cited", [acme]), claim(1, "Two.", "hypothesis")], false)).toBe(1);
  });

  it("excludes a seeded demo reply", () => {
    expect(citedCount([claim(0, "One.", "cited", [acme])], true)).toBe(0);
  });
});
