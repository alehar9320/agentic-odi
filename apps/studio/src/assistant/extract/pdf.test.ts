import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  ExtractionError,
  MAX_DOCUMENT_BYTES,
  MAX_EXTRACTED_CHARS,
  truncationSentence,
} from "./common";
import {
  PDF_CONTENT_TYPE,
  PDF_NO_TEXT_LAYER_REFUSAL,
  extractPdf,
  isPdfLike,
  pdfTooLargeMessage,
} from "./pdf";

// Vitest runs with the studio package as its working directory.
const fixture = (name: string): File =>
  new File([readFileSync(`src/assistant/extract/__fixtures__/${name}`)], name, {
    type: PDF_CONTENT_TYPE,
  });

describe("isPdfLike", () => {
  it("recognises the PDF content type even without the extension", () => {
    expect(isPdfLike("report", PDF_CONTENT_TYPE)).toBe(true);
  });

  it("recognises a .pdf name even when the browser reports no type", () => {
    expect(isPdfLike("report.pdf", "")).toBe(true);
  });

  it("trusts the name over a wrong type, so a mislabelled .pdf is still read", () => {
    expect(isPdfLike("report.pdf", "application/octet-stream")).toBe(true);
  });

  it("does not claim a docx or an unrelated file", () => {
    expect(isPdfLike("brief.docx", "")).toBe(false);
    expect(isPdfLike("notes.md", "text/markdown")).toBe(false);
  });
});

describe("extractPdf", () => {
  it("marks each page so a reader can find where a passage came from", async () => {
    const { text, truncated } = await extractPdf(fixture("two-page.pdf"));
    expect(text).toContain("[page 1]");
    expect(text).toContain("[page 2]");
    expect(text).toContain("The onboarding step takes far too long today.");
    expect(truncated).toBe(false);
  });

  it("keeps whole pages and names how many were left out when over the cap", async () => {
    const { text, truncated } = await extractPdf(fixture("long.pdf"));
    expect(truncated).toBe(true);
    // The kept prefix honours the cap; the notice is appended after it.
    const beforeNotice = text.split("\n\n[Truncated:")[0];
    expect(beforeNotice.length).toBeLessThanOrEqual(MAX_EXTRACTED_CHARS);
    // The cut falls on a page boundary: every kept page carries its marker and
    // the dropped count is the pages that never made it in.
    const keptPages = (beforeNotice.match(/\[page \d+\]/g) ?? []).length;
    const dropped = Number(/\[Truncated: (\d+) pages? (?:was|were) left out/.exec(text)?.[1]);
    expect(dropped).toBe(40 - keptPages);
    expect(text).toContain(truncationSentence(dropped, "pages"));
  });

  it("refuses a PDF with no text layer, naming the fix", async () => {
    const failure = await extractPdf(fixture("no-text-layer.pdf")).catch((error) => error);
    expect(failure).toBeInstanceOf(ExtractionError);
    expect((failure as ExtractionError).sentence).toContain("no-text-layer.pdf");
    expect((failure as ExtractionError).sentence).toContain(PDF_NO_TEXT_LAYER_REFUSAL);
  });

  it("refuses a password-protected PDF rather than sending it blank", async () => {
    const failure = await extractPdf(fixture("encrypted.pdf")).catch((error) => error);
    expect(failure).toBeInstanceOf(ExtractionError);
    expect((failure as ExtractionError).sentence).toContain("encrypted.pdf");
    expect((failure as ExtractionError).sentence).toContain("password");
  });

  it("refuses a file over the size limit before it is ever read", async () => {
    const file = new File(["x"], "huge.pdf", { type: PDF_CONTENT_TYPE });
    Object.defineProperty(file, "size", { value: MAX_DOCUMENT_BYTES + 1 });
    await expect(extractPdf(file)).rejects.toThrow(pdfTooLargeMessage("huge.pdf"));
  });
});
