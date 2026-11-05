import { describe, expect, it } from "vitest";

import { MAX_EXTRACTED_CHARS, capExtracted, truncationSentence } from "./common";

describe("capExtracted", () => {
  it("leaves text under the cap untouched and says nothing was dropped", () => {
    const result = capExtracted("A short passage.");
    expect(result).toEqual({ text: "A short passage.", truncated: false });
  });

  it("keeps text exactly at the cap without a notice", () => {
    const exact = "x".repeat(MAX_EXTRACTED_CHARS);
    expect(capExtracted(exact)).toEqual({ text: exact, truncated: false });
  });

  it("keeps a prefix and announces how many characters were dropped", () => {
    const long = "y".repeat(MAX_EXTRACTED_CHARS + 1_234);
    const result = capExtracted(long);
    expect(result.truncated).toBe(true);
    expect(result.text.startsWith("y".repeat(MAX_EXTRACTED_CHARS))).toBe(true);
    expect(result.text).toContain(truncationSentence(1_234, "characters"));
    expect(result.text).toContain("1,234");
    expect(result.text).toContain(MAX_EXTRACTED_CHARS.toLocaleString());
  });
});

describe("truncationSentence", () => {
  it("names the unit and the cap", () => {
    expect(truncationSentence(3, "pages")).toBe(
      "[Truncated: 3 pages were left out — the extracted text is capped at 20,000 characters.]",
    );
  });
});
