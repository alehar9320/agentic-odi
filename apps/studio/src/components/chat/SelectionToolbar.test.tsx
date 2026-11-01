import { act, fireEvent, render, screen } from "@testing-library/react";
import { ThreadPrimitive, useAuiState } from "@assistant-ui/react";
import { describe, expect, it, vi } from "vitest";

import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import { SelectionToolbar } from "./SelectionToolbar";

const harness = vi.hoisted(() => ({
  state: {
    messages: [] as unknown[],
    streaming: false,
    canvas: null,
    sendMessage: vi.fn(async () => {}),
    regenerateFrom: vi.fn(async () => {}),
    editFrom: vi.fn(async () => {}),
    switchBranch: vi.fn(),
    respondToApproval: vi.fn(async () => {}),
    stopStreaming: vi.fn(),
  },
}));

vi.mock("../../state/StudioContext", () => ({ useStudio: () => harness.state }));

function QuoteProbe() {
  const quote = useAuiState((state) => state.composer.quote);
  return <output data-testid="quote">{quote?.text ?? ""}</output>;
}

async function selectProse() {
  // jsdom has a Range but no layout; assistant-ui only needs a rectangle to
  // position the toolbar, so give it a plausible one.
  const rect = new DOMRect(0, 0, 100, 20);
  Object.defineProperty(Range.prototype, "getBoundingClientRect", {
    value: () => rect,
    configurable: true,
  });
  Object.defineProperty(Range.prototype, "getClientRects", {
    value: () => [rect],
    configurable: true,
  });

  const paragraph = screen.getByText(/approval step/);
  const range = document.createRange();
  range.selectNodeContents(paragraph);
  const selection = window.getSelection();
  selection?.removeAllRanges();
  selection?.addRange(range);

  act(() => {
    document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
  });
  await act(async () => {
    await new Promise((resolve) => requestAnimationFrame(() => resolve(null)));
  });
}

describe("SelectionToolbar", () => {
  it("quotes the selected passage into the composer", async () => {
    render(
      <StudioRuntimeProvider>
        <ThreadPrimitive.Root>
          <p data-message-id="a-1">The approval step is the only thing that hurts.</p>
          <SelectionToolbar />
          <QuoteProbe />
        </ThreadPrimitive.Root>
      </StudioRuntimeProvider>,
    );

    await selectProse();

    fireEvent.click(await screen.findByRole("button", { name: "Quote" }));

    expect(screen.getByTestId("quote").textContent).toContain("approval step");
  });

  it("does not appear until something is selected", () => {
    render(
      <StudioRuntimeProvider>
        <ThreadPrimitive.Root>
          <p data-message-id="a-1">The approval step is the only thing that hurts.</p>
          <SelectionToolbar />
        </ThreadPrimitive.Root>
      </StudioRuntimeProvider>,
    );

    expect(screen.queryByRole("button", { name: "Quote" })).toBeNull();
  });
});
