import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChangelogModal } from "./ChangelogModal";
import * as studioApi from "../api/studioApi";
import { CHANGELOG_READ_KEY } from "../lib/changelogRead";

vi.mock("../api/studioApi", () => ({
  fetchChangelog: vi.fn(),
}));

const TWO_RELEASES = {
  releases: [
    {
      version: "0.9.0",
      date: "2026-10-22",
      categories: [{ name: "Features", items: ["Newest feature"] }],
    },
    {
      version: "0.8.0",
      date: "2026-10-20",
      categories: [{ name: "Fixes", items: ["Older fix"] }],
    },
  ],
};

describe("ChangelogModal", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.mocked(studioApi.fetchChangelog).mockReset();
  });
  it("does not render when isOpen is false", () => {
    const { container } = render(
      <ChangelogModal isOpen={false} onClose={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders changelog content when open and fetch succeeds", async () => {
    vi.mocked(studioApi.fetchChangelog).mockResolvedValueOnce({
      releases: [
        {
          version: "0.8.0",
          date: "2026-10-20",
          categories: [
            {
              name: "Features",
              items: ["Added super powers feature"],
            },
          ],
        },
      ],
    });

    const onClose = vi.fn();
    render(<ChangelogModal isOpen={true} onClose={onClose} />);

    expect(screen.getByText("Release Notes & Progress")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("v0.8.0")).toBeInTheDocument();
      expect(screen.getByText("2026-10-20")).toBeInTheDocument();
      expect(screen.getByText("Added super powers feature")).toBeInTheDocument();
    });

    const closeBtn = screen.getByLabelText("Close changelog modal");
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("clears the unread badge and keeps it cleared after a remount", async () => {
    vi.mocked(studioApi.fetchChangelog).mockResolvedValue(TWO_RELEASES);
    const { unmount } = render(<ChangelogModal isOpen={true} onClose={vi.fn()} />);

    expect(await screen.findByRole("status")).toHaveTextContent("2 new");
    expect(screen.getAllByText("New")).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "Mark all read" }));

    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.queryByText("New")).toBeNull();
    expect(screen.getByRole("button", { name: "Mark all read" })).toBeDisabled();

    unmount();
    render(<ChangelogModal isOpen={true} onClose={vi.fn()} />);

    await screen.findByText("v0.9.0");
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.queryByText("New")).toBeNull();
    expect(screen.getByRole("button", { name: "Mark all read" })).toBeDisabled();
  });

  it("counts only the releases that were not acknowledged before", async () => {
    window.localStorage.setItem(CHANGELOG_READ_KEY, JSON.stringify(["0.8.0"]));
    vi.mocked(studioApi.fetchChangelog).mockResolvedValue(TWO_RELEASES);

    render(<ChangelogModal isOpen={true} onClose={vi.fn()} />);

    expect(await screen.findByRole("status")).toHaveTextContent("1 new");
    expect(screen.getAllByText("New")).toHaveLength(1);
  });

  it("says why there is nothing to show when the local backend has no notes", async () => {
    vi.mocked(studioApi.fetchChangelog).mockResolvedValue({ releases: [] });

    render(<ChangelogModal isOpen={true} onClose={vi.fn()} />);

    expect(
      await screen.findByText(/release notes come from the studio service/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/v0\./)).toBeNull();
  });

  it("closes on Escape key press", async () => {
    vi.mocked(studioApi.fetchChangelog).mockResolvedValueOnce({
      releases: [],
    });

    const onClose = vi.fn();
    await act(async () => {
      render(<ChangelogModal isOpen={true} onClose={onClose} />);
    });

    await act(async () => {
      fireEvent.keyDown(window, { key: "Escape" });
    });

    expect(onClose).toHaveBeenCalled();
  });
});
