import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ScorePopover } from "./ScorePopover";
import type { CanvasState } from "../../types";

const harness = vi.hoisted(() => ({
  state: {
    updateOutcome: vi.fn().mockResolvedValue(undefined),
    pushToast: vi.fn(),
    canvasState: { kind: "ready", data: { jobs: [], steps: [], outcomes: [], source: "seed" } } as CanvasState,
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

const outcome = {
  id: "O-101",
  statement: "Minimize the time to sync secrets when a deployment starts.",
  importance: 9,
  satisfaction: 2,
  opportunity_score: 16,
};

describe("ScorePopover", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the outcome statement and ID", () => {
    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    expect(screen.getByText("Minimize the time to sync secrets when a deployment starts.")).toBeInTheDocument();
    expect(screen.getByText("O-101")).toBeInTheDocument();
  });

  it("shows initial importance and satisfaction values", () => {
    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    expect(screen.getByLabelText("Importance")).toHaveValue(9);
    expect(screen.getByLabelText("Satisfaction")).toHaveValue(2);
  });

  it("displays live arithmetic formula with computed score", () => {
    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    expect(screen.getByText("9.0")).toBeInTheDocument();
    expect(screen.getByText("16.0")).toBeInTheDocument();
    // The formula gap shows the full arithmetic
    const formula = screen.getByTestId("score-formula");
    expect(formula).toHaveTextContent("9.0+max(9.0 − 2.0, 0) = 7.0=16.0(underserved > 10)");
  });

  it("updates computed score when importance changes", () => {
    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    const importanceSlider = screen.getByRole("slider", { name: /importance/i });
    fireEvent.change(importanceSlider, { target: { value: "8.5" } });

    expect(screen.getByLabelText("Importance")).toHaveValue(8.5);
    const formula = screen.getByTestId("score-formula");
    expect(formula).toHaveTextContent("8.5+max(8.5 − 2.0, 0) = 6.5=15.0(underserved > 10)");
    expect(screen.getByText("15.0")).toBeInTheDocument();
  });

  it("updates computed score when satisfaction changes", () => {
    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    const satisfactionSlider = screen.getByRole("slider", { name: /satisfaction/i });
    fireEvent.change(satisfactionSlider, { target: { value: "3.0" } });

    expect(screen.getByLabelText("Satisfaction")).toHaveValue(3);
    const formula = screen.getByTestId("score-formula");
    expect(formula).toHaveTextContent("9.0+max(9.0 − 3.0, 0) = 6.0=15.0(underserved > 10)");
    expect(screen.getByText("15.0")).toBeInTheDocument();
  });

  it("shows underserved indicator when score > 10", () => {
    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    expect(screen.getByText("(underserved > 10)")).toBeInTheDocument();
  });

  it("hides underserved indicator when score <= 10", () => {
    const servedOutcome = { ...outcome, importance: 5, satisfaction: 5, opportunity_score: 5 };
    render(<ScorePopover outcome={servedOutcome} onClose={vi.fn()} />);

    // The threshold text is always shown in the formula
    const formula = screen.getByTestId("score-formula");
    expect(formula).toHaveTextContent("5.0+max(5.0 − 5.0, 0) = 0.0=5.0(underserved > 10)");
  });

  it("shows mismatch notice when stored score differs from computed", () => {
    const mismatchedOutcome = { ...outcome, opportunity_score: 14.0 };
    render(<ScorePopover outcome={mismatchedOutcome} onClose={vi.fn()} />);

    expect(screen.getByText("⚠ Stored score differs from its inputs")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Recompute" })).toBeInTheDocument();
  });

  it("hides mismatch notice when stored score matches computed", () => {
    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    expect(screen.queryByText("Stored score differs from its inputs")).toBeNull();
  });

  it("calls updateOutcome with both values on save", async () => {
    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    const importanceSlider = screen.getByRole("slider", { name: /importance/i });
    fireEvent.change(importanceSlider, { target: { value: "8.0" } });

    const saveButton = screen.getByRole("button", { name: "Save scores" });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(harness.state.updateOutcome).toHaveBeenCalledWith("O-101", {
        importance: 8,
        satisfaction: 2,
      });
    });
    expect(harness.state.pushToast).toHaveBeenCalledWith("success", "Scores saved");
  });

  it("disables save button when no changes made", () => {
    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    const saveButton = screen.getByRole("button", { name: "Save scores" });
    expect(saveButton).toBeDisabled();
  });

  it("enables save button when changes made", () => {
    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    const importanceSlider = screen.getByRole("slider", { name: /importance/i });
    fireEvent.change(importanceSlider, { target: { value: "8.0" } });

    const saveButton = screen.getByRole("button", { name: "Save scores" });
    expect(saveButton).not.toBeDisabled();
  });

  it("shows server value after successful save", async () => {
    const refreshedOutcome = { ...outcome, opportunity_score: 15.5 };
    harness.state.canvasState = {
      kind: "ready",
      data: { jobs: [], steps: [], outcomes: [refreshedOutcome], source: "seed" },
    };

    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    const importanceSlider = screen.getByRole("slider", { name: /importance/i });
    fireEvent.change(importanceSlider, { target: { value: "8.0" } });

    const saveButton = screen.getByRole("button", { name: "Save scores" });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText(/Server returned:/)).toBeInTheDocument();
    });
  });

  it("shows error message on save failure", async () => {
    harness.state.updateOutcome.mockRejectedValueOnce(new Error("Network error"));

    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    const importanceSlider = screen.getByRole("slider", { name: /importance/i });
    fireEvent.change(importanceSlider, { target: { value: "8.0" } });

    const saveButton = screen.getByRole("button", { name: "Save scores" });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
    expect(harness.state.pushToast).toHaveBeenCalledWith("error", "Could not save scores");
  });

  it("calls updateOutcome on recompute and shows server value", async () => {
    const mismatchedOutcome = { ...outcome, opportunity_score: 14.0 };
    const refreshedOutcome = { ...outcome, opportunity_score: 15.5 };
    harness.state.canvasState = {
      kind: "ready",
      data: { jobs: [], steps: [], outcomes: [refreshedOutcome], source: "seed" },
    };

    render(<ScorePopover outcome={mismatchedOutcome} onClose={vi.fn()} />);

    const recomputeButton = screen.getByRole("button", { name: "Recompute" });
    fireEvent.click(recomputeButton);

    await waitFor(() => {
      expect(harness.state.updateOutcome).toHaveBeenCalledWith("O-101", {
        importance: 9,
        satisfaction: 2,
      });
    });
    expect(screen.getByText(/Server returned:/)).toBeInTheDocument();
  });

  it("closes on Escape key", () => {
    const onClose = vi.fn();
    render(<ScorePopover outcome={outcome} onClose={onClose} />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalled();
  });

  it("closes on scrim click", () => {
    const onClose = vi.fn();
    render(<ScorePopover outcome={outcome} onClose={onClose} />);

    const scrim = screen.getByTestId("score-popover-scrim");
    fireEvent.click(scrim);

    expect(onClose).toHaveBeenCalled();
  });

  it("closes on close button click", () => {
    const onClose = vi.fn();
    render(<ScorePopover outcome={outcome} onClose={onClose} />);

    const closeButton = screen.getByTestId("score-popover-close");
    fireEvent.click(closeButton);

    expect(onClose).toHaveBeenCalled();
  });

  it("enforces min/max bounds on number inputs", () => {
    render(<ScorePopover outcome={outcome} onClose={vi.fn()} />);

    const importanceInput = screen.getByLabelText("Importance");
    fireEvent.change(importanceInput, { target: { value: "11" } });

    // The input should clamp to max (10)
    expect(screen.getByLabelText("Importance")).toHaveValue(10);
  });
});