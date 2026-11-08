import { describe, expect, it } from "vitest";

import { arrivalAnnouncement, arrivalLabel, arrivedSince } from "./arrivalCount";

/**
 * The arrival arithmetic behind the scroll control.
 *
 * assistant-ui owns the viewport, so the only thing worth a unit test here is
 * the count: how many turns landed while the reader was scrolled up, and the
 * two strings that surface it. No DOM, no layout engine.
 */
describe("arrivedSince", () => {
  it("counts the turns appended after the last one seen from the bottom", () => {
    expect(arrivedSince(5, 8)).toBe(3);
  });

  it("counts nothing when the transcript has not grown", () => {
    expect(arrivedSince(5, 5)).toBe(0);
  });

  it("never reports a negative count when the transcript shrinks", () => {
    expect(arrivedSince(8, 2)).toBe(0);
  });
});

describe("arrivalLabel", () => {
  it("names the count when something arrived", () => {
    expect(arrivalLabel(3)).toBe("3 new ↓");
    expect(arrivalLabel(1)).toBe("1 new ↓");
  });

  it("says only that it is the latest when there is no count", () => {
    expect(arrivalLabel(0)).toBe("Latest ↓");
  });
});

describe("arrivalAnnouncement", () => {
  it("says nothing when there is nothing new", () => {
    expect(arrivalAnnouncement(0)).toBe("");
  });

  it("uses the singular for one", () => {
    expect(arrivalAnnouncement(1)).toBe("1 new message");
  });

  it("uses the plural otherwise", () => {
    expect(arrivalAnnouncement(3)).toBe("3 new messages");
  });
});
