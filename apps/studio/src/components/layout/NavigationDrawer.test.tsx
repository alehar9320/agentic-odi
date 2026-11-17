import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PRODUCT_NAME } from "../../lib/brand";
import { IDENTITY_ROLE_PLACEHOLDER } from "../../lib/identity";

const studio = vi.hoisted(() => ({
  conversations: [] as {
    id: string;
    title: string;
    updated_at: string;
    turn_count: number;
  }[],
  conversationId: null as string | null,
  openConversation: vi.fn(async () => undefined),
  refreshConversations: vi.fn(async () => undefined),
  drawerOpen: true,
  toggleDrawer: vi.fn(),
  openDetail: vi.fn(),
  openPanel: vi.fn(),
  pushToast: vi.fn(),
  displayName: "Ada Lovelace",
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => studio,
}));

import { NavigationDrawer } from "./NavigationDrawer";

function renderDrawer(overrides: { onHome?: () => void; onNew?: () => void } = {}) {
  const onHome = overrides.onHome ?? vi.fn();
  const onNew = overrides.onNew ?? vi.fn();
  render(<NavigationDrawer onHome={onHome} onNew={onNew} />);
  return { onHome, onNew };
}

beforeEach(() => {
  studio.conversations = [];
  studio.conversationId = null;
  studio.drawerOpen = true;
  studio.displayName = "Ada Lovelace";
  studio.openConversation.mockClear();
  studio.refreshConversations.mockClear();
  studio.toggleDrawer.mockClear();
  studio.openDetail.mockClear();
  studio.openPanel.mockClear();
  studio.pushToast.mockClear();
  window.localStorage.clear();
});

describe("NavigationDrawer", () => {
  it("is the Your work region and carries the brand", () => {
    const { onHome } = renderDrawer();

    expect(screen.getByRole("navigation", { name: "Your work" })).toBeInTheDocument();
    expect(screen.getByText(PRODUCT_NAME)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: `${PRODUCT_NAME}, go to home` }));
    expect(onHome).toHaveBeenCalledOnce();
  });

  it("offers one way to start, with the key that reaches the same sheet", () => {
    const { onNew } = renderDrawer();

    const control = screen.getByRole("button", { name: /new inquiry/i });
    expect(control).toHaveTextContent(/Ctrl K|⌘K/);
    fireEvent.click(control);
    expect(onNew).toHaveBeenCalledOnce();
  });

  it("lists the recent threads and opens one", () => {
    studio.conversations = [
      {
        id: "c-1",
        title: "Activation model",
        updated_at: "2026-11-15T10:00:00Z",
        turn_count: 2,
      },
      {
        id: "c-2",
        title: "Retention spike",
        updated_at: "2026-11-14T10:00:00Z",
        turn_count: 1,
      },
    ];
    studio.conversationId = "c-1";

    renderDrawer();

    const current = screen.getByRole("button", { name: /activation model/i });
    expect(current).toHaveAttribute("aria-current", "page");
    expect(current).toHaveTextContent("2 turns");

    fireEvent.click(screen.getByRole("button", { name: /retention spike/i }));
    expect(studio.openConversation).toHaveBeenCalledWith("c-2");
  });

  it("says so honestly when there are no threads", () => {
    renderDrawer();

    expect(screen.getByText(/no threads yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /new conversation/i })).toBeNull();
  });

  it("reaches the job map as a drawer destination", () => {
    renderDrawer();

    fireEvent.click(screen.getByRole("button", { name: "Job map" }));

    expect(studio.openDetail).toHaveBeenCalledWith("jobmap");
  });

  it("names the person and labels the role the product does not have", () => {
    renderDrawer();

    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText(IDENTITY_ROLE_PLACEHOLDER)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Identity options" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Set your name" }));

    expect(studio.openPanel).toHaveBeenCalledWith("settings");
  });

  it("reads the history when it opens", () => {
    renderDrawer();

    expect(studio.refreshConversations).toHaveBeenCalled();
  });

  it("renders no region while collapsed", () => {
    studio.drawerOpen = false;

    renderDrawer();

    expect(screen.queryByRole("navigation", { name: "Your work" })).toBeNull();
  });

  it("returns focus to the trigger when it collapses", () => {
    const toggle = document.createElement("button");
    toggle.id = "studio-drawer-toggle";
    document.body.append(toggle);

    const { rerender } = render(<NavigationDrawer onHome={vi.fn()} onNew={vi.fn()} />);
    studio.drawerOpen = false;
    rerender(<NavigationDrawer onHome={vi.fn()} onNew={vi.fn()} />);

    expect(toggle).toHaveFocus();
    toggle.remove();
  });
});
