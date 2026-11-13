import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { capabilityCatalogue, type Capability } from "../../bff/capabilities/registry";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";
import { CapabilityPopover, describeCapabilities } from "./CapabilityPopover";

const stubContext = (overrides: Record<string, unknown> = {}) => ({
  capabilities: [] as Capability[],
  openSetup: vi.fn(),
  ...overrides,
});

function renderPopover(overrides: Record<string, unknown> = {}) {
  vi.mocked(useStudio).mockReturnValue(stubContext(overrides) as never);
  return render(<CapabilityPopover />);
}

function probed(
  id: string,
  status: "available" | "unavailable",
  reason?: string,
): Capability {
  const entry = capabilityCatalogue.find((capability) => capability.id === id)!;
  return { ...entry, status, ...(reason ? { reason } : {}) };
}

beforeEach(() => {
  vi.mocked(useStudio).mockReturnValue(stubContext() as never);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("describeCapabilities", () => {
  it("gives every capability the registry models a word", () => {
    // A new capability with no wording fails here rather than rendering blank.
    const rows = describeCapabilities([]);
    expect(rows.map((row) => row.id)).toEqual(capabilityCatalogue.map((entry) => entry.id));
    for (const row of rows) {
      expect(row.word.length).toBeGreaterThan(0);
    }
  });

  it("says a probed capability works here", () => {
    const rows = describeCapabilities([probed("local-data", "available")]);
    const row = rows.find((entry) => entry.id === "local-data");
    expect(row?.state).toBe("works");
    expect(row?.word).toBe("Works here");
  });

  it("says a missing sidecar capability needs the local service", () => {
    const rows = describeCapabilities([probed("sidecar-mcp", "unavailable")]);
    expect(rows.find((entry) => entry.id === "sidecar-mcp")?.word).toBe(
      "Needs the local service",
    );
  });

  it("says a missing model capability needs a model", () => {
    const rows = describeCapabilities([probed("endpoint-model", "unavailable")]);
    expect(rows.find((entry) => entry.id === "endpoint-model")?.word).toBe("Needs a model");
  });

  it("never claims a capability works when no probe has reached it", () => {
    const rows = describeCapabilities([]);
    for (const row of rows) {
      expect(row.state).toBe("unknown");
      expect(row.word).toBe("Unknown — not checked yet");
      expect(row.word).not.toContain("Works");
    }
  });

  it("carries a probe's own reason in preference to the description", () => {
    const rows = describeCapabilities([
      probed("endpoint-model", "unavailable", "This endpoint is on your machine."),
    ]);
    expect(rows.find((entry) => entry.id === "endpoint-model")?.reason).toBe(
      "This endpoint is on your machine.",
    );
  });
});

describe("CapabilityPopover", () => {
  it("labels the control in words, with no badge and no red dot", () => {
    const { container } = renderPopover();
    const trigger = screen.getByRole("button", { name: "What works here" });
    expect(trigger).toHaveAttribute("aria-haspopup", "dialog");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(container.querySelector(".bell-badge")).toBeNull();
  });

  it("opens a titled dialog from the keyboard and closes on Escape", () => {
    renderPopover();
    const trigger = screen.getByRole("button", { name: "What works here" });

    // Enter and Space both activate a button; the dialog appears once.
    fireEvent.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "What works here" });
    expect(within(dialog).getByText("What works here")).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("says Unknown for a capability no probe has reached, never Works", () => {
    renderPopover();
    fireEvent.click(screen.getByRole("button", { name: "What works here" }));

    expect(screen.queryByText("Works here")).not.toBeInTheDocument();
    expect(screen.getAllByText("Unknown — not checked yet")).toHaveLength(
      capabilityCatalogue.length,
    );
  });

  it("says what needs the service and offers to start it", () => {
    const openSetup = vi.fn();
    renderPopover({
      openSetup,
      capabilities: [
        probed("local-data", "available"),
        probed("sidecar-connectors", "unavailable"),
      ],
    });
    fireEvent.click(screen.getByRole("button", { name: "What works here" }));

    expect(screen.getByText("Needs the local service")).toBeInTheDocument();
    expect(screen.queryByText("Works here")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Start the local service" }));
    expect(openSetup).toHaveBeenCalledOnce();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("offers no service action when nothing needs the service", () => {
    renderPopover({
      capabilities: capabilityCatalogue.map((entry) => probed(entry.id, "available")),
    });
    fireEvent.click(screen.getByRole("button", { name: "What works here" }));

    expect(screen.queryByRole("button", { name: "Start the local service" })).toBeNull();
  });
});
