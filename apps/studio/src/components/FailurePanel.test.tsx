import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FailurePanel } from "./FailurePanel";

function stubClipboard(writeText = vi.fn(async () => {})) {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText },
  });
  return writeText;
}

afterEach(() => {
  vi.useRealTimers();
});

describe("FailurePanel copy details (#693)", () => {
  it("copies the message, the detail, and the request id as plain text", async () => {
    const writeText = stubClipboard();
    vi.useFakeTimers();

    render(
      <FailurePanel
        error={{
          code: "model_unreachable",
          message: "The model did not answer.",
          detail: "connect ECONNREFUSED 127.0.0.1:8001",
          request_id: "req-42",
          retryable: true,
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Copy details" }));
    await act(async () => {});

    expect(writeText).toHaveBeenCalledWith(
      "The model did not answer.\nconnect ECONNREFUSED 127.0.0.1:8001\nRequest id: req-42",
    );
    expect(screen.getByRole("button", { name: "Copy details" })).toHaveTextContent("Copied");

    act(() => {
      vi.advanceTimersByTime(1600);
    });

    expect(screen.getByRole("button", { name: "Copy details" })).toHaveTextContent("Copy details");
  });

  it("offers no copy control when the message is all there is", () => {
    render(
      <FailurePanel error={{ code: "internal", message: "Something went wrong.", retryable: false }} />,
    );

    expect(screen.queryByRole("button", { name: "Copy details" })).toBeNull();
  });

  it("says so when the clipboard refuses instead of claiming a copy", async () => {
    stubClipboard(vi.fn(async () => Promise.reject(new Error("denied"))));

    render(
      <FailurePanel
        error={{ code: "internal", message: "Failed.", request_id: "req-9", retryable: false }}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Copy details" }));
    });

    expect(screen.getByRole("button", { name: "Copy details" })).toHaveTextContent("Copy failed");
  });
});
