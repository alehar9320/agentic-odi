import { afterEach, describe, expect, it, vi } from "vitest";

import { createSpeechAdapter, speechSupported } from "./speech";

const original = Object.getOwnPropertyDescriptor(window, "speechSynthesis");

afterEach(() => {
  if (original) {
    Object.defineProperty(window, "speechSynthesis", original);
  } else {
    Reflect.deleteProperty(window, "speechSynthesis");
  }
  vi.restoreAllMocks();
});

describe("speech adapter", () => {
  it("is absent in a shell without speech synthesis, without throwing", () => {
    Reflect.deleteProperty(window, "speechSynthesis");

    expect(speechSupported()).toBe(false);
    expect(createSpeechAdapter()).toBeNull();
  });

  it("returns one adapter in a supporting shell", () => {
    Object.defineProperty(window, "speechSynthesis", {
      value: { speak: vi.fn(), cancel: vi.fn() },
      configurable: true,
    });

    expect(speechSupported()).toBe(true);
    const adapter = createSpeechAdapter();
    expect(adapter).not.toBeNull();
    expect(typeof adapter?.speak).toBe("function");
  });
});
