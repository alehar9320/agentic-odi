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

  it("keeps the starters disabled while a reply streams", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext({ streaming: true }));

    renderPills();

    expect(screen.getByRole("button", { name: FIRST_STARTER })).toBeDisabled();
  });
});
