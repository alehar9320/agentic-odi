import { afterEach, describe, expect, it, vi } from "vitest";

import { clearDraft, loadDraft, saveDraft } from "./composerDraft";

describe("composerDraft", () => {
  afterEach(() => {
    clearDraft(null);
    clearDraft("c-1");
  });

  it("restores what was typed for the same conversation", () => {
    saveDraft("c-1", "line one\nline two\nline three");
    expect(loadDraft("c-1")).toBe("line one\nline two\nline three");
  });

  it("keeps a new conversation from inheriting another's draft", () => {
    saveDraft("c-1", "half a thought");
    expect(loadDraft(null)).toBe("");
    expect(loadDraft("c-2")).toBe("");
  });

  it("clears the draft when the message is sent", () => {
    saveDraft("c-1", "sent now");
    clearDraft("c-1");
    expect(loadDraft("c-1")).toBe("");
  });

  it("returns an empty string when nothing was stored", () => {
    expect(loadDraft("c-1")).toBe("");
  });

  it("fails soft when storage is unavailable", () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("denied");
    });
    expect(loadDraft("c-1")).toBe("");
    expect(() => saveDraft("c-1", "typed")).not.toThrow();
    getItem.mockRestore();
    setItem.mockRestore();
  });
});
