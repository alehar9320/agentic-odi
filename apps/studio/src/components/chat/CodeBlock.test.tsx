import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CodeBlock } from "./CodeBlock";

function stubClipboard(writeText = vi.fn(async () => {})) {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText },
  });
  return writeText;
}

afterEach(() => {
  vi.useRealTimers();
});

describe("CodeBlock", () => {
  it("copies the exact code and shows a tick for 1600 ms", async () => {
    const writeText = stubClipboard();
    vi.useFakeTimers();

    render(<CodeBlock code={"odi score\n  -- above 10 is underserved"} preClassName="md-pre" />);

    fireEvent.click(screen.getByRole("button", { name: "Copy code" }));
    await act(async () => {});

    expect(writeText).toHaveBeenCalledWith("odi score\n  -- above 10 is underserved");
    expect(screen.getByRole("button", { name: "Copy code" })).toHaveTextContent("Copied");

    act(() => {
      vi.advanceTimersByTime(1600);
    });

    expect(screen.getByRole("button", { name: "Copy code" })).toHaveTextContent("Copy");
  });

  it("keeps the copy control in the tab order rather than removing it", () => {
    stubClipboard();

    render(<CodeBlock code="plain" preClassName="md-pre" />);

    const copy = screen.getByRole("button", { name: "Copy code" });
    copy.focus();

    expect(copy.tabIndex).toBe(0);
    expect(copy).toHaveFocus();
  });
});
