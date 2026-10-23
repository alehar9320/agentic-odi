import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";
import { StudioBar } from "./StudioBar";

const stubContext = (overrides: Record<string, unknown> = {}) => ({
  llmHealth: { healthy: true, message: "ok" },
  unreadNotificationCount: 0,
  openPanel: vi.fn(),
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

  it("labels the model health control with its state and message", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        llmHealth: { healthy: false, message: "No model is reachable." },
        openPanel: vi.fn(),
      }) as never,
    );
    render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

    expect(
      screen.getByRole("button", { name: /model status: local mode\. no model is reachable\./i }),
    ).toBeInTheDocument();
  });

  it("keeps the brand mark decorative and labels the home control in text", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext() as never);
    const { container } = render(
      <StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />
    );
    expect(container.querySelector(".brand__mark")?.getAttribute("aria-hidden")).toBe("true");
    expect(container.querySelector(".brand--home")?.getAttribute("aria-label")).toBe("Go to home");
  });
});
