import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { downloadFile } from "./download";

describe("downloadFile", () => {
  let createObjectURL: ReturnType<typeof vi.fn>;
  let revokeObjectURL: ReturnType<typeof vi.fn>;
  let clickSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    createObjectURL = vi.fn(() => "blob:mock-url");
    revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", {
      createObjectURL,
      revokeObjectURL,
    });
    clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
    clickSpy.mockRestore();
  });

  it("does not revoke the object URL before the click is processed", () => {
    vi.useFakeTimers();
    downloadFile("contents", "file.json");
    expect(revokeObjectURL).not.toHaveBeenCalled();
    vi.advanceTimersByTime(0);
    // still not revoked synchronously within same turn assertion handled by not called before
  });

  it("revokes exactly once", () => {
    vi.useFakeTimers();
    downloadFile("contents", "file.json");
    vi.advanceTimersByTime(0);
    expect(revokeObjectURL).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");
  });

  it("removes the anchor from the document", () => {
    downloadFile("contents", "file.json");
    // after call, no anchor with download remains
    expect(document.querySelectorAll("a")).toHaveLength(0);
  });

  it("passes the filename and type through", () => {
    const appended: HTMLAnchorElement[] = [];
    vi.spyOn(document.body, "appendChild").mockImplementation((node) => {
      appended.push(node as HTMLAnchorElement);
      return node;
    });
    downloadFile("hello", "report.csv", "text/csv");
    expect(createObjectURL).toHaveBeenCalled();
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob.type).toBe("text/csv");
    expect(appended[0].download).toBe("report.csv");
    expect(clickSpy).toHaveBeenCalled();
  });
});
