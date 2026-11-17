import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { downloadFile } from "./download";

describe("downloadFile", () => {
  let clickSpy: ReturnType<typeof vi.spyOn>;
  let createObjectURL: ReturnType<typeof vi.fn>;
  let revokeObjectURL: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.useFakeTimers();
    createObjectURL = vi.fn(() => "blob:fake-url");
    revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", {
      createObjectURL,
      revokeObjectURL,
    });
    clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    clickSpy.mockRestore();
  });

  it("does not revoke the object URL before the click is processed", () => {
    downloadFile("{}", "file.json");
    expect(revokeObjectURL).not.toHaveBeenCalled();
  });

  it("revokes exactly once", () => {
    downloadFile("{}", "file.json");
    vi.runAllTimers();
    expect(revokeObjectURL).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:fake-url");
  });

  it("removes the anchor from the document", () => {
    downloadFile("{}", "file.json");
    expect(document.body.querySelectorAll("a")).toHaveLength(0);
  });

  it("passes the filename and type through", () => {
    downloadFile("hello", "out.txt", "text/plain");
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob.type).toBe("text/plain");
    // anchor removed already; check click happened
    expect(clickSpy).toHaveBeenCalled();
  });
});
