import { describe, expect, it } from "vitest";

import { textWithQuote } from "./quote";

describe("textWithQuote", () => {
  it("returns the question unchanged when nothing was quoted", () => {
    expect(textWithQuote("What about this?", null)).toBe("What about this?");
    expect(textWithQuote("What about this?", undefined)).toBe("What about this?");
    expect(textWithQuote("What about this?", { text: "   ", messageId: "a-1" })).toBe(
      "What about this?",
    );
  });

  it("puts the passage first, verbatim, with an attribution", () => {
    const passage = "the approval step is the only thing that actually hurts";
    const text = textWithQuote("Where did that come from?", {
      text: passage,
      messageId: "a-1",
    });

    expect(text.startsWith(`> ${passage}`)).toBe(true);
    expect(text).toContain("> — the assistant's reply");
    expect(text.endsWith("Where did that come from?")).toBe(true);
    // Exactly one copy: the composer strip is gone by the time the turn exists.
    expect(text.split(passage)).toHaveLength(2);
  });

  it("keeps a multi-line passage inside one blockquote", () => {
    const text = textWithQuote("And then?", {
      text: "First line\nSecond line",
      messageId: "a-2",
    });

    expect(text).toContain("> First line\n> Second line");
  });
});
