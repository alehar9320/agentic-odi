import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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

    const closeBtn = screen.getByLabelText("Close dialog");
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("exposes an accessible name through the dialog role", async () => {
    vi.mocked(studioApi.fetchChangelog).mockResolvedValueOnce({ releases: [] });

    render(<ChangelogModal isOpen={true} onClose={vi.fn()} />);

    expect(
      screen.getByRole("dialog", { name: "Release Notes & Progress" }),
    ).toBeInTheDocument();
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

  it("says so plainly when there are no release notes to show", async () => {
    vi.mocked(studioApi.fetchChangelog).mockResolvedValueOnce({ releases: [] });

    render(<ChangelogModal isOpen={true} onClose={vi.fn()} />);

    expect(
      await screen.findByText(/release notes come from the studio service/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("article")).toBeNull();
  });

  it("moves focus into the dialog when it opens", async () => {
    vi.mocked(studioApi.fetchChangelog).mockResolvedValueOnce({ releases: [] });

    render(<ChangelogModal isOpen={true} onClose={vi.fn()} />);

    const close = screen.getByRole("button", { name: "Close dialog" });
    await waitFor(() => expect(close).toHaveFocus());
  });

  it("closes on Escape key press", async () => {
    vi.mocked(studioApi.fetchChangelog).mockResolvedValueOnce({
      releases: [],
    });

    const onClose = vi.fn();
    render(<ChangelogModal isOpen={true} onClose={onClose} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Close dialog" })).toHaveFocus(),
    );

    // The primitive dismisses on a keydown it receives from the document,
    // which is where a real Escape lands before it bubbles to the window.
    fireEvent.keyDown(document, { key: "Escape" });

    expect(onClose).toHaveBeenCalled();
  });

  it("takes the page behind the dialog out of reach while it is open", async () => {
    vi.mocked(studioApi.fetchChangelog).mockResolvedValue({ releases: [] });

    const { unmount } = render(
      <div className="studio-app">
        <ChangelogModal isOpen={true} onClose={vi.fn()} />
      </div>,
    );

    const shell = document.querySelector(".studio-app");
    // The primitive hides the page behind from assistive technology (and marks
    // it inert where the browser supports it) by hiding every sibling of the
    // portaled content, so an ancestor of the shell carries the attribute.
    await waitFor(() =>
      expect(shell?.closest('[aria-hidden="true"]')).not.toBeNull(),
    );
    const hidden = shell?.closest('[aria-hidden="true"]') as HTMLElement | null;
    expect(hidden?.contains(screen.getByRole("dialog"))).toBe(false);

    unmount();
    expect(shell?.closest('[aria-hidden="true"]')).toBeNull();
  });

  it("announces how many releases were marked read without shifting the footer", async () => {
    vi.mocked(studioApi.fetchChangelog).mockResolvedValue(TWO_RELEASES);

    render(<ChangelogModal isOpen={true} onClose={vi.fn()} />);
    await screen.findByText("v0.9.0");

    fireEvent.click(screen.getByRole("button", { name: "Mark all read" }));

    expect(screen.getByText("2 releases marked read")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark all read" })).toBeDisabled();
  });

  it("makes each release date an interrogable <time>", async () => {
    vi.mocked(studioApi.fetchChangelog).mockResolvedValue(TWO_RELEASES);

    render(<ChangelogModal isOpen={true} onClose={vi.fn()} />);

    const date = await screen.findByText("2026-10-22", { selector: "time" });
    expect(date).toHaveAttribute("dateTime", "2026-10-22");
    expect(date.getAttribute("title")).toBeTruthy();
  });
});
