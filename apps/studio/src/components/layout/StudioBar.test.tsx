import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";
import { StudioBar } from "./StudioBar";

const stubContext = (overrides: Record<string, unknown> = {}) => ({
  llmHealth: { healthy: true, message: "ok" },
  messages: [],
  unreadNotificationCount: 0,
  openPanel: vi.fn(),
  pushToast: vi.fn(),
  ...overrides,
});

describe("StudioBar", () => {
  it("shows the Odi mark at 32 pixels so the pixel art stays crisp", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext() as never);
    const { container } = render(
      <StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />
    );
    const svg = container.querySelector(".brand__mark svg");
    expect(svg?.getAttribute("width")).toBe("32");
    expect(svg?.getAttribute("height")).toBe("32");
  });

  it("keeps the brand mark decorative and labels the home control in text", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext() as never);
    const { container } = render(
      <StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />
    );
    expect(container.querySelector(".brand__mark")?.getAttribute("aria-hidden")).toBe("true");
    expect(container.querySelector(".brand--home")?.getAttribute("aria-label")).toBe("Go to home");
  });

  it("exports the conversation as Markdown from the overflow menu", () => {
    const createObjectURL = vi.fn(() => "blob:conversation");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      value: createObjectURL,
      configurable: true,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      value: revokeObjectURL,
      configurable: true,
    });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        messages: [
          { role: "user", content: "Show me the top outcomes." },
          { role: "assistant", content: "Here they are." },
        ],
      }) as never,
    );

    render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "More actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /export.*markdown/i }));

    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:conversation");
    click.mockRestore();
  });
});
