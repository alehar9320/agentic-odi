import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { StudioConfig } from "../../types";
import { ModelSection } from "./sections/ModelSection";

const settings: StudioConfig = {
  base_url: "http://localhost:8001/v1",
  api_key: "local",
  model_name: "local-tools-model",
  mcp_url: "http://localhost:8000/mcp",
};

function renderSection(overrides: Partial<Parameters<typeof ModelSection>[0]> = {}) {
  const props = {
    settings,
    saveSettings: vi.fn(),
    models: [] as string[],
    modelsLoading: false,
    modelsMessage: null as string | null,
    refreshModels: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
  return { ...render(<ModelSection {...props} />), props };
}

describe("ModelSection", () => {
  it("offers the endpoint's models as suggestions and keeps typing free", () => {
    renderSection({ models: ["local-tools-model", "qwen3-8b"] });

    const model = screen.getByLabelText(/^model/i);
    expect(model).toHaveAttribute("list", "studio-model-options");
    expect(document.getElementById("studio-model-options")?.children).toHaveLength(2);
    expect(screen.getByText(/2 models available/i)).toBeInTheDocument();
  });

  it("says why there is no catalog instead of pretending the list is empty", () => {
    const refreshModels = vi.fn().mockResolvedValue(undefined);
    renderSection({ models: [], modelsMessage: "connection_error: connection refused", refreshModels });

    expect(screen.getByLabelText(/^model/i)).not.toHaveAttribute("list");
    expect(screen.getByText(/connection refused/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /find models/i }));
    expect(refreshModels).toHaveBeenCalled();
  });

  it("toggles API key visibility", () => {
    renderSection();

    const input = screen.getByLabelText("API key") as HTMLInputElement;
    expect(input.type).toBe("password");

    fireEvent.click(screen.getByRole("button", { name: /show api key/i }));
    expect(input.type).toBe("text");

    fireEvent.click(screen.getByRole("button", { name: /hide api key/i }));
    expect(input.type).toBe("password");
  });

  it("saves a changed model when the field is left and says so once", () => {
    const { props } = renderSection();

    const model = screen.getByLabelText(/^model/i);
    fireEvent.change(model, { target: { value: "qwen3-8b" } });
    expect(props.saveSettings).not.toHaveBeenCalled();

    fireEvent.blur(model);
    expect(props.saveSettings).toHaveBeenCalledTimes(1);
    expect(props.saveSettings).toHaveBeenCalledWith(
      expect.objectContaining({ model_name: "qwen3-8b" }),
    );
    expect(screen.getByText("Saved")).toBeInTheDocument();
  });

  it("refuses an invalid URL beside the field and keeps the old value in use", () => {
    const { props } = renderSection();

    const baseUrl = screen.getByLabelText("Base URL");
    fireEvent.change(baseUrl, { target: { value: "not a url" } });
    fireEvent.blur(baseUrl);

    expect(props.saveSettings).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/not saved/i);
    expect(screen.queryByText("Saved")).toBeNull();
  });
});
