import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { downloadFile } from "./download";

describe("downloadFile", () => {
  let createObjectURLSpy: ReturnType<typeof vi.fn>;
  let revokeObjectURLSpy: ReturnType<typeof vi.fn>;
  let clickSpy: ReturnType<typeof vi.fn>;
  let originalCreateObjectURL: typeof URL.createObjectURL;
  let originalRevokeObjectURL: typeof URL.revokeObjectURL;
  let originalClick: typeof HTMLAnchorElement.prototype.click;

  beforeEach(() => {
    vi.useFakeTimers();

    originalCreateObjectURL = URL.createObjectURL;
    originalRevokeObjectURL = URL.revokeObjectURL;
    originalClick = HTMLAnchorElement.prototype.click;

    createObjectURLSpy = vi.fn(() => "blob:mock-url");
    revokeObjectURLSpy = vi.fn();
    clickSpy = vi.fn();

    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: createObjectURLSpy,
      revokeObjectURL: revokeObjectURLSpy,
    });

    HTMLAnchorElement.prototype.click = clickSpy as () => void;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    HTMLAnchorElement.prototype.click = originalClick;
    URL.createObjectURL = originalCreateObjectURL;
    URL.revokeObjectURL = originalRevokeObjectURL;
    document.body.innerHTML = "";
  });

  it("does not revoke the object URL before the click is processed", () => {
    downloadFile("test content", "test.txt", "text/plain");

    expect(revokeObjectURLSpy).not.toHaveBeenCalled();

    vi.advanceTimersByTime(0);

    expect(revokeObjectURLSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectURLSpy).toHaveBeenCalledWith("blob:mock-url");
  });

  it("revokes exactly once", () => {
    downloadFile("test content", "test.txt", "text/plain");
    vi.advanceTimersByTime(0);

    expect(revokeObjectURLSpy).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(1000);
    expect(revokeObjectURLSpy).toHaveBeenCalledTimes(1);
  });

  it("removes the anchor from the document", () => {
    downloadFile("test content", "test.txt", "text/plain");

    const anchors = document.body.querySelectorAll("a");
    expect(anchors.length).toBe(0);
  });

  it("passes the filename and type through", () => {
    downloadFile("test content", "custom-name.csv", "text/csv");

    expect(createObjectURLSpy).toHaveBeenCalledTimes(1);
    const blobArg = createObjectURLSpy.mock.calls[0][0] as Blob;
    expect(blobArg.type).toBe("text/csv");
    expect(blobArg.size).toBeGreaterThan(0);
  });
});