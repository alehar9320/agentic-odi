import { configure } from "@chromatic-com/vitest";
import { userEvent } from "vitest/browser";
import { render } from "vitest-browser-react";
import { expect, it, vi } from "vitest";

import "../../styles/theme.css";
import { StudioBar } from "./StudioBar";

// The build table would otherwise name this `StudioBar.visual` after the file;
// the surface under review is the new-thread control, which is what #319 changes.
configure({ title: "New thread control" });

// vi.mock factories run while the imports above resolve, so the stand-in state
// has to exist before they do.
const stub = vi.hoisted(() => {
  const noop = () => {};
  return {
    studio: {
      llmHealth: { healthy: true, message: "ok" },
      probeRetry: { state: "closed", retryInMs: 0 },
      messages: [
        { id: "t-1", role: "user", content: "I own activation." },
        { id: "t-2", role: "assistant", content: "Tell me more." },
      ],
      sidecarReachable: true,
      streaming: false,
      unreadSignalCount: 0,
      openPanel: noop,
      activePanel: null,
      customizeOpen: false,
      setupOpen: false,
      openCustomize: noop,
      pushToast: noop,
      saveSettings: noop,
      settings: { theme: "dark", base_url: "", api_key: "", model_name: "" },
    } as Record<string, unknown>,
  };
});

vi.mock("../../state/StudioContext", () => ({ useStudio: () => stub.studio }));
vi.mock("../../updater", () => ({
  useUpdateSnapshot: () => ({ phase: "idle", currentVersion: null }),
}));

it("shows the labelled control over a saved thread", async () => {
  const screen = await render(
    <StudioBar onHome={vi.fn()} onNew={vi.fn()} onChangelog={vi.fn()} />,
  );

  await expect.element(screen.getByRole("button", { name: "Start a new thread" })).toBeVisible();
  // Review runs at 900px, above the breakpoint, so the words are in the shot.
  await expect.element(screen.getByText("New thread")).toBeVisible();
});

it("asks before discarding a reply, and hangs below the control that opened it", async () => {
  stub.studio.streaming = true;
  const onNew = vi.fn();
  const screen = await render(
    <StudioBar onHome={vi.fn()} onNew={onNew} onChangelog={vi.fn()} />,
  );

  const control = screen.getByRole("button", { name: "Start a new thread" });
  await expect.element(control).toHaveAttribute("aria-haspopup", "dialog");
  await userEvent.click(control);

  const ask = screen.getByRole("dialog", { name: /stop the reply and start a new thread\?/i });
  await expect.element(ask).toBeVisible();
  await expect.element(screen.getByRole("button", { name: "Keep writing" })).toBeVisible();

  const triggerBox = (await control.element()) as HTMLElement;
  const askBox = (await ask.element()) as HTMLElement;
  const trigger = triggerBox.getBoundingClientRect();
  const popover = askBox.getBoundingClientRect();
  // The ask belongs to the control: below it, and sharing its right edge.
  expect(popover.top).toBeGreaterThanOrEqual(trigger.bottom);
  expect(Math.abs(popover.right - trigger.right)).toBeLessThanOrEqual(2);

  await userEvent.click(screen.getByRole("button", { name: "Stop and start" }));
  await expect.element(ask).not.toBeInTheDocument();
  expect(onNew).toHaveBeenCalledWith({ stop: true });
});
