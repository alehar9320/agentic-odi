import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ShareSheet } from "./ShareSheet";
import type { ShareLink } from "../types";

const DAY = 24 * 60 * 60 * 1000;

function link(overrides: Partial<ShareLink> = {}): ShareLink {
  return {
    id: "share-1",
    token: "odi_sh_abc123",
    url: "http://127.0.0.1:8100/s/odi_sh_abc123",
    expires_at: new Date(Date.now() + 7 * DAY).toISOString(),
    ...overrides,
  };
}

let writeText: ReturnType<typeof vi.fn>;

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubClipboard(): void {
  writeText = vi.fn(async () => {});
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });
}

describe("ShareSheet", () => {
  it("renders nothing while closed", () => {
    const { container } = render(
      <ShareSheet isOpen={false} onClose={() => undefined} onCreate={vi.fn()} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("mints a link for the chosen duration and offers it to copy", async () => {
    stubClipboard();
    const onCreate = vi.fn(async () => link());
    render(<ShareSheet isOpen onClose={() => undefined} onCreate={onCreate} />);

    fireEvent.change(screen.getByLabelText(/expires/i), { target: { value: "14" } });
    fireEvent.click(screen.getByRole("button", { name: /create link/i }));

    await waitFor(() => expect(onCreate).toHaveBeenCalledWith(14));
    const copy = await screen.findByRole("button", { name: /copy link/i });
    fireEvent.click(copy);

    expect(writeText).toHaveBeenCalledWith(
      expect.stringContaining("/shared/odi_sh_abc123"),
    );
  });

  it("says the link cannot be revoked when the store offers no revoke", async () => {
    const onCreate = vi.fn(async () => link());
    render(<ShareSheet isOpen onClose={() => undefined} onCreate={onCreate} />);

    fireEvent.click(screen.getByRole("button", { name: /create link/i }));

    expect(
      await screen.findByText(/cannot be revoked from this build/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /revoke/i })).toBeNull();
  });

  it("offers revoke when the store supports it, and says so", async () => {
    const onCreate = vi.fn(async () => link());
    const onRevoke = vi.fn(async () => {});
    render(
      <ShareSheet isOpen onClose={() => undefined} onCreate={onCreate} onRevoke={onRevoke} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /create link/i }));
    const revoke = await screen.findByRole("button", { name: /revoke link/i });
    fireEvent.click(revoke);

    await waitFor(() => expect(onRevoke).toHaveBeenCalledWith("share-1"));
    expect(await screen.findByText(/no longer works/i)).toBeInTheDocument();
  });

  it("reports a failure instead of promising a link it did not mint", async () => {
    const onCreate = vi.fn(async () => {
      throw new Error("The sidecar is unreachable.");
    });
    render(<ShareSheet isOpen onClose={() => undefined} onCreate={onCreate} />);

    fireEvent.click(screen.getByRole("button", { name: /create link/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/unreachable/i);
    expect(screen.queryByRole("button", { name: /copy link/i })).toBeNull();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(<ShareSheet isOpen onClose={onClose} onCreate={vi.fn()} />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalled();
  });
});
