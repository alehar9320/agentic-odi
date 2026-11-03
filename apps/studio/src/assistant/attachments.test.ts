import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  MAX_ATTACHMENT_CHARS,
  MAX_DOCUMENT_BYTES,
  MAX_IMAGE_BYTES,
  attachmentRejection,
  formatFileSize,
  isTextLike,
  prepareAttachment,
} from "./attachments";

function fileOf(name: string, type: string, size = 10): File {
  const file = new File(["x"], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

const docxFixture = (name: string): File =>
  new File([readFileSync(`src/assistant/extract/__fixtures__/${name}`)], name, {
    type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  });

describe("attachmentRejection", () => {
  it("accepts a text file by extension even when the browser reports no type", () => {
    expect(attachmentRejection(fileOf("notes.md", ""))).toBeNull();
    expect(isTextLike("notes.md", "")).toBe(true);
  });

  it("accepts a small image", () => {
    expect(attachmentRejection(fileOf("shot.png", "image/png", 1024))).toBeNull();
  });

  it("accepts a .docx by name and by the OOXML content type", () => {
    expect(attachmentRejection(fileOf("brief.docx", ""))).toBeNull();
    expect(
      attachmentRejection(
        fileOf("brief", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
      ),
    ).toBeNull();
  });

  it("refuses a legacy .doc with a sentence that says what to do", () => {
    const rejection = attachmentRejection(fileOf("old.doc", "application/msword"));
    expect(rejection).toContain("old.doc");
    expect(rejection).toContain("Save it as .docx or .txt first");
    expect(rejection).toContain("old binary format is not supported");
  });

  it("refuses a .docx over the size limit before it is ever read", () => {
    const rejection = attachmentRejection(fileOf("huge.docx", "", MAX_DOCUMENT_BYTES + 1));
    expect(rejection).toContain("huge.docx");
    expect(rejection).toContain("25 MB");
  });

  it("explains that an oversized image will not be sent", () => {
    const rejection = attachmentRejection(
      fileOf("huge.png", "image/png", MAX_IMAGE_BYTES + 1),
    );
    expect(rejection).toContain("huge.png");
    expect(rejection).toContain("5 MB");
  });

  it("rejects a file the studio cannot read", () => {
    expect(attachmentRejection(fileOf("deck.pdf", "application/pdf"))).toContain("deck.pdf");
  });

  it("rejects an image format the model cannot be sent", () => {
    const rejection = attachmentRejection(fileOf("chart.svg", "image/svg+xml"));
    expect(rejection).toContain("chart.svg");
    expect(rejection).toContain("PNG");
  });
});

describe("prepareAttachment", () => {
  it("gives a .docx the same shape of record as a text file", async () => {
    const text = await prepareAttachment(fileOf("notes.md", "text/markdown"));
    const docx = await prepareAttachment(docxFixture("short.docx"));
    // Same keys, so a caller cannot tell which extractor ran.
    expect(Object.keys(docx).sort()).toEqual(Object.keys(text).sort());
    expect(docx).toMatchObject({ name: "short.docx" });
    expect(typeof docx.text).toBe("string");
    expect(docx.text).toContain("Outcome-Driven Innovation in practice.");
  });

  it("caps a long .docx at the shared limit and announces the truncation", async () => {
    const docx = await prepareAttachment(docxFixture("long.docx"));
    expect(docx.text?.startsWith("Paragraph 00")).toBe(true);
    expect(docx.text).toContain("[Truncated:");
    expect((docx.text ?? "").length).toBeGreaterThan(MAX_ATTACHMENT_CHARS);
  });

  it("never throws on a file it cannot read — the name is still shown", async () => {
    const docx = await prepareAttachment(docxFixture("legacy.doc"));
    expect(docx.name).toBe("legacy.doc");
    expect(docx.text).toBeUndefined();
  });
});


describe("formatFileSize", () => {
  it("reads at a human scale", () => {
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(2048)).toBe("2 KB");
    expect(formatFileSize(3 * 1024 * 1024)).toBe("3.0 MB");
  });

  it("says nothing when there is no size to report", () => {
    expect(formatFileSize(0)).toBe("");
  });
});
