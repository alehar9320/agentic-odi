import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const studio = vi.hoisted(() => ({
  settings: {
    base_url: "http://localhost:8001/v1",
    api_key: "local",
    model_name: "local-tools-model",
    mcp_url: "http://localhost:8000/mcp",
  },
  sidecarReachable: true as boolean | null,
  dismissedSidecarNotice: false,
  checkConnections: vi.fn(),
  recheckConnections: vi.fn(),
  openPanel: vi.fn(),
  openSetup: vi.fn(),
  dismissSidecarNotice: vi.fn(),
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => studio,
}));

import { SidecarNotice } from "./SidecarNotice";

describe("SidecarNotice", () => {
  it("renders nothing while the sidecar is reachable", () => {
    studio.sidecarReachable = true;
    const { container } = render(<SidecarNotice />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing while reachability is still unknown", () => {
    studio.sidecarReachable = null;
    const { container } = render(<SidecarNotice />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a subtle strip when the sidecar is down", () => {
    studio.sidecarReachable = false;
    render(<SidecarNotice />);

    expect(screen.getByText(/sidecar isn't running/i)).toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("offers to recheck and to open setup", () => {
    studio.sidecarReachable = false;
    render(<SidecarNotice />);

    fireEvent.click(screen.getByRole("button", { name: /recheck/i }));
    expect(studio.recheckConnections).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: /start the sidecar/i }));
    expect(studio.openSetup).toHaveBeenCalledTimes(1);
  });

  it("can be dismissed", () => {
    studio.sidecarReachable = false;
    render(<SidecarNotice />);

    fireEvent.click(screen.getByRole("button", { name: /dismiss/i }));
    expect(studio.dismissSidecarNotice).toHaveBeenCalledTimes(1);
  });
});
