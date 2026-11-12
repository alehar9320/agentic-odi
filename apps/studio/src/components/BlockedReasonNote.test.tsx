import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BlockedReasonNote } from "./BlockedReasonNote";

const openSetup = vi.fn();
const openPanel = vi.fn();
const recheckConnections = vi.fn().mockResolvedValue(undefined);

vi.mock("../state/StudioContext", () => ({
  useStudio: () => ({ openSetup, openPanel, recheckConnections }),
}));

describe("BlockedReasonNote", () => {
  it("says why in place and offers one real next action", () => {
    render(<BlockedReasonNote capability="sidecar-connectors" id="install-blocked" />);

    const note = document.getElementById("install-blocked");
    expect(note).not.toBeNull();
    expect(note?.textContent).toContain("needs the local service");

    fireEvent.click(screen.getByRole("button", { name: "Start the local service" }));
    expect(openSetup).toHaveBeenCalledTimes(1);
    expect(openPanel).not.toHaveBeenCalled();
  });

  it("sends a missing model to the settings panel", () => {
    openSetup.mockClear();
    render(<BlockedReasonNote capability="endpoint-model" />);

    fireEvent.click(screen.getByRole("button", { name: "Add a model" }));
    expect(openPanel).toHaveBeenCalledWith("settings");
  });
});
