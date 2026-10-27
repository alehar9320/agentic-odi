import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ModelPicker } from "./ModelPicker";

const harness = vi.hoisted(() => ({
  state: {
    settings: {
      base_url: "http://llm/v1",
      api_key: "k",
      model_name: "alpha",
      mcp_url: "http://mcp",
    },
    saveSettings: vi.fn(),
    llmHealth: { healthy: true, message: "ok" },
    openPanel: vi.fn(),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

const api = vi.hoisted(() => ({ fetchModels: vi.fn() }));

vi.mock("../../api/studioApi", () => ({
  fetchModels: api.fetchModels,
}));

function trigger() {
  return screen.getByRole("button", { name: /Model: alpha/ });
}

describe("ModelPicker", () => {
  beforeEach(() => {
    api.fetchModels.mockReset();
    harness.state.saveSettings.mockReset();
    harness.state.openPanel.mockReset();
    harness.state.llmHealth = { healthy: true, message: "ok" };
  });

  it("lists what the backend serves and marks the current model", async () => {
    api.fetchModels.mockResolvedValue({ models: ["alpha", "beta"], error: null });
    render(<ModelPicker />);

    fireEvent.click(trigger());

    const alpha = await screen.findByRole("option", { name: /alpha/ });
    expect(alpha.getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("option", { name: /beta/ }).getAttribute("aria-selected")).toBe(
      "false",
    );
  });

  it("saves the chosen model and closes the menu", async () => {
    api.fetchModels.mockResolvedValue({ models: ["alpha", "beta"], error: null });
    render(<ModelPicker />);

    fireEvent.click(trigger());
    fireEvent.click(await screen.findByRole("option", { name: /beta/ }));

    expect(harness.state.saveSettings).toHaveBeenCalledWith(
      expect.objectContaining({ model_name: "beta" }),
    );
    await waitFor(() => expect(screen.queryByRole("listbox")).toBeNull());
  });

  it("moves with the arrow keys and selects with Enter", async () => {
    api.fetchModels.mockResolvedValue({ models: ["alpha", "beta"], error: null });
    render(<ModelPicker />);

    fireEvent.click(trigger());
    await screen.findByRole("option", { name: /beta/ });

    fireEvent.keyDown(document.activeElement as Element, { key: "ArrowDown" });
    fireEvent.keyDown(document.activeElement as Element, { key: "Enter" });

    expect(harness.state.saveSettings).toHaveBeenCalledWith(
      expect.objectContaining({ model_name: "beta" }),
    );
  });

  it("closes on Escape and returns focus to the trigger", async () => {
    api.fetchModels.mockResolvedValue({ models: ["alpha"], error: null });
    render(<ModelPicker />);

    fireEvent.click(trigger());
    const option = await screen.findByRole("option", { name: /alpha/ });

    fireEvent.keyDown(option, { key: "Escape" });

    await waitFor(() => expect(screen.queryByRole("listbox")).toBeNull());
    expect(document.activeElement).toBe(trigger());
  });

  it("keeps the configured model selectable when the backend omits it", async () => {
    api.fetchModels.mockResolvedValue({ models: ["beta"], error: null });
    render(<ModelPicker />);

    fireEvent.click(trigger());

    const alpha = await screen.findByRole("option", { name: /alpha/ });
    expect(alpha.getAttribute("aria-selected")).toBe("true");
  });

  it("explains an unreachable model server and offers Settings", async () => {
    api.fetchModels.mockResolvedValue({
      models: [],
      error: "connection_error: connection refused",
    });
    render(<ModelPicker />);

    fireEvent.click(trigger());

    expect(await screen.findByText(/connection refused/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Model settings" }));
    expect(harness.state.openPanel).toHaveBeenCalledWith("settings");
  });

  it("probes once per backend, not once per open", async () => {
    api.fetchModels.mockResolvedValue({ models: ["alpha", "beta"], error: null });
    render(<ModelPicker />);

    fireEvent.click(trigger());
    await screen.findByRole("option", { name: /beta/ });
    fireEvent.click(trigger());
    fireEvent.click(trigger());

    await waitFor(() => expect(screen.getByRole("listbox")).toBeTruthy());
    expect(api.fetchModels).toHaveBeenCalledTimes(1);
  });
});
