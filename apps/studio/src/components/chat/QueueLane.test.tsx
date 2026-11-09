import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import { createTurnQueue, queuedUserMessage } from "../../assistant/queue";
import type { StudioContextValue } from "../../state/StudioContext";
import { QueueLane } from "./QueueLane";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";

const stubContext = (overrides: Record<string, unknown> = {}) =>
  ({
    messages: [],
    canvas: null,
    llmHealth: { healthy: true, message: "" },
    streaming: false,
    openPanel: vi.fn(),
    sendMessage: vi.fn(async () => {}),
    regenerateFrom: vi.fn(async () => {}),
    editFrom: vi.fn(async () => {}),
    switchBranch: vi.fn(),
    respondToApproval: vi.fn(async () => {}),
    stopStreaming: vi.fn(),
    ...overrides,
  }) as unknown as StudioContextValue;

// A turn that only settles when the test says so: everything queued behind it
// waits in the lane, which is exactly the state the component exists to show.
function liveController() {
  let settleTurn: () => void = () => undefined;
  const driver = {
    run: vi.fn(
      () =>
        new Promise<void>((resolve) => {
          settleTurn = () => resolve();
        }),
    ),
    cancel: vi.fn(),
  };
  const controller = createTurnQueue(driver);
  return { controller, driver, endTurn: () => settleTurn() };
}

// The external-store runtime re-reads the queue lanes when the store refreshes,
// which it does on every turn event in the real studio; in a unit test the
// pulse replaces that rhythm.
function renderLane(queue: StudioContextValue["queue"]) {
  const tree = () => (
    <StudioRuntimeProvider>
      <QueueLane />
    </StudioRuntimeProvider>
  );
  vi.mocked(useStudio).mockReturnValue(stubContext({ streaming: true, queue }));
  const view = render(tree());
  return {
    view,
    pulse: () => {
      vi.mocked(useStudio).mockReturnValue(stubContext({ streaming: true, queue }));
      view.rerender(tree());
    },
  };
}

describe("QueueLane", () => {
  beforeEach(() => {
    vi.mocked(useStudio).mockReturnValue(stubContext());
  });

  it("renders nothing while the lane is empty", () => {
    const { controller } = liveController();
    const { pulse } = renderLane(controller.adapter);

    pulse();
    expect(screen.queryByRole("log", { name: "Queued follow-ups" })).toBeNull();
  });

  it("shows the follow-ups waiting behind the live turn", async () => {
    const { controller } = liveController();
    const { pulse } = renderLane(controller.adapter);

    await act(async () => {
      controller.adapter.enqueue(queuedUserMessage("the live turn"));
      controller.adapter.enqueue(queuedUserMessage("draft the reply next"));
      controller.adapter.enqueue(queuedUserMessage("and log the outcome"));
    });
    pulse();

    const lane = screen.getByRole("log", { name: "Queued follow-ups" });
    expect(lane).toHaveTextContent("draft the reply next");
    expect(lane).toHaveTextContent("and log the outcome");
    // The dispatched turn is being answered, not queued — it is not in the lane.
    expect(lane).not.toHaveTextContent("the live turn");
  });

  it("Run now jumps a follow-up to the front without interrupting the answer", async () => {
    const { controller, driver, endTurn } = liveController();
    const { pulse } = renderLane(controller.adapter);

    await act(async () => {
      controller.adapter.enqueue(queuedUserMessage("the live turn"));
      controller.adapter.enqueue(queuedUserMessage("later please"));
      controller.adapter.enqueue(queuedUserMessage("actually, first"));
    });
    pulse();

    fireEvent.click(screen.getAllByRole("button", { name: "Run now" })[1]);
    pulse();

    // Run now is a re-place, not a cut of the wire: one stream at a time, so
    // the live turn is never cancelled by it (#410).
    expect(driver.cancel).not.toHaveBeenCalled();
    const lane = screen.getByRole("log", { name: "Queued follow-ups" });
    const jumped = lane.textContent?.indexOf("actually, first") ?? -1;
    const waiting = lane.textContent?.indexOf("later please") ?? -1;
    expect(jumped).toBeGreaterThanOrEqual(0);
    expect(jumped).toBeLessThan(waiting);

    // When the live answer settles, the jumped message is dispatched next.
    await act(async () => {
      endTurn();
    });
    expect(driver.run).toHaveBeenLastCalledWith(
      expect.objectContaining({ content: [{ type: "text", text: "actually, first" }] }),
      { steer: false },
    );
  });

  it("remove drops only its own message", async () => {
    const { controller, driver } = liveController();
    const { pulse } = renderLane(controller.adapter);

    await act(async () => {
      controller.adapter.enqueue(queuedUserMessage("the live turn"));
      controller.adapter.enqueue(queuedUserMessage("keep me"));
      controller.adapter.enqueue(queuedUserMessage("drop me"));
    });
    pulse();

    fireEvent.click(screen.getAllByRole("button", { name: "Remove queued message" })[1]);
    pulse();

    expect(screen.getByText("keep me")).toBeInTheDocument();
    expect(screen.queryByText("drop me")).toBeNull();

    await act(async () => {
      controller.release();
    });
    expect(driver.run).toHaveBeenCalledTimes(1);
  });
});
