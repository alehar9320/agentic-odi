import { afterEach, describe, expect, it } from "vitest";

import { createDictationAdapter, dictationSupported } from "./dictation";

const originalRecognition = Object.getOwnPropertyDescriptor(window, "SpeechRecognition");

afterEach(() => {
  if (originalRecognition) {
    Object.defineProperty(window, "SpeechRecognition", originalRecognition);
  } else {
    Reflect.deleteProperty(window, "SpeechRecognition");
  }
});

describe("dictation adapter", () => {
  it("is absent where the shell has no speech recognition", () => {
    expect(dictationSupported()).toBe(false);
    expect(createDictationAdapter()).toBeNull();
  });

  it("returns one adapter where recognition exists", () => {
    class FakeRecognition {}
    Object.defineProperty(window, "SpeechRecognition", {
      value: FakeRecognition,
      configurable: true,
    });

    expect(dictationSupported()).toBe(true);
    expect(createDictationAdapter()).not.toBeNull();
  });
});
