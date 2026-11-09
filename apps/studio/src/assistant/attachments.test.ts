import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import type { AttachmentAdapter, PendingAttachment } from "@assistant-ui/react";

import {
  ATTACHMENT_READ_FAILURE,
  AttachmentReadError,
  MAX_ATTACHMENT_CHARS,
  MAX_DOCUMENT_BYTES,
  MAX_IMAGE_BYTES,
  attachmentRejection,
  createAttachmentAdapter,
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

  it("refuses a file whose bytes it cannot turn into content", async () => {
    await expect(prepareAttachment(docxFixture("legacy.doc"))).rejects.toBeInstanceOf(
      AttachmentReadError,
    );
  });
});

/**
 * A file the browser accepts by name and type but hands back nothing for: the
 * transcript is locked, the disk hiccuped, the tab lost the handle.
 */
function unreadableFile(name = "notes.md"): File {
  const file = fileOf(name, "text/markdown");
  Object.defineProperty(file, "text", {
    value: () => Promise.reject(new Error("Read interrupted")),
  });
  return file;
}

/**
 * The states assistant-ui sees from one `add()` call. The adapter may return a
 * promise or an async generator of successive states for the same attachment,
 * so the test drains it the way the runtime does.
 */
async function addedStates(adapter: AttachmentAdapter, file: File): Promise<PendingAttachment[]> {
  const result = adapter.add({ file });
  if (Symbol.asyncIterator in result) {
    const states: PendingAttachment[] = [];
    for await (const state of result) {
      states.push(state);
    }
    return states;
  }
  return [await result];
}

describe("an unreadable file", () => {
  it("names the file and says it could not be read", async () => {
    const failure = await prepareAttachment(unreadableFile()).catch((error) => error);
    expect(failure).toBeInstanceOf(AttachmentReadError);
    expect((failure as AttachmentReadError).name).toBe("notes.md");
    expect((failure as AttachmentReadError).code).toBe("unreadable");
    expect((failure as AttachmentReadError).message).toContain("Could not read notes.md");
  });

  it("hands the composer a failed attachment rather than an invisible one", async () => {
    const states = await addedStates(createAttachmentAdapter(), unreadableFile());

    expect(states).toHaveLength(1);
    expect(states[0]).toMatchObject({
      name: "notes.md",
      status: { type: "incomplete", reason: "error", message: ATTACHMENT_READ_FAILURE },
    });
  });

  it("keeps a readable file on the path it was already on", async () => {
    const adapter = createAttachmentAdapter();
    const states = await addedStates(adapter, fileOf("notes.md", "text/markdown"));
    expect(states.at(-1)?.status).toEqual({ type: "requires-action", reason: "composer-send" });
    const sent = await adapter.send(states[0]!);
    expect(sent.status).toEqual({ type: "complete" });
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
