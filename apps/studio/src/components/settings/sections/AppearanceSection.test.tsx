import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { StudioConfig } from "../../../types";
import { AppearanceSection } from "./AppearanceSection";

/**
 * The palette control (ALH-201).
 *
 * Nothing in the app used to write `settings.theme`: three places read it, and
 * the only way to change the palette was to edit `localStorage` by hand. These
 * tests hold the control to what it promises — three named choices, the stored
 * one checked, and a click that persists.
 */
const SETTINGS: StudioConfig = {
  base_url: "http://127.0.0.1:8100",
  api_key: "local",
  model_name: "local-tools-model",
  mcp_url: "http://127.0.0.1:8000/mcp",
};

function renderSection(settings: StudioConfig = SETTINGS) {
  const saveSettings = vi.fn();
  render(<AppearanceSection settings={settings} saveSettings={saveSettings} />);
  return { saveSettings, group: screen.getByRole("radiogroup", { name: "Theme" }) };
}

describe("the appearance section", () => {
  it("offers Light, Dark, and System as one labelled radio group", () => {
    const { group } = renderSection();

    for (const name of ["Light", "Dark", "System"]) {
      expect(within(group).getByRole("radio", { name })).toBeInTheDocument();
    }
    // The group says what its third option means, because "System" alone does
    // not tell a reader that the other two pin the palette.
    expect(within(group).getByText(/follows your operating system/i)).toBeInTheDocument();
  });

  it("selects System when the person has pinned no palette", () => {
    const { group } = renderSection();

    expect(within(group).getByRole("radio", { name: "System" })).toBeChecked();
    expect(within(group).getByRole("radio", { name: "Light" })).not.toBeChecked();
  });

  it("selects the pinned palette whatever the operating system says", () => {
    const { group } = renderSection({ ...SETTINGS, theme: "light" });

    expect(within(group).getByRole("radio", { name: "Light" })).toBeChecked();
    expect(within(group).getByRole("radio", { name: "System" })).not.toBeChecked();
  });

  it("saves the palette the person picks without touching the rest of the configuration", () => {
    const { group, saveSettings } = renderSection();

    fireEvent.click(within(group).getByRole("radio", { name: "Dark" }));

    expect(saveSettings).toHaveBeenCalledWith({ ...SETTINGS, theme: "dark" });
  });

  it("stores System as a choice, so a reload keeps following the operating system", () => {
    const { group, saveSettings } = renderSection({ ...SETTINGS, theme: "dark" });

    fireEvent.click(within(group).getByRole("radio", { name: "System" }));

    // Clearing the key would also follow the OS, but it could not be told apart
    // from a person who never chose — and the choice is what survives a reload.
    expect(saveSettings).toHaveBeenCalledWith({ ...SETTINGS, theme: "system" });
  });

  it("is one tab stop a keyboard can move through", () => {
    const { group } = renderSection();

    const radios = within(group).getAllByRole("radio");
    // One shared name is what makes arrow keys move the selection in a real
    // browser; jsdom implements no such group behaviour, so this is the
    // assertion that the shipped markup earns the keyboard promise.
    expect(radios).toHaveLength(3);
    for (const radio of radios) {
      expect(radio).toHaveAttribute("name", "theme");
    }
  });
});
