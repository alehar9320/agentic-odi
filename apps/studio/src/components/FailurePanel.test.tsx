import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { StudioError } from "../types";
import { FailurePanel } from "./FailurePanel";

const baseError: StudioError = {
  code: "sidecar_unreachable",
  message: "The Living Studio sidecar is not answering.",
  retryable: true,
};

describe("FailurePanel copy details", () => {
  let writeText: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeText = vi.fn(async () => {});
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
  });

  it("copies message, detail, and request id as plain text and confirms in place", async () => {
    render(
      <FailurePanel
        error={{
          ...baseError,
          detail: "ECONNREFUSED 127.0.0.1:8100",
          request_id: "req-42",
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Copy details" }));

    expect(writeText).toHaveBeenCalledWith(
      "The Living Studio sidecar is not answering.\nECONNREFUSED 127.0.0.1:8100\nRequest id: req-42",
    );
    expect(await screen.findByRole("button", { name: "Details copied" })).toBeInTheDocument();
  });

  it("omits the control when there is nothing more than the message", () => {
    render(<FailurePanel error={baseError} />);
    expect(screen.queryByRole("button", { name: "Copy details" })).toBeNull();
  });

  it("includes only the parts the error actually carries", async () => {
    render(<FailurePanel error={{ ...baseError, request_id: "req-9" }} />);

    fireEvent.click(screen.getByRole("button", { name: "Copy details" }));

    expect(writeText).toHaveBeenCalledWith(
      "The Living Studio sidecar is not answering.\nRequest id: req-9",
    );
  });
});
