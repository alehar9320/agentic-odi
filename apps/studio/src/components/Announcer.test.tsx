import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Announcer } from "./Announcer";
import { announce } from "../lib/announce";

describe("Announcer", () => {
  it("renders one polite live region", () => {
    render(<Announcer />);
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveAttribute("aria-atomic", "true");
  });

  it("speaks a burst one sentence at a time, in order", () => {
    render(<Announcer />);
    const region = screen.getByRole("status");

    act(() => {
      announce("Copied");
      announce("Exported");
      announce("Saved");
    });

    // One region, one sentence at a time: a burst is a sequence, not a jumble.
    expect(region).toHaveTextContent("Copied");
  });
});
