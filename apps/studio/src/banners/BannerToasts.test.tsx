import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BannerProvider } from "./BannerProvider";
import { BannerStack } from "./BannerStack";
import { BannerToasts } from "./BannerToasts";

const studio = vi.hoisted(() => ({
  toasts: [] as { id: number; kind: string; message: string }[],
  dismissToast: vi.fn(),
}));

vi.mock("../state/StudioContext", () => ({
  useStudio: () => studio,
}));

function shell() {
  return render(
    <BannerProvider>
      <BannerToasts />
      <BannerStack />
    </BannerProvider>,
  );
}

describe("BannerToasts", () => {
  it("turns an error toast into a critical banner", () => {
    studio.toasts = [{ id: 1, kind: "error", message: "The MCP server is unreachable." }];
    shell();
    const banner = screen.getByText("The MCP server is unreachable.").closest(".banner");
    expect(banner).toHaveClass("banner--critical");
  });

  it("turns a success toast into a success banner", () => {
    studio.toasts = [{ id: 2, kind: "success", message: "Step added to Job Map!" }];
    shell();
    const banner = screen.getByText("Step added to Job Map!").closest(".banner");
    expect(banner).toHaveClass("banner--success");
  });

  it("turns an info toast into an info banner", () => {
    studio.toasts = [{ id: 3, kind: "info", message: "Background activity: sync finished." }];
    shell();
    const banner = screen.getByText("Background activity: sync finished.").closest(".banner");
    expect(banner).toHaveClass("banner--info");
  });

  it("does not raise a second banner for a toast it already showed", () => {
    studio.toasts = [{ id: 4, kind: "success", message: "Saved." }];
    const { rerender } = shell();
    rerender(
      <BannerProvider>
        <BannerToasts />
        <BannerStack />
      </BannerProvider>,
    );
    expect(screen.getAllByText("Saved.")).toHaveLength(1);
  });

  it("clears the banner when the toast is gone", () => {
    studio.toasts = [{ id: 5, kind: "success", message: "Gone soon." }];
    const { rerender } = shell();
    expect(screen.getByText("Gone soon.")).toBeInTheDocument();

    studio.toasts = [];
    rerender(
      <BannerProvider>
        <BannerToasts />
        <BannerStack />
      </BannerProvider>,
    );
    expect(screen.queryByText("Gone soon.")).not.toBeInTheDocument();
  });

  it("shows a toast that arrives later", () => {
    studio.toasts = [];
    const { rerender } = shell();
    act(() => {
      studio.toasts = [{ id: 6, kind: "error", message: "Late failure." }];
    });
    rerender(
      <BannerProvider>
        <BannerToasts />
        <BannerStack />
      </BannerProvider>,
    );
    expect(screen.getByText("Late failure.")).toBeInTheDocument();
  });
});
