import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";
import { StudioBar } from "./StudioBar";

const stubContext = (overrides: Record<string, unknown> = {}) => ({
  llmHealth: { healthy: true, message: "ok" },
  unreadNotificationCount: 0,
  markAllNotificationsAsRead: vi.fn(),
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

  it("keeps the brand mark decorative and labels the home control in text", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext() as never);
    const { container } = render(
      <StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />
    );
    expect(container.querySelector(".brand__mark")?.getAttribute("aria-hidden")).toBe("true");
    expect(container.querySelector(".brand--home")?.getAttribute("aria-label")).toBe("Go to home");
  });

  it("shows the unread count and clears it when catch-up opens", () => {
    const openPanel = vi.fn();
    const markAllNotificationsAsRead = vi.fn();
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        unreadNotificationCount: 3,
        openPanel,
        markAllNotificationsAsRead,
      }) as never,
    );
    const { getByRole } = render(
      <StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />
    );

    const bell = getByRole("button", { name: "Catch up notifications" });
    expect(bell.textContent).toContain("3");
    fireEvent.click(bell);

    expect(markAllNotificationsAsRead).toHaveBeenCalled();
    expect(openPanel).toHaveBeenCalledWith("catchup");
  });
});
