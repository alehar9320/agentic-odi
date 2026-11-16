import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ScorePopover } from "./ScorePopover";

const harness = vi.hoisted(() => ({
  state: {
    updateOutcome: vi.fn(),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

beforeEach(() => {
  harness.state.updateOutcome.mockReset();
  harness.state.updateOutcome.mockImplementation(serverRecompute);
});

// A consistent record: 8.6 + max(8.6 − 7.2, 0) = 10.0, right on the line.
const outcome = {
  id: "O-101",
  statement: "Minimize the time to sync secrets when a deployment starts.",
  importance: 8.6,
  satisfaction: 7.2,
  opportunity_score: 10,
};

/** What the sidecar does with a scored write: it recomputes from the inputs. */
function serverRecompute(
  _id: string,
  payload: { importance?: number; satisfaction?: number },
) {
  const importance = payload.importance ?? 0;
  const satisfaction = payload.satisfaction ?? 0;
  return Promise.resolve({
    ...outcome,
    importance,
    satisfaction,
    opportunity_score: importance + Math.max(importance - satisfaction, 0),
  });
}

describe("ScorePopover arithmetic", () => {
  it("shows the arithmetic and crosses the line as satisfaction moves", () => {
    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    // 8.6 + 1.4 = 10.0 — on the line, not over it.
    expect(screen.getByTestId("score-formula")).toHaveTextContent("8.6 + 1.4 = 10.0");
    expect(screen.getByText(/Served — 10 or below/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Satisfaction slider"), {
      target: { value: "7.1" },
    });

    // A tenth lower: 8.6 + 1.5 = 10.1, now underserved.
    expect(screen.getByTestId("score-formula")).toHaveTextContent("8.6 + 1.5 = 10.1");
    expect(screen.getByText(/Underserved — above 10/)).toBeInTheDocument();
  });

  it("clamps both inputs to the 1–10 range", () => {
    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Importance"), { target: { value: "11" } });
    expect(screen.getByLabelText("Importance")).toHaveValue(10);

    fireEvent.change(screen.getByLabelText("Satisfaction"), { target: { value: "0" } });
    expect(screen.getByLabelText("Satisfaction")).toHaveValue(1);
  });
});

describe("ScorePopover save", () => {
  it("issues exactly one write carrying both values and shows the server's score", async () => {
    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Importance"), { target: { value: "9" } });
    fireEvent.click(screen.getByRole("button", { name: "Save scores" }));

    await waitFor(() =>
      expect(harness.state.updateOutcome).toHaveBeenCalledWith("O-101", {
        importance: 9,
        satisfaction: 7.2,
      }),
    );
    expect(harness.state.updateOutcome).toHaveBeenCalledTimes(1);
    // The displayed stored score is the response (9 + 1.8 = 10.8), not the prior 10.0.
    // The panel is a portal to document.body, so it is read from there.
    await waitFor(() =>
      expect(document.querySelector(".score-popover__stored b")?.textContent).toBe("10.8"),
    );
  });

  it("keeps the panel open with the prior score and a message when the write is rejected", async () => {
    harness.state.updateOutcome.mockRejectedValueOnce(new Error("Network error"));

    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Importance"), { target: { value: "9.9" } });
    fireEvent.click(screen.getByRole("button", { name: "Save scores" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Network error"));
    // The panel is still here, the typed value is kept, and the stored score is the prior one.
    expect(screen.getByTestId("score-formula")).toBeInTheDocument();
    expect(screen.getByLabelText("Importance")).toHaveValue(9.9);
    expect(screen.getByText("10.0")).toBeInTheDocument();
  });
});

describe("ScorePopover stored-versus-computed mismatch", () => {
  // 8.6 + max(8.6 − 4.9, 0) = 12.3, but the record stores 14.0.
  const mismatched = { ...outcome, importance: 8.6, satisfaction: 4.9, opportunity_score: 14 };

  it("questions a stored score that disagrees, and writes nothing until asked", () => {
    render(<ScorePopover outcome={mismatched} onClose={vi.fn()} />);

    expect(screen.getByText("Stored score differs from its inputs")).toBeInTheDocument();
    // Never repaired on open, on render, or on read.
    expect(harness.state.updateOutcome).not.toHaveBeenCalled();
  });

  it("sends the current inputs when Recompute is pressed", async () => {
    render(<ScorePopover outcome={mismatched} onClose={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Recompute" }));

    await waitFor(() =>
      expect(harness.state.updateOutcome).toHaveBeenCalledWith("O-101", {
        importance: 8.6,
        satisfaction: 4.9,
      }),
    );
    expect(harness.state.updateOutcome).toHaveBeenCalledTimes(1);
  });

  it("stays quiet when the stored score agrees with its inputs", () => {
    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    expect(screen.queryByText("Stored score differs from its inputs")).toBeNull();
  });
});

describe("ScorePopover dismissal", () => {
  it("closes on Escape", async () => {
    const onClose = vi.fn();
    render(<ScorePopover outcome={outcome} onClose={onClose} />);

    fireEvent.keyDown(document.activeElement ?? document.body, { key: "Escape" });

    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});
