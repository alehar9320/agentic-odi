import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CapabilityPopover } from "./CapabilityPopover";
import type { Capability } from "../../bff/capabilities/registry";

function capability(
  id: Capability["id"],
  status: Capability["status"],
  reason?: string,
): Capability {
  return {
    id,
    label: id,
    description: `${id} on this device.`,
    status,
    ...(reason ? { reason } : {}),
  };
}

const LOCAL: Capability[] = [
  capability("local-data", "available"),
  capability("local-memory", "available"),
  capability("deterministic-assistant", "available"),
];

describe("CapabilityPopover", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders nothing while closed", () => {
    const { container } = render(
      <CapabilityPopover
        capabilities={LOCAL}
        checkedAt={null}
        isOpen={false}
        onClose={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("lists every capability with its word", () => {
    render(
      <CapabilityPopover
        capabilities={LOCAL}
        checkedAt="2026-11-11T00:00:00.000Z"
        isOpen
        onClose={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(screen.getByRole("dialog", { name: "What works here" })).toBeInTheDocument();
    for (const id of ["local-data", "local-memory", "deterministic-assistant"]) {
      expect(screen.getByText(id)).toBeInTheDocument();
      expect(screen.getAllByText("Works here")).toHaveLength(3);
    }
  });

  it("says Unknown — not checked yet for an absent probe, never Works", () => {
    render(
      <CapabilityPopover
        capabilities={[capability("sidecar-llm", "unavailable", "The sidecar did not answer.")]}
        checkedAt={null}
        isOpen
        onClose={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(screen.getByText("Unknown — not checked yet")).toBeInTheDocument();
    expect(screen.queryByText("Works here")).toBeNull();
    expect(screen.getByText("The sidecar did not answer.")).toBeInTheDocument();
  });

  it("says the local service is needed for a sidecar capability", () => {
    render(
      <CapabilityPopover
        capabilities={[capability("sidecar-mcp", "available")]}
        checkedAt={null}
        isOpen
        onClose={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(screen.getByText("Needs the local service")).toBeInTheDocument();
  });

  it("says a model is needed for model capabilities", () => {
    render(
      <CapabilityPopover
        capabilities={[capability("endpoint-model", "available")]}
        checkedAt={null}
        isOpen
        onClose={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(screen.getByText("Needs a model")).toBeInTheDocument();
  });

  it("says nothing has been checked yet when the probe list is empty", () => {
    render(
      <CapabilityPopover
        capabilities={[]}
        checkedAt={null}
        isOpen
        onClose={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(screen.getByText(/nothing has been checked yet/i)).toBeInTheDocument();
  });

  it("closes on Escape and returns focus to the trigger", () => {
    const onClose = vi.fn();
    render(
      <CapabilityPopover
        capabilities={LOCAL}
        checkedAt={null}
        isOpen
        onClose={onClose}
        onOpenSettings={vi.fn()}
      />,
    );

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("offers Start the local service when a sidecar probe failed", () => {
    render(
      <CapabilityPopover
        capabilities={[capability("sidecar-mcp", "unavailable")]}
        checkedAt={null}
        isOpen
        onClose={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Start the local service" })).toBeInTheDocument();
  });

  it("offers Recheck when the sidecar is running", () => {
    render(
      <CapabilityPopover
        capabilities={[capability("sidecar-mcp", "available")]}
        checkedAt={null}
        isOpen
        onClose={vi.fn()}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Recheck" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start the local service" })).toBeNull();
  });

  it("opens Settings from the footer and closes the popover", () => {
    const onOpenSettings = vi.fn();
    const onClose = vi.fn();
    render(
      <CapabilityPopover
        capabilities={LOCAL}
        checkedAt={null}
        isOpen
        onClose={onClose}
        onOpenSettings={onOpenSettings}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open Settings" }));
    expect(onOpenSettings).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
  });
});