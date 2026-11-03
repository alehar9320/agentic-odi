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
});
