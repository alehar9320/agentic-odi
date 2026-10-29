import { describe, expect, it } from "vitest";

import {
  MAX_IMAGE_BYTES,
  attachmentRejection,
  formatFileSize,
  isTextLike,
} from "./attachments";

function fileOf(name: string, type: string, size = 10): File {
  const file = new File(["x"], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

describe("attachmentRejection", () => {
  it("accepts a text file by extension even when the browser reports no type", () => {
    expect(attachmentRejection(fileOf("notes.md", ""))).toBeNull();
    expect(isTextLike("notes.md", "")).toBe(true);
  });

  it("accepts a small image", () => {
    expect(attachmentRejection(fileOf("shot.png", "image/png", 1024))).toBeNull();
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
