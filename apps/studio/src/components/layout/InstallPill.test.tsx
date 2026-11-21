import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { InstallController, InstallSnapshot } from "../../install";
import { InstallPill, InstallProvider } from "./InstallPill";

/** A controller double whose snapshot the test controls. */
function stubController(snapshot: InstallSnapshot, prompt = vi.fn(async () => "accepted" as const)) {
  return {
    getSnapshot: () => snapshot,
    subscribe: () => () => {},
    prompt,
    dismiss: vi.fn(),
    dispose: vi.fn(),
  } satisfies InstallController;
}

function renderPill(controller: InstallController) {
  return render(
    <InstallProvider controller={controller}>
      <InstallPill />
    </InstallProvider>,
  );
}

describe("InstallPill", () => {
  it("is absent when the browser has no install prompt", () => {
    renderPill(stubController({ canInstall: false, installed: false }));

    expect(screen.queryByRole("button", { name: /install/i })).toBeNull();
  });

  it("is absent when the app is already installed", () => {
    renderPill(stubController({ canInstall: false, installed: true }));

    expect(screen.queryByRole("button", { name: /install/i })).toBeNull();
  });

  it("offers install when the browser has a prompt", () => {
    renderPill(stubController({ canInstall: true, installed: false }));

    expect(
      screen.getByRole("button", { name: "Install the Studio as an app" }),
    ).toBeInTheDocument();
  });

  it("asks the browser to prompt only when the person clicks", () => {
    const prompt = vi.fn(async () => "accepted" as const);
    renderPill(stubController({ canInstall: true, installed: false }, prompt));

    // Nothing happens on render; the offer is not auto-prompted.
    expect(prompt).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Install the Studio as an app" }));

    expect(prompt).toHaveBeenCalledOnce();
  });
});
