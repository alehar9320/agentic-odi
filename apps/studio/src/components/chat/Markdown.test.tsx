import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown } from "./Markdown";

function html(source: string): HTMLElement {
  const { container } = render(<Markdown source={source} />);
  return container;
}

describe("Markdown", () => {
  it("renders bold, italic and inline code with the md classes", () => {
    const container = html("A **bold** and *soft* `code` line");

    const strong = container.querySelector("strong");
    expect(strong).toHaveTextContent("bold");
    expect(container.querySelector("em")).toHaveTextContent("soft");
    const code = container.querySelector("code");
    expect(code).toHaveTextContent("code");
    expect(code).toHaveClass("md-code");
  });

  it("renders a safe link as an anchor", () => {
    const container = html("see [docs](https://example.com/x)");

    const link = container.querySelector("a");
    expect(link).toHaveAttribute("href", "https://example.com/x");
    expect(link).toHaveTextContent("docs");
  });

  it("leaves unmatched markers as text", () => {
    const container = html("2 * 3 = 6");

    expect(container.textContent).toBe("2 * 3 = 6");
    expect(container.querySelector("em")).toBeNull();
  });

  it("renders heading levels 1 to 3", () => {
    const container = html("# One\n## Two\n### Three");

    expect(container.querySelector("h1")).toHaveClass("md-heading");
    expect(container.querySelector("h2")).toHaveClass("md-heading");
    expect(container.querySelector("h3")).toHaveClass("md-heading");
  });

  it("groups consecutive bullet items into one list", () => {
    const container = html("- define\n- locate\n- prepare");

    const lists = container.querySelectorAll("ul");
    expect(lists).toHaveLength(1);
    expect(lists[0]).toHaveClass("md-list");
    expect(lists[0].querySelectorAll("li")).toHaveLength(3);
  });

  it("keeps the start index of ordered lists", () => {
    const container = html("3. confirm\n4. execute");

    const list = container.querySelector("ol");
    expect(list).toHaveAttribute("start", "3");
    expect(list?.querySelectorAll("li")).toHaveLength(2);
  });

  it("preserves fenced code verbatim, including blank lines", () => {
    const container = html("```python\na = 1\n\nb = 2\n```");

    const pre = container.querySelector("pre");
    expect(pre).toHaveClass("md-pre");
    expect(pre?.textContent).toBe("a = 1\n\nb = 2");
  });

  it("joins soft-wrapped lines in a paragraph and splits on blank lines", () => {
    const container = html("first line\ncontinues\n\nsecond paragraph");

    const paragraphs = container.querySelectorAll("p");
    expect(paragraphs).toHaveLength(2);
    expect(paragraphs[0]).toHaveTextContent("first line continues");
    expect(paragraphs[1]).toHaveTextContent("second paragraph");
  });

  it("parses block quotes", () => {
    const container = html("> customers are stuck");

    const quote = container.querySelector("blockquote");
    expect(quote).toHaveClass("md-quote");
    expect(quote).toHaveTextContent("customers are stuck");
  });

  it("does not choke on an unterminated code fence", () => {
    const container = html("```\nstill typing");

    expect(container.querySelector("pre")?.textContent).toBe("still typing");
  });

  it("renders a GFM table as a table", () => {
    const container = html(
      "| Outcome | Score |\n| --- | --- |\n| Save time | 12 |\n| Avoid rework | 9 |",
    );

    const table = container.querySelector("table");
    expect(table).not.toBeNull();
    expect(table).toHaveClass("md-table");
    expect(table?.querySelectorAll("thead th")).toHaveLength(2);
    expect(table?.querySelectorAll("tbody tr")).toHaveLength(2);
    expect(table?.textContent).toContain("Save time");
  });

  it("renders GFM strikethrough", () => {
    const container = html("this ~~is gone~~");

    expect(container.querySelector("del")).toHaveTextContent("is gone");
  });

  it("renders a GFM task list with disabled checkboxes", () => {
    const container = html("- [x] done\n- [ ] todo");

    const boxes = container.querySelectorAll<HTMLInputElement>('input[type="checkbox"]');
    expect(boxes).toHaveLength(2);
    expect(boxes[0]).toBeChecked();
    expect(boxes[0]).toBeDisabled();
    expect(boxes[1]).not.toBeChecked();
  });

  it("turns a bare URL into a link", () => {
    const container = html("read https://example.com/a for more");

    const link = container.querySelector("a");
    expect(link).toHaveAttribute("href", "https://example.com/a");
  });

  it("keeps raw HTML inert", () => {
    const container = html("<img src=x onerror=alert(1)>");

    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<img src=x onerror=alert(1)>");
  });

  it("renders unsafe URLs as text, not links", () => {
    const container = html(
      "[script](javascript:alert(1)) and [data](data:text/html,<script>alert(1)</script>)",
    );

    expect(container.querySelector("a")).toBeNull();
    expect(container.textContent).toContain("script");
    expect(container.textContent).toContain("data");
  });

  it("opens external links safely in a new tab", () => {
    const container = html("[docs](https://example.com/x)");

    const link = container.querySelector("a");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer noopener");
  });

  it("wraps the rendered markdown in the md container", () => {
    const container = html("hello");

    expect(container.firstElementChild).toHaveClass("md");
  });
});