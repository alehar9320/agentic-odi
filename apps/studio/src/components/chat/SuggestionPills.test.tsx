import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NOTES_PROMPT, StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import type { StudioContextValue } from "../../state/StudioContext";
import { SuggestionPills } from "./composerParts";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";

const FIRST_STARTER = "Turn 40 interview notes into one bet";

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
    expect(sendMessage).toHaveBeenCalledWith(NOTES_PROMPT);
  });

  it("enqueues a starter clicked while a reply streams", () => {
    const sendMessage = vi.fn(async () => {});
    vi.mocked(useStudio).mockReturnValue(stubContext({ streaming: true, sendMessage }));

    renderPills();
    fireEvent.click(screen.getByRole("button", { name: FIRST_STARTER }));

    // The pill stays live mid-answer (#410): the context puts the follow-up
    // in the queue lane instead of the click being swallowed by a disabled
    // button.
    expect(sendMessage).toHaveBeenCalledTimes(1);
    expect(sendMessage).toHaveBeenCalledWith(NOTES_PROMPT);
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
