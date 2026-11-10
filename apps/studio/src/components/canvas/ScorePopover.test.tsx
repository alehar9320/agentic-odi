import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ScorePopover } from "./ScorePopover";

const harness = vi.hoisted(() => ({
  state: {
    ask: vi.fn(),
    deleteOutcome: vi.fn(),
    updateOutcome: vi.fn().mockResolvedValue({ id: "O-101", opportunity_score: 16, importance: 9, satisfaction: 2 }),
    pushToast: vi.fn(),
    canvasState: { kind: "ready", data: { jobs: [], steps: [], outcomes: [], source: "seed" } },
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

const outcome = {
  id: "O-101",
  statement: "Minimize the time to sync secrets when a deployment starts.",
  importance: 5,
  satisfaction: 5,
  opportunity_score: 5,
};

describe("ScorePopover", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders nothing when closed", () => {
    render(<ScorePopover outcome={outcome} isOpen={false} onClose={vi.fn()} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens as a modal dialog with focus inside it", () => {
    render(<ScorePopover outcome={outcome} isOpen={true} onClose={vi.fn()} />);

    expect(screen.getByRole("dialog", { name: "Adjust Assumptions" })).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
  });

  it("shows the current importance and satisfaction values", () => {
    render(<ScorePopover outcome={outcome} isOpen={true} onClose={vi.fn()} />);

    // Number inputs show "5" (the test's toHaveValue coerces to number)
    expect(screen.getByLabelText("Importance value")).toHaveValue(5);
    expect(screen.getByLabelText("Satisfaction value")).toHaveValue(5);
  });

  it("shows live arithmetic for the computed opportunity score", () => {
    render(<ScorePopover outcome={outcome} isOpen={true} onClose={vi.fn()} />);

    expect(screen.getByText(/Opportunity/)).toBeInTheDocument();
    // The formula text is split across multiple elements; verify the key parts exist
    const formulaValue = screen.getByTestId("score-popover-formula-value");
    expect(formulaValue).toHaveTextContent("5.0");
    expect(formulaValue).toHaveTextContent("+ max(");
    expect(formulaValue).toHaveTextContent("− 5.0, 0) = 5.0");
  });

  it("updates the computed score when sliders change", async () => {
    render(<ScorePopover outcome={outcome} isOpen={true} onClose={vi.fn()} />);

    const importanceSlider = screen.getByLabelText("Importance value").closest("label")?.querySelector('input[type="range"]') as HTMLInputElement;
    fireEvent.change(importanceSlider, { target: { value: "8.6" } });

    const satisfactionSlider = screen.getByLabelText("Satisfaction value").closest("label")?.querySelector('input[type="range"]') as HTMLInputElement;
    fireEvent.change(satisfactionSlider, { target: { value: "7.2" } });

    await waitFor(() => {
      expect(screen.getByText("10.0")).toBeInTheDocument();
    });
  });

  it("shows underserved verdict when score crosses threshold", async () => {
    render(<ScorePopover outcome={outcome} isOpen={true} onClose={vi.fn()} />);

    expect(screen.getByText("✓ Served")).toBeInTheDocument();
    expect(screen.queryByText("🔥 Underserved")).not.toBeInTheDocument();

    const importanceSlider = screen.getByLabelText("Importance value").closest("label")?.querySelector('input[type="range"]') as HTMLInputElement;
    fireEvent.change(importanceSlider, { target: { value: "8.6" } });

    const satisfactionSlider = screen.getByLabelText("Satisfaction value").closest("label")?.querySelector('input[type="range"]') as HTMLInputElement;
    fireEvent.change(satisfactionSlider, { target: { value: "7.1" } });

    await waitFor(() => {
      expect(screen.getByText("🔥 Underserved")).toBeInTheDocument();
    });
  });

  it("shows gap to underserved threshold", () => {
    render(<ScorePopover outcome={outcome} isOpen={true} onClose={vi.fn()} />);

    expect(screen.getByText("Gap to underserved threshold (10.0)")).toBeInTheDocument();
    expect(screen.getByText("-5.0")).toBeInTheDocument();
  });

  it("shows mismatch notice when stored score differs from computed", async () => {
    const mismatchedOutcome = { ...outcome, opportunity_score: 14.0 };
    render(<ScorePopover outcome={mismatchedOutcome} isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("Stored score (14.0) differs from its inputs (5.0).")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Recompute" })).toBeInTheDocument();
  });

  it("does not show mismatch when difference is within threshold", () => {
    const closeOutcome = { ...outcome, opportunity_score: 5.03 };
    render(<ScorePopover outcome={closeOutcome} isOpen={true} onClose={vi.fn()} />);

    expect(screen.queryByText(/differs from its inputs/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  it("saves through updateOutcome and closes on success", async () => {
    render(<ScorePopover outcome={outcome} isOpen={true} onClose={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(harness.state.updateOutcome).toHaveBeenCalledWith("O-101", {
        importance: 5,
        satisfaction: 5,
      });
    });
  });

  it("keeps panel open and shows error on save failure", async () => {
    harness.state.updateOutcome.mockRejectedValueOnce(new Error("Network error"));
    render(<ScorePopover outcome={outcome} isOpen={true} onClose={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("closes on Escape key", () => {
    const onClose = vi.fn();
    render(<ScorePopover outcome={outcome} isOpen={true} onClose={onClose} />);

    fireEvent.keyDown(document, { key: "Escape" });

    expect(onClose).toHaveBeenCalled();
  });

  it("closes on scrim click", () => {
    const onClose = vi.fn();
    render(<ScorePopover outcome={outcome} isOpen={true} onClose={onClose} />);

    fireEvent.click(screen.getByLabelText("Close score editor (background)"));

    expect(onClose).toHaveBeenCalled();
  });

  it("closes on close button click", () => {
    const onClose = vi.fn();
    render(<ScorePopover outcome={outcome} isOpen={true} onClose={onClose} />);

    fireEvent.click(screen.getByLabelText("Close score editor (button)"));

    expect(onClose).toHaveBeenCalled();
  });

  it("disables inputs while saving", async () => {
    let resolveSave: (value: unknown) => void;
    const savePromise = new Promise((resolve) => {
      resolveSave = resolve;
    });
    harness.state.updateOutcome.mockReturnValueOnce(savePromise);

    render(<ScorePopover outcome={outcome} isOpen={true} onClose={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
    });
    expect(screen.getByLabelText("Importance value")).toBeDisabled();
    expect(screen.getByLabelText("Satisfaction value")).toBeDisabled();

    resolveSave!({ id: "O-101", opportunity_score: 16, importance: 9, satisfaction: 2 });
  });

  it("sends recompute with current inputs when mismatch exists", async () => {
    const mismatchedOutcome = { ...outcome, opportunity_score: 14.0 };
    render(<ScorePopover outcome={mismatchedOutcome} isOpen={true} onClose={vi.fn()} />);

    const satisfactionSlider = screen.getByLabelText("Satisfaction value").closest("label")?.querySelector('input[type="range"]') as HTMLInputElement;
    fireEvent.change(satisfactionSlider, { target: { value: "4.9" } });

    await waitFor(() => {
      expect(screen.getByText("5.1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Recompute" }));

    await waitFor(() => {
      expect(harness.state.updateOutcome).toHaveBeenCalledWith("O-101", {
        importance: 5,
        satisfaction: 4.9,
      });
    });
  });

  it("shows formula with live values", () => {
    render(<ScorePopover outcome={outcome} isOpen={true} onClose={vi.fn()} />);

    expect(screen.getByText("Opportunity")).toBeInTheDocument();
    // Multiple elements show "5.0"; verify the formula value exists
    const formulaValue = screen.getByTestId("score-popover-formula-value");
    expect(formulaValue).toBeInTheDocument();
    expect(formulaValue).toHaveTextContent("5.0");
  });

  it("number inputs update sliders and vice versa", async () => {
    render(<ScorePopover outcome={outcome} isOpen={true} onClose={vi.fn()} />);

    const importanceNumber = screen.getByLabelText("Importance value");
    fireEvent.change(importanceNumber, { target: { value: "7.5" } });

    await waitFor(() => {
      const importanceSlider = screen.getByLabelText("Importance value").closest("label")?.querySelector('input[type="range"]') as HTMLInputElement;
      expect(importanceSlider.value).toBe("7.5");
    });
  });
});