import { describe, expect, it, vi } from "vitest";

import {
  NEXT_STEP_DISMISS_KEY,
  readNextStepDismissed,
  writeNextStepDismissed,
} from "./nextStep";

function storage(initial: Record<string, string> = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => {
      map.set(key, value);
    },
    entries: () => map,
  };
}

describe("next step dismissal", () => {
  it("offers the question until it is put away", () => {
    expect(readNextStepDismissed(storage())).toBe(false);
    expect(readNextStepDismissed(storage({ [NEXT_STEP_DISMISS_KEY]: "1" }))).toBe(true);
  });

  it("forgets the answer between sessions, because the step did not", () => {
    // A step is kept in the store until it is answered, so a dismissal kept for
    // good would silence the one question the product exists to ask. The visit
    // it belongs to is the session, so that is how long it lasts.
    const session = storage();
    writeNextStepDismissed(true, session);

    expect(session.entries().get(NEXT_STEP_DISMISS_KEY)).toBe("1");
    expect(readNextStepDismissed(storage())).toBe(false);
  });

  it("stays quiet when the browser refuses storage", () => {
    const denied = {
      getItem: () => null,
      setItem: () => {
        throw new Error("denied");
      },
    };

    expect(() => writeNextStepDismissed(true, denied)).not.toThrow();
    expect(readNextStepDismissed(denied)).toBe(false);
  });

  it("reads nothing when there is no browser", () => {
    vi.stubGlobal("window", undefined);
    try {
      expect(readNextStepDismissed()).toBe(false);
      expect(() => writeNextStepDismissed(true)).not.toThrow();
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
