import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { MAX_EXTRACTED_CHARS } from "./common";
import {
  DOCX_CONTENT_TYPE,
  ExtractionError,
  LEGACY_DOC_REFUSAL,
  extractDocx,
  isDocxLike,
  isLegacyDoc,
} from "./docx";

// Vitest runs with the studio package as its working directory.
const fixture = (name: string): File =>
  new File([readFileSync(`src/assistant/extract/__fixtures__/${name}`)], name, {
    type: DOCX_CONTENT_TYPE,
  });

describe("isDocxLike", () => {
  it("recognises the OOXML content type even without the extension", () => {
    expect(isDocxLike("report", DOCX_CONTENT_TYPE)).toBe(true);
  });

  it("recognises a .docx name even when the browser reports no type", () => {
    expect(isDocxLike("report.docx", "")).toBe(true);
  });

  it("trusts the name over a wrong type, so a mislabelled .docx is still read", () => {
    expect(isDocxLike("report.docx", "application/octet-stream")).toBe(true);
  });

  it("does not claim a legacy .doc or an unrelated file", () => {
    expect(isDocxLike("report.doc", "application/msword")).toBe(false);
    expect(isDocxLike("notes.md", "")).toBe(false);
  });
});

describe("isLegacyDoc", () => {
  it("recognises the legacy type and the .doc name", () => {
    expect(isLegacyDoc("report", "application/msword")).toBe(true);
    expect(isLegacyDoc("report.doc", "")).toBe(true);
  });

  it("leaves a .docx alone", () => {
    expect(isLegacyDoc("report.docx", DOCX_CONTENT_TYPE)).toBe(false);
    expect(isLegacyDoc("report.docx", "application/msword")).toBe(false);
  });
});

describe("extractDocx", () => {
  it("reads the paragraphs of a short document and joins them with a blank line", async () => {
    const { text, truncated } = await extractDocx(fixture("short.docx"));
    expect(truncated).toBe(false);
    expect(text).toContain("Outcome-Driven Innovation in practice.");
    expect(text).toContain(
      "A market is a group of people plus the job they are trying to get done.",
    );
    expect(text).toContain("Desired outcomes are the metrics customers use to measure success.");
    // Mammoth separates paragraphs with a blank line.
    expect(text).toMatch(/practice\.\n\nA market/);
  });

  it("leaves the header out of the extracted text", async () => {
    // The fixture carries a header; mammoth's raw text is the body only.
    const { text } = await extractDocx(fixture("short.docx"));
    expect(text).not.toContain("CONFIDENTIAL DRAFT");
  });

  it("caps a document over the limit and announces how much was dropped", async () => {
    const { text, truncated } = await extractDocx(fixture("long.docx"));
    expect(truncated).toBe(true);
    expect(text.startsWith("Paragraph 00")).toBe(true);
    expect(text).toContain("[Truncated:");
    expect(text).toContain("characters were left out");
    // The notice itself is inside the cap-sized payload, not past it.
    expect(text.length).toBeGreaterThan(MAX_EXTRACTED_CHARS);
    expect(text.length).toBeLessThan(MAX_EXTRACTED_CHARS + 200);
  });

  it("refuses a file that is not a readable docx, in words", async () => {
    const notADocx = new File([readFileSync("src/assistant/extract/__fixtures__/legacy.doc")], "legacy.doc");
    await expect(extractDocx(notADocx)).rejects.toBeInstanceOf(ExtractionError);
    await expect(extractDocx(notADocx)).rejects.toThrow(/could not be read as a Word document/);
  });
});

describe("the legacy refusal sentence", () => {
  it("tells the reader what to do instead", () => {
    expect(LEGACY_DOC_REFUSAL).toBe(
      "Save it as .docx or .txt first — the old binary format is not supported.",
    );
  });
});
