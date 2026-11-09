import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DataSection } from "./sections/DataSection";

const getStorageFacts = vi.hoisted(() => vi.fn());
const exportWorkspace = vi.hoisted(() => vi.fn());
const importWorkspace = vi.hoisted(() => vi.fn());
const pushToast = vi.hoisted(() => vi.fn());

vi.mock("../../api/studioApi", () => ({
  getStorageFacts,
  exportWorkspace,
  importWorkspace,
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => ({ pushToast }),
  pushToast,
}));

vi.mock("../../lib/export", () => ({
  downloadMarkdown: vi.fn(),
  exportFilename: vi.fn(() => "agentic-odi-workspace-2026-01-01.json"),
}));

function renderSection(overrides: Partial<Parameters<typeof DataSection>[0]> = {}) {
  const props = {
    sidecarReachable: true,
    ...overrides,
  };
  return { ...render(<DataSection {...props} />), props };
}

describe("DataSection (storage)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows loading state while fetching facts", () => {
    getStorageFacts.mockImplementation(() => new Promise(() => {}));
    renderSection();

    expect(screen.getByText(/loading storage facts/i)).toBeInTheDocument();
  });

  it("renders storage facts when loaded", async () => {
    getStorageFacts.mockResolvedValue({
      kind: "sidecar",
      path: "agentic-odi-studio",
      bytes: 1234567,
      lastWrittenAt: "2026-01-15T10:30:00.000Z",
    });

    renderSection();

    await waitFor(() => {
      expect(screen.getByText(/on this device \(sidecar\)/i)).toBeInTheDocument();
      expect(screen.getByText(/agentic-odi-studio/i)).toBeInTheDocument();
      expect(screen.getByText(/1.2 mb/i)).toBeInTheDocument();
    });
  });

  it("renders browser store when sidecar is not reachable", async () => {
    getStorageFacts.mockResolvedValue({
      kind: "browser",
      bytes: 512000,
      lastWrittenAt: "2026-01-15T10:30:00.000Z",
    });

    renderSection({ sidecarReachable: false });

    await waitFor(() => {
      expect(screen.getByText(/in this browser/i)).toBeInTheDocument();
      expect(screen.getByText(/500.0 kb/i)).toBeInTheDocument();
    });
  });

  it("shows unknown values as em dash", async () => {
    getStorageFacts.mockResolvedValue({
      kind: "browser",
      bytes: undefined,
      lastWrittenAt: undefined,
    });

    renderSection();

    await waitFor(() => {
      expect(screen.getByText(/in this browser/i)).toBeInTheDocument();
      expect(screen.getByText(/—/)).toBeInTheDocument();
    });
  });

  it("lists what the export does not contain", async () => {
    getStorageFacts.mockResolvedValue({
      kind: "sidecar",
      path: "agentic-odi-studio",
      bytes: 1000,
      lastWrittenAt: "2026-01-15T10:30:00.000Z",
    });

    renderSection();

    await waitFor(() => {
      expect(screen.getByText(/does not contain uploads, connector tokens, or provider api keys/i)).toBeInTheDocument();
    });
  });

  it("exports workspace and shows success toast", async () => {
    getStorageFacts.mockResolvedValue({
      kind: "sidecar",
      path: "agentic-odi-studio",
      bytes: 1000,
      lastWrittenAt: "2026-01-15T10:30:00.000Z",
    });
    exportWorkspace.mockResolvedValue('{"jobs":[]}');

    renderSection();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /export workspace/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /export workspace/i }));

    await waitFor(() => {
      expect(exportWorkspace).toHaveBeenCalled();
      expect(pushToast).toHaveBeenCalledWith("success", expect.stringContaining("Exported"));
    });
  });

  it("imports workspace and reloads on success", async () => {
    getStorageFacts.mockResolvedValue({
      kind: "sidecar",
      path: "agentic-odi-studio",
      bytes: 1000,
      lastWrittenAt: "2026-01-15T10:30:00.000Z",
    });
    importWorkspace.mockResolvedValue(undefined);

    renderSection();

    await waitFor(() => {
      expect(screen.getByLabelText(/import workspace/i)).toBeInTheDocument();
    });

    const fileInput = screen.getByLabelText(/import workspace/i) as HTMLInputElement;
    const file = new File(['{"jobs":[]}'], "workspace.json", { type: "application/json" });
    Object.defineProperty(fileInput, "files", {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(importWorkspace).toHaveBeenCalledWith('{"jobs":[]}');
      expect(pushToast).toHaveBeenCalledWith("success", "Imported workspace — reloading canvas");
    });
  });

  it("shows error state when facts fail to load", async () => {
    getStorageFacts.mockRejectedValue(new Error("Sidecar unreachable"));

    renderSection();

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/sidecar unreachable/i);
    });
  });

  it("disables buttons while loading", () => {
    getStorageFacts.mockImplementation(() => new Promise(() => {}));
    renderSection();

    expect(screen.getByRole("button", { name: /export workspace/i })).toBeDisabled();
    expect(screen.getByLabelText(/import workspace/i)).toBeDisabled();
  });

  it("disables buttons when error occurs", async () => {
    getStorageFacts.mockRejectedValue(new Error("Failed"));

    renderSection();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /export workspace/i })).toBeDisabled();
      expect(screen.getByLabelText(/import workspace/i)).toBeDisabled();
    });
  });

  it("does nothing when import is cancelled", async () => {
    getStorageFacts.mockResolvedValue({
      kind: "sidecar",
      path: "agentic-odi-studio",
      bytes: 1000,
      lastWrittenAt: "2026-01-15T10:30:00.000Z",
    });

    renderSection();

    await waitFor(() => {
      expect(screen.getByLabelText(/import workspace/i)).toBeInTheDocument();
    });

    const fileInput = screen.getByLabelText(/import workspace/i) as HTMLInputElement;
    Object.defineProperty(fileInput, "files", {
      value: [],
      writable: false,
    });

    fireEvent.change(fileInput);

    expect(importWorkspace).not.toHaveBeenCalled();
  });
});