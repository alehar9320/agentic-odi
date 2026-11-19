import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown } from "./Markdown";

describe("Markdown structure", () => {
  it("renders bold, italic and inline code", () => {
    const { container } = render(<Markdown source="A **bold** and *soft* `code` line" />);

    expect(container.querySelector("strong")?.textContent).toBe("bold");
    expect(container.querySelector("em")?.textContent).toBe("soft");
    expect(container.querySelector("code")?.textContent).toBe("code");
  });

  it("renders safe links", () => {
    render(<Markdown source="see [docs](https://example.com/x)" />);

    expect(screen.getByRole("link", { name: "docs" })).toHaveAttribute(
      "href",
      "https://example.com/x",
    );
  });

  it("leaves unmatched markers as text", () => {
    const { container } = render(<Markdown source="2 * 3 = 6" />);

    expect(container.textContent).toContain("2 * 3 = 6");
  });

  it("renders heading levels", () => {
    const { container } = render(<Markdown source={"## Desired outcomes\n\nIntro text."} />);

    const heading = container.querySelector("h2");
    expect(heading).not.toBeNull();
    expect(heading?.className).toBe("md-heading");
  });

  it("groups consecutive bullets into one list", () => {
    const { container } = render(<Markdown source={"- define\n- locate\n- prepare"} />);

    expect(container.querySelectorAll("ul.md-list")).toHaveLength(1);
    expect(container.querySelectorAll("li")).toHaveLength(3);
  });

  it("keeps the start index of an ordered list", () => {
    const { container } = render(<Markdown source={"3. confirm\n4. execute"} />);

    expect(container.querySelector("ol.md-list")).toHaveAttribute("start", "3");
  });

  it("preserves fenced code verbatim, including blank lines", () => {
    const { container } = render(<Markdown source={"```python\na = 1\n\nb = 2\n```"} />);

    // CommonMark keeps the fenced block's own trailing newline.
    const code = container.querySelector("pre.md-pre code");
    expect(code?.textContent?.replace(/\n$/, "")).toBe("a = 1\n\nb = 2");
  });

  it("joins soft-wrapped lines in a paragraph and splits on blank lines", () => {
    const { container } = render(<Markdown source={"first line\ncontinues\n\nsecond paragraph"} />);

    // A soft break is a newline that renders as a space, so one paragraph
    // reads as one joined sentence; a blank line starts the next paragraph.
    const paragraphs = container.querySelectorAll("p.md-paragraph");
    expect(paragraphs).toHaveLength(2);
    expect(paragraphs[0].textContent?.replace(/\s+/g, " ")).toBe("first line continues");
  });

  it("renders block quotes", () => {
    const { container } = render(<Markdown source="> customers are stuck" />);

    expect(container.querySelector("blockquote.md-quote")?.textContent).toContain(
      "customers are stuck",
    );
  });

  it("does not choke on an unterminated code fence", () => {
    const { container } = render(<Markdown source={"```\nstill typing"} />);

    expect(
      container.querySelector("pre.md-pre code")?.textContent?.replace(/\n$/, ""),
    ).toBe("still typing");
  });
});

describe("Markdown GFM", () => {
  it("renders a table as a table", () => {
    const source = "| Outcome | Score |\n| --- | --- |\n| Retention | 9.1 |";
    const { container } = render(<Markdown source={source} />);

    expect(container.querySelector("table.md-table")).not.toBeNull();
    expect(container.querySelectorAll("th")).toHaveLength(2);
    expect(container.querySelectorAll("td")).toHaveLength(2);
    expect(container.textContent).toContain("Retention");
  });

  it("renders strikethrough", () => {
    const { container } = render(<Markdown source="~~dropped~~" />);

    expect(container.querySelector("del")?.textContent).toBe("dropped");
  });

  it("renders task lists", () => {
    const { container } = render(<Markdown source={"- [x] grounded\n- [ ] guessed"} />);

    const boxes = container.querySelectorAll('input[type="checkbox"]');
    expect(boxes).toHaveLength(2);
    expect((boxes[0] as HTMLInputElement).checked).toBe(true);
    expect((boxes[1] as HTMLInputElement).checked).toBe(false);
  });

  it("autolinks a bare url", () => {
    render(<Markdown source="see https://example.com/x for detail" />);

    expect(screen.getByRole("link", { name: "https://example.com/x" })).toHaveAttribute(
      "href",
      "https://example.com/x",
    );
  });
});

describe("Markdown sanitisation", () => {
  it("renders <script> as inert text without a script node", () => {
    const { container } = render(<Markdown source="<script>alert(1)</script>" />);

    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText(/alert\(1\)/)).toBeInTheDocument();
  });

  it("renders <img onerror> as text without an img node", () => {
    const { container } = render(<Markdown source={'<img src=x onerror="alert(1)">x'} />);

    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<img src=x onerror=");
  });

  it("renders javascript: and data: urls as text, not links", () => {
    const { container } = render(
      <Markdown source={"[click](javascript:alert(1)) and [here](data:text/html,x)"} />,
    );

    expect(container.querySelector('a[href^="javascript:"]')).toBeNull();
    expect(container.querySelector('a[href^="data:"]')).toBeNull();
    expect(container.textContent).toContain("click");
    expect(container.textContent).toContain("here");
  });

  it("gives external links target=_blank and rel=noreferrer noopener", () => {
    render(<Markdown source="[docs](https://example.com/x)" />);

    const link = screen.getByRole("link", { name: "docs" });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer noopener");
  });

  it("hides claim markers inside the standalone renderer", () => {
    const { container } = render(<Markdown source="Three stalled. [[ev:E-1]] Next." />);

    expect(container.textContent).not.toContain("[[");
    expect(container.textContent).toContain("Three stalled.");
  });
});
