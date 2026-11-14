import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown } from "./Markdown";

describe("Markdown sanitisation", () => {
  it("renders <script> as inert text without a script node", () => {
    const { container } = render(<Markdown source="<script>alert(1)</script>" />);
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText(/alert\(1\)/)).toBeInTheDocument();
  });

  it("renders <img onerror> without an event handler or an img node", () => {
    const { container } = render(<Markdown source={'<img onerror="alert(1)">x'} />);
    expect(container.querySelector("img")).toBeNull();
  });

  it("does not render javascript: links", () => {
    const { container } = render(<Markdown source="[click](javascript:alert(1))" />);
    expect(container.querySelector('a[href^="javascript:"]')).toBeNull();
  });

  it("still renders safe https links", () => {
    render(<Markdown source="[docs](https://example.com/x)" />);
    expect(screen.getByRole("link", { name: "docs" })).toHaveAttribute(
      "href",
      "https://example.com/x",
    );
  });
});
