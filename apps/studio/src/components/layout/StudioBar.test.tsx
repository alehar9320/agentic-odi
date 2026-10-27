import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("../../updater", () => ({
  useUpdateSnapshot: vi.fn(),
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";
import { useUpdateSnapshot } from "../../updater";
import type { UpdateSnapshot } from "../../updater/types";
import { StudioBar } from "./StudioBar";

const stubContext = (overrides: Record<string, unknown> = {}) => ({
  llmHealth: { healthy: true, message: "ok" },
  messages: [],
  unreadNotificationCount: 0,
  markAllNotificationsAsRead: vi.fn(),
  openPanel: vi.fn(),
  pushToast: vi.fn(),
  saveSettings: vi.fn(),
  settings: { base_url: "", api_key: "", model_name: "", mcp_url: "", theme: "dark" },
  ...overrides,
});

const stubSnapshot = (overrides: Partial<UpdateSnapshot> = {}): UpdateSnapshot => ({
  phase: "up-to-date",
  currentVersion: "0.12.0",
  available: null,
  progress: null,
  lastCheckedAt: null,
  installed: false,
  pendingInstall: false,
  error: null,
  autoCheck: true,
  skippedVersion: null,
  dismissedVersion: null,
  ...overrides,
});

describe("StudioBar", () => {
  beforeEach(() => {
    vi.mocked(useUpdateSnapshot).mockReturnValue(stubSnapshot() as never);
  });
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

  it("switches to the light theme from the bar", () => {
    const saveSettings = vi.fn();
    vi.mocked(useStudio).mockReturnValue(stubContext({ saveSettings }) as never);
    const { getByRole } = render(
      <StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />
    );

    fireEvent.click(getByRole("button", { name: "Switch to light theme" }));

    expect(saveSettings).toHaveBeenCalledWith(expect.objectContaining({ theme: "light" }));
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

  it("shows the running version and opens update settings", () => {
    const openPanel = vi.fn();
    vi.mocked(useStudio).mockReturnValue(stubContext({ openPanel }) as never);
    render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

    const version = screen.getByRole("button", { name: "v0.12.0" });
    fireEvent.click(version);

    expect(openPanel).toHaveBeenCalledWith("settings");
  });

  it("says update ready when a restart will finish the job", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext() as never);
    vi.mocked(useUpdateSnapshot).mockReturnValue(stubSnapshot({ phase: "ready" }) as never);

    render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

    expect(screen.getByRole("button", { name: "Update ready" })).toBeInTheDocument();
  });
});
