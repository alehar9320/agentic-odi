import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CanvasData } from "../../types";
import { RecordsPanel } from "./RecordsPanel";

let mockCanvas: CanvasData | null = null;

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => ({ canvas: mockCanvas }),
}));

function canvas(overrides: Partial<CanvasData> = {}): CanvasData {
  return { jobs: [], steps: [], outcomes: [], source: "local", ...overrides };
}

describe("RecordsPanel export", () => {
  let createObjectURL: ReturnType<typeof vi.fn>;
  let revokeObjectURL: ReturnType<typeof vi.fn>;
  let click: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    createObjectURL = vi.fn(() => "blob:records");
    revokeObjectURL = vi.fn();
    Object.defineProperty(window, "URL", {
      value: { ...window.URL, createObjectURL, revokeObjectURL },
      configurable: true,
    });
    click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("refuses to export a store that holds nothing", () => {
    mockCanvas = canvas();
    render(<RecordsPanel />);
    expect(screen.getByRole("button", { name: /export csv/i })).toBeDisabled();
  });

  // The file a person opens in a spreadsheet, asserted from the bytes the button hands over.
  it("downloads the lens as CSV named records.csv", async () => {
    mockCanvas = canvas({
      jobs: [{ id: "J-1", name: "Activation" }],
      outcomes: [{ id: "O-1", job_id: "J-1", importance: 8, satisfaction: 4 }],
    });
    render(<RecordsPanel />);

    fireEvent.click(screen.getByRole("button", { name: /export csv/i }));

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob.type).toBe("text/csv;charset=utf-8");
    expect(await blob.text()).toBe(
      "Name,Description,Id\r\nJobs\r\nActivation,—,J-1\r\nDesired outcomes\r\n—,8,4,unscored,J-1,O-1",
    );
    const anchor = click.mock.contexts[0] as HTMLAnchorElement;
    expect(anchor.download).toBe("records.csv");
    expect(anchor.href).toBe("blob:records");
    await waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith("blob:records"));
  });
});
