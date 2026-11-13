import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CopyableCode } from "./Markdown";

describe("CopyableCode", () => {
  let writeText: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeText = vi.fn(async () => {});
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
  });

  it("copies the exact code, not the label around it", async () => {
    render(<CopyableCode code={"const x = 1;\nconsole.log(x);"} />);

    fireEvent.click(screen.getByRole("button", { name: "Copy code" }));

    expect(writeText).toHaveBeenCalledWith("const x = 1;\nconsole.log(x);");
    expect(await screen.findByRole("button", { name: "Code copied" })).toBeInTheDocument();
    expect(screen.getByText("Copied")).toBeInTheDocument();
  });

  it("keeps the copy control in the tab order so a keyboard can reach it", () => {
    render(<CopyableCode code="echo hi" />);
    const control = screen.getByRole("button", { name: "Copy code" });
    expect(control).toBeInTheDocument();
    expect(control).not.toHaveAttribute("tabindex", "-1");
  });

  it("uses the caller's block class for the transcript's own code", () => {
    const { container } = render(<CopyableCode className="claim-text__code" code="x" />);
    expect(container.querySelector("pre.claim-text__code")).not.toBeNull();
  });
});
