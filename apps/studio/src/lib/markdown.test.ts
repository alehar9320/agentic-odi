import { describe, expect, it } from "vitest";

import { parseInline, parseMarkdown } from "./markdown";

describe("parseInline", () => {
  it("reads bold, italic and inline code", () => {
    expect(parseInline("A **bold** and *soft* `code` line")).toEqual([
      { type: "text", text: "A " },
      { type: "strong", text: "bold" },
      { type: "text", text: " and " },
      { type: "em", text: "soft" },
      { type: "text", text: " " },
      { type: "code", text: "code" },
      { type: "text", text: " line" },
    ]);
  });

  it("keeps links and ignores unsafe urls later at render time", () => {
    expect(parseInline("see [docs](https://example.com/x)")).toEqual([
      { type: "text", text: "see " },
      { type: "link", text: "docs", href: "https://example.com/x" },
    ]);
  });

  it("leaves unmatched markers as text", () => {
    expect(parseInline("2 * 3 = 6")).toEqual([{ type: "text", text: "2 * 3 = 6" }]);
  });
});

describe("parseMarkdown", () => {
  it("parses headings with their level", () => {
    const blocks = parseMarkdown("## Desired outcomes\nIntro text.");
    expect(blocks[0]).toMatchObject({ type: "heading", level: 2 });
    expect(blocks[1]).toMatchObject({ type: "paragraph" });
  });

  it("groups consecutive bullet items into one list", () => {
    const blocks = parseMarkdown("- define\n- locate\n- prepare");
    expect(blocks).toHaveLength(1);
    expect(blocks[0]).toMatchObject({ type: "list", ordered: false });
    if (blocks[0].type === "list") {
      expect(blocks[0].items).toHaveLength(3);
    }
  });

  it("keeps the start index of ordered lists", () => {
    const blocks = parseMarkdown("3. confirm\n4. execute");
    expect(blocks[0]).toMatchObject({ type: "list", ordered: true, start: 3 });
  });

  it("preserves fenced code verbatim, including blank lines", () => {
    const blocks = parseMarkdown("```python\na = 1\n\nb = 2\n```");
    expect(blocks).toEqual([{ type: "code", language: "python", code: "a = 1\n\nb = 2" }]);
  });

  it("joins soft-wrapped lines in a paragraph and splits on blank lines", () => {
    const blocks = parseMarkdown("first line\ncontinues\n\nsecond paragraph");
    expect(blocks).toHaveLength(2);
    expect(blocks[0]).toEqual({
      type: "paragraph",
      spans: [{ type: "text", text: "first line continues" }],
    });
  });

  it("parses block quotes", () => {
    const blocks = parseMarkdown("> customers are stuck");
    expect(blocks[0]).toMatchObject({ type: "quote" });
  });

  it("does not choke on an unterminated code fence", () => {
    expect(parseMarkdown("```\nstill typing")).toEqual([
      { type: "code", language: "", code: "still typing" },
    ]);
  });
});
