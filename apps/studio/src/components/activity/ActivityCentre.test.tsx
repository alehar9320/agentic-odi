import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ActivityCentre } from "./ActivityCentre";
import type { ActivityApi } from "../../notices/ActivityProvider";
import type { Notice } from "../../notices/types";

function notice(overrides: Partial<Notice> = {}): Notice {
  return {
    id: "n-1",
    severity: "critical",
    title: "The studio sidecar isn't running.",
    detail: "The assistant is paused.",
    context: "Banner: sidecar-down",
    at: new Date("2026-11-13T09:00:00Z").getTime(),
    read: false,
    ...overrides,
  };
}

function makeApi(notices: Notice[]): ActivityApi {
  return {
    notices,
    unread: notices.filter((n) => !n.read).length,
    record: vi.fn(),
    dismiss: vi.fn(),
    markAllRead: vi.fn(),
  };
}

describe("ActivityCentre", () => {
  it("says nothing has happened rather than showing an empty list", () => {
    render(<ActivityCentre open onClose={() => {}} api={makeApi([])} />);
    expect(
      screen.getByText("Nothing has happened yet in this workspace."),
    ).toBeInTheDocument();
  });

  it("renders nothing when closed", () => {
    const { container } = render(
      <ActivityCentre open={false} onClose={() => {}} api={makeApi([notice()])} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows each row's severity word, title, and a time element", () => {
    render(
      <ActivityCentre
        open
        onClose={() => {}}
        api={makeApi([
          notice({ id: "n-1", severity: "critical", title: "Sidecar down" }),
          notice({ id: "n-2", severity: "success", title: "Outcome captured", at: Date.now() - 1000 }),
        ])}
      />,
    );

    const dialog = screen.getByRole("dialog", { name: "Activity" });
    expect(within(dialog).getByText("Critical")).toBeInTheDocument();
    expect(within(dialog).getByText("Done")).toBeInTheDocument();
    expect(within(dialog).getByText("Sidecar down")).toBeInTheDocument();
    // Severity is never colour alone: the word is in the accessible tree.
    expect(within(dialog).getAllByText(/sidecar down|outcome captured/i)).toHaveLength(2);
    expect(within(dialog).getAllByText(/ago|just now/i).length).toBeGreaterThan(0);
  });

  it("groups rows under a day heading", () => {
    render(
      <ActivityCentre
        open
        onClose={() => {}}
        api={makeApi([notice({ at: Date.now() })])}
      />,
    );
    expect(screen.getByRole("region", { name: "Today" })).toBeInTheDocument();
  });

  it("dismisses one row and leaves its neighbour", () => {
    const api = makeApi([
      notice({ id: "n-1", title: "First" }),
      notice({ id: "n-2", title: "Second", at: Date.now() - 1000 }),
    ]);
    render(<ActivityCentre open onClose={() => {}} api={api} />);

    const row = screen.getByText("First").closest("li") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Dismiss" }));

    expect(api.dismiss).toHaveBeenCalledWith("n-1");
  });

  it("clears the unread count without removing rows", () => {
    const api = makeApi([notice(), notice({ id: "n-2" })]);
    render(<ActivityCentre open onClose={() => {}} api={api} />);

    fireEvent.click(screen.getByRole("button", { name: "Mark all read" }));

    expect(api.markAllRead).toHaveBeenCalledTimes(1);
  });

  it("disables Mark all read when nothing is unread", () => {
    const api = makeApi([notice({ read: true })]);
    render(<ActivityCentre open onClose={() => {}} api={api} />);

    expect(screen.getByRole("button", { name: "Mark all read" })).toBeDisabled();
  });

  it("closes on Escape without dismissing a row", () => {
    const api = makeApi([notice()]);
    const onClose = vi.fn();
    render(<ActivityCentre open onClose={onClose} api={api} />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(api.dismiss).not.toHaveBeenCalled();
  });

  it("reveals the source and exact time behind a details disclosure", () => {
    render(<ActivityCentre open onClose={() => {}} api={makeApi([notice()])} />);

    const toggle = screen.getByRole("button", { name: "Details" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);

    expect(screen.getByRole("button", { name: "Hide details" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByText("Banner: sidecar-down")).toBeInTheDocument();
  });
});
