import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BootFailurePage } from "./BootFailurePage";
import type { StudioError } from "../types";

const STORE_CORRUPT: StudioError = {
  code: "store_corrupt",
  message:
    "Your database failed its integrity check: /home/me/.agentic-odi/odi.db. " +
    "Last backup: 06:14 (odi-20260102T061400Z.db). The file has been left untouched " +
    "— restore a backup before opening it again.",
  detail: "database disk image is malformed",
  suggestion:
    "Restore odi-20260102T061400Z.db over odi.db, then restart. " +
    "The damaged file has not been changed.",
  retryable: false,
};

describe("BootFailurePage", () => {
  it("names the file and the backup from the sidecar's message", () => {
    render(<BootFailurePage error={STORE_CORRUPT} onRecheck={() => undefined} />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Your database failed its integrity check: /home/me/.agentic-odi/odi.db",
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Last backup: 06:14");
  });

  it("shows the suggestion and keeps the check detail behind a disclosure", () => {
    render(<BootFailurePage error={STORE_CORRUPT} onRecheck={() => undefined} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Restore odi-20260102T061400Z.db");
    expect(screen.getByText("database disk image is malformed")).toBeInTheDocument();
  });

  it("offers a recheck that never offers to delete the file", () => {
    const onRecheck = vi.fn();
    render(<BootFailurePage error={STORE_CORRUPT} onRecheck={onRecheck} />);

    fireEvent.click(screen.getByRole("button", { name: "Recheck the database" }));

    expect(onRecheck).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/delete/i)).not.toBeInTheDocument();
  });

  it("still renders when the sidecar sent no suggestion", () => {
    render(
      <BootFailurePage
        error={{ ...STORE_CORRUPT, suggestion: null, detail: null }}
        onRecheck={() => undefined}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("failed its integrity check");
  });
});
