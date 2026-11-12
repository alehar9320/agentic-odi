import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NoticesProvider, useNoticesActions, useToasts } from "./NoticesContext";

function Harness() {
  const { pushToast } = useNoticesActions();
  const toasts = useToasts();
  return (
    <div>
      <button type="button" onClick={() => pushToast("error", "boom")}>
        fail
      </button>
      <button type="button" onClick={() => pushToast("success", "ok")}>
        succeed
      </button>
      {toasts.map((toast) => (
        <span key={toast.id}>{toast.message}</span>
      ))}
    </div>
  );
}

describe("NoticesContext toast lifetime", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("keeps an error toast until it is dismissed, not for six seconds", () => {
    vi.useFakeTimers();
    render(
      <NoticesProvider>
        <Harness />
      </NoticesProvider>,
    );

    act(() => {
      screen.getByRole("button", { name: "fail" }).click();
    });
    expect(screen.getByText("boom")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.getByText("boom")).toBeInTheDocument();
  });

  it("still expires a success toast on its own", () => {
    vi.useFakeTimers();
    render(
      <NoticesProvider>
        <Harness />
      </NoticesProvider>,
    );

    act(() => {
      screen.getByRole("button", { name: "succeed" }).click();
    });
    expect(screen.getByText("ok")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(6000);
    });
    expect(screen.queryByText("ok")).toBeNull();
  });
});
