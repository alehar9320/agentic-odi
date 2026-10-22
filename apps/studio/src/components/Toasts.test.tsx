import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Toasts } from "./Toasts";

const harness = vi.hoisted(() => ({
  state: {
    toasts: [] as unknown[],
    dismissToast: vi.fn(),
  },
}));

vi.mock("../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

describe("Toasts", () => {
  it("announces an error toast as an alert", () => {
    harness.state.toasts = [{ id: 1, kind: "error", message: "The MCP server is unreachable." }];

    render(<Toasts />);

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("The MCP server is unreachable.");
  });

  it("announces a success toast as a status", () => {
    harness.state.toasts = [{ id: 2, kind: "success", message: "Step added to Job Map!" }];

    render(<Toasts />);

    expect(screen.getByRole("status").textContent).toContain("Step added to Job Map!");
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
