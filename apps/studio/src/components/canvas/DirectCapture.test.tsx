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
