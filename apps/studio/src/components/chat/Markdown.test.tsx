import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown } from "./Markdown";

describe("Markdown sanitisation", () => {
  it("renders <script> as inert text without a script node", () => {
    render(<Markdown source="<script>alert(1)</script>" />);
    expect(screen.queryBySelector("script")).toBeNull();
  });

  it("renders <img onerror> without an event handler or an img node", () => {
    render(<Markdown source='<img onerror="alert(1)">x" />');
    expect(screen.queryBySelector("img")).toBeNull();
  });

  it("does not render javascript: links", () => {
    render(<Markdown source="[click](javascript:alert(1))" />);
    expect(screen.queryBySelector('a[href="javascript:alert(1)"]')).toBeNull();
  });

  it("still renders safe https links", () => {
    render(<Markdown source="[docs](https://example.com/x)" />);
    expect(screen.getByRole("link", { name: "docs" })).toHaveAttribute(
      "href",
      "https://example.com/x",
    );
  });
});
