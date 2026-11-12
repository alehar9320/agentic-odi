import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ActivityCentre } from "./ActivityCentre";
import type { StoredNotice } from "../../bff/store/types";

// Mock useStudio
vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";

type StudioMock = {
  store: object;
  loadNotices: () => Promise<StoredNotice[]>;
  saveNotices: (notices: StoredNotice[]) => Promise<void>;
};

function mockStudioContext(overrides: Partial<StudioMock> = {}) {
  vi.mocked(useStudio).mockReturnValue({
    store: {},
    loadNotices: vi.fn().mockResolvedValue([]),
    saveNotices: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  } as ReturnType<typeof useStudio>);
}

const mockNotices: StoredNotice[] = [
  {
    id: "notice-1",
    severity: "info",
    title: "Info notice",
    detail: "Something informative happened",
    context: "context info",
    at: new Date(Date.now() - 10000).toISOString(),
    dismissed: false,
  },
  {
    id: "notice-2",
    severity: "warning",
    title: "Warning notice",
    detail: "Something concerning happened",
    context: null,
    at: new Date(Date.now() - 20000).toISOString(),
    dismissed: false,
  },
  {
    id: "notice-3",
    severity: "success",
    title: "Success notice",
    detail: "Something good happened",
    context: "context success",
    at: new Date(Date.now() - 30000).toISOString(),
    dismissed: true,
  },
];

describe("ActivityCentre", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when not open", () => {
    mockStudioContext();
    const { queryByRole } = render(
      <ActivityCentre isOpen={false} onClose={vi.fn()} />,
    );
    expect(queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders empty state when no notices", async () => {
    mockStudioContext({
      loadNotices: vi.fn().mockResolvedValue([]),
    });

    const { getByRole } = render(<ActivityCentre isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(getByRole("dialog")).toBeInTheDocument();
    });

    expect(screen.getByText("Nothing has happened yet in this workspace.")).toBeInTheDocument();
  });

  it("renders notices grouped by day", async () => {
    mockStudioContext({
      loadNotices: vi.fn().mockResolvedValue(mockNotices),
    });

    const { getByRole } = render(<ActivityCentre isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(getByRole("dialog")).toBeInTheDocument();
    });

    expect(screen.getByText("Activity centre")).toBeInTheDocument();
    expect(screen.getByText("Info notice")).toBeInTheDocument();
    expect(screen.getByText("Warning notice")).toBeInTheDocument();
    expect(screen.getByText("Success notice")).toBeInTheDocument();
    expect(screen.getByText("Something informative happened")).toBeInTheDocument();
    expect(screen.getByText("Something concerning happened")).toBeInTheDocument();
    expect(screen.getByText("Something good happened")).toBeInTheDocument();
    expect(screen.getByText("context info")).toBeInTheDocument();
    expect(screen.getByText("context success")).toBeInTheDocument();
  });

  it("shows severity labels", async () => {
    mockStudioContext({
      loadNotices: vi.fn().mockResolvedValue(mockNotices),
    });

    render(<ActivityCentre isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("Info")).toBeInTheDocument();
      expect(screen.getByText("Warning")).toBeInTheDocument();
      expect(screen.getByText("Success")).toBeInTheDocument();
    });
  });

  it("shows Mark all read button when there are unread notices", async () => {
    mockStudioContext({
      loadNotices: vi.fn().mockResolvedValue(mockNotices),
    });

    render(<ActivityCentre isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Mark all read" })).toBeInTheDocument();
    });
  });

  it("does not show Mark all read button when all notices are dismissed", async () => {
    const allDismissed = mockNotices.map((n) => ({ ...n, dismissed: true }));
    mockStudioContext({
      loadNotices: vi.fn().mockResolvedValue(allDismissed),
    });

    render(<ActivityCentre isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Mark all read" })).not.toBeInTheDocument();
    });
  });

  it("dismisses a notice when dismiss button is clicked", async () => {
    const saveNotices = vi.fn().mockResolvedValue(undefined);
    mockStudioContext({
      loadNotices: vi.fn().mockResolvedValue(mockNotices),
      saveNotices,
    });

    render(<ActivityCentre isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: 'Dismiss "Info notice"' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: 'Dismiss "Info notice"' }));

    await waitFor(() => {
      expect(saveNotices).toHaveBeenCalled();
      const savedNotices = vi.mocked(saveNotices).mock.calls[0][0];
      expect(savedNotices.find((n) => n.id === "notice-1")?.dismissed).toBe(true);
    });
  });

  it("marks all as read when Mark all read is clicked", async () => {
    const saveNotices = vi.fn().mockResolvedValue(undefined);
    mockStudioContext({
      loadNotices: vi.fn().mockResolvedValue(mockNotices),
      saveNotices,
    });

    render(<ActivityCentre isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Mark all read" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Mark all read" }));

    await waitFor(() => {
      expect(saveNotices).toHaveBeenCalled();
      const savedNotices = vi.mocked(saveNotices).mock.calls[0][0];
      expect(savedNotices.every((n) => n.dismissed)).toBe(true);
    });
  });

  it("closes on Escape key", async () => {
    const onClose = vi.fn();
    mockStudioContext({
      loadNotices: vi.fn().mockResolvedValue(mockNotices),
    });

    render(<ActivityCentre isOpen={true} onClose={onClose} />);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const dialog = screen.getByRole("dialog");
    fireEvent.keyDown(dialog, { key: "Escape" });

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("has close button", async () => {
    mockStudioContext({
      loadNotices: vi.fn().mockResolvedValue(mockNotices),
    });

    render(<ActivityCentre isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Close activity centre" })).toBeInTheDocument();
    });
  });
});