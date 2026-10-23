import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChangelogModal } from "./ChangelogModal";
import * as studioApi from "../api/studioApi";

vi.mock("../api/studioApi", () => ({
  fetchChangelog: vi.fn(),
}));

const RELEASES = [
  { version: "0.8.0", date: "2026-10-20", categories: [{ name: "Features", items: ["New"] }] },
  { version: "0.7.0", date: "2026-10-10", categories: [{ name: "Fixes", items: ["Old"] }] },
];

beforeEach(() => {
  window.localStorage.clear();
});

describe("ChangelogModal", () => {
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

  it("badges the releases the reader has not seen yet", async () => {
    window.localStorage.setItem("studio.changelog.seen", JSON.stringify(["0.7.0"]));
    vi.mocked(studioApi.fetchChangelog).mockResolvedValueOnce({ releases: RELEASES });

    render(<ChangelogModal isOpen={true} onClose={vi.fn()} />);

    expect(await screen.findByLabelText("New in 0.8.0")).toBeInTheDocument();
    expect(screen.queryByLabelText("New in 0.7.0")).not.toBeInTheDocument();
  });

  it("remembers what was read so the badge does not come back", async () => {
    vi.mocked(studioApi.fetchChangelog).mockResolvedValue({ releases: RELEASES });
    const onClose = vi.fn();
    const { rerender } = render(<ChangelogModal isOpen={true} onClose={onClose} />);

    expect(await screen.findByLabelText("New in 0.8.0")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /done/i }));
    expect(onClose).toHaveBeenCalled();

    // The app closes the drawer through `onClose`; mirror that here.
    rerender(<ChangelogModal isOpen={false} onClose={onClose} />);

    await waitFor(() => {
      expect(JSON.parse(window.localStorage.getItem("studio.changelog.seen") ?? "[]")).toEqual(
        expect.arrayContaining(["0.8.0", "0.7.0"]),
      );
    });

    rerender(<ChangelogModal isOpen={true} onClose={onClose} />);

    expect(await screen.findByText("v0.8.0")).toBeInTheDocument();
    expect(screen.queryByLabelText("New in 0.8.0")).not.toBeInTheDocument();
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
