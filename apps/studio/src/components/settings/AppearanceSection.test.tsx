import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppearanceSection } from "./sections/AppearanceSection";
import { useStudio } from "../../state/StudioContext";
import type { StudioContextValue } from "../../state/StudioContext";
import type { StudioConfig } from "../../types";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

const SETTINGS: StudioConfig = {
  base_url: "http://localhost:8001/v1",
  api_key: "local",
  model_name: "local-tools-model",
  mcp_url: "http://localhost:8000/mcp",
};

/**
 * `painted` is the palette the provider resolved, which is what the caption may
 * name; the control itself must never read it, or *Follow the system* would look
 * like it had been abandoned whenever the operating system disagreed.
 */
function renderSection({
  settings = SETTINGS,
  painted = "dark",
  saveSettings = vi.fn(),
}: {
  settings?: StudioConfig;
  painted?: "light" | "dark";
  saveSettings?: (config: StudioConfig) => void;
} = {}) {
  vi.mocked(useStudio).mockReturnValue({ theme: painted } as unknown as StudioContextValue);
  return render(<AppearanceSection settings={settings} saveSettings={saveSettings} />);
}

describe("AppearanceSection", () => {
  it("offers the three choices, in one group named for the reader to find", () => {
    renderSection();

    const group = screen.getByRole("radiogroup", { name: /theme/i });
    const radios = screen.getAllByRole("radio");

    expect(radios).toHaveLength(3);
    expect(
      radios.map((radio) => radio.closest("label")?.textContent),
    ).toEqual(["Light", "Dark", "Follow the system"]);
    // One shared input name is what makes arrow keys walk the group.
    expect(new Set(radios.map((radio) => radio.getAttribute("name")))).toEqual(
      new Set(["studio-theme"]),
    );
    expect(group).toContainElement(radios[0]);
  });

  it("puts the dot on Follow the system when no choice was ever stored", () => {
    renderSection();

    // An arrow-key group with nothing checked gives the keyboard no landing
    // point, and every first-time reader sits in that state.
    expect(screen.getByRole("radio", { name: /follow the system/i })).toBeChecked();
    expect(screen.getByRole("radio", { name: /^light$/i })).not.toBeChecked();
  });

  it("shows the stored choice even when the operating system disagrees", () => {
    renderSection({ settings: { ...SETTINGS, theme: "light" }, painted: "dark" });

    expect(screen.getByRole("radio", { name: /^light$/i })).toBeChecked();
    expect(screen.getByRole("radio", { name: /^dark$/i })).not.toBeChecked();
  });

  it("writes the chosen value and leaves every other setting alone", () => {
    const saveSettings = vi.fn();
    renderSection({ saveSettings });

    fireEvent.click(screen.getByRole("radio", { name: /^dark$/i }));

    expect(saveSettings).toHaveBeenCalledTimes(1);
    expect(saveSettings).toHaveBeenCalledWith({ ...SETTINGS, theme: "dark" });
  });

  it("moves the dot when the stored choice moves", () => {
    // The control reads the settings it is handed, so a choice that persistence
    // refused to keep cannot leave a radio lying about what is stored.
    const { rerender } = renderSection();

    fireEvent.click(screen.getByRole("radio", { name: /^light$/i }));
    rerender(
      <AppearanceSection
        settings={{ ...SETTINGS, theme: "light" }}
        saveSettings={vi.fn()}
      />,
    );

    expect(screen.getByRole("radio", { name: /^light$/i })).toBeChecked();
  });
});
