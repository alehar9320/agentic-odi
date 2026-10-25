import { describe, expect, it } from "vitest";

import {
  MAX_ATTACHMENT_BYTES,
  MAX_ATTACHMENTS,
  attachmentProblem,
  formatBytes,
  isImage,
  readAttachment,
  releaseAttachment,
  toPayload,
} from "./attachments";

function fakeFile(name: string, type: string, size = 12): File {
  return new File([new Uint8Array(size)], name, { type });
}

describe("attachmentProblem", () => {
  it("accepts images and text, whatever the reader names them", () => {
    expect(attachmentProblem(fakeFile("shot.png", "image/png"), 0)).toBeNull();
    expect(attachmentProblem(fakeFile("notes.md", "text/markdown"), 0)).toBeNull();
    expect(attachmentProblem(fakeFile("data.json", "application/json"), 0)).toBeNull();
  });

  it("refuses what the model cannot read, by type rather than by name", () => {
    const problem = attachmentProblem(fakeFile("deck.pdf", "application/pdf"), 0);

    expect(problem).toContain("deck.pdf");
    expect(problem).toContain("application/pdf");
    expect(problem).toContain("image or a text file");
  });

  it("refuses an empty file instead of sending nothing", () => {
    expect(attachmentProblem(fakeFile("empty.txt", "text/plain", 0), 0)).toContain("empty");
  });

  it("refuses a file over the limit before reading it", () => {
    const huge = fakeFile("huge.txt", "text/plain", MAX_ATTACHMENT_BYTES + 1);

    expect(attachmentProblem(huge, 0)).toContain("larger than 8 MB");
  });

  it("stops the tray from growing past its limit", () => {
    expect(attachmentProblem(fakeFile("a.png", "image/png"), MAX_ATTACHMENTS)).toContain(
      "up to 6 files",
    );
  });
});

describe("readAttachment", () => {
  it("reads bytes into base64 with the media type, and previews images only", async () => {
    const image = await readAttachment(fakeFile("shot.png", "image/png", 3));

    expect(image.name).toBe("shot.png");
    expect(image.media_type).toBe("image/png");
    expect(image.data).toBe(btoa("\x00\x00\x00"));
    expect(image.preview_url).toContain("blob:");

    const notes = await readAttachment(fakeFile("notes.md", "text/markdown", 2));
    expect(notes.data).toBe(btoa("\x00\x00"));
    expect(notes.preview_url).toBeUndefined();
  });

  it("sends only what the sidecar needs", async () => {
    const staged = await readAttachment(fakeFile("notes.md", "text/markdown", 2));
    const released = releaseAttachment(staged);

    expect(released).toBeUndefined();
    expect(toPayload(staged)).toEqual({
      name: "notes.md",
      media_type: "text/markdown",
      data: staged.data,
    });
  });
});

describe("isImage and formatBytes", () => {
  it("recognises images and sizes", () => {
    expect(isImage({ media_type: "image/png" })).toBe(true);
    expect(isImage({ media_type: "text/plain" })).toBe(false);
    expect(formatBytes(900)).toBe("900 B");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(3 * 1024 * 1024)).toBe("3.0 MB");
  });
});
