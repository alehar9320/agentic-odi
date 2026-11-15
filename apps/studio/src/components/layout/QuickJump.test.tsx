import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
  pushToast: vi.fn(),
  closeCustomize: vi.fn(),
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => studio,
}));

import { QuickJump } from "./QuickJump";

function renderJump(overrides: { onClose?: () => void; onNewInquiry?: () => void; onCommand?: (command: unknown) => void } = {}) {
  const onClose = overrides.onClose ?? vi.fn();
  const onNewInquiry = overrides.onNewInquiry ?? vi.fn();
  const onCommand = overrides.onCommand ?? vi.fn();
  render(
    <QuickJump
      open
      onClose={onClose}
      onNewInquiry={onNewInquiry}
      onCommand={onCommand as never}
    />,
  );
  return { onClose, onNewInquiry, onCommand };
}

beforeEach(() => {
  studio.conversations = [];
  studio.conversationId = null;
  studio.openConversation.mockClear();
  studio.refreshConversations.mockClear();
  studio.pushToast.mockClear();
  studio.closeCustomize.mockClear();
});

describe("QuickJump", () => {
  it("is a dialog whose first row is New inquiry", () => {
    renderJump();

    const dialog = screen.getByRole("dialog", { name: "Quick jump" });
    const rows = screen.getAllByRole("option");
    expect(dialog).toBeInTheDocument();
    expect(rows[0]).toHaveTextContent("New inquiry");
  });

  it("hands the caret back through New inquiry without clearing the thread", () => {
    const { onNewInquiry } = renderJump();

    fireEvent.click(screen.getByRole("option", { name: /new inquiry/i }));

    expect(onNewInquiry).toHaveBeenCalledOnce();
    expect(studio.closeCustomize).toHaveBeenCalled();
  });

  it("lists threads and opens one", () => {
    studio.conversations = [
      {
        id: "c-1",
        title: "Activation model",
        updated_at: "2026-11-15T10:00:00Z",
        turn_count: 2,
      },
    ];
    const { onClose } = renderJump();

    fireEvent.click(screen.getByRole("option", { name: /activation model/i }));

    expect(studio.openConversation).toHaveBeenCalledWith("c-1");
    expect(onClose).toHaveBeenCalled();
  });

  it("stays put when the chosen thread is already on the mainstage", () => {
    studio.conversations = [
      {
        id: "c-1",
        title: "Activation model",
        updated_at: "2026-11-15T10:00:00Z",
        turn_count: 2,
      },
    ];
    studio.conversationId = "c-1";
    const { onClose } = renderJump();

    fireEvent.click(screen.getByRole("option", { name: /activation model/i }));

    expect(studio.openConversation).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it("runs the same commands as the slash palette", () => {
    const { onCommand, onClose } = renderJump();

    fireEvent.change(screen.getByRole("combobox", { name: /search threads and commands/i }), {
      target: { value: "landscape" },
    });
    fireEvent.click(screen.getByRole("option", { name: /\/landscape/i }));

    expect(onCommand).toHaveBeenCalledWith(expect.objectContaining({ id: "landscape" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("matches a command typed with its own slash", () => {
    renderJump();

    fireEvent.change(screen.getByRole("combobox", { name: /search threads and commands/i }), {
      target: { value: "/help" },
    });

    expect(screen.getByRole("option", { name: /\/help/i })).toBeInTheDocument();
  });

  it("filters to what matches, and says so when nothing does", () => {
    renderJump();
    const field = screen.getByRole("combobox", { name: /search threads and commands/i });

    fireEvent.change(field, { target: { value: "retention" } });
    expect(screen.queryByRole("option", { name: /new inquiry/i })).toBeNull();

    fireEvent.change(field, { target: { value: "zzz-no-such-thing" } });
    expect(screen.getByRole("status")).toHaveTextContent(/no thread or command matches/i);
  });

  it("closes on Escape without reaching the stream behind it", () => {
    const { onClose } = renderJump();

    fireEvent.keyDown(screen.getByRole("dialog", { name: "Quick jump" }), { key: "Escape" });

    expect(onClose).toHaveBeenCalledOnce();
  });

  it("moves the highlight with the arrow keys and runs it with Enter", () => {
    const { onNewInquiry } = renderJump();

    fireEvent.keyDown(screen.getByRole("combobox", { name: /search threads and commands/i }), {
      key: "Enter",
    });

    expect(onNewInquiry).toHaveBeenCalledOnce();
  });

  it("tells the focused field which option is active, and moves it", () => {
    renderJump();
    const field = screen.getByRole("combobox", { name: /search threads and commands/i });
    const rows = screen.getAllByRole("option");

    expect(field).toHaveAttribute("aria-activedescendant", rows[0]?.id);

    fireEvent.keyDown(field, { key: "ArrowDown" });

    expect(field).toHaveAttribute("aria-activedescendant", rows[1]?.id);
  });

  it("lets an input method keep Enter and Escape while it is composing", () => {
    const { onNewInquiry, onClose } = renderJump();
    const field = screen.getByRole("combobox", { name: /search threads and commands/i });

    fireEvent.keyDown(field, { key: "Enter", isComposing: true });
    fireEvent.keyDown(field, { key: "Escape", isComposing: true });

    expect(onNewInquiry).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("reads the history when it opens", () => {
    renderJump();

    expect(studio.refreshConversations).toHaveBeenCalled();
  });
});
