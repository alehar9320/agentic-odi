import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BannerStack } from "./BannerStack";
import { BannerProvider } from "./BannerProvider";
import type { Banner } from "./types";

function banner(overrides: Partial<Banner> = {}): Banner {
  return {
    id: "sidecar-down",
    kind: "sidecar-down",
    title: "The studio sidecar isn't running.",
    body: "The assistant is paused.",
    severity: "critical",
    life: "persistent",
    dock: "top",
    durationMs: 0,
    actions: [],
    dismissible: true,
    raisedAt: 1,
    ...overrides,
  };
}

describe("BannerStack", () => {
  it("renders the title and the body of a banner", () => {
    render(<BannerStack banners={[banner()]} overflow={0} onDismiss={() => {}} onIntent={() => {}} />);
    expect(screen.getByText("The studio sidecar isn't running.")).toBeInTheDocument();
    expect(screen.getByText("The assistant is paused.")).toBeInTheDocument();
  });

  it("announces a critical banner as an alert and a quiet one as a status", () => {
    const { unmount } = render(
      <BannerStack banners={[banner()]} overflow={0} onDismiss={() => {}} onIntent={() => {}} />,
    );
    // Scope to the banner itself: Radix also renders its own `role="status"`
    // announcer, so a document-wide query would match more than one node.
    expect(screen.getByText("The studio sidecar isn't running.").closest("[role]")).toHaveAttribute(
      "role",
      "alert",
    );
    unmount();

    render(
      <BannerStack
        banners={[banner({ id: "info", severity: "info", title: "Heads up.", body: "" })]}
        overflow={0}
        onDismiss={() => {}}
        onIntent={() => {}}
      />,
    );
    expect(screen.getByText("Heads up.").closest("[role]")).toHaveAttribute("role", "status");
  });

  it("sends an action's intent when it is clicked", () => {
    const onIntent = vi.fn();
    render(
      <BannerStack
        banners={[
          banner({
            actions: [{ label: "Recheck", intent: "Recheck the sidecar.", tone: "ghost" }],
          }),
        ]}
        overflow={0}
        onDismiss={() => {}}
        onIntent={onIntent}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Recheck" }));
    expect(onIntent).toHaveBeenCalledWith("Recheck the sidecar.");
  });

  it("calls onDismiss with the banner's id", () => {
    const onDismiss = vi.fn();
    render(
      <BannerStack banners={[banner()]} overflow={0} onDismiss={onDismiss} onIntent={() => {}} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /dismiss/i }));
    expect(onDismiss).toHaveBeenCalledWith("sidecar-down");
  });

  it("keeps each banner in the dock it names", () => {
    render(
      <BannerStack
        banners={[
          banner(),
          banner({ id: "toast-1", kind: "success", title: "Saved.", body: "", dock: "corner" }),
        ]}
        overflow={0}
        onDismiss={() => {}}
        onIntent={() => {}}
      />,
    );
    expect(screen.getByText("The studio sidecar isn't running.").closest("ol")).toHaveClass(
      "banner-dock--top",
    );
    expect(screen.getByText("Saved.").closest("ol")).toHaveClass("banner-dock--corner");
  });

  it("shows how many banners are hidden behind the cap", () => {
    render(
      <BannerStack
        banners={[banner(), banner({ id: "model-offline", kind: "model-offline" })]}
        overflow={2}
        onDismiss={() => {}}
        onIntent={() => {}}
      />,
    );
    expect(screen.getByText(/2 more/i)).toBeInTheDocument();
  });

  it("hides the dismiss control for a banner that is not dismissible", () => {
    render(
      <BannerStack
        banners={[banner({ dismissible: false })]}
        overflow={0}
        onDismiss={() => {}}
        onIntent={() => {}}
      />,
    );
    expect(screen.queryByRole("button", { name: /dismiss/i })).not.toBeInTheDocument();
  });
});

describe("BannerProvider with BannerStack", () => {
  it("renders what the store holds", () => {
    function Harness() {
      return <BannerStack />;
    }
    render(
      <BannerProvider>
        <Harness />
      </BannerProvider>,
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
