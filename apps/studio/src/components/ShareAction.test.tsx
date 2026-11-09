import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CanvasState } from "../types";
import { ShareAction } from "./ShareAction";

const createShareLink = vi.hoisted(() => vi.fn());

vi.mock("../api/studioApi", () => ({
  createShareLink,
}));

const harness = vi.hoisted(() => ({
  state: {
    canvasState: { kind: "ready", data: null } as unknown as CanvasState,
    sidecarReachable: true as boolean | null,
    settings: { mcp_url: "http://localhost:8000/mcp" },
  },
}));

vi.mock("../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

const READY_CANVAS = {
  kind: "ready",
  data: {
    jobs: [{ id: "JOB-1", name: "Deploy Service" }],
    steps: [],
    outcomes: [
      { id: "O-101", statement: "Minimize time spent syncing secrets", opportunity_score: 16 },
    ],
    source: "local" as const,
  },
} as unknown as CanvasState;

afterEach(() => {
  vi.unstubAllGlobals();
  createShareLink.mockReset();
});

beforeEach(() => {
  harness.state.canvasState = READY_CANVAS;
  harness.state.sidecarReachable = true;
});

describe("ShareAction", () => {
  it("offers a share control and mints a landscape link for the chosen duration", async () => {
    createShareLink.mockResolvedValue({
      id: "share-1",
      token: "odi_sh_abc",
      url: "http://127.0.0.1:8100/s/odi_sh_abc",
      expires_at: new Date(Date.now() + 7 * 86400_000).toISOString(),
    });

    render(<ShareAction />);
    fireEvent.click(screen.getByRole("button", { name: /share/i }));

    fireEvent.change(screen.getByLabelText(/expires/i), { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: /create link/i }));

    await waitFor(() =>
      expect(createShareLink).toHaveBeenCalledWith({ kind: "landscape", expires_in_days: 30 }),
    );
    expect(await screen.findByLabelText(/shareable link/i)).toBeInTheDocument();
  });

  it("disables sharing and says why when the sidecar is unreachable", () => {
    harness.state.sidecarReachable = false;

    render(<ShareAction />);

    expect(screen.getByRole("button", { name: /share/i })).toBeDisabled();
    expect(screen.getByText(/sidecar/i)).toBeInTheDocument();
  });

  it("disables sharing when the canvas holds nothing", () => {
    harness.state.canvasState = {
      kind: "empty",
      data: { jobs: [], steps: [], outcomes: [], source: "local" },
    } as unknown as CanvasState;

    render(<ShareAction />);

    expect(screen.getByRole("button", { name: /share/i })).toBeDisabled();
    expect(screen.getByText(/nothing to share yet/i)).toBeInTheDocument();
  });
});
