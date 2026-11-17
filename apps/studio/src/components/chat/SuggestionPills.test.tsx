import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  CAPTURE_PROMPT,
  NOTES_PROMPT,
  StudioRuntimeProvider,
} from "../../assistant/StudioRuntime";
import { createTurnQueue, queuedUserMessage } from "../../assistant/queue";
import type { StudioContextValue } from "../../state/StudioContext";
import { SuggestionPills } from "./composerParts";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";

const FIRST_STARTER = "Turn 40 interview notes into one bet";
const CANVAS_STARTER = "Capture what you heard";

const stubContext = (overrides: Record<string, unknown> = {}) =>
  ({
    messages: [],
    canvas: null,
    llmHealth: { healthy: true, message: "" },
    streaming: false,
    openPanel: vi.fn(),
    sendMessage: vi.fn(async () => {}),
    ...overrides,
  }) as unknown as StudioContextValue;

function renderPills() {
  return render(
    <StudioRuntimeProvider>
      <SuggestionPills />
    </StudioRuntimeProvider>,
  );
}

// A turn that only settles when the test says so, so a click mid-answer has
// nowhere to go but the queue lane (#410).
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
  return { controller: createTurnQueue(driver), driver, endTurn: () => settleTurn() };
}

describe("SuggestionPills starters", () => {
  beforeEach(() => {
    vi.mocked(useStudio).mockReturnValue(stubContext());
  });

  it("sends the starter's exported prompt verbatim", () => {
    const sendMessage = vi.fn(async () => {});
    vi.mocked(useStudio).mockReturnValue(stubContext({ sendMessage }));

    renderPills();
    fireEvent.click(screen.getByRole("button", { name: FIRST_STARTER }));

    // Exactly one call, exactly the constant: no prefix, suffix, or wrapper.
    expect(sendMessage).toHaveBeenCalledTimes(1);
    expect(sendMessage).toHaveBeenCalledWith(NOTES_PROMPT, []);
  });

  it("lets the runtime own submission: the prompt enters the queue, not a hand-rolled send", async () => {
    const { controller, driver } = liveController();
    const sendMessage = vi.fn(async () => {});
    vi.mocked(useStudio).mockReturnValue(
      stubContext({ streaming: true, queue: controller.adapter, sendMessage }),
    );

    renderPills();

    // A turn is already in flight, so the queue is busy: the click has to wait
    // its turn rather than opening a second stream.
    await act(async () => {
      controller.adapter.enqueue(queuedUserMessage("the live turn"));
      fireEvent.click(screen.getByRole("button", { name: FIRST_STARTER }));
    });

    // The suggestion primitive routes through the runtime; the context's own
    // send path is untouched. A hand-built onClick would have called
    // sendMessage directly and swallowed the click mid-answer (#410).
    expect(sendMessage).not.toHaveBeenCalled();
    const texts = driver.run.mock.calls.map((call: unknown[]) => {
      const message = call[0] as { content?: { text?: string }[] };
      return message.content?.[0]?.text;
    });
    expect(texts).toContain(NOTES_PROMPT);
  });

  it("submits a returning-user starter from a non-empty canvas unchanged", () => {
    const sendMessage = vi.fn(async () => {});
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        canvas: { jobs: [{ id: "job-1" }], outcomes: [] },
        sendMessage,
      }),
    );

    renderPills();
    fireEvent.click(screen.getByRole("button", { name: CANVAS_STARTER }));

    expect(sendMessage).toHaveBeenCalledTimes(1);
    expect(sendMessage).toHaveBeenCalledWith(CAPTURE_PROMPT, []);
  });

  it("renders the starters as one list of three cards", () => {
    const { container } = renderPills();

    const list = screen.getByRole("list");
    const cards = list.querySelectorAll("li > button");
    expect(cards).toHaveLength(3);
    // The wrapping pill row is gone; the grid is the only container.
    expect(container.querySelector(".composer__pills")).toBeNull();
  });

  it("gives every card an icon, a title, an artifact preview, and one action", () => {
    const { container } = renderPills();

    for (const card of container.querySelectorAll(".starter")) {
      expect(card.querySelector(".starter__icon")).not.toBeNull();
      expect(card.querySelector(".starter__title")?.textContent).toBeTruthy();
      expect(card.querySelector(".starter__artifact")?.textContent).toBeTruthy();
      expect(card.querySelectorAll(".starter__action")).toHaveLength(1);
    }
  });

  it("describes each card with its artifact preview", () => {
    const { container } = renderPills();

    for (const card of container.querySelectorAll(".starter")) {
      const artifact = card.querySelector(".starter__artifact");
      expect(artifact).not.toBeNull();
      expect(card.getAttribute("aria-describedby")).toBe(artifact?.id);
    }
  });

  it("never nests an interactive element inside a card", () => {
    const { container } = renderPills();

    for (const card of container.querySelectorAll(".starter")) {
      expect(card.querySelector("button, a[href]")).toBeNull();
    }
  });

  it("names the artifact's shape without a count, price, or date", () => {
    const { container } = renderPills();

    for (const artifact of container.querySelectorAll(".starter__artifact")) {
      // Drop the decorative "Produces" label, then hold the copy to a shape.
      const text = (artifact.textContent ?? "").replace(/^Produces/, "");
      expect(text).not.toMatch(/\d/);
      expect(text).not.toMatch(/[€$£]|%|price|per (month|year|seat)/i);
    }
  });

  it("keeps the panel opener out of the card list", () => {
    const { container } = renderPills();

    const aside = screen.getByRole("button", { name: "Opportunity landscape" });
    expect(aside.classList.contains("composer__starter-aside")).toBe(true);
    expect(container.querySelector(".starter-grid")?.contains(aside)).toBe(false);
    // No card carries the landscape label.
    for (const card of container.querySelectorAll(".starter")) {
      expect(card.textContent).not.toContain("Opportunity landscape");
    }
  });

  it("marks the first card as recommended exactly once", () => {
    const { container } = renderPills();

    expect(container.querySelectorAll(".starter__recommended")).toHaveLength(1);
    expect(container.querySelector(".starter__recommended")?.closest(".starter")).toBe(
      container.querySelector(".starter"),
    );
  });
});
