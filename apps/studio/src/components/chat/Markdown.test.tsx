import { render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Markdown } from "./Markdown";

afterEach(() => {
  document.body.innerHTML = "";
});

describe("Markdown", () => {
  it("renders model output as text, never as DOM", () => {
    const { container } = render(
      <Markdown source={"# Title\n\nA prompt-injected reply: `<img src=x onerror=alert(1)>` and `<script>alert(1)</script>`"} />,
    );

    // The parser keeps the literal text of the code spans, so the tags are
    // visible as characters and never become elements.
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("h1")).not.toBeNull();
    expect(container.textContent).toContain("onerror=alert(1)");
    expect(container.textContent).toContain("alert(1)");
  });

  it("does not let an image tag register a handler", () => {
    const { container } = render(<Markdown source={"<img src=x onerror=alert(1)>"} />);

    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("onerror=alert(1)");
  });

  it("does not let a script tag execute", () => {
    const { container } = render(<Markdown source={"<script>alert(1)</script>"} />);

    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain("<script>alert(1)</script>");
  });
});