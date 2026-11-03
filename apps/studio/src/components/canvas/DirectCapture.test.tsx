import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StudioApiError } from "../../api/studioApi";
import { DirectCapture } from "./DirectCapture";

const harness = vi.hoisted(() => ({
  state: {
    canvas: { jobs: [{ id: "JOB-1", name: "Ship a service" }], steps: [], outcomes: [] } as unknown,
    addOutcome: vi.fn<(payload: unknown) => Promise<void>>(),
    createJob: vi.fn<(payload: unknown) => Promise<string | null>>(),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

describe("DirectCapture", () => {
  it("explains what to enter and what each rating means", () => {
    render(<DirectCapture />);

    expect(screen.getByLabelText("Job")).toHaveAccessibleDescription(
      /what the customer is trying to get done/i,
    );
    expect(screen.getByLabelText(/desired outcome/i)).toHaveAccessibleDescription(
      /direction.*unit of measure.*object.*context/i,
    );
    expect(screen.getByText(/Minimize the time it takes to …/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Importance/)).toHaveAccessibleDescription(
      /how much this outcome matters/i,
    );
    expect(screen.getByLabelText(/^Current satisfaction/)).toHaveAccessibleDescription(
      /how well it is met today/i,
    );
  });

  it("keeps both ratings on a 1 to 10 scale in 0.1 steps", () => {
    render(<DirectCapture />);

    for (const rating of [screen.getByLabelText(/^Importance/), screen.getByLabelText(/^Current satisfaction/)]) {
      expect(rating).toHaveAttribute("type", "range");
      expect(rating).toHaveAttribute("min", "1");
      expect(rating).toHaveAttribute("max", "10");
      expect(rating).toHaveAttribute("step", "0.1");
    }
  });

  it("says the displayed score is a preview, not verified customer evidence", () => {
    render(<DirectCapture />);

    expect(screen.getByText(/Opportunity/)).toHaveAccessibleDescription(
      /preview.*not customer evidence.*not independently verified/i,
    );
  });

  it("records the typed outcome with the chosen scores unchanged", async () => {
    harness.state.addOutcome = vi.fn(async () => undefined);

    render(<DirectCapture />);
    fireEvent.change(screen.getByLabelText(/desired outcome/i), {
      target: { value: "Minimize the time it takes to rotate deployment secrets" },
    });
    fireEvent.change(screen.getByLabelText(/^Importance/), { target: { value: "9.2" } });
    fireEvent.change(screen.getByLabelText(/^Current satisfaction/), { target: { value: "2.4" } });
    fireEvent.click(screen.getByRole("button", { name: /record outcome/i }));

    await waitFor(() => {
      expect(harness.state.addOutcome).toHaveBeenCalledWith({
        job_id: "JOB-1",
        statement: "Minimize the time it takes to rotate deployment secrets",
        importance: 9.2,
        satisfaction: 2.4,
      });
    });
  });

  it("shows the server's suggestion next to the form and keeps what was typed", async () => {
    harness.state.addOutcome = vi.fn(async () => {
      throw new StudioApiError({
        code: "out_of_range",
        message: "importance must be between 1 and 10",
        suggestion: "Use a value between 1.0 and 10.0.",
        retryable: false,
      });
    });

    render(<DirectCapture />);

    fireEvent.change(screen.getByLabelText(/desired outcome/i), {
      target: { value: "Minimize the time it takes to ship" },
    });
    fireEvent.click(screen.getByRole("button", { name: /record outcome/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("Use a value between 1.0 and 10.0.");
    });
    expect(screen.getByLabelText(/desired outcome/i)).toHaveValue(
      "Minimize the time it takes to ship",
    );
  });

  it("clears the failure once the outcome is recorded", async () => {
    harness.state.addOutcome = vi.fn(async () => {
      throw new StudioApiError({
        code: "out_of_range",
        message: "importance must be between 1 and 10",
        retryable: false,
      });
    });

    render(<DirectCapture />);
    fireEvent.change(screen.getByLabelText(/desired outcome/i), {
      target: { value: "Minimize the time it takes to ship" },
    });
    fireEvent.click(screen.getByRole("button", { name: /record outcome/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());

    harness.state.addOutcome = vi.fn(async () => undefined);
    fireEvent.click(screen.getByRole("button", { name: /record outcome/i }));

    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });
});

describe("DirectCapture score preview", () => {
  // The capture form is where a score is born, and it showed two decimals while
  // the card it produces shows one — "13.50" here, "13.5" there.
  it("shows the computed opportunity score to one decimal", () => {
    const { container } = render(<DirectCapture />);

    expect(container.querySelector(".score-preview b")?.textContent).toBe("13.5");
  });
});
