import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChangelogModal } from "./ChangelogModal";
import * as studioApi from "../api/studioApi";

vi.mock("../api/studioApi", () => ({
  fetchChangelog: vi.fn(),
}));

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
